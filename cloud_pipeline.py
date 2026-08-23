import os
import sys
import io
import json
import time
import uuid
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client
from google import genai
from google.genai import types

# Load Environment
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

SESSIONS_DIR = BASE_DIR / "sessions"
OUTPUTS_DIR = BASE_DIR / "outputs"
INPUTS_DIR = BASE_DIR / "inputs"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
INPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Dynamic Secrets & Configuration
def get_secret(key: str, default: str = "") -> str:
    """Safely retrieves a secret from st.secrets first, then os.getenv."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            val = str(st.secrets[key])
            if val.strip():
                return val.strip()
    except Exception:
        pass
    return os.getenv(key, default)

DEFAULT_GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")

MODEL_CANDIDATES = [
    DEFAULT_GEMINI_MODEL,
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest"
]

def get_groq_client() -> Optional[Groq]:
    api_key = get_secret("GROQ_API_KEY")
    if api_key:
        try:
            return Groq(api_key=api_key)
        except Exception as e:
            print(f"[!] Groq Client Init Error: {e}", flush=True)
    return None

def get_supabase_client() -> Optional[Client]:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    if url and key:
        try:
            return create_client(url, key)
        except Exception as e:
            print(f"[!] Supabase Client Init Error: {e}", flush=True)
    return None

def get_gemini_client() -> Optional[genai.Client]:
    api_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
    if api_key:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            print(f"[!] Gemini Client Init Error: {e}", flush=True)
    return None


def format_seconds_to_hhmmss(seconds: float) -> str:
    """Formats float seconds into HH:MM:SS or MM:SS."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_duration_human(seconds: float) -> str:
    """Formats duration into human-readable string like '16m 35s'."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# =============================================================================
# 1. GROQ CLOUD WHISPER-LARGE-V3 TRANSCRIPTION
# =============================================================================
def transcribe_audio_groq(
    audio_file_path: Path,
    prompt: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str, float]:
    """
    Transcribes audio file using Groq Whisper-large-v3 API with verbose JSON timestamps.
    Returns: (segments_list, full_text_transcript, duration_seconds)
    """
    groq_client = get_groq_client()
    if not groq_client:
        raise ValueError("GROQ_API_KEY is not configured in .env file.")

    if not audio_file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    print(f"[*] Sending audio to Groq Whisper-large-v3: {audio_file_path.name}...", flush=True)
    start_t = time.time()

    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()

    transcription = groq_client.audio.transcriptions.create(
        file=(audio_file_path.name, audio_bytes),
        model="whisper-large-v3",
        response_format="verbose_json",
        temperature=0.0,
        prompt=prompt
    )

    elapsed = time.time() - start_t
    print(f"[+] Groq Transcription Completed in {elapsed:.2f}s!", flush=True)

    full_text = transcription.text.strip()
    duration = getattr(transcription, "duration", 0.0) or 0.0

    raw_segments = getattr(transcription, "segments", []) or []
    formatted_segments = []

    for idx, seg in enumerate(raw_segments):
        start_sec = seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0)
        end_sec = seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0)
        text = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
        
        if not text:
            continue

        ts_str = format_seconds_to_hhmmss(start_sec)
        formatted_segments.append({
            "index": idx + 1,
            "start": start_sec,
            "end": end_sec,
            "timestamp": ts_str,
            "speaker": f"Speaker {((idx % 3) + 1)}",
            "text": text
        })

    # If segments were empty, construct a fallback single segment
    if not formatted_segments and full_text:
        formatted_segments.append({
            "index": 1,
            "start": 0.0,
            "end": duration,
            "timestamp": "00:00",
            "speaker": "Speaker 1",
            "text": full_text
        })

    return formatted_segments, full_text, duration


# =============================================================================
# 2. GEMINI 2.5 FLASH STRUCTURED INTELLIGENCE PIPELINE
# =============================================================================
def build_intelligence_prompt(topic: str, transcript_text: str, duration_str: str) -> str:
    return f"""You are an elite Executive Meeting Intelligence AI Analyst powered by Plaud AI methodology.
Your objective is to produce a comprehensive, structured, high-impact intelligence report from the provided meeting transcript.

Topic/Title: {topic}
Meeting Duration: {duration_str}
Spoken Transcript:
\"\"\"
{transcript_text}
\"\"\"

Analyze the transcript thoroughly and generate the report adhering STRICTLY to the following Markdown structure:

# 🎙️ Meeting Intelligence Report: {topic}

**Duration:** {duration_str}
**Identified Participants:** [List all identified participants or speakers]

---

## ⚡ Executive Brief
> • **Strategic Purpose:** [1 sentence summarizing the core objective and purpose of this session]
> • **Key Breakthrough & Consensus:** [1 sentence highlighting the major agreement, breakthrough, or conclusion]
> • **Immediate Next Step:** [1 sentence summarizing the most urgent action or critical milestone]

---

## 🏛️ Key Discussion Pillars

Divide the meeting into clear thematic pillars in chronological order with precise timestamps.

### 1. [00:00:00] [Pillar 1 Title]
- **Context & Objective:** [Summary of why this topic was brought up]
- **Key Arguments & Perspectives:**
  - **Speaker A:** [Key perspective/points]
  - **Speaker B:** [Counterpoint or supporting points]
- **Consensus & Outcome:** [What was agreed or concluded on this pillar]

### 2. [00:05:00] [Pillar 2 Title]
- **Context & Objective:** [Summary]
- **Key Arguments & Perspectives:**
  - **Speaker A:** [Details]
- **Consensus & Outcome:** [Outcome]

---

## 📋 Action Items Matrix

Provide a complete, actionable markdown table capturing all commitments, deliverables, owners, urgency, and deadlines mentioned.
CRITICAL RULE: In the "Task Deliverable" column, NEVER write brief generic phrases like "Keep it simple" or "Follow up". You MUST specify the EXACT complete deliverable, context, and expected outcome (e.g., "Design and build a 5-question quiz for SOC 2 awareness training and distribute to all staff" or "Draft security questionnaire response for enterprise vendor review").

| # | Task Deliverable | Owner | Priority | Due Date | Acceptance Criteria & Notes |
|---|------------------|-------|----------|----------|-----------------------------|
| 1 | [Comprehensive, concrete task deliverable description] | [Specific Person or Role] | [HIGH / MED / LOW] | [YYYY-MM-DD or timeframe] | [Clear acceptance criteria or dependencies] |

---

## ⚖️ Decisions & Reversals

### ✅ Final Decisions Approved
1. **[00:00:00] [Decision Title]:** [Detailed explanation of the agreed decision and owner]

### 🔄 Rejected & Overturned Ideas (Reversals)
1. **[00:00:00] [Rejected Proposal Title]:** [What idea was proposed, why the group rejected or reversed course, and what alternative was adopted instead]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

Generate a valid Mermaid mindmap representing the meeting taxonomy, themes, decisions, and action items. Keep node texts clean without special characters or parentheses that break Mermaid rendering.

```mermaid
mindmap
  root((Meeting Topic))
    Executive Brief
      Strategic Direction
      Key Milestone
    Discussion Pillars
      Pillar 1
        Point A
        Point B
      Pillar 2
        Point A
        Point B
    Decisions
      Approved Decision 1
      Approved Decision 2
    Action Items
      High Priority
        Task 1
      Medium Priority
        Task 2
```
"""


def extract_intelligence_gemini(
    topic: str,
    transcript_text: str,
    duration_str: str,
    model_name: str = DEFAULT_GEMINI_MODEL
) -> Dict[str, Any]:
    """Extracts executive brief, pillars, actions, decisions, and mindmap using Gemini (with Groq fallback)."""
    client = get_gemini_client()
    groq_client = get_groq_client()
    prompt = build_intelligence_prompt(topic, transcript_text, duration_str)

    resp_text = None
    used_model = model_name
    candidates = [model_name] + [m for m in MODEL_CANDIDATES if m != model_name]

    # 1. Try Gemini
    if client:
        for candidate in candidates:
            try:
                print(f"[*] Calling Gemini ({candidate}) for Meeting Intelligence...", flush=True)
                resp = client.models.generate_content(
                    model=candidate,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.15,
                        max_output_tokens=4000
                    )
                )
                if resp and resp.text:
                    resp_text = resp.text.strip()
                    used_model = f"Gemini ({candidate})"
                    break
            except Exception as e:
                print(f"[!] Gemini Model {candidate} Error: {e}", flush=True)
                continue

    # 2. Fallback to Groq LPU if Gemini is unavailable or rate-limited
    if not resp_text and groq_client:
        groq_models = ["qwen/qwen3.6-27b", "openai/gpt-oss-120b", "groq/compound"]
        for g_model in groq_models:
            try:
                print(f"[*] Calling Groq LPU ({g_model}) for Meeting Intelligence...", flush=True)
                g_resp = groq_client.chat.completions.create(
                    model=g_model,
                    messages=[
                        {"role": "system", "content": "You are an elite Executive Meeting Intelligence AI Analyst. Adhere strictly to the requested markdown format."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.15
                )
                if g_resp and g_resp.choices and g_resp.choices[0].message.content:
                    raw = g_resp.choices[0].message.content.strip()
                    # Strip reasoning tags if present
                    clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    if clean:
                        resp_text = clean
                        used_model = f"Groq ({g_model})"
                        break
            except Exception as ge:
                print(f"[!] Groq Model {g_model} Error: {ge}", flush=True)
                continue

    if not resp_text:
        raise RuntimeError("Failed to generate intelligence report from all available AI providers.")

    return parse_markdown_to_session_dict(resp_text, used_model)


def parse_markdown_to_session_dict(raw_markdown: str, model_name: str) -> Dict[str, Any]:
    """Parses standard markdown report into clean structured session dictionary."""
    # 1. Executive Brief
    exec_brief = []
    exec_match = re.search(r"## ⚡ Executive Brief\s*(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if exec_match:
        for line in exec_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("> •") or line.startswith("> -") or line.startswith("•") or line.startswith("-"):
                clean = re.sub(r"^>\s*[•\-]\s*", "• ", line).strip()
                if clean:
                    exec_brief.append(clean)

    # 2. Discussion Pillars
    pillars = []
    pillars_match = re.search(r"## 🏛️ Key Discussion Pillars\s*(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if pillars_match:
        pillar_blocks = re.findall(r"###\s*(\d+\.\s*\[(.*?)\]\s*(.*?))\n(.*?)(?=\n###|\Z)", pillars_match.group(1), re.DOTALL)
        for num_match, ts, title, details in pillar_blocks:
            pillars.append({
                "title": title.strip(),
                "timestamp": ts.strip(),
                "details": details.strip()
            })

    # 3. Action Items Matrix
    action_items = []
    table_match = re.search(r"\|(?:\s*#\s*\|\s*Task Deliverable.*?\n)(.*?)(?=\n\n|---|##|\Z)", raw_markdown, re.DOTALL)
    if table_match:
        rows = [r.strip() for r in table_match.group(1).splitlines() if r.strip() and not r.strip().startswith("|---")]
        for r in rows:
            cols = [c.strip() for c in r.split("|")[1:-1]]
            if len(cols) >= 6:
                try:
                    num = int(cols[0])
                except Exception:
                    num = len(action_items) + 1
                action_items.append({
                    "number": num,
                    "description": cols[1],
                    "assignee": cols[2],
                    "priority": cols[3].upper(),
                    "due_date": cols[4],
                    "notes": cols[5]
                })

    # 4. Decisions & Reversals
    decisions = []
    dec_match = re.search(r"### ✅ Final Decisions Approved\s*(.*?)(?=### 🔄|## |\Z)", raw_markdown, re.DOTALL)
    if dec_match:
        for line in dec_match.group(1).splitlines():
            line = line.strip()
            if re.match(r"^\d+\.", line) or line.startswith("-"):
                clean = re.sub(r"^\d+\.\s*|-\s*", "", line).strip()
                if clean:
                    decisions.append(clean)

    reversals = []
    rev_match = re.search(r"### 🔄 Rejected & Overturned Ideas.*?\n(.*?)(?=## |\Z)", raw_markdown, re.DOTALL)
    if rev_match:
        for line in rev_match.group(1).splitlines():
            line = line.strip()
            if re.match(r"^\d+\.", line) or line.startswith("-"):
                clean = re.sub(r"^\d+\.\s*|-\s*", "", line).strip()
                if clean:
                    reversals.append(clean)

    # 5. Mermaid Mindmap
    mindmap = ""
    mm_match = re.search(r"```mermaid\s*(mindmap.*?)```", raw_markdown, re.DOTALL)
    if mm_match:
        mindmap = mm_match.group(1).strip()

    return {
        "executive_brief": exec_brief,
        "discussion_pillars": pillars,
        "action_items": action_items,
        "decisions": decisions,
        "reversals": reversals,
        "mermaid_mindmap": mindmap,
        "raw_markdown": raw_markdown,
        "model_used": model_name
    }


# =============================================================================
# 3. COMPLETE CLOUD PIPELINE ORCHESTRATOR
# =============================================================================
def process_meeting_file_cloud(
    audio_path: Path,
    custom_title: Optional[str] = None,
    model_choice: str = DEFAULT_GEMINI_MODEL,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    End-to-end cloud pipeline:
    1. Transcribe with Groq Whisper-large-v3
    2. Extract intelligence with Gemini 2.5 Flash
    3. Save locally & Sync to Supabase cloud with user_id
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = custom_title or audio_path.stem.replace("_", " ").title()

    start_time = time.time()

    # 1. Groq Transcription
    segments, full_text, duration_sec = transcribe_audio_groq(audio_path)
    duration_str = format_duration_human(duration_sec)

    # 2. Gemini Analysis
    intel = extract_intelligence_gemini(
        topic=title,
        transcript_text=full_text,
        duration_str=duration_str,
        model_name=model_choice
    )

    total_time_str = f"{time.time() - start_time:.2f}s"

    session_data = {
        "metadata": {
            "session_id": session_id,
            "user_id": user_id,
            "source_file": audio_path.name,
            "filename": f"session_{session_id}.json",
            "file_size": f"{audio_path.stat().st_size / (1024*1024):.2f} MB" if audio_path.exists() else "0 MB",
            "mime_type": "audio/mp3",
            "model": f"Groq Whisper-large-v3 + {intel.get('model_used', model_choice)}",
            "processing_time": total_time_str,
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exported_at": datetime.now().isoformat(),
            "duration": duration_str,
            "duration_seconds": duration_sec
        },
        "transcript_segments": segments,
        "full_transcript_text": full_text,
        "executive_brief": intel.get("executive_brief", []),
        "discussion_pillars": intel.get("discussion_pillars", []),
        "action_items": intel.get("action_items", []),
        "decisions": intel.get("decisions", []),
        "reversals": intel.get("reversals", []),
        "mermaid_mindmap": intel.get("mermaid_mindmap", ""),
        "raw_markdown": intel.get("raw_markdown", "")
    }

    # 3. Save locally and sync to Supabase
    save_session_record(session_id, title, session_data, user_id=user_id)

    return session_data


# =============================================================================
# 4. SUPABASE AUTH & MULTI-TENANCY OPERATIONS
# =============================================================================
def auth_sign_in(email: str, password: str) -> Tuple[bool, Optional[Any], str]:
    """Signs in user with email and password via Supabase Auth."""
    sb = get_supabase_client()
    if not sb:
        return False, None, "Supabase client is not configured."
    try:
        res = sb.auth.sign_in_with_password({"email": email.strip(), "password": password})
        if res and res.user:
            return True, res.user, "Login successful."
        return False, None, "Login failed: No user returned."
    except Exception as e:
        err_msg = str(e)
        if "Invalid login credentials" in err_msg:
            err_msg = "Invalid email or password. Please try again or create an account."
        return False, None, err_msg


def auth_sign_up(email: str, password: str) -> Tuple[bool, Optional[Any], str]:
    """Registers a new user account with email and password via Supabase Auth."""
    sb = get_supabase_client()
    if not sb:
        return False, None, "Supabase client is not configured."
    try:
        res = sb.auth.sign_up({"email": email.strip(), "password": password})
        if res and res.user:
            return True, res.user, "Account created successfully! You are now logged in."
        return False, None, "Sign up failed: No user created."
    except Exception as e:
        return False, None, str(e)


def auth_sign_out():
    """Signs out the active user."""
    sb = get_supabase_client()
    if sb:
        try:
            sb.auth.sign_out()
        except Exception:
            pass


def get_user_usage(user_id: Optional[str], plan_tier: str = "free") -> Dict[str, Any]:
    """
    Calculates monthly audio processing usage for the user.
    Free tier: 3 meetings / month
    Pro tier: Unlimited
    """
    sessions = fetch_all_sessions(user_id=user_id)
    current_month_prefix = datetime.now().strftime("%Y-%m")
    
    monthly_count = 0
    for s in sessions:
        p_at = str(s.get("processed_at", ""))
        if p_at.startswith(current_month_prefix):
            monthly_count += 1

    limit = 9999 if plan_tier.lower() == "pro" else 3
    can_upload = monthly_count < limit or plan_tier.lower() == "pro"
    percent = min(100, int((monthly_count / 3.0) * 100)) if plan_tier.lower() == "free" else 100

    return {
        "used_count": monthly_count,
        "limit": limit,
        "plan_tier": plan_tier.upper(),
        "can_upload": can_upload,
        "percent": percent,
        "remaining": max(0, limit - monthly_count) if plan_tier.lower() == "free" else 9999
    }


def save_session_record(
    session_id: str,
    title: str,
    session_data: Dict[str, Any],
    user_id: Optional[str] = None
) -> bool:
    """Saves session locally to JSON and attempts to sync to Supabase with user_id."""
    if user_id:
        if "metadata" not in session_data:
            session_data["metadata"] = {}
        session_data["metadata"]["user_id"] = user_id

    # 1. Local Save
    local_file = SESSIONS_DIR / f"session_{session_id}.json"
    try:
        with open(local_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Local Save Error: {e}", flush=True)

    # 2. Supabase Sync
    sb = get_supabase_client()
    if sb:
        try:
            # Deterministic or random UUID for Supabase
            try:
                sid_uuid = str(uuid.UUID(session_id))
            except Exception:
                sid_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(session_id)))

            row = {
                "id": sid_uuid,
                "title": title,
                "duration": session_data.get("metadata", {}).get("duration", "N/A"),
                "transcript": json.dumps(session_data, ensure_ascii=False),
                "created_at": datetime.now().isoformat()
            }
            if user_id:
                row["user_id"] = user_id

            sb.table("sessions").upsert(row).execute()
            print(f"[+] Supabase Cloud Sync Success: session_{session_id} (user: {user_id})", flush=True)
            return True
        except Exception as e:
            print(f"[!] Supabase Cloud Sync Note (stored locally): {e}", flush=True)

    return True


def fetch_all_sessions(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches all past meetings filtered by user_id for multi-tenancy.
    Seamlessly merges cloud and local storage.
    """
    sessions_map: Dict[str, Dict[str, Any]] = {}

    # 1. Load Local Files
    for p in SESSIONS_DIR.glob("session_*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            file_user_id = data.get("metadata", {}).get("user_id")
            # Multi-tenant local filter: if user_id is provided, only show matching sessions or unassigned demo sessions
            if user_id and file_user_id and file_user_id != user_id:
                continue

            sid = p.stem.replace("session_", "")
            title = data.get("metadata", {}).get("source_file", f"Meeting {sid}")
            if title.endswith(".json") or title.endswith(".wav") or title.endswith(".mp3"):
                title = title.rsplit(".", 1)[0].replace("_", " ").title()

            sessions_map[sid] = {
                "id": sid,
                "title": title,
                "duration": data.get("metadata", {}).get("duration", "15m 00s"),
                "processed_at": data.get("metadata", {}).get("processed_at", datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")),
                "file_path": str(p),
                "data": data,
                "user_id": file_user_id,
                "source": "Local"
            }
        except Exception as e:
            print(f"[!] Error reading local session {p.name}: {e}", flush=True)

    # 2. Query Supabase
    sb = get_supabase_client()
    if sb:
        try:
            query = sb.table("sessions").select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            res = query.order("created_at", desc=True).execute()

            for row in res.data or []:
                sid = str(row.get("id"))
                title = row.get("title") or f"Cloud Session {sid}"
                duration = row.get("duration") or "N/A"
                created_at = row.get("created_at") or datetime.now().isoformat()
                row_user_id = row.get("user_id")
                
                raw_t = row.get("transcript")
                parsed_data = {}
                if isinstance(raw_t, str):
                    try:
                        parsed_data = json.loads(raw_t)
                    except Exception:
                        parsed_data = {"raw_markdown": raw_t}
                elif isinstance(raw_t, dict):
                    parsed_data = raw_t

                sessions_map[sid] = {
                    "id": sid,
                    "title": title,
                    "duration": duration,
                    "processed_at": created_at[:16].replace("T", " "),
                    "file_path": str(SESSIONS_DIR / f"session_{sid}.json"),
                    "data": parsed_data,
                    "user_id": row_user_id,
                    "source": "Supabase Cloud"
                }
        except Exception as e:
            print(f"[!] Supabase Fetch Note: {e}", flush=True)

    # Sort descending by processed_at / date
    sorted_sessions = sorted(
        sessions_map.values(),
        key=lambda x: str(x.get("processed_at", "")),
        reverse=True
    )
    return sorted_sessions


def delete_session_record(session_id: str, user_id: Optional[str] = None) -> bool:
    """Deletes a session from local storage and Supabase."""
    # 1. Delete Local
    local_file = SESSIONS_DIR / f"session_{session_id}.json"
    if local_file.exists():
        try:
            local_file.unlink()
        except Exception:
            pass

    # 2. Delete Supabase
    sb = get_supabase_client()
    if sb:
        try:
            try:
                sid_uuid = str(uuid.UUID(session_id))
            except Exception:
                sid_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(session_id)))

            query = sb.table("sessions").delete().eq("id", sid_uuid)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
        except Exception:
            pass

    return True


def rename_session_record(session_id: str, new_title: str, user_id: Optional[str] = None) -> bool:
    """Renames a session title locally and in Supabase."""
    local_file = SESSIONS_DIR / f"session_{session_id}.json"
    if local_file.exists():
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["metadata"]["source_file"] = new_title
            with open(local_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    sb = get_supabase_client()
    if sb:
        try:
            try:
                sid_uuid = str(uuid.UUID(session_id))
            except Exception:
                sid_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(session_id)))

            query = sb.table("sessions").update({"title": new_title}).eq("id", sid_uuid)
            if user_id:
                query = query.eq("user_id", user_id)
            query.execute()
        except Exception:
            pass

    return True


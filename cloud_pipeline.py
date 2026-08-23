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
        raise ValueError("GROQ_API_KEY is not configured in secrets or environment.")

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
# 2. INTELLIGENCE PROMPTS & SUMMARY TEMPLATES
# =============================================================================
def build_intelligence_prompt(
    topic: str,
    transcript_text: str,
    duration_str: str,
    template_type: str = "executive"
) -> str:
    """Builds prompt tailored to the selected intelligence template."""
    base_header = f"""You are an elite AI Meeting & Speech Intelligence Analyst powered by Plaud AI methodology.
Your objective is to produce a structured, high-impact intelligence report from the provided transcript.

Topic/Title: {topic}
Duration: {duration_str}
Spoken Transcript:
\"\"\"
{transcript_text}
\"\"\"
"""

    if template_type == "academic":
        return base_header + """
Analyze the academic lecture thoroughly and generate the report adhering STRICTLY to this Markdown structure:

# 🎓 Academic Lecture Intelligence: {topic}

**Duration:** {duration_str}

---

## ⚡ Executive Brief
> • **Core Thesis & Subject:** [1 sentence summarizing the central thesis or concept taught]
> • **Primary Academic Takeaway:** [1 sentence on the most critical principle or formula discussed]
> • **Follow-up Study Requirement:** [1 sentence summarizing homework, assigned reading, or exam focus]

---

## 🏛️ Key Discussion Pillars

### 1. [00:00:00] [Conceptual Theme 1]
- **Context & Definition:** [Summary of theoretical foundation]
- **Key Explanations & Examples:** [Specific breakdown taught by instructor]
- **Core Principle & Takeaway:** [Essential principle to master]

### 2. [00:15:00] [Conceptual Theme 2]
- **Context & Definition:** [Details]
- **Key Explanations & Examples:** [Details]
- **Core Principle & Takeaway:** [Details]

---

## 📋 Action Items Matrix

Provide a structured table of important academic terms, formulas, and study deliverables mentioned.

| # | Task Deliverable | Owner | Priority | Due Date | Acceptance Criteria & Notes |
|---|------------------|-------|----------|----------|-----------------------------|
| 1 | [Study deliverable or exam topic to review] | Student / Study Group | [HIGH / MED / LOW] | Next Class / Exam | [Key formulas, definitions or problem sets] |

---

## ⚖️ Decisions & Reversals

### ✅ Final Decisions Approved
1. **[00:00:00] [Confirmed Academic Principle]:** [Explanation of approved standard or guideline]

### 🔄 Rejected & Overturned Ideas (Reversals)
1. **[00:00:00] [Common Misconception Debunked]:** [Misconception clarified by lecturer]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

```mermaid
mindmap
  root((Lecture Topic))
    Core Thesis
      Foundational Concept
      Primary Principle
    Theoretical Pillars
      Concept A
      Concept B
    Exam Focus
      Key Definition
      Review Questions
```
"""

    elif template_type == "brainstorm":
        return base_header + """
Analyze the brainstorming and ideation session thoroughly and generate the report adhering STRICTLY to this Markdown structure:

# 💡 Brainstorm & Ideation Report: {topic}

**Duration:** {duration_str}

---

## ⚡ Executive Brief
> • **Strategic Purpose:** [1 sentence summarizing the ideation challenge or innovation goal]
> • **Key Breakthrough & Consensus:** [1 sentence highlighting the most promising creative concept]
> • **Immediate Next Step:** [1 sentence on the first experiment or prototype to build]

---

## 🏛️ Key Discussion Pillars

### 1. [00:00:00] [Ideation Track 1 Title]
- **Context & Challenge:** [What creative problem is addressed]
- **Key Ideas & Suggestions:** [Key proposals generated]
- **Consensus & Outcome:** [Promising angles selected]

### 2. [00:15:00] [Ideation Track 2 Title]
- **Context & Challenge:** [Details]
- **Key Ideas & Suggestions:** [Details]
- **Consensus & Outcome:** [Details]

---

## 📋 Action Items Matrix

| # | Task Deliverable | Owner | Priority | Due Date | Acceptance Criteria & Notes |
|---|------------------|-------|----------|----------|-----------------------------|
| 1 | [Prototype, mock, or research experiment deliverable] | [Owner or Team] | [HIGH / MED / LOW] | Next Sprint | [Success metrics or test criteria] |

---

## ⚖️ Decisions & Reversals

### ✅ Final Decisions Approved
1. **[00:00:00] [Selected Concept / Idea]:** [Detailed explanation of why this idea won approval]

### 🔄 Rejected & Overturned Ideas (Reversals)
1. **[00:00:00] [Discarded Idea]:** [Idea proposed and why the team chose not to pursue it]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

```mermaid
mindmap
  root((Brainstorm Topic))
    Core Challenge
      User Need
      Opportunity
    Idea Tracks
      Concept 1
      Concept 2
    Next Experiments
      Prototype Alpha
      Validation Test
```
"""

    else:
        # Default: Executive Meeting Template
        return base_header + """
Analyze the meeting transcript thoroughly and generate the report adhering STRICTLY to this Markdown structure:

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
    model_name: str = DEFAULT_GEMINI_MODEL,
    template_type: str = "executive"
) -> Dict[str, Any]:
    """Extracts executive brief, pillars, actions, decisions, and mindmap using Gemini (with Groq fallback)."""
    client = get_gemini_client()
    groq_client = get_groq_client()
    prompt = build_intelligence_prompt(topic, transcript_text, duration_str, template_type=template_type)

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

    return parse_markdown_to_session_dict(resp_text, used_model, template_type=template_type)


def parse_markdown_to_session_dict(
    raw_markdown: str,
    model_name: str,
    template_type: str = "executive"
) -> Dict[str, Any]:
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

    # 3. Action Items Matrix (Multi-Strategy Robust Parsing)
    action_items = []
    
    # Strategy A: Standard Action Items Table
    table_match = re.search(r"## 📋 Action Items Matrix.*?\n(\|.*?\n\|[-:\s|]+\n)(.*?)(?=\n\n\S|---|##|\Z)", raw_markdown, re.DOTALL)
    if not table_match:
        table_match = re.search(r"(\|(?:\s*#\s*\|\s*Task Deliverable.*?\n)(.*?)(?=\n\n\S|---|##|\Z))", raw_markdown, re.DOTALL)

    if table_match:
        content_to_parse = table_match.group(2) if len(table_match.groups()) >= 2 else table_match.group(0)
        rows = [r.strip() for r in content_to_parse.splitlines() if r.strip() and "|" in r and not re.match(r"^\|[\s\-:|]+\|$", r.strip())]
        for r in rows:
            cols = [c.strip() for c in r.split("|")[1:-1]]
            if len(cols) >= 3:
                num = len(action_items) + 1
                desc = cols[1] if len(cols) > 1 and cols[0].isdigit() else cols[0]
                assignee = cols[2] if len(cols) > 2 and cols[0].isdigit() else (cols[1] if len(cols) > 1 else "Team")
                prio = cols[3].upper() if len(cols) > 3 and cols[0].isdigit() else "MED"
                due = cols[4] if len(cols) > 4 and cols[0].isdigit() else (cols[2] if len(cols) > 2 else "Next Sprint")
                notes = cols[5] if len(cols) > 5 and cols[0].isdigit() else "—"

                # Filter out header row if accidentally caught
                if "task" in desc.lower() and "deliverable" in desc.lower():
                    continue

                if desc and len(desc) > 3:
                    action_items.append({
                        "number": num,
                        "description": desc,
                        "assignee": assignee or "Team",
                        "priority": "HIGH" if "HIGH" in prio else ("LOW" if "LOW" in prio else "MED"),
                        "due_date": due or "Next Sprint",
                        "notes": notes or "—"
                    })

    # Strategy B: Fallback to Bulleted / Numbered Action Lists
    if not action_items:
        act_section = re.search(r"## 📋 Action Items.*?\n(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
        if act_section:
            for line in act_section.group(1).splitlines():
                line = line.strip()
                if not line or line.startswith("|"):
                    continue
                # Matches: 1. [Task] - Owner: X or - [ ] Task
                clean_line = re.sub(r"^\d+\.\s*|-\s*\[[\sxX]?\]\s*|-\s*", "", line).strip()
                if clean_line and len(clean_line) > 5:
                    owner = "Team"
                    owner_m = re.search(r"(?:Owner|Assignee|Lead):\s*([^,;\(\)]+)", clean_line, re.IGNORECASE)
                    if owner_m:
                        owner = owner_m.group(1).strip()
                    due = "Next Sprint"
                    due_m = re.search(r"(?:Due|Deadline|Target):\s*([^,;\(\)]+)", clean_line, re.IGNORECASE)
                    if due_m:
                        due = due_m.group(1).strip()
                    
                    prio = "MED"
                    if any(k in clean_line.lower() for k in ["high", "urgent", "critical", "p0", "p1"]):
                        prio = "HIGH"
                    elif any(k in clean_line.lower() for k in ["low", "p3", "optional"]):
                        prio = "LOW"

                    action_items.append({
                        "number": len(action_items) + 1,
                        "description": clean_line,
                        "assignee": owner,
                        "priority": prio,
                        "due_date": due,
                        "notes": "—"
                    })

    # 4. Decisions & Reversals
    decisions = []
    dec_match = re.search(r"### ✅ Final Decisions Approved\s*(.*?)(?=### 🔄|## |\Z)", raw_markdown, re.DOTALL)
    if not dec_match:
        dec_match = re.search(r"## ⚖️ Decisions.*?\n(.*?)(?=### 🔄|## |\Z)", raw_markdown, re.DOTALL)
    if dec_match:
        for line in dec_match.group(1).splitlines():
            line = line.strip()
            if re.match(r"^\d+\.", line) or line.startswith("-"):
                clean = re.sub(r"^\d+\.\s*|-\s*", "", line).strip()
                if clean and not clean.startswith("###"):
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

    # 5. Mermaid Mindmap Sanitization
    mindmap = ""
    mm_match = re.search(r"```mermaid\s*(.*?)```", raw_markdown, re.DOTALL)
    if mm_match:
        mindmap = mm_match.group(1).strip()
    
    if not mindmap or len(mindmap) < 20:
        # Build clean valid Mermaid mindmap
        clean_topic = re.sub(r"[\(\)\[\]\"\{\}]", "", model_name).strip() or "Meeting Intelligence"
        mindmap = f"""mindmap
  root["{clean_topic}"]
    Executive Brief
      Strategic Direction
      Key Milestone
    Discussion Pillars
      Theme Analysis
      Consensus Reached
    Decisions & Actions
      Agreed Milestones
      Task Deliverables"""

    return {
        "template_type": template_type,
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
# 3. INTERACTIVE CHAT WITH AUDIO ASSISTANT (HESH REC BOT)
# =============================================================================
def chat_with_session(
    session_data: Dict[str, Any],
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    model_name: str = DEFAULT_GEMINI_MODEL
) -> str:
    """Answers conversational questions grounded strictly in the meeting transcript and intelligence."""
    client = get_gemini_client()
    groq_client = get_groq_client()

    meta = session_data.get("metadata", {})
    title = meta.get("source_file", "Meeting")
    full_transcript = session_data.get("full_transcript_text") or session_data.get("raw_markdown", "")
    exec_summary = "\n".join(session_data.get("executive_brief", []))
    decisions = "\n".join([f"- {d}" for d in session_data.get("decisions", [])])

    system_context = f"""You are Hesh Rec Bot (هشام ريك بوت), an elite AI meeting and lecture intelligence copilot.
Meeting Title: {title}
Executive Summary:
{exec_summary}

Decisions Agreed:
{decisions}

Full Spoken Transcript:
\"\"\"
{full_transcript}
\"\"\"

Answer the user's questions clearly, concisely, and accurately in the user's language (English or Arabic). Cite specific timestamps, quotes, and decisions when relevant.
"""

    messages_payload = [{"role": "system", "content": system_context}]
    if chat_history:
        for msg in chat_history[-6:]:
            role = "assistant" if msg["role"] == "assistant" else "user"
            messages_payload.append({"role": role, "content": msg["content"]})
    messages_payload.append({"role": "user", "content": user_query})

    # 1. Try Gemini
    if client:
        try:
            gemini_prompt = f"{system_context}\n\nUser Question: {user_query}"
            resp = client.models.generate_content(
                model=model_name,
                contents=gemini_prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1000)
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            print(f"[!] Gemini Chat Error: {e}", flush=True)

    # 2. Fallback to Groq
    if groq_client:
        try:
            g_resp = groq_client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages_payload,
                max_tokens=1000,
                temperature=0.2
            )
            if g_resp and g_resp.choices and g_resp.choices[0].message.content:
                clean = re.sub(r"<think>.*?</think>", "", g_resp.choices[0].message.content, flags=re.DOTALL).strip()
                return clean
        except Exception as ge:
            print(f"[!] Groq Chat Error: {ge}", flush=True)

    return "I'm sorry, I was unable to connect to the AI model to analyze this audio. Please check your credentials."


# =============================================================================
# 4. PRINTABLE HTML / PDF EXPORT GENERATOR
# =============================================================================
def generate_printable_html(session_data: Dict[str, Any]) -> str:
    """Generates a standalone, beautiful HTML document suitable for browser print-to-PDF."""
    meta = session_data.get("metadata", {})
    title = meta.get("source_file", "Meeting Intelligence Report")
    duration = meta.get("duration", "N/A")
    date_str = meta.get("processed_at", datetime.now().strftime("%Y-%m-%d"))
    model_str = meta.get("model", "Hesh-rec AI")
    exec_brief = session_data.get("executive_brief", [])
    pillars = session_data.get("discussion_pillars", [])
    action_items = session_data.get("action_items", [])
    decisions = session_data.get("decisions", [])
    reversals = session_data.get("reversals", [])
    transcript_segments = session_data.get("transcript_segments", [])

    brief_html = "".join([f"<li>{p.lstrip('•*- ')}</li>" for p in exec_brief])

    pillars_html = []
    for p in pillars:
        pillars_html.append(f"""
        <div class="pillar">
            <h3><span class="badge">{p.get('timestamp', '00:00')}</span> {p.get('title', 'Pillar')}</h3>
            <p>{p.get('details', '').replace(chr(10), '<br>')}</p>
        </div>
        """)

    action_rows = []
    for a in action_items:
        action_rows.append(f"""
        <tr>
            <td><strong>{a.get('description', '')}</strong></td>
            <td>{a.get('assignee', 'Team')}</td>
            <td><span class="prio prio-{a.get('priority', 'MED').lower()}">{a.get('priority', 'MED')}</span></td>
            <td>{a.get('due_date', 'Next Sprint')}</td>
            <td>{a.get('notes', '—')}</td>
        </tr>
        """)

    decisions_html = "".join([f"<li>{d}</li>" for d in decisions])
    reversals_html = "".join([f"<li>{r}</li>" for r in reversals])

    transcript_html = []
    for s in transcript_segments:
        transcript_html.append(f"""
        <div class="turn">
            <span class="time">[{s.get('timestamp', '00:00')}]</span>
            <strong>{s.get('speaker', 'Speaker')}:</strong> {s.get('text', '')}
        </div>
        """)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} - Hesh-rec Report</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 40px; color: #1E293B; line-height: 1.6; }}
        h1 {{ font-size: 24px; color: #0F172A; border-bottom: 2px solid #0284C7; padding-bottom: 8px; margin-bottom: 4px; }}
        .meta {{ font-size: 13px; color: #64748B; margin-bottom: 24px; }}
        .badge {{ background: #E0F2FE; color: #0284C7; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
        h2 {{ font-size: 16px; color: #0284C7; text-transform: uppercase; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; margin-top: 24px; }}
        .pillar {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px; margin-bottom: 12px; }}
        .pillar h3 {{ margin: 0 0 6px 0; font-size: 14px; color: #0F172A; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
        th, td {{ border: 1px solid #CBD5E1; padding: 8px 10px; text-align: left; }}
        th {{ background: #F1F5F9; color: #475569; }}
        .prio {{ padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px; }}
        .prio-high {{ background: #FFE4E6; color: #E11D48; }}
        .prio-med {{ background: #FEF3C7; color: #D97706; }}
        .prio-low {{ background: #D1FAE5; color: #059669; }}
        .turn {{ font-size: 12px; margin-bottom: 6px; }}
        .turn .time {{ color: #0284C7; font-weight: bold; }}
        @media print {{ body {{ margin: 20px; }} }}
    </style>
</head>
<body>
    <h1>🎙️ {title}</h1>
    <div class="meta">⏱️ Duration: {duration} | 📅 Date: {date_str} | ⚡ Model: {model_str}</div>

    <h2>⚡ Executive Summary</h2>
    <ul>{brief_html}</ul>

    <h2>🏛️ Key Discussion Pillars</h2>
    {''.join(pillars_html)}

    <h2>📋 Action Items Matrix</h2>
    <table>
        <thead>
            <tr><th>Task Deliverable</th><th>Owner</th><th>Priority</th><th>Due Date</th><th>Acceptance Notes</th></tr>
        </thead>
        <tbody>
            {''.join(action_rows)}
        </tbody>
    </table>

    {'<h2>✅ Approved Decisions</h2><ul>' + decisions_html + '</ul>' if decisions else ''}
    {'<h2>🔄 Rejected Proposals & Reversals</h2><ul>' + reversals_html + '</ul>' if reversals else ''}

    <h2>🗣️ Spoken Transcript</h2>
    {''.join(transcript_html) if transcript_html else '<p>Transcript in turn format not available.</p>'}
</body>
</html>"""


# =============================================================================
# 5. COMPLETE CLOUD PIPELINE ORCHESTRATOR
# =============================================================================
def process_meeting_file_cloud(
    audio_path: Path,
    custom_title: Optional[str] = None,
    model_choice: str = DEFAULT_GEMINI_MODEL,
    user_id: Optional[str] = None,
    template_type: str = "executive"
) -> Dict[str, Any]:
    """
    End-to-end cloud pipeline:
    1. Transcribe with Groq Whisper-large-v3
    2. Extract intelligence with Gemini 2.5 Flash / Groq LLM using selected template
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
        model_name=model_choice,
        template_type=template_type
    )

    total_time_str = f"{time.time() - start_time:.2f}s"

    session_data = {
        "metadata": {
            "session_id": session_id,
            "user_id": user_id,
            "template_type": template_type,
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
# 6. SUPABASE AUTH & MULTI-TENANCY OPERATIONS
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

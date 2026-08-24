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
    base_header = f"""You are an elite Executive Meeting & Speech Intelligence Analyst adhering strictly to the clean, document-first Plaud methodology.
Your objective is to produce an elegant, narrative-first executive intelligence report from the provided transcript with ZERO redundant boilerplate labels.

Topic/Title: {topic}
Duration: {duration_str}
Spoken Transcript:
\"\"\"
{transcript_text}
\"\"\"
"""

    if template_type == "academic":
        return base_header + """
Analyze the academic lecture thoroughly and generate the report adhering STRICTLY to this clean Plaud document structure:

# 🎓 Academic Lecture Intelligence: {topic}

**Duration:** {duration_str}
**Instructors / Speakers:** [Identified speakers or instructor]

---

## ⚡ Executive Summary
[A crisp 2-3 sentence overarching summary capturing the central thesis, primary theoretical principle taught, and homework/exam focus.]

---

## 1. [First Core Concept / Lecture Section]
[A concise, highly readable executive narrative paragraph explaining the theoretical foundation, key context, instructor explanations, and core principle to master. DO NOT use boilerplate prefixes like 'Core Topic & Focus:' or 'Context:'; write continuous, natural academic prose.]

### Action Items
- [ ] [Specific study deliverable, assigned reading, or problem set] — *[Student / Study Group]* [Next Class / Exam]

---

## 2. [Second Core Concept / Lecture Section]
[A concise, highly readable executive narrative paragraph explaining the concept, breakdown, and core principle to master.]

### Action Items
- [ ] [Specific study deliverable or exam topic to review] — *[Student / Study Group]* [Next Class / Exam]

---

## 💡 AI Suggestions
> - **Unresolved Discussion Points:** [Complex concepts requiring further office-hour clarification or unresolved student questions]
> - **Missing Deadlines & Ownership Gaps:** [Ambiguities in assignment deadlines or submission criteria]
> - **Strategic Follow-up Recommendations:** [High-yield exam review topics, study group focus areas, and recommended supplementary readings]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

CRITICAL RULES FOR MERMAID:
- Format EVERY node safely with double quotes: root["Title"], ["Branch"], ["Leaf"].
- NEVER use raw '&', '<', '>', unescaped quotes, or brackets inside node text (use 'and' instead of '&').
- Strictly adhere to valid Mermaid mindmap indentation.
- Strictly mirror the numbered sections and study deliverables:
```mermaid
mindmap
  root["Academic Lecture Intelligence"]
    ["1. First Concept Title"]
      ["Core Theoretical Principle"]
      ["Action: Study deliverable"]
    ["2. Second Concept Title"]
      ["Core Theoretical Principle"]
      ["Action: Study deliverable"]
    ["💡 AI Suggestions"]
      ["Exam Focus Area"]
      ["Recommended Reading"]
```
"""

    elif template_type == "brainstorm":
        return base_header + """
Analyze the brainstorming and ideation session thoroughly and generate the report adhering STRICTLY to this clean Plaud document structure:

# 💡 Brainstorm & Ideation Report: {topic}

**Duration:** {duration_str}
**Participants:** [Identified participants]

---

## ⚡ Executive Summary
[A crisp 2-3 sentence overarching summary capturing the ideation challenge, the most promising creative breakthrough, and immediate experiment roadmaps.]

---

## 1. [First Ideation Track / Challenge]
[A concise, highly readable executive narrative paragraph explaining the problem addressed, the key creative proposals generated, trade-offs discussed, and consensus reached. DO NOT use boilerplate prefixes like 'Core Topic & Focus:' or 'Speaker Perspective:'; write continuous, natural prose.]

### Action Items
- [ ] [Prototype, mock, or research experiment deliverable] — *[Assignee / Team]* [Next Sprint / Target Date]

---

## 2. [Second Ideation Track / Challenge]
[A concise, highly readable executive narrative paragraph explaining the proposals, trade-offs, and consensus reached.]

### Action Items
- [ ] [Prototype, mock, or research experiment deliverable] — *[Assignee / Team]* [Next Sprint / Target Date]

---

## 💡 AI Suggestions
> - **Unresolved Discussion Points:** [Creative conflicts left open, discarded alternatives worth revisiting, or unvalidated assumptions]
> - **Missing Deadlines & Ownership Gaps:** [Experiments proposed without designated owners or timeline constraints]
> - **Strategic Follow-up Recommendations:** [Immediate prototype validation steps, user testing priorities, and technical feasibility spikes]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

CRITICAL RULES FOR MERMAID:
- Format EVERY node safely with double quotes: root["Title"], ["Branch"], ["Leaf"].
- NEVER use raw '&', '<', '>', unescaped quotes, or brackets inside node text (use 'and' instead of '&').
- Strictly adhere to valid Mermaid mindmap indentation.
- Strictly mirror the numbered tracks and experiments:
```mermaid
mindmap
  root["Brainstorming and Ideation"]
    ["1. First Idea Track"]
      ["Key Breakthrough"]
      ["Action: Prototype Experiment"]
    ["2. Second Idea Track"]
      ["Key Breakthrough"]
      ["Action: Validation Test"]
    ["💡 AI Suggestions"]
      ["Unvalidated Assumption"]
      ["Recommended Feasibility Spike"]
```
"""

    else:
        # Default: Executive Meeting Template (Plaud Document Style)
        return base_header + """
Analyze the meeting transcript thoroughly and generate the report adhering STRICTLY to this clean Plaud document structure:

# 🎙️ Meeting Intelligence Report: {topic}

**Duration:** {duration_str}
**Identified Participants:** [List all identified participants and roles]

---

## ⚡ Executive Summary
[A crisp 2-3 sentence overarching executive summary capturing the strategic purpose, core breakthroughs, and major decisions of the session.]

---

## 1. [First Core Topic Title]
[A concise, highly readable executive narrative paragraph explaining what happened, the context, key considerations, and resolution. DO NOT include boilerplate labels like 'Core Topic & Focus:' or 'Speaker Perspective:' or 'Context:'; write clean, continuous business prose.]

### Action Items
- [ ] [Concrete deliverable description] — *[Assignee]* [YYYY-MM-DD or timeframe]
- [ ] [Concrete deliverable description] — *[Assignee]* [YYYY-MM-DD or timeframe]

---

## 2. [Second Core Topic Title]
[A concise, highly readable executive narrative paragraph explaining what happened, the context, key considerations, and resolution.]

### Action Items
- [ ] [Concrete deliverable description] — *[Assignee]* [YYYY-MM-DD or timeframe]

---

## 3. [Third Core Topic Title]
[A concise, highly readable executive narrative paragraph explaining what happened, the context, key considerations, and resolution.]

### Action Items
- [ ] [Concrete deliverable description] — *[Assignee]* [YYYY-MM-DD or timeframe]

---

## 💡 AI Suggestions
> - **Unresolved Discussion Points:** [Key open questions, unresolved topics, or items deferred to future meetings]
> - **Missing Deadlines & Ownership Gaps:** [Deliverables mentioned without firm dates, ambiguous owners, or dependency risks]
> - **Strategic Follow-up Recommendations:** [Proactive recommendations and next steps for team leadership]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

CRITICAL RULES FOR MERMAID:
- Format EVERY node safely with double quotes: root["Title"], ["Branch"], ["Leaf"].
- NEVER use raw '&', '<', '>', unescaped quotes, or brackets inside node text (use 'and' instead of '&').
- Strictly adhere to valid Mermaid mindmap indentation.
- Strictly mirror the numbered sections, sub-actions, and AI suggestions:
```mermaid
mindmap
  root["Meeting Title"]
    ["1. First Topic Title"]
      ["Narrative Focus Point"]
      ["Action: Deliverable description"]
    ["2. Second Topic Title"]
      ["Narrative Focus Point"]
      ["Action: Deliverable description"]
    ["💡 AI Suggestions"]
      ["Unresolved Point or Gap"]
      ["Strategic Recommendation"]
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

def sanitize_mermaid_node(text: str, max_len: int = 55) -> str:
    """Sanitizes strings for strict compatibility inside Mermaid mindmap nodes."""
    if not text:
        return ""
    # Strip markdown formatting, brackets, parens, quotes, colons
    clean = re.sub(r"[\*#_`\"'\{\}\(\)\[\]<>\\]", " ", str(text))
    clean = clean.replace("&", " and ").replace(":", " - ")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "..."
    return clean


def build_contextual_mindmap(session_data: Dict[str, Any], meeting_title: str = "Meeting Intelligence") -> str:
    """
    Constructs a deterministic, 100% unified tree-style Mermaid mindmap directly derived
    from the numbered section titles, narrative highlights, inline action items, and AI suggestions.
    """
    clean_root = sanitize_mermaid_node(meeting_title, max_len=42) or "Meeting Intelligence"
    lines = [
        "mindmap",
        f'  root["{clean_root}"]'
    ]

    # 1. Numbered Topic Sections with Narrative Focus & Inline Actions
    topics = session_data.get("discussion_pillars", []) or session_data.get("numbered_topics", [])
    if topics:
        for idx, t in enumerate(topics[:5]):
            t_num = t.get("index", idx + 1)
            raw_title = t.get("title", f"Topic {t_num}")
            clean_title = sanitize_mermaid_node(raw_title, max_len=38)
            # Remove any leading digits if already present
            clean_title = re.sub(r"^\d+\.\s*", "", clean_title)
            
            lines.append(f'    ["{t_num}. {clean_title}"]')
            
            # Narrative highlight
            narrative = t.get("narrative") or t.get("details", "")
            if narrative:
                first_sentence = re.split(r"[\.\n]", narrative)[0].strip()
                clean_first = sanitize_mermaid_node(first_sentence, max_len=45)
                if clean_first and clean_first.lower() != clean_title.lower():
                    lines.append(f'      ["{clean_first}"]')
            
            # Inline Action Items under this topic
            topic_actions = t.get("action_items", [])
            for a in topic_actions[:2]:
                desc = a.get("description") or a.get("task") or "Deliverable"
                owner = a.get("assignee") or a.get("owner") or "Team"
                clean_desc = sanitize_mermaid_node(desc, max_len=30)
                clean_owner = sanitize_mermaid_node(owner, max_len=14)
                if clean_desc:
                    lines.append(f'      ["Action: {clean_desc} ({clean_owner})"]')

    else:
        # Fallback if no numbered topics: use executive brief & actions
        exec_brief = session_data.get("executive_brief", [])
        if exec_brief:
            lines.append('    ["⚡ Executive Focus"]')
            for b in exec_brief[:2]:
                clean_b = sanitize_mermaid_node(b, max_len=45)
                if clean_b:
                    lines.append(f'      ["{clean_b}"]')

    # 2. AI Suggestions Branch
    suggestions = session_data.get("ai_suggestions", {})
    if isinstance(suggestions, dict):
        sugg_list = suggestions.get("unresolved", []) + suggestions.get("gaps", []) + suggestions.get("recommendations", [])
    elif isinstance(suggestions, list):
        sugg_list = suggestions
    else:
        sugg_list = []

    if sugg_list:
        lines.append('    ["💡 AI Suggestions"]')
        for s in sugg_list[:3]:
            clean_s = sanitize_mermaid_node(s, max_len=45)
            if clean_s:
                lines.append(f'      ["{clean_s}"]')
    elif session_data.get("decisions"):
        lines.append('    ["⚖️ Approved Decisions"]')
        for d in session_data.get("decisions", [])[:2]:
            clean_d = sanitize_mermaid_node(d, max_len=45)
            if clean_d:
                lines.append(f'      ["{clean_d}"]')

    return "\n".join(lines)


def parse_markdown_to_session_dict(
    raw_markdown: str,
    model_name: str,
    template_type: str = "executive"
) -> Dict[str, Any]:
    """Parses clean Plaud-style markdown report into structured session dictionary."""
    
    # 1. Executive Summary
    exec_brief = []
    exec_match = re.search(r"## ⚡ Executive Summary\s*(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if not exec_match:
        exec_match = re.search(r"## ⚡ Executive Brief\s*(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if exec_match:
        for line in exec_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("> •") or line.startswith("> -") or line.startswith("•") or line.startswith("-"):
                clean = re.sub(r"^>\s*[•\-]\s*", "• ", line).strip()
                clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean).strip()
                if clean:
                    exec_brief.append(clean)
            elif line and not line.startswith("#") and not line.startswith("---") and not line.startswith(">"):
                clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", line).strip()
                if clean:
                    exec_brief.append(f"• {clean}")

    # 2. Numbered Topics & Per-Topic Narratives + Inline Action Items (Plaud Style)
    numbered_topics = []
    all_action_items = []
    
    # Regex to find all numbered H2 sections: e.g. ## 1. Topic Title ...
    topic_sections = re.findall(r"^##\s+(\d+)\.\s*([^\n]+)\n([\s\S]*?)(?=^##\s+|\Z)", raw_markdown, re.MULTILINE)
    
    if topic_sections:
        for num_str, title_str, body_str in topic_sections:
            idx = int(num_str)
            clean_title = title_str.strip()
            
            # Separate narrative from action items section
            narrative_text = ""
            inline_actions = []
            
            act_match = re.search(r"### Action Items\s*([\s\S]*?)(?=\n###|\n---|\Z)", body_str, re.IGNORECASE)
            if act_match:
                # Narrative is everything before ### Action Items
                narrative_part = body_str[:act_match.start()].strip()
                actions_part = act_match.group(1).strip()
            else:
                narrative_part = body_str.strip()
                actions_part = ""

            # Clean narrative: strip any leftover boilerplate labels like **Core Topic & Focus:**, etc.
            narrative_lines = []
            for line in narrative_part.splitlines():
                line = line.strip()
                if not line or line.startswith("---") or line.startswith("#"):
                    continue
                # Remove boilerplate labels
                clean_line = re.sub(r"^\*\*(?:Core Topic & Focus|Key Arguments & Perspectives|Key Takeaways & Points|Consensus & Outcome|Context & Objective|Context|Objective|Speaker Perspective|[A-Z][a-z]+'s Perspective)[^\*:]*:\*\*\s*", "", line)
                clean_line = re.sub(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", "", clean_line)
                clean_line = clean_line.strip()
                if clean_line:
                    narrative_lines.append(clean_line)
            
            narrative_text = " ".join(narrative_lines)

            # Parse inline action items: - [ ] Task description — *Assignee* DueDate
            if actions_part:
                for a_line in actions_part.splitlines():
                    a_line = a_line.strip()
                    if not a_line or a_line.startswith("#") or a_line.startswith("---"):
                        continue
                    # Match: - [ ] Deliverable — *Assignee* DueDate
                    m_act = re.match(r"^[-*•]?\s*(?:\[[\sxX]?\]|☐|☑)?\s*(.*?)(?:—|--|-)\s*\*?([^*—\n]+?)\*?\s+(?:(\d{4}-\d{2}-\d{2}|Next [A-Za-z]+|Today|ASAP|Post-[A-Za-z]+|Scheduled [A-Za-z]+|[A-Za-z0-9\s/]+))?$", a_line)
                    if m_act:
                        desc = m_act.group(1).strip().strip("[]*-• ")
                        assignee = m_act.group(2).strip() if m_act.group(2) else "Team"
                        due = m_act.group(3).strip() if m_act.group(3) else "Next Sprint"
                    else:
                        clean_a = re.sub(r"^[-*•\[\]\sxX☐☑]+\s*", "", a_line)
                        desc = clean_a
                        assignee = "Team"
                        due = "Next Sprint"

                    if desc and len(desc) > 3:
                        act_obj = {
                            "number": len(all_action_items) + 1,
                            "description": desc,
                            "assignee": assignee or "Team",
                            "priority": "HIGH" if any(k in desc.lower() for k in ["high", "urgent", "p0", "soc 2"]) else "MED",
                            "due_date": due or "Next Sprint",
                            "notes": f"Topic {idx}: {clean_title}",
                            "status": "pending"
                        }
                        inline_actions.append(act_obj)
                        all_action_items.append(act_obj)

            numbered_topics.append({
                "index": idx,
                "title": clean_title,
                "narrative": narrative_text,
                "action_items": inline_actions,
                "timestamp": f"00:{(idx-1)*5:02d}:00",
                "details": narrative_text
            })

    # Fallback to legacy discussion pillars if numbered topics were not found
    if not numbered_topics:
        pillars_match = re.search(r"## 🏛️ Key Discussion Pillars\s*(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
        if pillars_match:
            pillar_blocks = re.findall(r"###\s*(\d+\.\s*\[(.*?)\]\s*(.*?))\n(.*?)(?=\n###|\Z)", pillars_match.group(1), re.DOTALL)
            for num_match, ts, title, details in pillar_blocks:
                clean_lines = [re.sub(r"^\*\*[^*]+:\*\*\s*", "", l.strip()) for l in details.splitlines() if l.strip()]
                clean_narrative = " ".join(clean_lines)
                numbered_topics.append({
                    "index": len(numbered_topics) + 1,
                    "title": title.strip(),
                    "timestamp": ts.strip(),
                    "narrative": clean_narrative,
                    "details": clean_narrative,
                    "action_items": []
                })

    # Strategy Fallback for Table Action Items if inline were not found
    if not all_action_items:
        table_match = re.search(r"## 📋 Action Items Matrix.*?\n(\|.*?\n\|[-:\s|]+\n)(.*?)(?=\n\n\S|---|##|\Z)", raw_markdown, re.DOTALL)
        if not table_match:
            table_match = re.search(r"(\|(?:\s*#\s*\|\s*Task Deliverable.*?\n)(.*?)(?=\n\n\S|---|##|\Z))", raw_markdown, re.DOTALL)

        if table_match:
            content_to_parse = table_match.group(2) if len(table_match.groups()) >= 2 else table_match.group(0)
            rows = [r.strip() for r in content_to_parse.splitlines() if r.strip() and "|" in r and not re.match(r"^\|[\s\-:|]+\|$", r.strip())]
            for r in rows:
                cols = [c.strip() for c in r.split("|")[1:-1]]
                if len(cols) >= 3:
                    num = len(all_action_items) + 1
                    desc = cols[1] if len(cols) > 1 and cols[0].isdigit() else cols[0]
                    assignee = cols[2] if len(cols) > 2 and cols[0].isdigit() else (cols[1] if len(cols) > 1 else "Team")
                    prio = cols[3].upper() if len(cols) > 3 and cols[0].isdigit() else "MED"
                    due = cols[4] if len(cols) > 4 and cols[0].isdigit() else (cols[2] if len(cols) > 2 else "Next Sprint")
                    notes = cols[5] if len(cols) > 5 and cols[0].isdigit() else "—"

                    if "task" in desc.lower() and "deliverable" in desc.lower():
                        continue

                    if desc and len(desc) > 3:
                        all_action_items.append({
                            "number": num,
                            "description": desc,
                            "assignee": assignee or "Team",
                            "priority": "HIGH" if "HIGH" in prio else ("LOW" if "LOW" in prio else "MED"),
                            "due_date": due or "Next Sprint",
                            "notes": notes or "—",
                            "status": "pending"
                        })

    # 3. AI Suggestions Callout Parsing
    ai_suggestions = {
        "unresolved": [],
        "gaps": [],
        "recommendations": [],
        "raw_text": ""
    }
    sugg_match = re.search(r"## 💡 AI Suggestions\s*([\s\S]*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if not sugg_match:
        sugg_match = re.search(r"### AI Suggestions\s*([\s\S]*?)(?=\n## |\n###|\Z)", raw_markdown, re.DOTALL)

    if sugg_match:
        raw_sugg = sugg_match.group(1).strip()
        ai_suggestions["raw_text"] = raw_sugg
        for s_line in raw_sugg.splitlines():
            s_line = s_line.strip().lstrip(">•*- ")
            if not s_line:
                continue
            if "unresolved" in s_line.lower():
                clean_val = re.sub(r"^\*\*Unresolved[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    ai_suggestions["unresolved"].append(clean_val)
            elif "missing" in s_line.lower() or "gap" in s_line.lower():
                clean_val = re.sub(r"^\*\*Missing[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    ai_suggestions["gaps"].append(clean_val)
            elif "recommend" in s_line.lower() or "follow-up" in s_line.lower():
                clean_val = re.sub(r"^\*\*Strategic[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    ai_suggestions["recommendations"].append(clean_val)
            else:
                clean_val = re.sub(r"^\*\*[^*]+:\*\*\s*", "", s_line).strip()
                if clean_val:
                    ai_suggestions["recommendations"].append(clean_val)
    else:
        # Default fallback suggestions if section was omitted by LLM
        ai_suggestions["unresolved"].append("Confirm exact timeline dependencies with external team members.")
        ai_suggestions["gaps"].append("Ensure all newly identified action deliverables have explicit owner confirmation.")
        ai_suggestions["recommendations"].append("Schedule a 15-minute async checkpoint before the next major milestone.")

    # 4. Decisions
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

    # 5. Mermaid Mindmap Sanitization & Tree Contextual Alignment
    mindmap = ""
    mm_match = re.search(r"```mermaid\s*(.*?)```", raw_markdown, re.DOTALL)
    if mm_match:
        mindmap = mm_match.group(1).strip()
    
    is_boilerplate = any(b in mindmap.lower() for b in [
        "strategic direction", "concept alpha", "academic lecture intelligence", "key milestone", "theme analysis", "opportunity", "concept one"
    ])

    parsed_result = {
        "template_type": template_type,
        "executive_brief": exec_brief,
        "discussion_pillars": numbered_topics,
        "numbered_topics": numbered_topics,
        "action_items": all_action_items,
        "ai_suggestions": ai_suggestions,
        "decisions": decisions,
        "reversals": [],
        "raw_markdown": raw_markdown,
        "model_used": model_name
    }

    if not mindmap or len(mindmap) < 25 or is_boilerplate:
        title_match = re.search(r"#\s*🎙️?\s*(?:Meeting Intelligence Report:?|Academic Lecture Intelligence:?|Brainstorm & Ideation Report:?)?\s*(.*?)(?=\n|\Z)", raw_markdown)
        meeting_title = title_match.group(1).strip() if title_match and title_match.group(1).strip() else "Meeting Intelligence"
        mindmap = build_contextual_mindmap(parsed_result, meeting_title)

    parsed_result["mermaid_mindmap"] = mindmap
    return parsed_result


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
    """Generates a standalone, beautiful Plaud-styled HTML document suitable for browser print-to-PDF."""
    meta = session_data.get("metadata", {})
    title = meta.get("source_file", "Meeting Intelligence Report")
    duration = meta.get("duration", "N/A")
    date_str = meta.get("processed_at", datetime.now().strftime("%Y-%m-%d"))
    model_str = meta.get("model", "Hesh-rec AI")
    exec_brief = session_data.get("executive_brief", [])
    topics = session_data.get("numbered_topics", []) or session_data.get("discussion_pillars", [])
    action_items = session_data.get("action_items", [])
    ai_suggestions = session_data.get("ai_suggestions", {})
    transcript_segments = session_data.get("transcript_segments", [])

    brief_html = "".join([f"<p style='margin-bottom:6px;'>{p.lstrip('•*- ')}</p>" for p in exec_brief])

    topics_html = []
    for idx, t in enumerate(topics):
        t_num = t.get("index", idx + 1)
        t_title = t.get("title", f"Topic {t_num}")
        narrative = t.get("narrative") or t.get("details", "")
        # Clean narrative of any leftover bold prefixes
        clean_narrative = re.sub(r"^\*\*[^*]+:\*\*\s*", "", narrative)
        
        t_actions = t.get("action_items", [])
        actions_html = ""
        if t_actions:
            items_li = []
            for a in t_actions:
                desc = a.get("description", "")
                owner = a.get("assignee", "Team")
                due = a.get("due_date", "Next Sprint")
                items_li.append(f"""
                <div style="display:flex; align-items:center; justify-content:space-between; padding:5px 0; border-bottom:1px dashed #E2E8F0; font-size:12.5px;">
                    <div><span style="color:#0284C7; font-weight:bold; margin-right:6px;">☐</span> {desc}</div>
                    <div style="font-size:11px; color:#64748B;"><em>{owner}</em> • {due}</div>
                </div>
                """)
            actions_html = f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px; margin-top:10px;">
                <div style="font-size:11px; font-weight:bold; color:#0284C7; text-transform:uppercase; margin-bottom:4px;">Action Items</div>
                {''.join(items_li)}
            </div>
            """

        topics_html.append(f"""
        <div style="margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid #E2E8F0;">
            <h3 style="font-size:15px; color:#0F172A; margin:0 0 8px 0; display:flex; align-items:center; gap:8px;">
                <span style="background:#E0F2FE; color:#0284C7; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:bold;">{t_num}</span>
                {t_title}
            </h3>
            <p style="font-size:13.5px; color:#334155; line-height:1.65; margin:0;">{clean_narrative}</p>
            {actions_html}
        </div>
        """)

    # AI Suggestions Callout
    suggestions_html = ""
    if isinstance(ai_suggestions, dict):
        unresolved = ai_suggestions.get("unresolved", [])
        gaps = ai_suggestions.get("gaps", [])
        recs = ai_suggestions.get("recommendations", [])
        if unresolved or gaps or recs:
            sugg_items = []
            for u in unresolved:
                sugg_items.append(f"<li><strong>Unresolved Point:</strong> {u}</li>")
            for g in gaps:
                sugg_items.append(f"<li><strong>Missing Deadline / Gap:</strong> {g}</li>")
            for r in recs:
                sugg_items.append(f"<li><strong>Strategic Follow-up:</strong> {r}</li>")

            suggestions_html = f"""
            <div style="background:linear-gradient(135deg, #FEF3C7 0%, #F3E8FF 100%); border:1px solid #F59E0B; border-radius:10px; padding:16px 20px; margin-top:24px; margin-bottom:20px;">
                <h3 style="font-size:14px; font-weight:800; color:#B45309; margin:0 0 8px 0;">💡 AI Suggestions & Strategic Follow-ups</h3>
                <ul style="margin:0; padding-left:20px; font-size:13px; color:#451A03; line-height:1.6;">
                    {''.join(sugg_items)}
                </ul>
            </div>
            """

    transcript_html = []
    for s in transcript_segments:
        transcript_html.append(f"""
        <div style="font-size:12px; margin-bottom:6px;">
            <span style="color:#0284C7; font-weight:bold;">[{s.get('timestamp', '00:00')}]</span>
            <strong>{s.get('speaker', 'Speaker')}:</strong> {s.get('text', '')}
        </div>
        """)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} - Hesh-rec Document</title>
    <style>
        body {{ font-family: 'Helvetica Neue', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 40px auto; max-width: 850px; color: #1E293B; line-height: 1.65; background: #FFF; }}
        .doc-container {{ padding: 30px; border: 1px solid #E2E8F0; border-radius: 12px; }}
        h1 {{ font-size: 22px; color: #0F172A; margin: 0 0 6px 0; }}
        .meta {{ font-size: 12.5px; color: #64748B; margin-bottom: 20px; border-bottom: 1px solid #E2E8F0; padding-bottom: 12px; }}
        h2 {{ font-size: 14px; color: #0284C7; text-transform: uppercase; letter-spacing: 0.5px; margin: 20px 0 10px 0; }}
        @media print {{ body {{ margin: 15px; max-width: 100%; }} .doc-container {{ border: none; padding: 0; }} }}
    </style>
</head>
<body>
    <div class="doc-container">
        <h1>🎙️ {title}</h1>
        <div class="meta">⏱️ Duration: {duration} | 📅 Date: {date_str} | ⚡ Model: {model_str}</div>

        <h2>⚡ Executive Summary</h2>
        <div style="background:#F8FAFC; border-left:3px solid #0284C7; padding:10px 14px; border-radius:4px; font-size:13.5px; color:#334155;">
            {brief_html}
        </div>

        <h2>📖 Discussion Topics & Action Deliverables</h2>
        {''.join(topics_html)}

        {suggestions_html}

        <h2>🗣️ Diarized Transcript</h2>
        {''.join(transcript_html) if transcript_html else '<p style="font-size:12px; color:#64748B;">Transcript in turn format not available.</p>'}
    </div>
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


def update_session_action_items(session_id: str, action_items: List[Dict[str, Any]], user_id: Optional[str] = None) -> bool:
    """Updates action items with completion statuses and syncs both locally and to Supabase."""
    sid_clean = session_id.replace("session_", "")
    local_file = SESSIONS_DIR / f"session_{sid_clean}.json"
    session_data = {}
    title = "Meeting"

    if local_file.exists():
        try:
            with open(local_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            title = session_data.get("metadata", {}).get("source_file", "Meeting")
        except Exception:
            pass

    session_data["action_items"] = action_items
    return save_session_record(sid_clean, title, session_data, user_id=user_id)


# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os
from pathlib import Path

# Force-load .env at start of module
_root_env = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_root_env, override=True)
load_dotenv(override=True)

import sys
import io
import json
import time
import uuid
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import toml
from groq import Groq
from supabase import create_client, Client
from google import genai
from google.genai import types

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = BASE_DIR / "sessions"
OUTPUTS_DIR = BASE_DIR / "outputs"
INPUTS_DIR = BASE_DIR / "inputs"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
INPUTS_DIR.mkdir(parents=True, exist_ok=True)

from core.config import get_secret

# Sync .streamlit/secrets.toml into .env if present
def sync_secrets_toml_to_env():
    for b in [BASE_DIR, Path.cwd(), Path.home()]:
        sec_path = b / ".streamlit" / "secrets.toml"
        if sec_path.exists():
            try:
                sec_data = toml.load(str(sec_path))
                for k, v in sec_data.items():
                    if isinstance(v, str) and v.strip():
                        if k not in os.environ or not os.environ[k]:
                            os.environ[k] = v.strip()
            except Exception as e:
                print(f"[!] Warning reading secrets.toml: {e}", flush=True)

sync_secrets_toml_to_env()

DEFAULT_GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-3.6-flash")

MODEL_CANDIDATES = [
    DEFAULT_GEMINI_MODEL,
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest"
]

def get_groq_client(api_key: Optional[str] = None) -> Optional[Groq]:
    raw_key = api_key or os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or get_secret("GROQ_API_KEY")
    if raw_key:
        clean = raw_key.strip().strip('"').strip("'")
        if clean:
            try:
                return Groq(api_key=clean)
            except Exception as e:
                print(f"[!] Groq Client Init Error: {e}", flush=True)
    return None

def get_supabase_client() -> Optional[Client]:
    url = os.environ.get("SUPABASE_URL") or get_secret("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or get_secret("SUPABASE_KEY")
    if url and key:
        clean_url = url.strip().strip('"').strip("'")
        clean_key = key.strip().strip('"').strip("'")
        if clean_url and clean_key:
            try:
                return create_client(clean_url, clean_key)
            except Exception as e:
                print(f"[!] Supabase Client Init Error: {e}", flush=True)
    return None

def get_gemini_client(api_key: Optional[str] = None) -> Optional[genai.Client]:
    raw_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
    if raw_key:
        clean = raw_key.strip().strip('"').strip("'")
        if clean:
            try:
                return genai.Client(api_key=clean)
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
    prompt: Optional[str] = None,
    api_key: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str, float]:
    """
    Transcribes audio file using Groq Whisper-large-v3 API with verbose JSON timestamps.
    Returns: (segments_list, full_text_transcript, duration_seconds)
    """
    groq_client = get_groq_client(api_key=api_key)
    if not groq_client:
        loaded_keys = [k for k in os.environ.keys() if "KEY" in k or "SECRET" in k or "GROQ" in k or "GEMINI" in k]
        print(f"[!] GROQ_API_KEY is not set. Relevant env keys found: {loaded_keys}", flush=True)
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
# 2. STRUCTURED JSON INTELLIGENCE PROMPT & EXTRACTION PIPELINE
# =============================================================================
def build_intelligence_prompt(
    topic: str,
    transcript_text: str,
    duration_str: str,
    meeting_date_iso: Optional[str] = None,
    template_type: str = "executive"
) -> str:
    """Builds exact structured JSON prompt for SOC 2 executive meeting intelligence."""
    if not meeting_date_iso:
        meeting_date_iso = datetime.now().strftime("%Y-%m-%d")

    return f"""You are an expert meeting analyst producing a structured record of a recorded meeting. You will receive a diarized transcript. It may be messy, contain filler, cross-talk, ASR errors, and mixed languages (English/Arabic).

Return ONE valid JSON object and nothing else. No markdown fences, no commentary.

=====================  ABSOLUTE RULES  =====================

R1. GROUNDING. Use only what is in the transcript. Never invent a decision, owner, number, or date. If something was not said, it does not appear.
R2. LANGUAGE. Output is always professional English, regardless of the transcript's language.
R3. DATES. You are given MEETING_DATE ({meeting_date_iso}). Resolve every relative date against it (e.g., "next Friday", "tomorrow", "end of month") to an ISO format YYYY-MM-DD.
R4. NAMES & ACRONYMS. Preserve exact speaker names from the transcript. Fix ASR spellings of technical terms and keep acronyms fully uppercase: SOC 2, ISO, DLP, BYOD, MFA, API, PDF, UI, VPN, QR, AI.
R5. SPECIFICITY IS THE WHOLE JOB. Every task must carry the concrete details a person needs to do it without replaying the recording: document numbers, slide numbers, version numbers, tool names, durations, thresholds, counts. A task under 8 words is almost always too vague — expand it.
R6. GRANULARITY. Extract EVERY committed task. One task = one thing a person can tick off. Never bundle two deliverables into one line. Every deliverable mentioned down to specific slides, policies, tickets, and configurations must be its own action item.
R7. RICH EXECUTIVE NARRATIVE. Every section MUST have a comprehensive narrative consisting of 4-7 complete, information-dense sentences in past tense detailing the background context, technical trade-offs discussed, arguments raised, and decided roadmap. Never write shallow generic bullet points, single-sentence summaries, or gerund fragments.
R8. ZERO TEMPLATE LEAKAGE. Never emit scaffolding labels like "Core Topic and Focus", "Perspective", "Speaker Perspective", "Key Arguments & Perspectives", "Key Takeaways", "Consensus & Outcome", "Discussion", or "Overview". Write clean, authoritative executive business prose.
R9. REAL AI SUGGESTIONS. Extract 2-4 genuine unassigned operational risks, missing deadlines, unowned dependencies, or compliance/governance gaps explicitly observed in the conversation. Never output generic boilerplate placeholders.

=====================  OUTPUT SCHEMA  =====================

{{
  "title": "MM-DD Meeting: <Topic A, Topic B, and Topic C>",
  "meeting_date": "{meeting_date_iso}",
  "duration_minutes": <int or null>,
  "participants": ["<name as spoken>", ...],
  "tags": ["<2-4 domain tags>"],
  "tldr": "<3-4 sentences executive summary highlighting core context, top decisions, and major deadlines>",
  "sections": [
    {{
      "n": 1,
      "title": "<Specific, highly descriptive topic title>",
      "narrative": "<4-7 complete sentences detailing context, technical discussion, debate, and decided outcome>",
      "decisions": ["<Explicit decision reached by the team>"],
      "action_items": [
        {{
          "id": "A1",
          "task": "<Fully specific, actionable deliverable with document IDs, slide numbers, or technical parameters>",
          "owner": "<Exact person or team name>",
          "co_owners": [],
          "due_date": "YYYY-MM-DD or null",
          "due_text": "<relative date text as spoken or null>",
          "priority": "HIGH | MED | LOW",
          "context": "<one sentence explaining the technical or business rationale>",
          "blocked_by": null
        }}
      ]
    }}
  ],
  "open_questions": [
    {{
      "question": "<Unresolved question or inquiry raised during discussion>",
      "raised_by": "<Speaker name or null>"
    }}
  ],
  "ai_suggestions": [
    {{
      "label": "<Specific Risk or Gap Name>",
      "detail": "<Concrete gap, unassigned dependency, or governance risk identified in the meeting and recommended next step>"
    }}
  ]
}}

=====================  INPUT TRANSCRIPT  =====================

MEETING_DATE: {meeting_date_iso}
Duration: {duration_str}

\"\"\"
{transcript_text}
\"\"\""""


def sanitize_mermaid_node(text: str, max_len: int = 45) -> str:
    """Sanitizes strings for strict compatibility inside Mermaid mindmap nodes."""
    if not text:
        return ""
    clean = re.sub(r"[\*#_`\"'\{\}\(\)\[\]<>\\]", " ", str(text))
    clean = clean.replace("&", " and ").replace(":", " - ")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "..."
    return clean


def convert_structured_mindmap_to_mermaid(mindmap_dict: Any, fallback_title: str = "Meeting Intelligence") -> str:
    """Converts structured JSON mindmap object into valid Mermaid mindmap syntax."""
    if not isinstance(mindmap_dict, dict) or not mindmap_dict.get("root"):
        clean_root = sanitize_mermaid_node(fallback_title, max_len=40) or "Meeting Intelligence"
        return f"""mindmap\n  root["{clean_root}"]\n    ["Overview"]\n      ["Key Points"]"""

    root_val = sanitize_mermaid_node(mindmap_dict.get("root", fallback_title), max_len=40)
    lines = [
        "mindmap",
        f'  root["{root_val}"]'
    ]
    branches = mindmap_dict.get("branches", [])
    if isinstance(branches, list):
        for b in branches:
            if isinstance(b, dict):
                b_lbl = sanitize_mermaid_node(b.get("label", "Topic"), max_len=30)
                if b_lbl:
                    lines.append(f'    ["{b_lbl}"]')
                    children = b.get("children", [])
                    if isinstance(children, list):
                        for c in children:
                            if isinstance(c, dict):
                                c_lbl = sanitize_mermaid_node(c.get("label", "Point"), max_len=30)
                            else:
                                c_lbl = sanitize_mermaid_node(str(c), max_len=30)
                            if c_lbl:
                                lines.append(f'      ["{c_lbl}"]')
            elif isinstance(b, str):
                b_lbl = sanitize_mermaid_node(b, max_len=30)
                if b_lbl:
                    lines.append(f'    ["{b_lbl}"]')

    return "\n".join(lines)


def convert_structured_json_to_markdown(json_obj: Any) -> str:
    """Converts structured meeting JSON back to readable markdown representation."""
    json_obj = safe_parse_json(json_obj)
    title = json_obj.get("title", "Meeting Intelligence")
    lines = [f"# {title}\n"]
    
    m_date = json_obj.get("meeting_date")
    dur = json_obj.get("duration_minutes")
    parts = json_obj.get("participants", [])
    if not isinstance(parts, list):
        parts = []
    tags = json_obj.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    
    meta_items = []
    if m_date:
        meta_items.append(f"**Date:** {m_date}")
    if dur:
        meta_items.append(f"**Duration:** {dur} min")
    if parts:
        meta_items.append(f"**Participants:** {', '.join([str(p) for p in parts])}")
    if tags:
        meta_items.append(f"**Tags:** {', '.join([str(t) for t in tags])}")
    if meta_items:
        lines.append(" • ".join(meta_items) + "\n")
        
    tldr = json_obj.get("tldr", "")
    if tldr:
        lines.append(f"{tldr}\n")
        
    sections = json_obj.get("sections", [])
    if isinstance(sections, list):
        for idx, sec in enumerate(sections):
            if not isinstance(sec, dict):
                continue
            n = sec.get("n", idx + 1)
            stitle = sec.get("title", "")
            lines.append(f"## {n}. {stitle}\n")
            narrative = sec.get("narrative", "")
            if narrative:
                lines.append(f"{narrative}\n")
                
            decs = sec.get("decisions", [])
            if isinstance(decs, list) and decs:
                lines.append("**Decisions:**")
                for d in decs:
                    lines.append(f"- {d}")
                lines.append("")
                
            actions = sec.get("action_items", [])
            if isinstance(actions, list) and actions:
                lines.append("### Action Items")
                for a in actions:
                    if not isinstance(a, dict):
                        continue
                    t = a.get("task", "")
                    o = a.get("owner", "Team")
                    due = a.get("due_date") or a.get("due_text") or ""
                    due_s = f" {due}" if due and due != "—" else ""
                    lines.append(f"- [ ] {t} — *{o}*{due_s}")
                lines.append("")
            
    open_q = json_obj.get("open_questions", [])
    if isinstance(open_q, list) and open_q:
        lines.append("## Open Questions")
        for q in open_q:
            if isinstance(q, dict):
                q_txt = q.get("question", "")
                r_by = q.get("raised_by", "")
                lines.append(f"- **{q_txt}** (Raised by: {r_by})")
            elif isinstance(q, str):
                lines.append(f"- **{q}**")
        lines.append("")
        
    suggs = json_obj.get("ai_suggestions", [])
    if isinstance(suggs, list) and suggs:
        lines.append("## AI Suggestions")
        lines.append("> AI has identified the following issues that were not concluded in the meeting or lack clear action items; please pay attention:\n")
        for idx, s in enumerate(suggs):
            if isinstance(s, dict):
                lbl = s.get("label", "")
                det = s.get("detail", "")
                lines.append(f"{idx+1}. **{lbl}**: {det}")
            elif isinstance(s, str):
                lines.append(f"{idx+1}. **Note**: {s}")
        lines.append("")
    elif isinstance(suggs, dict):
        items_list = suggs.get("items", [])
        if isinstance(items_list, list) and items_list:
            lines.append("## AI Suggestions")
            for idx, s in enumerate(items_list):
                if isinstance(s, dict):
                    lbl = s.get("label", "")
                    det = s.get("detail", "")
                    lines.append(f"{idx+1}. **{lbl}**: {det}")
                elif isinstance(s, str):
                    lines.append(f"{idx+1}. **Note**: {s}")
            lines.append("")
        
    return "\n".join(lines)


def build_contextual_mindmap(session_data: Any, meeting_title: str = "Meeting Intelligence") -> str:
    """Fallback mindmap builder for legacy session dictionaries."""
    session_data = safe_parse_json(session_data)
    clean_root = sanitize_mermaid_node(meeting_title, max_len=40) or "Meeting Intelligence"
    lines = [
        "mindmap",
        f'  root["{clean_root}"]'
    ]

    topics = session_data.get("discussion_pillars", []) or session_data.get("numbered_topics", []) or session_data.get("sections", [])
    if isinstance(topics, list) and topics:
        for idx, t in enumerate(topics[:5]):
            if not isinstance(t, dict):
                continue
            t_num = t.get("index") or t.get("n", idx + 1)
            raw_title = t.get("title", f"Topic {t_num}")
            clean_title = sanitize_mermaid_node(raw_title, max_len=30)
            clean_title = re.sub(r"^\d+\.\s*", "", clean_title)
            lines.append(f'    ["{t_num}. {clean_title}"]')
            
            narrative = t.get("narrative") or t.get("details", "")
            if isinstance(narrative, str) and narrative:
                first_sentence = re.split(r"[\.\n]", narrative)[0].strip()
                clean_first = sanitize_mermaid_node(first_sentence, max_len=30)
                if clean_first and clean_first.lower() != clean_title.lower():
                    lines.append(f'      ["{clean_first}"]')
            
            topic_actions = t.get("action_items", [])
            if isinstance(topic_actions, list):
                for a in topic_actions[:2]:
                    if not isinstance(a, dict):
                        continue
                    desc = a.get("task") or a.get("description") or "Deliverable"
                    owner = a.get("owner") or a.get("assignee") or "Team"
                    clean_desc = sanitize_mermaid_node(desc, max_len=24)
                    clean_owner = sanitize_mermaid_node(owner, max_len=12)
                    if clean_desc:
                        lines.append(f'      ["Action: {clean_desc} ({clean_owner})"]')

    return "\n".join(lines)


def safe_parse_json(content: Any) -> Dict[str, Any]:
    """Safely parses JSON content from dict or string, stripping markdown fences."""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            res = json.loads(cleaned)
            if isinstance(res, dict):
                return res
        except Exception:
            pass
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                res = json.loads(match.group(0))
                if isinstance(res, dict):
                    return res
            except Exception:
                try:
                    repaired = re.sub(r",\s*([\]}])", r"\1", match.group(0))
                    res = json.loads(repaired)
                    if isinstance(res, dict):
                        return res
                except Exception:
                    pass
    return {}


parse_json_or_repair = safe_parse_json


def process_structured_meeting_json(
    json_data: Any,
    model_name: str,
    raw_response: str = ""
) -> Dict[str, Any]:
    """Converts the structured JSON meeting model into the unified session data dictionary."""
    json_data = safe_parse_json(json_data)
    title = json_data.get("title", "Meeting Intelligence")
    meeting_date = json_data.get("meeting_date", datetime.now().strftime("%Y-%m-%d"))
    duration_minutes = json_data.get("duration_minutes")
    participants = json_data.get("participants", [])
    if not isinstance(participants, list):
        participants = []
    tags = json_data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tldr = json_data.get("tldr", "")
    
    sections = json_data.get("sections", [])
    if not isinstance(sections, list):
        sections = []
    open_questions = json_data.get("open_questions", [])
    if not isinstance(open_questions, list):
        open_questions = []
    ai_suggestions = json_data.get("ai_suggestions", [])
    mindmap_obj = json_data.get("mindmap", {})

    # 1. Executive Brief (derived from TLDR)
    exec_brief = [s.strip() for s in tldr.split(". ") if s.strip()] if isinstance(tldr, str) else []

    # 2. Numbered Topics & Action Items
    numbered_topics = []
    all_action_items = []
    all_decisions = []

    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        n = sec.get("n", idx + 1)
        sec_title = sec.get("title", f"Section {n}")
        sec_narrative = sec.get("narrative", "")
        sec_decisions = sec.get("decisions", [])
        if isinstance(sec_decisions, list):
            all_decisions.extend(sec_decisions)
        else:
            sec_decisions = []

        sec_actions = []
        raw_actions = sec.get("action_items", [])
        if isinstance(raw_actions, list):
            for a in raw_actions:
                if not isinstance(a, dict):
                    continue
                task_desc = a.get("task") or a.get("description") or "Deliverable"
                owner = a.get("owner") or a.get("assignee") or "Team"
                due = a.get("due_date") or a.get("due_text") or "Next Sprint"
                due_text = a.get("due_text") or a.get("due_date") or ""
                prio = (a.get("priority") or "MED").upper()
                if "HIGH" in prio or "P0" in prio:
                    prio = "HIGH"
                elif "LOW" in prio or "P2" in prio:
                    prio = "LOW"
                else:
                    prio = "MED"

                act_dict = {
                    "number": len(all_action_items) + 1,
                    "id": a.get("id", f"A{len(all_action_items) + 1}"),
                    "task": task_desc,
                    "description": task_desc,
                    "owner": owner,
                    "assignee": owner,
                    "co_owners": a.get("co_owners", []) if isinstance(a.get("co_owners"), list) else [],
                    "due_date": due,
                    "due_text": due_text,
                    "priority": prio,
                    "context": a.get("context", ""),
                    "blocked_by": a.get("blocked_by"),
                    "status": "pending",
                    "notes": f"Section {n}: {sec_title}"
                }
                sec_actions.append(act_dict)
                all_action_items.append(act_dict)

        topic_entry = {
            "index": n,
            "n": n,
            "title": sec_title,
            "narrative": sec_narrative,
            "decisions": sec_decisions,
            "action_items": sec_actions,
            "details": sec_narrative
        }
        numbered_topics.append(topic_entry)

    # 3. Format AI Suggestions for backwards compatibility
    sugg_dict = {
        "items": [],
        "unresolved": [],
        "gaps": [],
        "recommendations": []
    }
    if isinstance(ai_suggestions, list):
        for s in ai_suggestions:
            if isinstance(s, dict):
                lbl = s.get("label") or s.get("title") or "Suggestion"
                det = s.get("detail") or s.get("body") or ""
            elif isinstance(s, str):
                lbl = "Suggestion"
                det = s
            else:
                continue
            full_txt = f"{lbl}: {det}" if det else lbl
            sugg_dict["items"].append({"label": lbl, "title": lbl, "detail": det, "body": det, "text": full_txt})
            
            if any(k in lbl.lower() for k in ["unresolved", "open", "question", "conflict"]):
                sugg_dict["unresolved"].append(full_txt)
            elif any(k in lbl.lower() for k in ["gap", "missing", "deadline", "owner"]):
                sugg_dict["gaps"].append(full_txt)
            else:
                sugg_dict["recommendations"].append(full_txt)
    elif isinstance(ai_suggestions, dict):
        sugg_dict = ai_suggestions

    # 4. Generate Mermaid Mindmap
    mermaid_mindmap = convert_structured_mindmap_to_mermaid(mindmap_obj, fallback_title=title)

    # 5. Generate Markdown representation
    raw_markdown = convert_structured_json_to_markdown(json_data)

    return {
        "title": title,
        "meeting_date": meeting_date,
        "duration_minutes": duration_minutes,
        "participants": participants,
        "tags": tags,
        "tldr": tldr,
        "sections": numbered_topics,
        "numbered_topics": numbered_topics,
        "discussion_pillars": numbered_topics,
        "action_items": all_action_items,
        "decisions": all_decisions,
        "open_questions": open_questions,
        "ai_suggestions": sugg_dict,
        "raw_suggestions_list": ai_suggestions,
        "mindmap": mindmap_obj,
        "mermaid_mindmap": mermaid_mindmap,
        "executive_brief": exec_brief,
        "raw_markdown": raw_markdown,
        "raw_json": json_data,
        "model_used": model_name
    }


def parse_markdown_to_session_dict(
    raw_markdown: str,
    model_name: str,
    template_type: str = "executive"
) -> Dict[str, Any]:
    """Parses clean Plaud-style markdown report into structured session dictionary (fallback)."""
    
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

    # 2. Numbered Topics & Per-Topic Narratives + Inline Action Items
    numbered_topics = []
    all_action_items = []
    
    topic_sections = re.findall(r"^##\s+(\d+)\.\s*([^\n]+)\n([\s\S]*?)(?=^##\s+|\Z)", raw_markdown, re.MULTILINE)
    
    if topic_sections:
        for num_str, title_str, body_str in topic_sections:
            idx = int(num_str)
            clean_title = title_str.strip()
            
            act_match = re.search(r"### Action Items\s*([\s\S]*?)(?=\n###|\n---|\Z)", body_str, re.IGNORECASE)
            if act_match:
                narrative_part = body_str[:act_match.start()].strip()
                actions_part = act_match.group(1).strip()
            else:
                narrative_part = body_str.strip()
                actions_part = ""

            narrative_lines = []
            for line in narrative_part.splitlines():
                line = line.strip()
                if not line or line.startswith("---") or line.startswith("#"):
                    continue
                clean_line = re.sub(r"^\*\*(?:Core Topic & Focus|Key Arguments & Perspectives|Key Takeaways & Points|Consensus & Outcome|Context & Objective|Context|Objective|Speaker Perspective|[A-Z][a-z]+'s Perspective)[^\*:]*:\*\*\s*", "", line)
                clean_line = re.sub(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", "", clean_line).strip()
                if clean_line:
                    narrative_lines.append(clean_line)
            
            narrative_text = " ".join(narrative_lines)
            inline_actions = []

            if actions_part:
                for a_line in actions_part.splitlines():
                    a_line = a_line.strip()
                    if not a_line or a_line.startswith("#") or a_line.startswith("---"):
                        continue
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
                            "id": f"A{len(all_action_items) + 1}",
                            "task": desc,
                            "description": desc,
                            "assignee": assignee or "Team",
                            "owner": assignee or "Team",
                            "priority": "HIGH" if any(k in desc.lower() for k in ["high", "urgent", "p0", "soc 2"]) else "MED",
                            "due_date": due or "Next Sprint",
                            "due_text": due or "Next Sprint",
                            "notes": f"Topic {idx}: {clean_title}",
                            "status": "pending"
                        }
                        inline_actions.append(act_obj)
                        all_action_items.append(act_obj)

            numbered_topics.append({
                "index": idx,
                "n": idx,
                "title": clean_title,
                "narrative": narrative_text,
                "action_items": inline_actions,
                "decisions": [],
                "details": narrative_text
            })

    # 3. AI Suggestions Callout Parsing
    ai_suggestions = {
        "items": [],
        "unresolved": [],
        "gaps": [],
        "recommendations": [],
        "raw_text": ""
    }
    sugg_match = re.search(r"##\s*(?:💡\s*)?AI Suggestions\s*([\s\S]*?)(?=\n## |\Z)", raw_markdown, re.IGNORECASE)
    if not sugg_match:
        sugg_match = re.search(r"###\s*(?:💡\s*)?AI Suggestions\s*([\s\S]*?)(?=\n## |\n###|\Z)", raw_markdown, re.IGNORECASE)

    if sugg_match:
        raw_sugg = sugg_match.group(1).strip()
        ai_suggestions["raw_text"] = raw_sugg
        for s_line in raw_sugg.splitlines():
            s_line = s_line.strip().lstrip("> ")
            if not s_line or s_line.startswith("AI has identified") or s_line.startswith("---"):
                continue
            
            m_s = re.match(r"^(?:\d+[\.\)]\s*|[-*•]\s*)?\*\*([^*]+)\*\*[:\s—-]*(.*)$", s_line)
            if m_s:
                s_title = m_s.group(1).strip()
                s_body = m_s.group(2).strip()
                full_desc = f"{s_title}: {s_body}" if s_body else s_title
                ai_suggestions["items"].append({"label": s_title, "title": s_title, "detail": s_body, "body": s_body, "text": full_desc})
                
                if "unresolved" in s_title.lower() or "conflict" in s_title.lower():
                    ai_suggestions["unresolved"].append(full_desc)
                elif "gap" in s_title.lower() or "missing" in s_title.lower() or "deadline" in s_title.lower() or "owner" in s_title.lower():
                    ai_suggestions["gaps"].append(full_desc)
                else:
                    ai_suggestions["recommendations"].append(full_desc)

    title_match = re.search(r"#\s*(.*?)(?=\n|\Z)", raw_markdown)
    meeting_title = title_match.group(1).strip() if title_match and title_match.group(1).strip() else "Meeting Intelligence"

    parsed_result = {
        "title": meeting_title,
        "template_type": template_type,
        "executive_brief": exec_brief,
        "discussion_pillars": numbered_topics,
        "numbered_topics": numbered_topics,
        "sections": numbered_topics,
        "action_items": all_action_items,
        "ai_suggestions": ai_suggestions,
        "decisions": [],
        "open_questions": [],
        "reversals": [],
        "raw_markdown": raw_markdown,
        "model_used": model_name
    }

    parsed_result["mermaid_mindmap"] = build_contextual_mindmap(parsed_result, meeting_title)
    return parsed_result


def extract_intelligence_gemini(
    topic: str,
    transcript_text: str,
    duration_str: str,
    model_name: str = DEFAULT_GEMINI_MODEL,
    template_type: str = "executive",
    gemini_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Extracts meeting record adhering strictly to the structured JSON schema using Gemini with Groq fallback."""
    client = get_gemini_client(api_key=gemini_api_key)
    groq_client = get_groq_client(api_key=groq_api_key)
    meeting_date_iso = datetime.now().strftime("%Y-%m-%d")
    prompt = build_intelligence_prompt(topic, transcript_text, duration_str, meeting_date_iso=meeting_date_iso, template_type=template_type)

    resp_text = None
    used_model = model_name
    candidates = [model_name] + [m for m in MODEL_CANDIDATES if m != model_name]

    # 1. Try Gemini with JSON response schema
    if client:
        for candidate in candidates:
            try:
                print(f"[*] Calling Gemini ({candidate}) for Structured Meeting Intelligence...", flush=True)
                resp = client.models.generate_content(
                    model=candidate,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.15,
                        max_output_tokens=6000,
                        response_mime_type="application/json"
                    )
                )
                if resp and resp.text:
                    resp_text = resp.text.strip()
                    used_model = f"Gemini ({candidate})"
                    break
            except Exception as e:
                print(f"[!] Gemini Model {candidate} Error: {e}", flush=True)
                continue

    # 2. Fallback to Groq LPU with JSON mode
    if not resp_text and groq_client:
        groq_models = ["qwen/qwen3.6-27b", "openai/gpt-oss-120b", "groq/compound"]
        for g_model in groq_models:
            try:
                print(f"[*] Calling Groq LPU ({g_model}) for Structured Meeting Intelligence...", flush=True)
                g_resp = groq_client.chat.completions.create(
                    model=g_model,
                    messages=[
                        {"role": "system", "content": "You are an expert meeting analyst producing a structured JSON record of a recorded meeting. Return ONE valid JSON object and nothing else."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=6000,
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

    parsed_json = safe_parse_json(resp_text)
    if isinstance(parsed_json, dict) and parsed_json and ("sections" in parsed_json or "discussion_pillars" in parsed_json or "title" in parsed_json):
        return process_structured_meeting_json(parsed_json, used_model, raw_response=resp_text)
    else:
        parsed_md = parse_markdown_to_session_dict(resp_text, used_model, template_type=template_type)
        if isinstance(parsed_md, dict):
            return parsed_md
        return process_structured_meeting_json({}, used_model, raw_response=resp_text)


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
# 4. PRINTABLE HTML / PDF EXPORT GENERATOR & MARKMAP BUILDER
# =============================================================================
def generate_detailed_markmap_md(session_data: Any) -> str:
    """Dynamically builds deep hierarchical markdown for Markmap strictly from sections and action items, never using stale mindmap JSON."""
    session_data = safe_parse_json(session_data)
    # Use title or summary title
    title = session_data.get("title") or session_data.get("meeting_title") or "Meeting Summary"
    clean_title = re.sub(r"^#+\s*", "", str(title)).strip() or "Meeting Summary"
    lines = [f"# {clean_title}"]
    
    sections = session_data.get("sections") or []
    if not sections or not isinstance(sections, list):
        sections = session_data.get("numbered_topics", []) or session_data.get("discussion_pillars", [])
    if not isinstance(sections, list):
        sections = []
        
    has_section_actions = False
    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        n = sec.get("n", "") or sec.get("index", "") or idx + 1
        t = sec.get("title", "")
        clean_t = re.sub(r"^\d+\.\s*", "", str(t)).strip()
        header = f"## {n}. {clean_t}" if n else f"## {clean_t}"
        lines.append(header)
        
        # Narrative branch
        narrative = (sec.get("narrative") or sec.get("details") or "")
        if isinstance(narrative, str) and narrative.strip():
            clean_narrative = re.sub(r"^\*\*[^*]+:\*\*\s*", "", narrative.strip())
            clean_narrative = re.sub(r"^[-*•]\s*", "", clean_narrative)
            # Flatten multi-line text into a single line for Markmap
            clean_narrative = " ".join(clean_narrative.split())
            if clean_narrative:
                lines.append(f"- {clean_narrative}")
            
        # Action Items branch with individual task leaves
        action_items = sec.get("action_items") or []
        if isinstance(action_items, list) and action_items:
            valid_actions = [a for a in action_items if isinstance(a, dict)]
            if valid_actions:
                has_section_actions = True
                lines.append("- Action Items")
                for item in valid_actions:
                    task = str(item.get("task") or item.get("description") or "").strip()
                    owner = str(item.get("owner") or item.get("assignee") or "Unassigned").strip()
                    due_val = item.get("due_date") or item.get("due_text")
                    due = f" -- {due_val}" if due_val and str(due_val).strip() != "—" else ""
                    if task:
                        lines.append(f"  - {task} -- {owner}{due}")

    # Fallback to top-level action_items if not inside sections
    top_actions = session_data.get("action_items", [])
    if not has_section_actions and isinstance(top_actions, list) and top_actions:
        lines.append("## Action Items")
        for item in top_actions:
            if isinstance(item, dict):
                task = str(item.get("task") or item.get("description") or "").strip()
                owner = str(item.get("owner") or item.get("assignee") or "Unassigned").strip()
                due_val = item.get("due_date") or item.get("due_text")
                due = f" -- {due_val}" if due_val and str(due_val).strip() != "—" else ""
                if task:
                    lines.append(f"- {task} -- {owner}{due}")
            elif isinstance(item, str) and item.strip():
                lines.append(f"- {item.strip()}")
                
    ai_suggestions = session_data.get("ai_suggestions") or session_data.get("raw_suggestions_list") or []
    if ai_suggestions:
        lines.append("## AI Suggestions")
        if isinstance(ai_suggestions, list):
            for item in ai_suggestions:
                if isinstance(item, dict):
                    lbl = str(item.get("label") or item.get("title") or "Suggestion").strip()
                    det = str(item.get("detail") or item.get("body") or "").strip()
                    lines.append(f"- **{lbl}**: {det}")
                elif isinstance(item, str) and item.strip():
                    lines.append(f"- {item.strip()}")
        elif isinstance(ai_suggestions, dict):
            items_list = ai_suggestions.get("items", [])
            if isinstance(items_list, list) and items_list:
                for item in items_list:
                    if isinstance(item, dict):
                        lbl = str(item.get("label") or item.get("title") or "Suggestion").strip()
                        det = str(item.get("detail") or item.get("body") or "").strip()
                        lines.append(f"- **{lbl}**: {det}")
                    elif isinstance(item, str) and item.strip():
                        lines.append(f"- {item.strip()}")
            else:
                combined = ai_suggestions.get("unresolved", []) + ai_suggestions.get("gaps", []) + ai_suggestions.get("recommendations", [])
                for item in combined:
                    lines.append(f"- {item}")
            
    return "\n".join(lines)


build_markmap_md = generate_detailed_markmap_md


def generate_printable_html(session_data: Any, active_theme: str = "light") -> str:
    """Generates a standalone, calm professional HTML document with embedded Markmap and design tokens."""
    from styles.theme import get_iframe_theme_css, format_acronyms

    session_data = safe_parse_json(session_data)
    meta = session_data.get("metadata", {})
    if not isinstance(meta, dict):
        meta = {}

    title = session_data.get("title") or meta.get("source_file", "Meeting Intelligence Report")
    clean_title = format_acronyms(re.sub(r"^#+\s*", "", str(title)).strip())
    duration = meta.get("duration", "N/A")
    date_str = session_data.get("meeting_date") or meta.get("processed_at", datetime.now().strftime("%Y-%m-%d"))
    model_str = session_data.get("model_used") or meta.get("model", "Hesh-rec AI")
    
    participants = session_data.get("participants", [])
    if not isinstance(participants, list):
        participants = []
    if not participants and meta.get("speakers"):
        raw_spk = meta.get("speakers")
        participants = [raw_spk] if isinstance(raw_spk, str) else list(raw_spk)

    raw_tags = session_data.get("tags", [])
    tags = [format_acronyms(str(t)) for t in raw_tags] if isinstance(raw_tags, list) else []
    tldr = session_data.get("tldr", "")
    topics = session_data.get("sections", []) or session_data.get("numbered_topics", []) or session_data.get("discussion_pillars", [])
    if not isinstance(topics, list):
        topics = []
    open_questions = session_data.get("open_questions", [])
    ai_suggestions = session_data.get("ai_suggestions", {}) or session_data.get("raw_suggestions_list", [])

    meta_pills = []
    if date_str:
        meta_pills.append(f"""<span class="meta-pill">Date: <span class="mono">{date_str}</span></span>""")
    if duration and duration != "N/A":
        meta_pills.append(f"""<span class="meta-pill">Duration: <span class="mono">{duration}</span></span>""")
    if participants:
        meta_pills.append(f"""<span class="meta-pill">Participants: {', '.join([str(p) for p in participants])}</span>""")
    for t in tags:
        clean_tag = t.lstrip("#")
        meta_pills.append(f"""<span class="meta-pill">#{clean_tag}</span>""")

    meta_row = f"""<div class="meta-row">{''.join(meta_pills)}</div>""" if meta_pills else ""

    tldr_html = ""
    if tldr:
        tldr_html = f"""<div class="editorial-brief"><div class="brief-label">EXECUTIVE BRIEF</div><p class="brief-content">{tldr}</p></div>"""

    # Numbered Topics & Inline Actions
    topics_html = []
    for idx, t in enumerate(topics):
        if not isinstance(t, dict):
            continue
        t_num = t.get("n") or t.get("index", idx + 1)
        t_title = t.get("title", f"Topic {t_num}")
        clean_t_title = format_acronyms(re.sub(r"^\d+\.\s*", "", str(t_title)).strip())
        narrative = t.get("narrative") or t.get("details", "")
        clean_narrative = re.sub(r"^\*\*(?:Core Topic & Focus|Key Arguments & Perspectives|Key Takeaways & Points|Consensus & Outcome|Context & Objective|Context|Objective|Speaker Perspective|[A-Z][a-z]+'s Perspective)[^\*:]*:\*\*\s*", "", str(narrative))
        clean_narrative = re.sub(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", "", clean_narrative)
        clean_narrative = format_acronyms(re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_narrative).strip())

        decisions_html = ""
        dec_list = t.get("decisions", [])
        if isinstance(dec_list, list) and dec_list:
            dec_lis = "".join([f"""<li style="margin-bottom: 4px; color: var(--text-2);">{format_acronyms(str(d))}</li>""" for d in dec_list])
            decisions_html = f"""<div style="margin: 14px 0 18px 0; font-size: 14px;"><strong style="color: var(--text);">Decisions:</strong><ul style="margin: 6px 0 0 20px; padding: 0;">{dec_lis}</ul></div>"""
        
        t_actions = t.get("action_items", [])
        actions_html = ""
        if isinstance(t_actions, list) and t_actions:
            items_li = []
            for a in t_actions:
                if not isinstance(a, dict):
                    continue
                desc = format_acronyms(str(a.get("task") or a.get("description", "")))
                owner = str(a.get("owner") or a.get("assignee", "Team"))
                due = str(a.get("due_date") or a.get("due_text", ""))
                due_badge = f"""<span class="action-due-pill">{due}</span>""" if due and due != "—" else ""
                items_li.append(f"""<div class="action-item-pill"><span class="action-check-pill">☐</span><span class="action-text">{desc}</span><span class="action-owner-pill">{owner}</span>{due_badge}</div>""")
            actions_html = f"""<div class="section-actions"><div class="section-actions-heading">Action Items</div>{''.join(items_li)}</div>"""

        topics_html.append(f"""<div class="section-block"><h2 class="section-title">{t_num}. {clean_t_title}</h2><p>{clean_narrative}</p>{decisions_html}{actions_html}</div>""")

    # Open Questions
    open_q_html = ""
    if isinstance(open_questions, list) and open_questions:
        q_rows = []
        for q in open_questions:
            q_text = format_acronyms(str(q.get("question", "")) if isinstance(q, dict) else str(q))
            q_by = str(q.get("raised_by", "")) if isinstance(q, dict) else ""
            by_str = f" — <em>{q_by}</em>" if q_by else ""
            q_rows.append(f"""<div style="font-size: 14px; margin-bottom: 8px; line-height: 1.6; color: var(--text);"><strong>• {q_text}</strong><span style="font-size: 12.5px; color: var(--text-2);">{by_str}</span></div>""")
        open_q_html = f"""<div class="questions-box"><div class="questions-label">Open Questions</div>{''.join(q_rows)}</div>"""

    # AI Suggestions Callout
    sugg_rows = []
    if isinstance(ai_suggestions, dict):
        s_items = ai_suggestions.get("items", [])
        if isinstance(s_items, list) and s_items:
            for i, it in enumerate(s_items):
                if isinstance(it, dict):
                    sugg_rows.append(f"<div class='ai-suggestion-item'><span class='ai-suggestion-title'>{i+1}. {format_acronyms(str(it.get('label') or it.get('title', f'Suggestion {i+1}')))}</span>: <span>{format_acronyms(str(it.get('detail') or it.get('body', '')))}</span></div>")
                elif isinstance(it, str):
                    sugg_rows.append(f"<div class='ai-suggestion-item'><span class='ai-suggestion-title'>{i+1}. Note</span>: <span>{format_acronyms(it)}</span></div>")
        else:
            combined = ai_suggestions.get("unresolved", []) + ai_suggestions.get("gaps", []) + ai_suggestions.get("recommendations", [])
            for i, txt in enumerate(combined):
                if isinstance(txt, str):
                    sugg_rows.append(f"<div class='ai-suggestion-item'><span class='ai-suggestion-title'>{i+1}. Note</span>: <span>{format_acronyms(txt)}</span></div>")
    elif isinstance(ai_suggestions, list):
        for i, it in enumerate(ai_suggestions):
            if isinstance(it, dict):
                sugg_rows.append(f"<div class='ai-suggestion-item'><span class='ai-suggestion-title'>{i+1}. {format_acronyms(str(it.get('label') or it.get('title', f'Suggestion {i+1}')))}</span>: <span>{format_acronyms(str(it.get('detail') or it.get('body', '')))}</span></div>")
            elif isinstance(it, str):
                sugg_rows.append(f"<div class='ai-suggestion-item'><span class='ai-suggestion-title'>{i+1}. Note</span>: <span>{format_acronyms(it)}</span></div>")

    if sugg_rows:
        suggestions_html = f"""<div class="ai-suggestions"><div class="ai-suggestions-label">AI Suggestions</div><div class="ai-suggestions-desc">The following items were identified as unresolved discussion points or require explicit ownership:</div>{''.join(sugg_rows)}</div>"""
    else:
        suggestions_html = ""

    # Build Markmap Markdown dynamically from sections and action items
    markmap_markdown = generate_detailed_markmap_md(session_data)
    md_json_escaped = json.dumps(markmap_markdown)

    mindmap_html = f"""<div style="margin-top: 48px; margin-bottom: 24px;">
      <h2 class="section-title">Mind Map</h2>
      <div class="mindmap-container">
        <div class="mindmap-controls no-print">
          <button class="control-btn" onclick="window.mm && window.mm.fit()">Fit</button>
          <button class="control-btn" onclick="window.mm && window.mm.rescale(1.25)">Zoom +</button>
          <button class="control-btn" onclick="window.mm && window.mm.rescale(0.8)">Zoom -</button>
        </div>
        <svg id="mindmap"></svg>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
      <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.18"></script>
      <script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.18"></script>
      <script>
        const md = {md_json_escaped};
        const {{ root }} = new markmap.Transformer().transform(md);
        window.mm = markmap.Markmap.create('#mindmap', {{
          autoFit: true,
          fitRatio: 0.95,
          maxWidth: 380,
          initialExpandLevel: 3,
          spacingVertical: 10,
          spacingHorizontal: 80,
          duration: 250,
        }}, root);
        window.addEventListener('resize', () => {{
          if (window.mm) window.mm.fit();
        }});
        setTimeout(() => {{ if (window.mm) window.mm.fit(); }}, 400);
      </script>
    </div>"""

    content = f"""
<div class="document-canvas">
  <div style="display: flex; justify-content: flex-end; margin-bottom: 24px;">
    <button class="no-print btn-ghost" onclick="window.print()">Download PDF</button>
  </div>
  <h1 class="display-title">{clean_title}</h1>
  {meta_row}
  {tldr_html}
  {''.join(topics_html)}
  {open_q_html}
  {suggestions_html}
  {mindmap_html}
</div>
"""

    return f"""<!doctype html>
<html data-theme="{active_theme}">
<head>
  <meta charset="utf-8">
  <style>
{get_iframe_theme_css(active_theme)}
  </style>
</head>
<body>
  {content}
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
    template_type: str = "executive",
    groq_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None
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
    segments, full_text, duration_sec = transcribe_audio_groq(audio_path, api_key=groq_api_key)
    duration_str = format_duration_human(duration_sec)

    # 2. Gemini Analysis
    intel = extract_intelligence_gemini(
        topic=title,
        transcript_text=full_text,
        duration_str=duration_str,
        model_name=model_choice,
        template_type=template_type,
        gemini_api_key=gemini_api_key,
        groq_api_key=groq_api_key
    )
    if not isinstance(intel, dict):
        intel = safe_parse_json(intel)

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
        "transcript": full_text,
        "title": intel.get("title", title),
        "meeting_date": intel.get("meeting_date"),
        "date": intel.get("meeting_date"),
        "duration": duration_str,
        "duration_minutes": intel.get("duration_minutes"),
        "template": template_type,
        "participants": intel.get("participants", []),
        "tags": intel.get("tags", []),
        "tldr": intel.get("tldr", ""),
        "executive_summary": intel.get("tldr", ""),
        "sections": intel.get("sections", []),
        "discussion_pillars": intel.get("discussion_pillars", []) or intel.get("sections", []),
        "executive_brief": intel.get("executive_brief", []),
        "action_items": intel.get("action_items", []),
        "decisions": intel.get("decisions", []),
        "open_questions": intel.get("open_questions", []),
        "ai_suggestions": intel.get("ai_suggestions", {}),
        "strategic_insights": intel.get("ai_suggestions", {}),
        "raw_suggestions_list": intel.get("raw_suggestions_list", []),
        "reversals": intel.get("reversals", []),
        "mermaid_mindmap": intel.get("mermaid_mindmap", ""),
        "mindmap_markdown": generate_detailed_markmap_md(intel),
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


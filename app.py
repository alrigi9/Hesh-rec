# -*- coding: utf-8 -*-
import sys
import os
import re
import io
import json
import time
import base64
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

# Enforce UTF-8 on Windows standard streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from streamlit_mermaid import st_mermaid
from audio_recorder_streamlit import audio_recorder

from core.config import BASE_DIR, INPUTS_DIR, OUTPUTS_DIR, DEFAULT_MODEL, is_supported_media
from cloud_pipeline import (
    process_meeting_file_cloud,
    fetch_all_sessions,
    save_session_record,
    delete_session_record,
    rename_session_record,
    update_session_action_items,
    auth_sign_in,
    auth_sign_up,
    auth_sign_out,
    get_user_usage,
    chat_with_session,
    generate_printable_html,
    get_secret,
    build_contextual_mindmap,
    sanitize_mermaid_node
)

SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
INPUTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# STREAMLIT APPLICATION CONFIGURATION & PERSISTENT SESSION SYSTEM
# =============================================================================
st.set_page_config(
    page_title="Hesh-rec | AI Meeting & Speech Intelligence Platform",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Persistent Session Helpers (Preserves login on Page Refresh / F5 via query_params)
def save_persistent_session(user_id: str, email: str, plan_tier: str = "free", is_vip: bool = False, is_admin: bool = False):
    """Encodes and stores active session in URL query params so refresh doesn't log out user."""
    try:
        data = {
            "id": str(user_id),
            "email": str(email),
            "tier": str(plan_tier),
            "vip": bool(is_vip),
            "admin": bool(is_admin)
        }
        token = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
        st.query_params["session"] = token
    except Exception:
        pass


def restore_persistent_session():
    """Restores user authentication session from URL query params upon page load or F5."""
    if "session" in st.query_params and st.session_state.get("user") is None:
        try:
            token = st.query_params["session"]
            decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            data = json.loads(decoded)
            user_id = data.get("id", "user")
            email = data.get("email", "")
            plan_tier = data.get("tier", "free")
            is_vip = bool(data.get("vip", False))
            is_admin = bool(data.get("admin", False))

            if email:
                st.session_state.user = type("PersistentUser", (), {
                    "id": user_id,
                    "email": email,
                    "display_name": "Hesham (Admin)" if is_admin else email
                })()
                st.session_state.user_email = email
                st.session_state.plan_tier = plan_tier
                st.session_state.is_vip = is_vip
                st.session_state.is_admin = is_admin
        except Exception:
            pass


def clear_persistent_session():
    """Clears persistent session tokens upon manual sign out."""
    try:
        if "session" in st.query_params:
            del st.query_params["session"]
    except Exception:
        pass


# Initialize Session State
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "current_nav" not in st.session_state:
    st.session_state.current_nav = "dashboard"
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "model_choice" not in st.session_state:
    st.session_state.model_choice = "gemini-2.5-flash"
if "template_choice" not in st.session_state:
    st.session_state.template_choice = "executive"
if "rename_target" not in st.session_state:
    st.session_state.rename_target = None
if "user" not in st.session_state:
    st.session_state.user = None
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "plan_tier" not in st.session_state:
    st.session_state.plan_tier = "free"
if "is_vip" not in st.session_state:
    st.session_state.is_vip = False
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = {}

# Restore session if available in query params
restore_persistent_session()

from styles.theme import inject_theme, format_acronyms, get_iframe_theme_css

# Inject single source of truth design system
inject_theme(st.session_state.get("theme", "light"))



# =============================================================================
# DATA HELPERS & PARSERS
# =============================================================================
def get_current_user_id() -> str | None:
    if st.session_state.user:
        return str(getattr(st.session_state.user, "id", ""))
    return None


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


def generate_unified_document_html(session_data: Any, meta: Optional[Dict[str, Any]] = None, active_theme: str = "light") -> str:
    """
    Builds ONE self-contained HTML document string with active theme and print styling containing:
    - Theme & print CSS from styles.theme in <head>
    - Ghost Download PDF action bar
    - Title, Metadata pills, TL;DR
    - Numbered Sections with 78ch narrative & inline Action Items
    - AI Suggestions callout box
    - Embedded Interactive D3 Markmap Tree
    """
    session_data = safe_parse_json(session_data)
    if meta is None:
        meta = session_data.get("metadata", {})
    if not isinstance(meta, dict):
        meta = {}

    doc_title = session_data.get("title") or meta.get("source_file", "Meeting Summary")
    clean_title = format_acronyms(re.sub(r"^#+\s*", "", str(doc_title)).strip())

    meeting_date = session_data.get("meeting_date") or meta.get("processed_at", "")
    duration_str = meta.get("duration", "")
    if not duration_str and session_data.get("duration_minutes"):
        duration_str = f"{session_data.get('duration_minutes')} min"

    participants = session_data.get("participants", [])
    if not isinstance(participants, list):
        participants = []
    if not participants and meta.get("speakers"):
        raw_spk = meta.get("speakers")
        participants = [raw_spk] if isinstance(raw_spk, str) else list(raw_spk)

    raw_tags = session_data.get("tags", [])
    tags = [format_acronyms(str(t)) for t in raw_tags] if isinstance(raw_tags, list) else []
    tldr = session_data.get("tldr", "")
    sections = session_data.get("sections", []) or session_data.get("numbered_topics", []) or session_data.get("discussion_pillars", [])
    if not isinstance(sections, list):
        sections = []
    open_questions = session_data.get("open_questions", [])
    ai_suggestions = session_data.get("ai_suggestions", {}) or session_data.get("raw_suggestions_list", [])

    # Metadata Pills Row
    meta_pills = []
    if meeting_date:
        meta_pills.append(f"""<span class="meta-pill">Date: <span class="mono">{meeting_date}</span></span>""")
    if duration_str:
        meta_pills.append(f"""<span class="meta-pill">Duration: <span class="mono">{duration_str}</span></span>""")
    if participants:
        meta_pills.append(f"""<span class="meta-pill">Participants: {', '.join([str(p) for p in participants])}</span>""")
    for t in tags:
        clean_tag = t.lstrip("#")
        meta_pills.append(f"""<span class="meta-pill">#{clean_tag}</span>""")

    meta_row = f"""<div class="meta-row">{''.join(meta_pills)}</div>""" if meta_pills else ""

    # TL;DR Executive Summary Box
    tldr_html = ""
    if tldr:
        tldr_html = f"""<div class="tldr-box"><div class="tldr-label">Executive Summary</div><p class="tldr-content">{tldr}</p></div>"""

    # Numbered Sections
    sections_html = []
    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        n = sec.get("n") or sec.get("index", idx + 1)
        raw_sec_title = sec.get("title", f"Topic {n}")
        clean_sec_title = format_acronyms(re.sub(r"^\d+\.\s*", "", str(raw_sec_title)).strip())

        narrative = sec.get("narrative") or sec.get("details", "")
        clean_narrative = re.sub(r"^\*\*(?:Core Topic & Focus|Key Arguments & Perspectives|Key Takeaways & Points|Consensus & Outcome|Context & Objective|Context|Objective|Speaker Perspective|[A-Z][a-z]+'s Perspective)[^\*:]*:\*\*\s*", "", str(narrative))
        clean_narrative = re.sub(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", "", clean_narrative)
        clean_narrative = format_acronyms(re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_narrative).strip())

        # Decisions
        decisions_html = ""
        dec_list = sec.get("decisions", [])
        if isinstance(dec_list, list) and dec_list:
            dec_lis = "".join([f"""<li style="margin-bottom: 4px; color: var(--text-2);">{format_acronyms(str(d))}</li>""" for d in dec_list])
            decisions_html = f"""<div style="margin: 12px 0 16px 0; font-size: 13.5px;"><strong style="color: var(--text);">Decisions:</strong><ul style="margin: 6px 0 0 20px; padding: 0;">{dec_lis}</ul></div>"""

        # Action Items
        actions_html = ""
        actions_list = sec.get("action_items", [])
        if isinstance(actions_list, list) and actions_list:
            act_rows = []
            for a in actions_list:
                if not isinstance(a, dict):
                    continue
                task = format_acronyms(str(a.get("task") or a.get("description") or "Deliverable"))
                owner = str(a.get("owner") or a.get("assignee") or "Team")
                due = str(a.get("due_date") or a.get("due_text") or "")
                due_s = f" {due}" if due and due != "—" else ""
                act_rows.append(f"""<div class="action-row"><span class="action-check">☐</span><span>{task} — <span class="action-owner">{owner}</span><span class="action-due">{due_s}</span></span></div>""")
            actions_html = f"""<div class="section-actions"><div class="section-actions-heading">Action Items</div>{''.join(act_rows)}</div>"""

        sections_html.append(f"""<div class="section-block" style="margin-bottom: 48px;"><h2 class="section-title">{n}. {clean_sec_title}</h2><p>{clean_narrative}</p>{decisions_html}{actions_html}</div>""")

    # Open Questions
    open_q_html = ""
    if isinstance(open_questions, list) and open_questions:
        q_rows = []
        for q in open_questions:
            q_text = format_acronyms(str(q.get("question", "")) if isinstance(q, dict) else str(q))
            q_by = str(q.get("raised_by", "")) if isinstance(q, dict) else ""
            by_str = f" — <em>{q_by}</em>" if q_by else ""
            q_rows.append(f"""<div style="font-size: 14px; margin-bottom: 6px; line-height: 1.6; color: var(--text);"><strong>• {q_text}</strong><span style="font-size: 12.5px; color: var(--text-2);">{by_str}</span></div>""")
        open_q_html = f"""<div class="questions-box"><div class="questions-label">Open Questions</div>{''.join(q_rows)}</div>"""

    # AI Suggestions
    sugg_entries = []
    if isinstance(ai_suggestions, dict):
        s_items = ai_suggestions.get("items", [])
        if isinstance(s_items, list) and s_items:
            for s_idx, item in enumerate(s_items):
                if isinstance(item, dict):
                    s_t = format_acronyms(str(item.get("label") or item.get("title", f"Suggestion {s_idx+1}")))
                    s_b = format_acronyms(str(item.get("detail") or item.get("body", "")))
                    if s_b:
                        sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. {s_t}</span>: <span>{s_b}</span></div>""")
                    else:
                        sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. {s_t}</span></div>""")
                elif isinstance(item, str):
                    sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. Note</span>: <span>{format_acronyms(item)}</span></div>""")
        else:
            combined_suggs = ai_suggestions.get("unresolved", []) + ai_suggestions.get("gaps", []) + ai_suggestions.get("recommendations", [])
            for s_idx, text in enumerate(combined_suggs):
                if isinstance(text, str):
                    if ":" in text:
                        p_t, p_b = text.split(":", 1)
                        sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. {format_acronyms(p_t.strip())}</span>: <span>{format_acronyms(p_b.strip())}</span></div>""")
                    else:
                        sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. Note</span>: <span>{format_acronyms(text)}</span></div>""")
    elif isinstance(ai_suggestions, list):
        for s_idx, item in enumerate(ai_suggestions):
            if isinstance(item, dict):
                s_t = format_acronyms(str(item.get("label") or item.get("title", f"Suggestion {s_idx+1}")))
                s_b = format_acronyms(str(item.get("detail") or item.get("body", "")))
                sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. {s_t}</span>: <span>{s_b}</span></div>""")
            elif isinstance(item, str):
                sugg_entries.append(f"""<div class="ai-suggestion-item"><span class="ai-suggestion-title">{s_idx+1}. Note</span>: <span>{format_acronyms(item)}</span></div>""")

    if sugg_entries:
        ai_suggestions_markup = f"""<div class="ai-suggestions"><div class="ai-suggestions-label">AI Suggestions</div><div class="ai-suggestions-desc">The following items were identified as unresolved discussion points or require explicit ownership:</div>{''.join(sugg_entries)}</div>"""
    else:
        ai_suggestions_markup = ""

    # Build Markmap Markdown dynamically from sections and action items
    markmap_markdown = generate_detailed_markmap_md(session_data)
    md_json_escaped = json.dumps(markmap_markdown)

    # Mind Map Section
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
        setTimeout(() => window.mm && window.mm.fit(), 300);
      </script>
    </div>"""

    content = f"""
  <div style="display: flex; justify-content: flex-end; margin-bottom: 24px;">
    <button class="no-print btn-ghost" onclick="window.print()">Download PDF</button>
  </div>
  <h1 class="display-title">{clean_title}</h1>
  {meta_row}
  {tldr_html}
  {''.join(sections_html)}
  {open_q_html}
  {ai_suggestions_markup}
  {mindmap_html}
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



def extract_smart_tags(title: str, session_data: dict) -> list[str]:
    tags = []
    text_corpus = (title + " " + json.dumps(session_data)).lower()
    if any(k in text_corpus for k in ["soc 2", "compliance", "security", "audit", "policy"]):
        tags.append("#Compliance")
    if any(k in text_corpus for k in ["sprint", "roadmap", "engineering", "deploy", "server", "azure", "docker"]):
        tags.append("#Engineering")
    if any(k in text_corpus for k in ["lecture", "academic", "theory", "concept", "exam", "student"]):
        tags.append("#Academic")
    if any(k in text_corpus for k in ["marketing", "growth", "campaign", "leads", "sales"]):
        tags.append("#Growth")
    if any(k in text_corpus for k in ["brainstorm", "ideation", "design", "creative"]):
        tags.append("#Ideation")

    if not tags:
        tags.append("#Meeting")
    return tags[:3]


def parse_transcript_turns(raw_markdown: str) -> list[dict]:
    turns = []
    t_match = re.search(r"## 🗣️.*?(?:\n)(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    content = t_match.group(1) if t_match else raw_markdown

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*?):\s*(.*)$", line)
        if m:
            ts = m.group(1).strip()
            spk = m.group(2).strip().strip("*_:")
            txt = m.group(3).strip()
            sec = 0.0
            try:
                parts = [float(p) for p in ts.split(":")]
                if len(parts) == 3:
                    sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                elif len(parts) == 2:
                    sec = parts[0] * 60 + parts[1]
            except Exception:
                pass
            turns.append({"time": ts, "speaker": spk, "text": txt, "seconds": sec})
    return turns


def load_user_sessions() -> list[dict]:
    """Loads all sessions strictly belonging to the active user (or demo for guests)."""
    user_id = get_current_user_id()
    raw_sessions = fetch_all_sessions(user_id=user_id)
    sessions = []
    seen_keys = set()

    for s in raw_sessions:
        sid = s["id"]
        data = s.get("data", {})
        clean_title = s.get("title", f"Meeting {sid}")

        dedup_key = clean_title.lower()
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        proc_date = s.get("processed_at", "")
        duration = s.get("duration", "N/A")
        tags = extract_smart_tags(clean_title, data)
        action_items = data.get("action_items", [])
        decisions = data.get("decisions", [])
        pillars = data.get("discussion_pillars", [])

        sessions.append({
            "id": sid if sid.startswith("session_") else f"session_{sid}",
            "raw_id": sid,
            "title": clean_title,
            "date_display": proc_date,
            "duration": duration,
            "tags": tags,
            "action_count": len(action_items),
            "decision_count": len(decisions),
            "pillar_count": len(pillars),
            "template_type": data.get("metadata", {}).get("template_type", "executive"),
            "source": s.get("source", "Cloud"),
            "data": data
        })

    return sessions


# =============================================================================
# MODALS & DIALOGS
# =============================================================================
# DIALOGS & MODALS
# =============================================================================
@st.dialog("New Recording")
def new_recording_dialog():
    user_id = get_current_user_id()
    usage = get_user_usage(user_id, plan_tier=st.session_state.plan_tier)

    if not usage["can_upload"]:
        st.error("Monthly limit reached. Please upgrade to Pro in the sidebar for unlimited processing.")
        return

    tab_upload, tab_voice = st.tabs(["Upload Audio", "Voice Memo"])

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Upload file",
            type=["mp3", "wav", "m4a", "mp4", "aac", "ogg", "flac"],
            label_visibility="collapsed"
        )

        col_t1, col_t2 = st.columns([1.2, 1.2])
        with col_t1:
            template_mode = st.selectbox(
                "Summary Template",
                ["Executive Meeting", "Academic Lecture", "Brainstorm & Ideation"],
                index=0
            )
        with col_t2:
            model_mode = st.selectbox(
                "Intelligence Engine",
                ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
                index=0
            )

        tpl_key = "executive"
        if "Academic" in template_mode:
            tpl_key = "academic"
        elif "Brainstorm" in template_mode:
            tpl_key = "brainstorm"

        if uploaded_file is not None:
            if st.button("Transcribe & Analyze", type="primary", use_container_width=True):
                save_path = INPUTS_DIR / uploaded_file.name
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                with st.spinner("Processing audio with Groq Whisper and Gemini..."):
                    try:
                        result = process_meeting_file_cloud(
                            save_path,
                            model_choice=model_mode,
                            user_id=user_id,
                            template_type=tpl_key
                        )
                        sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                        st.session_state.active_session_id = f"session_{sid}"
                        st.toast("Meeting synchronized to workspace.")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Processing failed: {ex}")

    with tab_voice:
        st.markdown("<div style='font-size: 13px; color: var(--text-2); margin-bottom: 12px;'>Record voice notes directly from your browser microphone:</div>", unsafe_allow_html=True)
        col_rec_btn, col_rec_action = st.columns([1.0, 1.4])
        with col_rec_btn:
            recorded_bytes = audio_recorder(
                pause_threshold=2.5,
                text="Record Memo",
                recording_color="#c0392b",
                neutral_color="#5b616e",
                icon_size="2x"
            )
        with col_rec_action:
            if recorded_bytes:
                st.audio(recorded_bytes, format="audio/wav")
                if st.button("Process Voice Memo", type="primary", use_container_width=True):
                    memo_filename = f"voice_memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    memo_path = INPUTS_DIR / memo_filename
                    with open(memo_path, "wb") as f:
                        f.write(recorded_bytes)
                    with st.spinner("Transcribing voice recording..."):
                        try:
                            result = process_meeting_file_cloud(
                                memo_path,
                                custom_title="Voice Memo Recording",
                                model_choice=st.session_state.model_choice,
                                user_id=user_id,
                                template_type="executive"
                            )
                            sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                            st.session_state.active_session_id = f"session_{sid}"
                            st.toast("Voice memo transcribed.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Analysis failed: {ex}")


@st.dialog("Rename Meeting")
def rename_meeting_dialog(session_id: str, current_title: str):
    new_title = st.text_input("Meeting Title", value=current_title)
    col_cnl, col_sav = st.columns([1.0, 1.0])
    with col_cnl:
        if st.button("Cancel", type="secondary", use_container_width=True):
            st.session_state.rename_target = None
            st.rerun()
    with col_sav:
        if st.button("Save Title", type="primary", use_container_width=True):
            if new_title.strip():
                try:
                    user_id = get_current_user_id()
                    rename_session_record(session_id, new_title.strip(), user_id=user_id)
                    st.toast("Title updated.")
                    st.session_state.rename_target = None
                    time.sleep(0.3)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to rename: {e}")


# =============================================================================
# SIDEBAR NAVIGATION & AUTHENTICATION
# =============================================================================
def render_sidebar():
    with st.sidebar:
        # App Branding Header
        st.markdown("""
        <div style="margin-bottom: 24px; padding-left: 2px;">
            <div style="font-weight: 650; font-size: 15px; color: var(--text); letter-spacing: -0.01em;">
                Hesh Rec <span class="mono" style="font-size: 11px; color: var(--text-3); font-weight: 500; margin-left: 4px;">v2.4</span>
            </div>
            <div style="font-size: 11.5px; color: var(--text-2); margin-top: 2px;">Speech Intelligence Studio</div>
        </div>
        """, unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 1. USER AUTHENTICATION & MULTI-TENANCY PANEL
        # ---------------------------------------------------------------------
        if st.session_state.user:
            user_email = st.session_state.user.email if hasattr(st.session_state.user, "email") else st.session_state.user_email
            display_name = user_email[:20] if user_email else "User"

            if st.session_state.get("is_admin", False):
                plan_pill = '<span class="pill">Admin</span>'
            elif st.session_state.get("is_vip", False):
                plan_pill = '<span class="pill">Pro VIP</span>'
            elif st.session_state.plan_tier == "pro":
                plan_pill = '<span class="pill">Pro</span>'
            else:
                plan_pill = '<span class="pill">Free</span>'

            st.markdown(f"""
            <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                    <span style="font-size: 13px; font-weight: 600; color: var(--text);">{display_name}</span>
                    {plan_pill}
                </div>
                <div style="font-size: 11px; color: var(--text-3);">Tenant Cloud Isolated</div>
            </div>
            """, unsafe_allow_html=True)

            # Promo Code Redeemer for Logged In User
            if not st.session_state.get("is_vip", False) and st.session_state.plan_tier == "free":
                st.markdown("<div style='font-size: 11px; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;'>Redeem Code</div>", unsafe_allow_html=True)
                col_code, col_redeem = st.columns([1.5, 1.0])
                with col_code:
                    promo_input = st.text_input("Promo Code", key="input_promo_code", placeholder="Code (e.g. Hesh)", label_visibility="collapsed")
                with col_redeem:
                    if st.button("Redeem", key="btn_redeem_promo", type="secondary", use_container_width=True):
                        if promo_input.strip().lower() in ["hesh", "alrigi"]:
                            st.session_state.plan_tier = "pro"
                            st.session_state.is_vip = True
                            save_persistent_session(get_current_user_id() or "vip_user", st.session_state.user_email, "pro", True, st.session_state.get("is_admin", False))
                            st.toast("Pro plan activated.")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error("Invalid code.")

            if st.button("Sign Out", key="btn_signout", type="secondary", use_container_width=True):
                auth_sign_out()
                clear_persistent_session()
                st.session_state.user = None
                st.session_state.user_email = ""
                st.session_state.plan_tier = "free"
                st.session_state.is_vip = False
                st.session_state.is_admin = False
                st.session_state.active_session_id = None
                st.toast("Signed out.")
                time.sleep(0.3)
                st.rerun()

        else:
            st.markdown("<div style='font-size: 11.5px; font-weight: 600; color: var(--text-2); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em;'>Account</div>", unsafe_allow_html=True)
            auth_tab_in, auth_tab_up, auth_tab_promo = st.tabs(["Sign In", "Register", "Promo"])

            with auth_tab_in:
                login_email = st.text_input("Email / Username", key="in_email", placeholder="user@company.com")
                login_pwd = st.text_input("Password", type="password", key="in_pwd")
                if st.button("Sign In", type="primary", use_container_width=True):
                    if login_email and login_pwd:
                        clean_u = login_email.strip().lower()
                        clean_p = login_pwd.strip().lower()
                        if clean_u in ["hesh", "hesham", "alrigi", "hesh@heshrec.ai"] and clean_p == "alrigi":
                            st.session_state.user = type("AdminUser", (), {
                                "id": "hesh_admin",
                                "email": "hesh@heshrec.ai",
                                "display_name": "Hesham (Admin)"
                            })()
                            st.session_state.user_email = "hesh@heshrec.ai"
                            st.session_state.plan_tier = "pro"
                            st.session_state.is_vip = True
                            st.session_state.is_admin = True
                            save_persistent_session("hesh_admin", "hesh@heshrec.ai", "pro", True, True)
                            st.toast("Welcome back, Hesham.")
                            time.sleep(0.3)
                            st.rerun()
                        else:
                            with st.spinner("Authenticating..."):
                                success, user_obj, msg = auth_sign_in(login_email, login_pwd)
                                if success:
                                    st.session_state.user = user_obj
                                    st.session_state.user_email = login_email
                                    uid = getattr(user_obj, "id", login_email)
                                    save_persistent_session(uid, login_email, "free", False, False)
                                    st.toast("Welcome back.")
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        st.warning("Please provide login credentials.")

            with auth_tab_up:
                up_email = st.text_input("Email", key="up_email", placeholder="newuser@company.com")
                up_pwd = st.text_input("Password", type="password", key="up_pwd")
                if st.button("Create Account", type="primary", use_container_width=True):
                    if up_email and up_pwd:
                        with st.spinner("Creating account..."):
                            success, user_obj, msg = auth_sign_up(up_email, up_pwd)
                            if success:
                                st.session_state.user = user_obj
                                st.session_state.user_email = up_email
                                uid = getattr(user_obj, "id", up_email)
                                save_persistent_session(uid, up_email, "free", False, False)
                                st.toast("Account created.")
                                time.sleep(0.3)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.warning("Please provide valid details.")

            with auth_tab_promo:
                st.markdown("<div style='font-size: 12px; color: var(--text-2); margin-bottom: 8px;'>Enter Promo Code:</div>", unsafe_allow_html=True)
                guest_promo = st.text_input("Promo Code", key="guest_promo_input", placeholder="Code (e.g. Hesh)", label_visibility="collapsed")
                if st.button("Redeem Access", key="btn_guest_redeem", type="primary", use_container_width=True):
                    if guest_promo.strip().lower() in ["hesh", "alrigi"]:
                        st.session_state.user_email = "vip_guest@heshrec.ai"
                        st.session_state.user = type("VIPUser", (), {"id": "vip_guest", "email": "vip_guest@heshrec.ai"})()
                        st.session_state.plan_tier = "pro"
                        st.session_state.is_vip = True
                        save_persistent_session("vip_guest", "vip_guest@heshrec.ai", "pro", True, False)
                        st.toast("Pro plan activated.")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error("Invalid promo code.")

        st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 16px 0;'>", unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 2. PRIMARY ACTION & WORKSPACE NAVIGATION
        # ---------------------------------------------------------------------
        if st.session_state.user:
            # Single filled accent button in app
            if st.button("New Session", type="primary", use_container_width=True):
                new_recording_dialog()

            st.markdown("<div style='font-size: 11px; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 20px; margin-bottom: 6px; padding-left: 2px;'>Navigation</div>", unsafe_allow_html=True)

            is_dash_active = st.session_state.current_nav == "dashboard" and st.session_state.active_session_id is None
            if st.button("Dashboard", key="nav_btn_dash", use_container_width=True, type="primary" if is_dash_active else "secondary"):
                st.session_state.current_nav = "dashboard"
                st.session_state.active_session_id = None
                st.rerun()

            is_recents_active = st.session_state.current_nav == "recents" and st.session_state.active_session_id is None
            if st.button("Recent Summaries", key="nav_btn_recents", use_container_width=True, type="primary" if is_recents_active else "secondary"):
                st.session_state.current_nav = "recents"
                st.session_state.active_session_id = None
                st.rerun()

            is_actions_active = st.session_state.current_nav == "actions" and st.session_state.active_session_id is None
            if st.button("Action Items", key="nav_btn_actions", use_container_width=True, type="primary" if is_actions_active else "secondary"):
                st.session_state.current_nav = "actions"
                st.session_state.active_session_id = None
                st.rerun()

            is_export_active = st.session_state.current_nav == "export" and st.session_state.active_session_id is None
            if st.button("Export Center", key="nav_btn_export", use_container_width=True, type="primary" if is_export_active else "secondary"):
                st.session_state.current_nav = "export"
                st.session_state.active_session_id = None
                st.rerun()

            # -----------------------------------------------------------------
            # 3. PAST SESSIONS HISTORY LIST (REAL CSS ELLIPSIS)
            # -----------------------------------------------------------------
            sessions = load_user_sessions()
            if sessions:
                st.markdown("<div style='font-size: 11px; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 24px; margin-bottom: 6px; padding-left: 2px;'>Past Sessions</div>", unsafe_allow_html=True)
                for s in sessions[:5]:
                    is_sess_active = st.session_state.active_session_id == s["id"]
                    btn_type = "primary" if is_sess_active else "secondary"
                    clean_s_title = format_acronyms(s["title"])
                    short_title = clean_s_title[:24] + "..." if len(clean_s_title) > 24 else clean_s_title
                    if st.button(short_title, key=f"side_sess_{s['id']}", use_container_width=True, type=btn_type):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()

            st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 16px 0;'>", unsafe_allow_html=True)

            # -----------------------------------------------------------------
            # 4. FREEMIUM USAGE & QUOTA BAR (ULTRA-SLIM 4PX METER)
            # -----------------------------------------------------------------
            user_id = get_current_user_id()
            usage = get_user_usage(user_id, plan_tier=st.session_state.plan_tier)

            if not st.session_state.get("is_vip", False) and st.session_state.plan_tier == "free":
                used_c = usage['used_count']
                limit_c = usage['limit']
                pct = usage['percent']
                st.markdown(f"""
                <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                    <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:500; color:var(--text); margin-bottom:4px;">
                        <span>Monthly Storage</span>
                        <span class="mono">{used_c} / {limit_c} Files</span>
                    </div>
                    <div class="storage-progress">
                        <div class="storage-progress-fill" style="width: {pct}%;"></div>
                    </div>
                    <div style="font-size: 11px; color: var(--text-3); margin-top: 4px;">Free tier limit: {limit_c} files / mo</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("Upgrade to Pro", key="btn_upgrade_pro", type="secondary", use_container_width=True):
                    st.session_state.plan_tier = "pro"
                    save_persistent_session(get_current_user_id() or "user", st.session_state.user_email, "pro", st.session_state.is_vip, st.session_state.get("is_admin", False))
                    st.toast("Upgraded to Pro.")
                    time.sleep(0.3)
                    st.rerun()

            else:
                st.markdown(f"""
                <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 12px; font-weight: 600; color: var(--text);">Storage Quota</span>
                        <span class="pill">Unlimited</span>
                    </div>
                    <div class="storage-progress">
                        <div class="storage-progress-fill" style="width: 100%;"></div>
                    </div>
                    <div style="font-size: 11px; color: var(--text-3); margin-top: 4px;">Cloud sync & priority processing active</div>
                </div>
                """, unsafe_allow_html=True)

        # Theme Switcher
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        theme_label = "Light Theme" if st.session_state.theme == "dark" else "Dark Theme"
        if st.button(theme_label, key="sidebar_theme_toggle", type="secondary", use_container_width=True):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()


# =============================================================================
# GUEST LANDING PAGE (PROTECTED WORKSPACE)
# =============================================================================
def render_landing_page():
    # Hero Section
    st.markdown("""
    <div style="background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 40px 32px; margin-bottom: 32px;">
        <div style="margin-bottom: 12px;">
            <span class="pill">SOC 2 Ready Meeting Intelligence</span>
        </div>
        <h1 class="display-title" style="margin-bottom: 12px; max-width: 800px;">
            Turn audio meetings into structured audit-ready records in seconds.
        </h1>
        <p style="font-size: 15px; color: var(--text-2); line-height: 1.65; max-width: 720px; margin-bottom: 24px;">
            Hesh Rec pairs low-latency transcription via Groq Whisper with deterministic intelligence extraction via Gemini. Generate clean executive briefs, numbered topic narratives, inline action item matrices, and interactive mind maps.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_demo, col_auth = st.columns([1.2, 1.2])
    with col_demo:
        st.markdown("<div style='font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 8px;'>Interactive Demo Workspace</div>", unsafe_allow_html=True)
        if st.button("Explore Sample Workspace", type="primary", use_container_width=True):
            st.session_state.user_email = "guest_demo@heshrec.ai"
            st.session_state.current_nav = "dashboard"
            st.session_state.user = type("GuestUser", (), {"id": "guest_demo", "email": "guest_demo@heshrec.ai"})()
            save_persistent_session("guest_demo", "guest_demo@heshrec.ai", "free", False, False)
            st.rerun()

    with col_auth:
        st.markdown("<div style='font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 8px;'>Workspace Access</div>", unsafe_allow_html=True)
        st.info("Sign In or Register in the sidebar to access your private workspace and upload audio.")

    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)

    # 3 Core Template Showcases
    st.markdown("<h2 class='section-title' style='margin-top: 0;'>Summary Templates</h2>", unsafe_allow_html=True)
    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.markdown("""
        <div class="card-flat">
            <div style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 6px;">Executive Meeting</div>
            <div style="font-size: 13px; color: var(--text-2); line-height: 1.6;">
                Captures strategic context, numbered discussion pillars, strict action item matrices with explicit owners, and approved decisions.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_t2:
        st.markdown("""
        <div class="card-flat">
            <div style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 6px;">Academic Lecture</div>
            <div style="font-size: 13px; color: var(--text-2); line-height: 1.6;">
                Extracts core lecture thesis, foundational theoretical concepts, glossary of technical definitions, and review questions.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_t3:
        st.markdown("""
        <div class="card-flat">
            <div style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 6px;">Brainstorm & Ideation</div>
            <div style="font-size: 13px; color: var(--text-2); line-height: 1.6;">
                Documents creative insights, exploratory tracks, feasibility assessment notes, and immediate experiment deliverables.
            </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# VIEW 1: DASHBOARD
# =============================================================================
def render_dashboard_view():
    sessions = load_user_sessions()
    user_id = get_current_user_id()
    usage = get_user_usage(user_id, plan_tier=st.session_state.plan_tier)

    total_duration_mins = sum([int(float(s["data"].get("metadata", {}).get("duration_seconds", 900)) / 60.0) for s in sessions])
    total_actions = sum([s["action_count"] for s in sessions])
    total_decisions = sum([s["decision_count"] for s in sessions])

    st.markdown("""
    <div style="margin-bottom: 24px;">
        <h1 class="display-title">Executive Dashboard</h1>
        <div style="font-size: 13px; color: var(--text-2);">Workspace intelligence metrics and rapid audio transcription</div>
    </div>
    """, unsafe_allow_html=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""<div class="metric-tile"><div class="metric-tile-label">Total Meetings</div><div class="metric-tile-value">{len(sessions)}</div></div>""", unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""<div class="metric-tile"><div class="metric-tile-label">Spoken Time</div><div class="metric-tile-value">{total_duration_mins}m</div></div>""", unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""<div class="metric-tile"><div class="metric-tile-label">Action Items</div><div class="metric-tile-value">{total_actions}</div></div>""", unsafe_allow_html=True)
    with col_m4:
        st.markdown(f"""<div class="metric-tile"><div class="metric-tile-label">Decisions Agreed</div><div class="metric-tile-value">{total_decisions}</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # Main Upload & Audio Processing Studio Card
    st.markdown("""
    <div style="background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px; margin-bottom: 24px;">
        <div style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 4px;">Upload Audio or Record Memo</div>
        <div style="font-size: 13px; color: var(--text-2); margin-bottom: 16px;">Powered by Groq Whisper and Gemini with Supabase Cloud Sync</div>
    </div>
    """, unsafe_allow_html=True)

    tab_up, tab_voice = st.tabs(["Upload File", "Voice Memo"])

    with tab_up:
        uploaded_file = st.file_uploader("Drop audio files here", type=["mp3", "wav", "m4a", "mp4", "aac", "ogg", "flac"], label_visibility="collapsed")
        col_opt1, col_opt2 = st.columns([1.2, 1.2])
        with col_opt1:
            template_mode = st.selectbox(
                "Summary Template",
                ["Executive Meeting", "Academic Lecture", "Brainstorm & Ideation"],
                key="dash_tpl_select",
                index=0
            )
        with col_opt2:
            model_mode = st.selectbox(
                "Intelligence Engine",
                ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
                key="dash_model_select",
                index=0
            )

        tpl_key = "executive"
        if "Academic" in template_mode:
            tpl_key = "academic"
        elif "Brainstorm" in template_mode:
            tpl_key = "brainstorm"

        if uploaded_file is not None:
            if not usage["can_upload"]:
                st.error("Monthly limit reached. Please upgrade to Pro in the sidebar for unlimited processing.")
            else:
                if st.button("Transcribe & Analyze", type="primary", use_container_width=True):
                    save_path = INPUTS_DIR / uploaded_file.name
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner("Processing on Groq LPUs and Gemini..."):
                        try:
                            result = process_meeting_file_cloud(
                                save_path,
                                model_choice=model_mode,
                                user_id=user_id,
                                template_type=tpl_key
                            )
                            sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                            st.session_state.active_session_id = f"session_{sid}"
                            st.toast("Meeting synchronized to workspace.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Processing failed: {ex}")

    with tab_voice:
        st.markdown("<div style='font-size: 13px; color: var(--text-2); margin-bottom: 12px;'>Record voice notes directly from your browser microphone:</div>", unsafe_allow_html=True)
        col_rec_btn, col_rec_action = st.columns([1.0, 1.4])
        with col_rec_btn:
            recorded_bytes = audio_recorder(pause_threshold=2.5, text="Record Voice Memo", recording_color="#c0392b", neutral_color="#5b616e", icon_size="2x")
        with col_rec_action:
            if recorded_bytes:
                st.audio(recorded_bytes, format="audio/wav")
                if not usage["can_upload"]:
                    st.error("Monthly limit reached. Upgrade to Pro for unlimited recording.")
                else:
                    if st.button("Process Voice Memo", type="primary", use_container_width=True):
                        memo_filename = f"voice_memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                        memo_path = INPUTS_DIR / memo_filename
                        with open(memo_path, "wb") as f:
                            f.write(recorded_bytes)
                        with st.spinner("Transcribing voice recording..."):
                            try:
                                result = process_meeting_file_cloud(memo_path, custom_title="Voice Memo Recording", model_choice=st.session_state.model_choice, user_id=user_id, template_type="executive")
                                sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                                st.session_state.active_session_id = f"session_{sid}"
                                st.toast("Voice memo transcribed.")
                                time.sleep(0.3)
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Analysis failed: {ex}")

    # Latest Meetings
    st.markdown("<h2 class='section-title' style='margin-top: 36px; margin-bottom: 14px;'>Recent Meetings</h2>", unsafe_allow_html=True)
    if not sessions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-title">No meeting sessions recorded yet</div>
            <div>Upload an audio recording above to generate your first structured intelligence report.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for s in sessions[:3]:
            with st.container():
                col_info, col_act = st.columns([3.5, 1.0])
                with col_info:
                    clean_s_title = format_acronyms(s['title'])
                    st.markdown(f"""
                    <div style="font-weight: 600; font-size: 14.5px; color: var(--text); margin-bottom: 4px;">{clean_s_title}</div>
                    <div style="display: flex; gap: 8px; font-size: 12px; color: var(--text-2);">
                        <span>Duration: <span class="mono">{s['duration']}</span></span>
                        <span>&bull;</span>
                        <span>Date: <span class="mono">{s['date_display']}</span></span>
                        <span>&bull;</span>
                        <span>{s['action_count']} Action Items</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col_act:
                    if st.button("Open Report", key=f"quick_open_{s['id']}", type="secondary", use_container_width=True):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()
            st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 10px 0;'>", unsafe_allow_html=True)


# =============================================================================
# VIEW 2: RECENT SUMMARIES
# =============================================================================
def render_recents_view():
    sessions = load_user_sessions()
    user_id = get_current_user_id()

    col_title, col_search = st.columns([2.0, 1.5])
    with col_title:
        st.markdown("""
        <div>
            <h1 class="display-title">Recent Summaries</h1>
            <div style="font-size: 13px; color: var(--text-2);">All cloud-synchronized meeting intelligence archives</div>
        </div>
        """, unsafe_allow_html=True)
    with col_search:
        st.session_state.search_query = st.text_input("Search", placeholder="Search meetings or tags...", label_visibility="collapsed")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    if st.session_state.search_query.strip():
        q = st.session_state.search_query.lower()
        sessions = [
            s for s in sessions 
            if q in s["title"].lower() or any(q in t.lower() for t in s["tags"]) or q in json.dumps(s["data"]).lower()
        ]

    if not sessions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-title">No meeting records found</div>
            <div>Upload an audio file in the Dashboard to get started.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for s in sessions:
        with st.container():
            col_info, col_actions = st.columns([3.4, 1.4])

            with col_info:
                clean_title = format_acronyms(s['title'])
                tag_pills = ' '.join([f'<span class="pill">#{format_acronyms(t.lstrip("#"))}</span>' for t in s['tags']])
                st.markdown(f"""
                <div style="font-size: 14.5px; font-weight: 600; color: var(--text); margin-bottom: 4px;" class="ellipsis-text">{clean_title}</div>
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px; color: var(--text-2);">
                    <span>Duration: <span class="mono">{s['duration']}</span></span>
                    <span>&bull;</span>
                    <span>Date: <span class="mono">{s['date_display']}</span></span>
                    <span>&bull;</span>
                    <span>{s['action_count']} Actions</span>
                    <span>&bull;</span>
                    <span>{s['decision_count']} Decisions</span>
                    {tag_pills}
                </div>
                """, unsafe_allow_html=True)

            with col_actions:
                col_btn_open, col_btn_ren, col_btn_del = st.columns([1.1, 0.5, 0.5])
                with col_btn_open:
                    if st.button("Open", key=f"open_{s['id']}", type="secondary", use_container_width=True):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()
                with col_btn_ren:
                    if st.button("Edit", key=f"ren_{s['id']}", help="Rename Title", type="secondary", use_container_width=True):
                        st.session_state.rename_target = (s["raw_id"], s["title"])
                with col_btn_del:
                    if st.button("Del", key=f"del_{s['id']}", help="Delete Meeting", type="secondary", use_container_width=True):
                        try:
                            delete_session_record(s["raw_id"], user_id=user_id)
                            st.toast("Session deleted.")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception:
                            pass

            st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 8px 0;'>", unsafe_allow_html=True)

    if st.session_state.rename_target:
        rename_meeting_dialog(st.session_state.rename_target[0], st.session_state.rename_target[1])


# =============================================================================
# VIEW 3: ACTION ITEMS TRACKER
# =============================================================================
def render_action_tracker_view():
    sessions = load_user_sessions()

    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 class="display-title">Action Items Tracker</h1>
        <div style="font-size: 13px; color: var(--text-2);">Aggregated matrix of all deliverables, owners, and target completion dates</div>
    </div>
    """, unsafe_allow_html=True)

    all_actions = []
    for s in sessions:
        actions = s["data"].get("action_items", [])
        for a in actions:
            item = dict(a)
            item["meeting_title"] = s["title"]
            item["meeting_id"] = s["id"]
            all_actions.append(item)

    if not all_actions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-title">No action deliverables identified</div>
            <div>Action items will automatically aggregate here once meetings are processed.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    col_f1, col_f2 = st.columns([1.5, 1.5])
    with col_f1:
        prio_filter = st.multiselect("Filter by Priority", ["HIGH", "MED", "LOW"], default=["HIGH", "MED", "LOW"])
    with col_f2:
        owners = list(set([a.get("assignee", "Team") for a in all_actions]))
        owner_filter = st.multiselect("Filter by Owner", owners, default=owners)

    filtered_actions = [
        a for a in all_actions
        if (a.get("priority", "MED").upper() in prio_filter) and (a.get("assignee", "Team") in owner_filter)
    ]

    comp_count = len([a for a in filtered_actions if a.get("status") == "completed"])
    total_f_count = len(filtered_actions)
    pct = int((comp_count / total_f_count) * 100) if total_f_count > 0 else 0

    st.markdown(f"""
    <div style="margin-bottom: 12px; display: flex; justify-content: space-between; font-size: 12.5px; color: var(--text-2);">
        <span>Showing {total_f_count} action items</span>
        <span class="mono">{comp_count} of {total_f_count} complete ({pct}%)</span>
    </div>
    """, unsafe_allow_html=True)

    rows_html = []
    for a in filtered_actions:
        deliverable = format_acronyms(a.get("description") or a.get("task") or "Task")
        owner = a.get("assignee") or a.get("owner") or "Team"
        owner_initial = owner[0].upper() if owner else "T"
        prio = (a.get("priority") or "MED").upper()
        due = a.get("due_date") or "Next Sprint"
        notes = format_acronyms(a.get("notes") or a.get("acceptance_criteria") or "—")
        meeting = format_acronyms(a.get("meeting_title", "Meeting"))

        prio_class = "priority-med"
        if "HIGH" in prio:
            prio_class = "priority-high"
        elif "LOW" in prio:
            prio_class = "priority-low"

        rows_html.append(f"""
        <tr>
            <td style="font-weight: 500; color: var(--text);"><span style="color: var(--text-3); margin-right: 8px;">&#9633;</span>{deliverable}</td>
            <td><span class="avatar-circle" style="margin-right: 6px;">{owner_initial}</span><span style="color: var(--text-2);">{owner}</span></td>
            <td><span class="{prio_class}">{prio}</span></td>
            <td><span class="mono" style="color: var(--text-2); font-size: 12.5px;">{due}</span></td>
            <td style="color: var(--text-2); font-size: 12.5px;">{notes}</td>
            <td style="color: var(--text-3); font-size: 12px;" class="ellipsis-text">{meeting}</td>
        </tr>
        """)

    table_html = f"""
    <table class="action-table">
        <thead>
            <tr>
                <th style="width: 34%;">Deliverable</th>
                <th style="width: 14%;">Owner</th>
                <th style="width: 10%;">Priority</th>
                <th style="width: 12%;">Due Date</th>
                <th style="width: 16%;">Notes</th>
                <th style="width: 14%;">Source Meeting</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows_html)}
        </tbody>
    </table>
    """
    st.html(table_html)


# =============================================================================
# VIEW 4: EXPORT CENTER
# =============================================================================
def render_export_center_view():
    sessions = load_user_sessions()

    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 class="display-title">Export Center</h1>
        <div style="font-size: 13px; color: var(--text-2);">Download meeting transcripts, executive briefs, printable HTML/PDF, and structured JSON data</div>
    </div>
    """, unsafe_allow_html=True)

    if not sessions:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-title">No meeting sessions available to export</div>
            <div>Recorded and processed meetings will appear here with one-click export formats.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for s in sessions:
        with st.container():
            col_info, col_md, col_txt, col_html, col_json = st.columns([2.2, 0.7, 0.7, 0.8, 0.6])
            with col_info:
                clean_title = format_acronyms(s['title'])
                st.markdown(f"""
                <div style="font-size: 14.5px; font-weight: 600; color: var(--text); margin-bottom: 2px;">{clean_title}</div>
                <div style="font-size: 12px; color: var(--text-2);">Date: <span class="mono">{s['date_display']}</span> &bull; Duration: <span class="mono">{s['duration']}</span></div>
                """, unsafe_allow_html=True)

            raw_md = s["data"].get("raw_markdown", "# Meeting Report")
            full_txt = s["data"].get("full_transcript_text", raw_md)
            printable_html = generate_printable_html(s["data"], active_theme=st.session_state.get("theme", "light"))

            with col_md:
                st.download_button("Markdown", data=raw_md, file_name=f"{s['id']}.md", mime="text/markdown", key=f"exp_md_{s['id']}", use_container_width=True)
            with col_txt:
                st.download_button("Plain Text", data=full_txt, file_name=f"{s['id']}.txt", mime="text/plain", key=f"exp_txt_{s['id']}", use_container_width=True)
            with col_html:
                st.download_button("PDF View", data=printable_html, file_name=f"{s['id']}_report.html", mime="text/html", key=f"exp_html_{s['id']}", use_container_width=True)
            with col_json:
                st.download_button("JSON", data=json.dumps(s["data"], indent=2), file_name=f"{s['id']}.json", mime="application/json", key=f"exp_json_{s['id']}", use_container_width=True)

            st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 8px 0;'>", unsafe_allow_html=True)


# =============================================================================
# VIEW 5: MEETING DETAIL WORKSPACE (4 DEDICATED SECTIONS)
# =============================================================================
def render_meeting_detail_view(session_id: str):
    sessions = load_user_sessions()
    active_item = next((s for s in sessions if s["id"] == session_id or s["raw_id"] == session_id), None)

    if not active_item:
        st.error("Meeting session not found or deleted.")
        if st.button("← Back to Dashboard"):
            st.session_state.active_session_id = None
            st.rerun()
        return

    data = active_item["data"]
    meta = data.get("metadata", {})
    title = active_item["title"]
    duration = active_item["duration"]
    date_str = active_item["date_display"]
    model_name = meta.get("model", "Groq Whisper-large-v3 + Gemini 2.5 Flash")
    tpl_name = active_item.get("template_type", "executive").capitalize()

    clean_title = format_acronyms(title)

    # Header Title Banner & Export Suite
    col_h_left, col_h_right = st.columns([2.8, 1.8])
    with col_h_left:
        pills = []
        if duration:
            pills.append(f'<span class="pill">{duration}</span>')
        if date_str:
            pills.append(f'<span class="pill">{date_str}</span>')
        if model_name:
            pills.append(f'<span class="pill">{model_name}</span>')
        if tpl_name:
            pills.append(f'<span class="pill">{tpl_name} Template</span>')
        for t in active_item.get("tags", []):
            clean_t = format_acronyms(t.lstrip("#"))
            pills.append(f'<span class="pill">#{clean_t}</span>')

        header_markup = f"""
        <div style="margin-bottom: 20px;">
            <h1 class="display-title">{clean_title}</h1>
            <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 8px;">
                {''.join(pills)}
            </div>
        </div>
        """
        st.markdown(header_markup, unsafe_allow_html=True)

    with col_h_right:
        col_back, col_md, col_pdf, col_json = st.columns([0.8, 0.9, 0.9, 0.7])
        raw_md = data.get("raw_markdown", "# Meeting Report")
        printable_html = generate_printable_html(data, active_theme=st.session_state.get("theme", "light"))

        with col_back:
            if st.button("Back", key="btn_back_detail", type="secondary", use_container_width=True):
                st.session_state.active_session_id = None
                st.rerun()
        with col_md:
            st.download_button("Markdown", data=raw_md, file_name=f"{session_id}.md", mime="text/markdown", use_container_width=True)
        with col_pdf:
            st.download_button("PDF View", data=printable_html, file_name=f"{session_id}_report.html", mime="text/html", use_container_width=True)
        with col_json:
            st.download_button("JSON", data=json.dumps(data, indent=2), file_name=f"{session_id}.json", mime="application/json", use_container_width=True)

    st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin-bottom: 24px;'>", unsafe_allow_html=True)

    # 4 Dedicated Tabs (Clean, no emoji)
    tab_summary, tab_actions, tab_transcript, tab_chat = st.tabs([
        "Summary",
        "Action Items",
        "Transcript",
        "Chat"
    ])

    user_id = get_current_user_id()

    # -------------------------------------------------------------------------
    # TAB 1: UNIFIED THEMED DOCUMENT (SUMMARY + D3 MARKMAP TREE)
    # -------------------------------------------------------------------------
    with tab_summary:
        active_theme = st.session_state.get("theme", "light")
        doc_html = generate_unified_document_html(data, meta=meta, active_theme=active_theme)
        components.html(doc_html, height=2200, scrolling=True)

    # -------------------------------------------------------------------------
    # TAB 2: INTERACTIVE ACTION ITEMS TRACKER (FULL MANAGEMENT SUITE)
    # -------------------------------------------------------------------------
    with tab_actions:
        action_items = data.get("action_items", [])
        
        # Fallback scan if empty
        if not action_items and raw_md:
            for line in raw_md.splitlines():
                if ("|" in line and ("p0" in line.lower() or "high" in line.lower() or "med" in line.lower() or "due" in line.lower())) or line.strip().startswith("- [ ]"):
                    clean_item = re.sub(r"^[-*|\d\.\s\[\]]+", "", line).strip()
                    if len(clean_item) > 5 and not clean_item.startswith("Task Deliverable"):
                        action_items.append({
                            "number": len(action_items) + 1,
                            "description": clean_item,
                            "assignee": "Team",
                            "priority": "HIGH" if "high" in clean_item.lower() else "MED",
                            "due_date": "Next Sprint",
                            "status": "pending",
                            "notes": "—"
                        })

        # Ensure all items have a status
        for idx, item in enumerate(action_items):
            if "status" not in item:
                item["status"] = "pending"
            if "number" not in item:
                item["number"] = idx + 1

        total_cnt = len(action_items)
        comp_cnt = len([a for a in action_items if a.get("status") == "completed"])
        pend_cnt = total_cnt - comp_cnt
        comp_percent = int((comp_cnt / total_cnt) * 100) if total_cnt > 0 else 0

        # Header metrics & progress bar
        col_act_head, col_act_prog = st.columns([1.5, 1.5])
        with col_act_head:
            st.markdown(f"""
            <div>
                <h3 style="font-size: 16px; font-weight: 600; margin: 0 0 2px 0; color: var(--text);">Action Items Manager</h3>
                <div style="font-size: 12.5px; color: var(--text-2);">Track deliverable completion, assign owners, and synchronize to workspace</div>
            </div>
            """, unsafe_allow_html=True)
        with col_act_prog:
            st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:12px; font-weight:500; color:var(--text); margin-bottom:4px;'><span>Task Completion: {comp_cnt} of {total_cnt} done</span><span class='mono'>{comp_percent}%</span></div>", unsafe_allow_html=True)
            st.progress(comp_percent / 100.0)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        col_filter, col_add_btn = st.columns([2.0, 1.0])
        with col_filter:
            action_filter = st.radio(
                "Filter Tasks",
                [f"All ({total_cnt})", f"Pending ({pend_cnt})", f"Completed ({comp_cnt})"],
                horizontal=True,
                label_visibility="collapsed"
            )

        # Filter items list
        display_items = []
        for a in action_items:
            if "Pending" in action_filter and a.get("status") == "completed":
                continue
            if "Completed" in action_filter and a.get("status") != "completed":
                continue
            display_items.append(a)

        # Render Task Cards
        if not display_items:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-state-title">No action items match the selected filter</div>
                <div>Switch filter or add a new action item below.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for item in display_items:
                orig_idx = action_items.index(item)
                is_done = item.get("status") == "completed"
                prio = (item.get("priority") or "MED").upper()
                prio_class = "priority-high" if "HIGH" in prio else ("priority-low" if "LOW" in prio else "priority-med")
                owner = item.get("assignee") or item.get("owner") or "Team"
                owner_initial = owner[0].upper() if owner else "T"
                due = item.get("due_date") or "Next Sprint"
                desc = format_acronyms(item.get("description") or item.get("task") or "Deliverable")

                desc_style = "text-decoration: line-through; color: var(--text-3);" if is_done else "font-weight: 500; color: var(--text);"

                with st.container():
                    col_chk, col_txt, col_meta, col_del = st.columns([0.3, 2.3, 1.1, 0.3])
                    with col_chk:
                        chk_val = st.checkbox("", value=is_done, key=f"chk_act_{session_id}_{orig_idx}")
                        if chk_val != is_done:
                            action_items[orig_idx]["status"] = "completed" if chk_val else "pending"
                            data["action_items"] = action_items
                            update_session_action_items(session_id, action_items, user_id=user_id)
                            st.toast("Task status updated.")
                            time.sleep(0.2)
                            st.rerun()

                    with col_txt:
                        st.markdown(f"<div style='font-size: 13.5px; padding-top: 2px; {desc_style}'>{desc}</div>", unsafe_allow_html=True)

                    with col_meta:
                        st.markdown(f"""
                        <div style="display:flex; gap:6px; align-items:center; font-size:11.5px; padding-top:2px;">
                            <span class="{prio_class}">{prio}</span>
                            <span class="avatar-circle" style="width: 18px; height: 18px; font-size: 9.5px;">{owner_initial}</span>
                            <span style="color:var(--text-2);">{owner}</span>
                            <span class="mono" style="color:var(--text-3); font-size:11.5px;">{due}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_del:
                        if st.button("Del", key=f"del_task_{session_id}_{orig_idx}", help="Delete Task", type="secondary"):
                            action_items.pop(orig_idx)
                            data["action_items"] = action_items
                            update_session_action_items(session_id, action_items, user_id=user_id)
                            st.toast("Task removed.")
                            time.sleep(0.2)
                            st.rerun()

                    st.markdown("<hr style='border: none; border-top: 1px solid var(--border); margin: 6px 0;'>", unsafe_allow_html=True)

        # Expandable Add New Task Form
        with st.expander("Add Action Item"):
            with st.form(key=f"form_add_action_{session_id}"):
                new_task_desc = st.text_input("Task Deliverable", placeholder="e.g. Finalize SOC 2 audit policies and Azure key rotation")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    new_task_owner = st.text_input("Owner / Assignee", value="Team")
                with col_f2:
                    new_task_prio = st.selectbox("Priority", ["HIGH", "MED", "LOW"], index=1)
                with col_f3:
                    new_task_due = st.text_input("Due Date", value="Next Sprint")
                
                submitted = st.form_submit_button("Save Action Item", type="primary", use_container_width=True)
                if submitted:
                    if new_task_desc.strip():
                        action_items.append({
                            "number": len(action_items) + 1,
                            "description": new_task_desc.strip(),
                            "assignee": new_task_owner.strip() or "Team",
                            "priority": new_task_prio,
                            "due_date": new_task_due.strip() or "Next Sprint",
                            "status": "pending",
                            "notes": "Manually added"
                        })
                        data["action_items"] = action_items
                        update_session_action_items(session_id, action_items, user_id=user_id)
                        st.toast("Action item saved.")
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.warning("Please provide a task description.")

    # -------------------------------------------------------------------------
    # TAB 3: DIARIZED TRANSCRIPT & SYNCED AUDIO PLAYER
    # -------------------------------------------------------------------------
    with tab_transcript:
        found_audio = None
        source_path = meta.get("source_file", "")
        if source_path and Path(source_path).exists() and is_supported_media(Path(source_path)):
            found_audio = Path(source_path)
        else:
            for ext in [".mp3", ".wav", ".m4a", ".mp4"]:
                cand = INPUTS_DIR / f"{session_id}{ext}"
                if cand.exists():
                    found_audio = cand
                    break
                cand_sess = INPUTS_DIR / f"session_{session_id}{ext}"
                if cand_sess.exists():
                    found_audio = cand_sess
                    break
                for p in INPUTS_DIR.glob(f"*{ext}"):
                    if session_id in p.stem or (source_path and p.name == source_path):
                        found_audio = p
                        break

        # Top Audio Player Widget
        if found_audio and found_audio.exists():
            st.markdown("<div style='font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 6px;'>Audio Waveform Player</div>", unsafe_allow_html=True)
            with open(found_audio, "rb") as af:
                audio_bytes = af.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        transcript_turns = []
        if "transcript_segments" in data and data["transcript_segments"]:
            for seg in data["transcript_segments"]:
                transcript_turns.append({
                    "time": seg.get("timestamp", "00:00"),
                    "speaker": seg.get("speaker", "Speaker 1"),
                    "text": seg.get("text", ""),
                    "seconds": seg.get("start", 0.0)
                })
        else:
            transcript_turns = parse_transcript_turns(data.get("raw_markdown", ""))

        theme_mode = st.session_state.theme
        bg_bubble = "#1c2027" if theme_mode == "dark" else "#f6f7f9"
        bg_bubble_hover = "#262b33" if theme_mode == "dark" else "#ebeef2"
        border_col = "#262b33" if theme_mode == "dark" else "#e7e8ec"
        text_pri = "#e9ecf1" if theme_mode == "dark" else "#16181d"
        text_sec = "#a2a9b6" if theme_mode == "dark" else "#5b616e"
        accent_col = "#ff6f5e" if theme_mode == "dark" else "#c0392b"

        transcript_cards_html = []
        for idx, turn in enumerate(transcript_turns):
            t_sec_val = turn.get("seconds", 0.0)
            t_spk_val = turn.get("speaker", "Speaker 1")
            t_time_val = turn.get("time", "00:00")
            t_txt_val = turn.get("text", "")
            transcript_cards_html.append(f"""
            <div class="turn-card" data-seek="{t_sec_val}" id="turn_{idx}" style="background: {bg_bubble}; border: 1px solid {border_col}; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; transition: all 0.15s ease;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 12px; font-weight: 600; color: {text_pri}; background: var(--surface, #ffffff); border: 1px solid {border_col}; padding: 2px 8px; border-radius: 999px;">{t_spk_val}</span>
                        <span class="mono" style="font-size: 11.5px; color: {text_sec};">{t_time_val}</span>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button onclick="seekToAudio({t_sec_val}, this)" style="background: var(--surface, #ffffff); border: 1px solid {border_col}; color: {text_pri}; border-radius: 6px; font-size: 11.5px; font-weight: 500; padding: 4px 10px; cursor: pointer;">Play</button>
                        <button onclick="copyTurnText('txt_{idx}', this)" style="background: var(--surface, #ffffff); border: 1px solid {border_col}; color: {text_sec}; border-radius: 6px; font-size: 11.5px; font-weight: 500; padding: 4px 10px; cursor: pointer;">Copy</button>
                    </div>
                </div>
                <div id="txt_{idx}" style="font-size: 13.5px; color: {text_pri}; line-height: 1.65;">{t_txt_val}</div>
            </div>
            """)

        turns_content = ''.join(transcript_cards_html) if transcript_cards_html else f'<div style="padding:32px; text-align:center; color:{text_sec}; font-size: 13.5px;">Transcript turns will appear here once audio is diarized.</div>'

        interactive_player_html = """<!DOCTYPE html>
<html>
<head>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; padding: 0; background: transparent; color: __TEXT_PRI__; font-family: 'Inter', -apple-system, sans-serif; }
        .turn-card.active {
            border-left: 3px solid __ACCENT__ !important;
            background: __BG_HOVER__ !important;
        }
        .transcript-stream {
            max-height: 560px; overflow-y: auto; padding-right: 6px;
        }
        .transcript-stream::-webkit-scrollbar { width: 4px; }
        .transcript-stream::-webkit-scrollbar-thumb { background: __BORDER__; border-radius: 4px; }
        .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    </style>
</head>
<body>
    <div class="transcript-stream" id="transcriptStream">
        __TURNS_CONTENT__
    </div>

    <script>
        function seekToAudio(seconds, btn) {
            var audio = window.parent.document.querySelector('audio');
            if (audio) {
                audio.currentTime = seconds;
                audio.play();
            }
            var card = btn ? btn.closest('.turn-card') : null;
            document.querySelectorAll('.turn-card').forEach(function(c) { c.classList.remove('active'); });
            if (card) {
                card.classList.add('active');
            }
        }

        function copyTurnText(elementId, btn) {
            var el = document.getElementById(elementId);
            if (el) {
                navigator.clipboard.writeText(el.innerText).then(function() {
                    var orig = btn.innerText;
                    btn.innerText = 'Copied';
                    setTimeout(function() { btn.innerText = orig; }, 1500);
                });
            }
        }
    </script>
</body>
</html>""".replace("__TEXT_PRI__", text_pri).replace("__ACCENT__", accent_col).replace("__BG_HOVER__", bg_bubble_hover).replace("__BORDER__", border_col).replace("__TURNS_CONTENT__", turns_content)
        components.html(interactive_player_html, height=580, scrolling=False)

    # -------------------------------------------------------------------------
    # TAB 4: INTERACTIVE CHAT WITH AUDIO (ASSISTANT BOT)
    # -------------------------------------------------------------------------
    with tab_chat:
        st.markdown("""
        <div style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;">
            <div style="font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 2px;">Meeting Assistant</div>
            <div style="font-size: 12.5px; color: var(--text-2);">Ask questions, clarify points, or request specific summaries grounded directly in this recording.</div>
        </div>
        """, unsafe_allow_html=True)

        if session_id not in st.session_state.chat_messages:
            st.session_state.chat_messages[session_id] = [
                {"role": "assistant", "content": "I am your meeting assistant. Ask any question about this recording, discussion topics, decisions, or action items."}
            ]

        for msg in st.session_state.chat_messages[session_id]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_q = st.chat_input("Ask a question about this meeting...")
        if user_q:
            st.session_state.chat_messages[session_id].append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing meeting context..."):
                    answer = chat_with_session(
                        session_data=data,
                        user_query=user_q,
                        chat_history=st.session_state.chat_messages[session_id],
                        model_name=st.session_state.model_choice
                    )
                    st.markdown(answer)
                    st.session_state.chat_messages[session_id].append({"role": "assistant", "content": answer})


# =============================================================================
# MAIN APPLICATION ROUTER
# =============================================================================
def main():
    render_sidebar()

    # Route 1: Active Meeting Detail Workspace
    if st.session_state.active_session_id is not None:
        render_meeting_detail_view(st.session_state.active_session_id)
        return

    # Route 2: Guest Landing Page if not authenticated
    if not st.session_state.user:
        render_landing_page()
        return

    # Route 3: Authenticated Workspace Navigation
    if st.session_state.current_nav == "dashboard":
        render_dashboard_view()
    elif st.session_state.current_nav == "recents":
        render_recents_view()
    elif st.session_state.current_nav == "actions":
        render_action_tracker_view()
    elif st.session_state.current_nav == "export":
        render_export_center_view()

if __name__ == "__main__":
    main()

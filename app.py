import sys
import os
import re
import io
import json
import time
import base64
import subprocess
from pathlib import Path
from datetime import datetime

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

from core.config import BASE_DIR, INPUTS_DIR, OUTPUTS_DIR, DEFAULT_MODEL, get_api_key, is_supported_media
from cloud_pipeline import (
    process_meeting_file_cloud,
    fetch_all_sessions,
    save_session_record,
    delete_session_record,
    rename_session_record,
    get_groq_client,
    get_supabase_client,
    get_gemini_client
)

SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
INPUTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# STREAMLIT CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="Plaud Studio | Cloud Meeting Intelligence",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if "theme" not in st.session_state:
    st.session_state.theme = "light"
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "model_choice" not in st.session_state:
    st.session_state.model_choice = "gemini-2.5-flash"
if "rename_target" not in st.session_state:
    st.session_state.rename_target = None

# =============================================================================
# DYNAMIC THEME SYSTEM & CSS VARIABLES
# =============================================================================
def apply_theme_css(theme: str):
    if theme == "dark":
        css_vars = """
        :root {
            --plaud-bg: #0D1117;
            --plaud-card-bg: #161B22;
            --plaud-card-hover: #1C2128;
            --plaud-border: #30363D;
            --plaud-border-hover: #58A6FF;
            --plaud-text-primary: #F0F6FC;
            --plaud-text-secondary: #8B949E;
            --plaud-text-muted: #6E7681;
            --plaud-blue: #38BDF8;
            --plaud-blue-hover: #7DD3FC;
            --plaud-blue-subtle: rgba(56, 189, 248, 0.12);
            --plaud-pill-bg: #21262D;
            --plaud-bubble-bg: #161B22;
            --plaud-bubble-border: #30363D;
            --plaud-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            --plaud-table-stripe: #1C2128;
        }
        """
    else:
        css_vars = """
        :root {
            --plaud-bg: #F8F9FA;
            --plaud-card-bg: #FFFFFF;
            --plaud-card-hover: #F8FAFC;
            --plaud-border: #E5E7EB;
            --plaud-border-hover: #CBD5E1;
            --plaud-text-primary: #111827;
            --plaud-text-secondary: #4B5563;
            --plaud-text-muted: #9CA3AF;
            --plaud-blue: #2563EB;
            --plaud-blue-hover: #1D4ED8;
            --plaud-blue-subtle: #EFF6FF;
            --plaud-pill-bg: #F3F4F6;
            --plaud-bubble-bg: #F9FAFB;
            --plaud-bubble-border: #F3F4F6;
            --plaud-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
            --plaud-table-stripe: #F9FAFB;
        }
        """

    full_css = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

        {css_vars}

        * {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }}

        .stApp {{
            background-color: var(--plaud-bg) !important;
            color: var(--plaud-text-primary) !important;
        }}

        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}

        footer {{
            display: none !important;
        }}

        #MainMenu {{
            visibility: hidden;
        }}

        .block-container {{
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 1440px !important;
        }}

        /* Buttons Styling */
        button[kind="primary"] {{
            background: var(--plaud-blue) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            padding: 8px 18px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        }}
        button[kind="primary"]:hover {{
            background: var(--plaud-blue-hover) !important;
            transform: translateY(-1px);
        }}

        button[kind="secondary"] {{
            background: var(--plaud-card-bg) !important;
            color: var(--plaud-text-primary) !important;
            border: 1px solid var(--plaud-border) !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            padding: 7px 14px !important;
            transition: all 0.15s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: var(--plaud-card-hover) !important;
            border-color: var(--plaud-border-hover) !important;
        }}

        /* Input Controls */
        div[data-baseweb="input"] {{
            background-color: var(--plaud-card-bg) !important;
            border: 1px solid var(--plaud-border) !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="input"]:focus-within {{
            border-color: var(--plaud-blue) !important;
            box-shadow: 0 0 0 2px var(--plaud-blue-subtle) !important;
        }}
        input.st-bc {{
            color: var(--plaud-text-primary) !important;
        }}

        /* Cards & Section Containers */
        .plaud-card {{
            background: var(--plaud-card-bg);
            border: 1px solid var(--plaud-border);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
            transition: all 0.2s ease;
            box-shadow: var(--plaud-shadow);
        }}
        .plaud-card:hover {{
            border-color: var(--plaud-border-hover);
            transform: translateY(-1px);
            background: var(--plaud-card-hover);
        }}

        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 18px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--plaud-border);
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 700;
            color: var(--plaud-text-primary);
            letter-spacing: -0.4px;
            margin: 0;
        }}
        .section-count {{
            font-size: 13px;
            color: var(--plaud-text-muted);
            font-weight: 500;
        }}

        /* Table & Lists */
        .file-title {{
            font-size: 14.5px;
            font-weight: 600;
            color: var(--plaud-text-primary);
            margin-bottom: 4px;
            cursor: pointer;
        }}
        .file-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            color: var(--plaud-text-muted);
        }}
        .tag-pill {{
            background: var(--plaud-pill-bg);
            color: var(--plaud-text-secondary);
            border-radius: 100px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}

        /* Detail Workspace Boxes */
        .detail-box {{
            background: var(--plaud-card-bg);
            border: 1px solid var(--plaud-border);
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 16px;
            box-shadow: var(--plaud-shadow);
        }}
        .box-title {{
            font-size: 13.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--plaud-blue);
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Clean Timestamp Badges */
        .time-badge {{
            display: inline-block;
            background: var(--plaud-blue-subtle);
            color: var(--plaud-blue);
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            margin-right: 8px;
            letter-spacing: 0.3px;
        }}

        /* Clean Pillar Accordion */
        details.pillar-card {{
            background: var(--plaud-bubble-bg);
            border: 1px solid var(--plaud-border);
            border-radius: 8px;
            margin-bottom: 8px;
            overflow: hidden;
            transition: border-color 0.2s ease;
        }}
        details.pillar-card[open] {{
            border-color: var(--plaud-border-hover);
        }}
        summary {{
            padding: 10px 14px;
            font-size: 13px;
            font-weight: 600;
            color: var(--plaud-text-primary);
            cursor: pointer;
            list-style: none;
            display: flex;
            align-items: center;
            user-select: none;
        }}
        summary::-webkit-details-marker {{
            display: none;
        }}
        .pillar-body {{
            padding: 10px 14px 14px 14px;
            font-size: 12.5px;
            color: var(--plaud-text-secondary);
            line-height: 1.55;
            border-top: 1px solid var(--plaud-border);
        }}

        /* Action Items Table */
        .action-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 12.5px;
            border: 1px solid var(--plaud-border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .action-table th {{
            background: var(--plaud-bubble-bg);
            color: var(--plaud-text-muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--plaud-border);
        }}
        .action-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--plaud-border);
            color: var(--plaud-text-primary);
            line-height: 1.45;
        }}
        .action-table tr:last-child td {{
            border-bottom: none;
        }}
        .action-table tr:hover td {{
            background: var(--plaud-card-hover);
        }}
        .priority-high {{
            color: #EF4444; font-weight: 700; background: rgba(239, 68, 68, 0.12); padding: 2px 6px; border-radius: 4px; font-size: 10.5px;
        }}
        .priority-med {{
            color: #F59E0B; font-weight: 700; background: rgba(245, 158, 11, 0.12); padding: 2px 6px; border-radius: 4px; font-size: 10.5px;
        }}
        .priority-low {{
            color: #10B981; font-weight: 700; background: rgba(16, 185, 129, 0.12); padding: 2px 6px; border-radius: 4px; font-size: 10.5px;
        }}

        .plaud-badge {{
            background: var(--plaud-blue-subtle);
            color: var(--plaud-blue);
            font-weight: 700;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
        }}
    </style>
    """
    st.markdown(full_css, unsafe_allow_html=True)

apply_theme_css(st.session_state.theme)


# =============================================================================
# HELPER PARSERS & TAG GENERATION
# =============================================================================
def extract_smart_tags(title: str, session_data: dict) -> list[str]:
    tags = []
    text_corpus = (title + " " + json.dumps(session_data)).lower()
    
    if any(k in text_corpus for k in ["soc 2", "compliance", "security", "audit", "policy"]):
        tags.append("#Compliance")
    if any(k in text_corpus for k in ["sprint", "roadmap", "engineering", "deploy", "server", "azure", "docker"]):
        tags.append("#Engineering")
    if any(k in text_corpus for k in ["marketing", "growth", "campaign", "leads", "sales"]):
        tags.append("#Growth")
    if any(k in text_corpus for k in ["training", "onboarding", "hr", "quiz"]):
        tags.append("#Training")
    if any(k in text_corpus for k in ["whisper", "live copilot", "gemini", "groq"]):
        tags.append("#AIStudio")

    if not tags:
        tags.append("#Meeting")
    return tags[:3]


def parse_timestamp_to_seconds(ts_str: str) -> float:
    try:
        parts = [float(p) for p in ts_str.strip("[] ").split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return 0.0


def parse_transcript_turns(raw_markdown: str) -> list[dict]:
    turns = []
    t_match = re.search(r"## 🗣️ Full Spoken Transcript.*?\n(.*?)(?=\n## |\Z)", raw_markdown, re.DOTALL)
    if t_match:
        lines = t_match.group(1).splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*?):\s*(.*)$", line)
            if m:
                ts = m.group(1).strip()
                spk = m.group(2).strip().strip("*_:")
                txt = m.group(3).strip()
                sec = parse_timestamp_to_seconds(ts)
                turns.append({"time": ts, "speaker": spk, "text": txt, "seconds": sec})
    return turns


def load_all_sessions() -> list[dict]:
    """Loads all structured session objects from Supabase Cloud and local sessions/."""
    raw_sessions = fetch_all_sessions()
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
            "source": s.get("source", "Cloud/Local"),
            "data": data
        })

    return sessions


# =============================================================================
# MODALS & DIALOGS (st.dialog)
# =============================================================================
@st.dialog("⚡ New Meeting Recording / Upload")
def new_recording_dialog():
    tab_upload, tab_record = st.tabs(["📤 Upload Audio/Video (Groq + Gemini)", "🎙️ Record Live Meeting / HUD"])

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Upload file",
            type=["mp3", "wav", "m4a", "mp4", "aac"],
            label_visibility="collapsed"
        )

        col_opt1, col_opt2 = st.columns([1.5, 1.0])
        with col_opt1:
            st.session_state.model_choice = st.selectbox(
                "Gemini Intelligence Engine",
                ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
                index=0
            )

        with col_opt2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if uploaded_file is not None:
                if st.button("⚡ Transcribe & Analyze", type="primary", use_container_width=True):
                    save_path = INPUTS_DIR / uploaded_file.name
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner("🚀 Transcribing with Groq Whisper-large-v3 + Gemini 2.5 Flash + Supabase Sync..."):
                        try:
                            result = process_meeting_file_cloud(
                                save_path,
                                model_choice=st.session_state.model_choice
                            )
                            sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                            st.session_state.active_session_id = f"session_{sid}"
                            st.toast("✅ Meeting processed and synchronized to Cloud!", icon="🚀")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Processing failed: {ex}")

    with tab_record:
        st.markdown("""
        <div style="font-size: 13px; color: var(--plaud-text-secondary); line-height: 1.5; margin-bottom: 14px;">
            <b>🎙️ Cloud Voice Memo & Meeting Recording:</b> Record directly from your browser. Audio is uploaded to Groq Whisper-large-v3 and analyzed with Gemini.
        </div>
        """, unsafe_allow_html=True)

        col_rec_btn, col_rec_action = st.columns([1.0, 1.4])
        with col_rec_btn:
            recorded_bytes = audio_recorder(
                pause_threshold=2.5,
                text="Record Browser Audio",
                recording_color="#EF4444",
                neutral_color="#38BDF8",
                icon_size="2x"
            )
        
        with col_rec_action:
            if recorded_bytes:
                st.audio(recorded_bytes, format="audio/wav")
                if st.button("🚀 Transcribe & Analyze Memo", type="primary", use_container_width=True):
                    memo_filename = f"voice_memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    memo_path = INPUTS_DIR / memo_filename
                    with open(memo_path, "wb") as f:
                        f.write(recorded_bytes)
                    with st.spinner("Processing voice recording with Groq & Gemini..."):
                        try:
                            result = process_meeting_file_cloud(
                                memo_path,
                                custom_title="Voice Memo Recording",
                                model_choice=st.session_state.model_choice
                            )
                            sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                            st.session_state.active_session_id = f"session_{sid}"
                            st.toast("✅ Voice memo transcribed and saved!", icon="🎙️")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Analysis failed: {ex}")


@st.dialog("✏️ Rename Meeting Title")
def rename_meeting_dialog(session_id: str, current_title: str):
    new_title = st.text_input("Meeting Title", value=current_title)
    col_cnl, col_sav = st.columns([1.0, 1.0])
    
    with col_cnl:
        if st.button("Cancel", use_container_width=True):
            st.session_state.rename_target = None
            st.rerun()
    with col_sav:
        if st.button("Save Title", type="primary", use_container_width=True):
            if new_title.strip():
                try:
                    rename_session_record(session_id, new_title.strip())
                    st.toast("Title updated successfully!", icon="✅")
                    st.session_state.rename_target = None
                    time.sleep(0.3)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to rename: {e}")


# =============================================================================
# TOP NAVIGATION BAR COMPONENT
# =============================================================================
def render_navbar():
    col_logo, col_search, col_theme, col_btn = st.columns([1.3, 1.7, 0.4, 1.2])
    
    with col_logo:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; padding-top: 4px;">
            <span style="font-size: 24px;">🎙️</span>
            <span style="font-weight: 800; font-size: 19px; color: var(--plaud-text-primary); letter-spacing: -0.5px;">Plaud Studio</span>
            <span class="plaud-badge">Cloud AI</span>
        </div>
        """, unsafe_allow_html=True)

    with col_search:
        if st.session_state.active_session_id is None:
            st.session_state.search_query = st.text_input(
                "Search",
                placeholder="🔍 Search notes, decisions, or transcripts...",
                label_visibility="collapsed"
            )
        else:
            st.write("")

    with col_theme:
        theme_icon = "🌙" if st.session_state.theme == "light" else "☀️"
        theme_tooltip = "Switch to Dark Mode" if st.session_state.theme == "light" else "Switch to Light Mode"
        if st.button(theme_icon, help=theme_tooltip, type="secondary", use_container_width=True):
            st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"
            st.rerun()

    with col_btn:
        if st.session_state.active_session_id is None:
            if st.button("+ New Recording / Upload", type="primary", use_container_width=True):
                new_recording_dialog()
        else:
            if st.button("← Back to Recent files", type="secondary", use_container_width=True):
                st.session_state.active_session_id = None
                st.rerun()


# =============================================================================
# VIEW 1: RECENT FILES WORKSPACE (DEFAULT LANDING PAGE)
# =============================================================================
def render_recent_files_view():
    sessions = load_all_sessions()

    # Filter by search query
    if st.session_state.search_query.strip():
        q = st.session_state.search_query.lower()
        sessions = [
            s for s in sessions 
            if q in s["title"].lower() or any(q in t.lower() for t in s["tags"]) or q in json.dumps(s["data"]).lower()
        ]

    # Section Header
    st.markdown(f"""
    <div class="section-header">
        <div>
            <h1 class="section-title">Recent files</h1>
            <span class="section-count">{len(sessions)} recorded meetings & intelligence sessions (Supabase Cloud + Local)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not sessions:
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px; background: var(--plaud-card-bg); border: 1px dashed var(--plaud-border); border-radius: 12px;">
            <span style="font-size: 38px;">📁</span>
            <div style="font-size: 16px; font-weight: 600; color: var(--plaud-text-primary); margin-top: 10px;">No recent meeting sessions found</div>
            <div style="font-size: 13px; color: var(--plaud-text-muted); margin-top: 4px;">Click "+ New Recording / Upload" above to get started with Groq & Gemini.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Render List of File Cards
    for s in sessions:
        with st.container():
            col_icon, col_info, col_actions = st.columns([0.35, 3.2, 1.45])

            with col_icon:
                st.markdown("<div style='font-size: 26px; padding-top: 6px;'>🎙️</div>", unsafe_allow_html=True)

            with col_info:
                source_badge = f'<span class="tag-pill" style="color: var(--plaud-blue);">☁️ {s.get("source", "Cloud")}</span>'
                st.markdown(f"""
                <div class="file-title">{s['title']}</div>
                <div class="file-meta">
                    <span>⏱️ {s['duration']}</span>
                    <span>📅 {s['date_display']}</span>
                    <span>⚡ {s['action_count']} Action Items</span>
                    <span>📌 {s['decision_count']} Decisions</span>
                    {source_badge}
                    {' '.join([f'<span class="tag-pill">{t}</span>' for t in s['tags']])}
                </div>
                """, unsafe_allow_html=True)

            with col_actions:
                col_btn_open, col_btn_ren, col_btn_del = st.columns([1.1, 0.5, 0.5])
                with col_btn_open:
                    if st.button("Open ↗️", key=f"open_{s['id']}", type="secondary", use_container_width=True):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()
                with col_btn_ren:
                    if st.button("✏️", key=f"ren_{s['id']}", help="Rename Meeting", type="secondary", use_container_width=True):
                        st.session_state.rename_target = (s["raw_id"], s["title"])
                with col_btn_del:
                    if st.button("🗑️", key=f"del_{s['id']}", help="Delete Meeting", type="secondary", use_container_width=True):
                        try:
                            delete_session_record(s["raw_id"])
                            st.toast("Session deleted.", icon="🗑️")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception:
                            pass

            st.markdown("<hr style='border: none; border-top: 1px solid var(--plaud-border); margin: 8px 0;'>", unsafe_allow_html=True)

    if st.session_state.rename_target:
        rename_meeting_dialog(st.session_state.rename_target[0], st.session_state.rename_target[1])


# =============================================================================
# VIEW 2: MEETING DETAIL WORKSPACE (TWO-COLUMN EXECUTIVE REPORT)
# =============================================================================
def render_meeting_detail_view(session_id: str):
    sessions = load_all_sessions()
    active_item = next((s for s in sessions if s["id"] == session_id or s["raw_id"] == session_id), None)

    if not active_item:
        st.error("Meeting session not found or deleted.")
        if st.button("← Back to Recent files"):
            st.session_state.active_session_id = None
            st.rerun()
        return

    data = active_item["data"]
    meta = data.get("metadata", {})
    title = active_item["title"]
    duration = active_item["duration"]
    date_str = active_item["date_display"]
    model_name = meta.get("model", "Groq Whisper-large-v3 + Gemini 2.5 Flash")

    # Header Title Banner
    col_h_left, col_h_right = st.columns([3.0, 1.5])
    with col_h_left:
        st.markdown(f"""
        <div style="margin-bottom: 16px;">
            <div style="font-size: 24px; font-weight: 800; color: var(--plaud-text-primary); letter-spacing: -0.5px; margin-bottom: 6px;">
                {title}
            </div>
            <div style="display: flex; gap: 10px; font-size: 12px; color: var(--plaud-text-secondary); font-weight: 500;">
                <span>⏱️ {duration}</span>
                <span>•</span>
                <span>📅 {date_str}</span>
                <span>•</span>
                <span>⚡ {model_name}</span>
                {' '.join([f'<span class="tag-pill">{t}</span>' for t in active_item['tags']])}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_h_right:
        col_cp, col_dl = st.columns([1.0, 1.0])
        raw_md = data.get("raw_markdown", "# Meeting Report")
        with col_cp:
            st.download_button(
                "📄 Download .md",
                data=raw_md,
                file_name=f"{session_id}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_dl:
            st.download_button(
                "📦 Export JSON",
                data=json.dumps(data, indent=2),
                file_name=f"{session_id}.json",
                mime="application/json",
                use_container_width=True
            )

    st.markdown("<hr style='border: none; border-top: 1px solid var(--plaud-border); margin-bottom: 20px;'>", unsafe_allow_html=True)

    # Executive Two-Column Layout
    col_left, col_right = st.columns([1.15, 0.85], gap="large")

    # -------------------------------------------------------------------------
    # LEFT COLUMN: EXECUTIVE INTELLIGENCE & STRUCTURE
    # -------------------------------------------------------------------------
    with col_left:
        # 1. Executive Brief
        exec_brief = data.get("executive_brief", [])
        if exec_brief:
            points_html = "".join([f"<div style='font-size: 13px; color: var(--plaud-text-secondary); margin-bottom: 6px; line-height: 1.5;'>• {p.lstrip('•*- ').strip()}</div>" for p in exec_brief])
            st.html(f"""<div class="detail-box"><div class="box-title">⚡ Executive Summary</div>{points_html}</div>""")

        # 2. Discussion Pillars (Clean custom details, no arrow_right glitch)
        pillars = data.get("discussion_pillars", [])
        if pillars:
            pillars_html = []
            for idx, pillar in enumerate(pillars):
                p_title = pillar.get("title", f"Pillar {idx+1}")
                p_time = pillar.get("timestamp", "00:00:00")
                p_details = pillar.get("details", "").replace("\n", "<br>")
                open_attr = "open" if idx == 0 else ""
                pillars_html.append(f"""<details class="pillar-card" {open_attr}><summary><span class="time-badge">{p_time}</span> <span>{p_title}</span></summary><div class="pillar-body">{p_details}</div></details>""")
            st.html(f"""<div class="detail-box"><div class="box-title">🏛️ Key Discussion Pillars</div>{''.join(pillars_html)}</div>""")

        # 3. Decisions & Reversals
        decisions = data.get("decisions", [])
        reversals = data.get("reversals", [])
        if decisions or reversals:
            dec_html = []
            if decisions:
                dec_html.append("<div style='font-size: 12px; font-weight: 700; color: #10B981; margin-bottom: 6px;'>✅ Approved Decisions</div>")
                for dec in decisions:
                    dec_html.append(f"<div style='font-size: 12.5px; color: var(--plaud-text-secondary); margin-bottom: 5px; line-height: 1.45;'>• {dec}</div>")
            if reversals:
                dec_html.append("<div style='font-size: 12px; font-weight: 700; color: #EF4444; margin-top: 10px; margin-bottom: 6px;'>🔄 Rejected Proposals & Reversals</div>")
                for rev in reversals:
                    dec_html.append(f"<div style='font-size: 12.5px; color: var(--plaud-text-secondary); margin-bottom: 5px; line-height: 1.45;'>• {rev}</div>")
            st.html(f"""<div class="detail-box"><div class="box-title">⚖️ Decisions Approved & Reversals</div>{''.join(dec_html)}</div>""")

        # 4. Action Items Matrix (Enhanced schema with Task Deliverable & Acceptance Criteria)
        action_items = data.get("action_items", [])
        if action_items:
            rows_html = []
            for item in action_items:
                deliverable = item.get("description") or item.get("task") or "Action deliverable"
                owner = item.get("assignee") or item.get("owner") or "Team"
                prio = (item.get("priority") or "MED").upper()
                due = item.get("due_date") or "Next Sprint"
                notes = item.get("notes") or item.get("acceptance_criteria") or "—"
                
                prio_class = "priority-med"
                if "HIGH" in prio:
                    prio_class = "priority-high"
                elif "LOW" in prio:
                    prio_class = "priority-low"

                rows_html.append(f"""<tr><td style="font-weight: 600; color: var(--plaud-text-primary);">{deliverable}</td><td style="color: var(--plaud-blue); font-weight: 600;">{owner}</td><td><span class="{prio_class}">{prio}</span></td><td style="color: var(--plaud-text-secondary); font-size: 11.5px;">{due}</td><td style="color: var(--plaud-text-secondary); font-size: 11.5px;">{notes}</td></tr>""")

            table_html = f"""<div class="detail-box"><div class="box-title">📋 Action Items Matrix</div><table class="action-table"><thead><tr><th style="width: 38%;">Task Deliverable</th><th style="width: 16%;">Owner</th><th style="width: 12%;">Priority</th><th style="width: 14%;">Due Date</th><th style="width: 20%;">Acceptance Criteria & Notes</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>"""
            st.html(table_html)

        # 5. Mermaid Architecture Mindmap
        mindmap = data.get("mermaid_mindmap", "")
        if mindmap and "mindmap" in mindmap:
            st.markdown("""
            <div class="detail-box">
                <div class="box-title">🗺️ Visual Meeting Mindmap</div>
            """, unsafe_allow_html=True)
            try:
                st_mermaid(mindmap, height="320px")
            except Exception:
                st.code(mindmap, language="mermaid")
            st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # RIGHT COLUMN: AUDIO & INTERACTIVE DIARIZED TRANSCRIPT
    # -------------------------------------------------------------------------
    with col_right:
        # 1. Locate media file
        found_audio = None
        source_path = meta.get("source_file", "")
        if source_path and Path(source_path).exists() and is_supported_media(Path(source_path)):
            found_audio = Path(source_path)
        else:
            # Match media from inputs/ directory
            for ext in [".mp3", ".wav", ".m4a", ".mp4"]:
                cand = INPUTS_DIR / f"{session_id}{ext}"
                if cand.exists():
                    found_audio = cand
                    break
                cand_clean = INPUTS_DIR / f"{title}{ext}"
                if cand_clean.exists():
                    found_audio = cand_clean
                    break

        # 2. Extract transcript turns
        transcript_turns = []
        if "transcript_segments" in data and data["transcript_segments"]:
            for seg in data["transcript_segments"]:
                transcript_turns.append({
                    "time": seg.get("timestamp", "00:00"),
                    "speaker": seg.get("speaker", "Speaker"),
                    "text": seg.get("text", ""),
                    "seconds": seg.get("start", 0.0)
                })
        else:
            transcript_turns = parse_transcript_turns(raw_md)

        # Q&A History Log (if present from Live Copilot)
        qna_history = data.get("qna_history", [])
        if qna_history:
            qna_cards = []
            for qa in qna_history:
                qna_cards.append(f"""<div style="background: var(--plaud-blue-subtle); border: 1px solid var(--plaud-border); border-radius: 8px; padding: 10px; margin-bottom: 8px;"><div style="font-size: 11px; font-weight: 700; color: var(--plaud-blue);">⏱️ {qa.get('time', '')} • Q&A</div><div style="font-size: 12px; font-weight: 700; color: var(--plaud-text-primary); margin: 2px 0;">Q: {qa.get('question', '')}</div><div style="font-size: 12px; color: var(--plaud-text-secondary); line-height: 1.45;">{qa.get('answer', '')}</div></div>""")
            st.html(f"""<div class="detail-box"><div class="box-title">🎯 Live Q&A Cheat-Sheets</div>{''.join(qna_cards)}</div>""")

        # 3. Interactive Timestamp Seeking Component
        st.html("""<div class="detail-box"><div class="box-title">🗣️ Synced Audio & Diarized Transcript</div></div>""")

        audio_b64 = ""
        audio_mime = "audio/mp3"
        if found_audio:
            try:
                with open(found_audio, "rb") as af:
                    audio_b64 = base64.b64encode(af.read()).decode("utf-8")
                if found_audio.suffix.lower() == ".wav":
                    audio_mime = "audio/wav"
                elif found_audio.suffix.lower() == ".m4a":
                    audio_mime = "audio/mp4"
            except Exception:
                pass

        # Build Interactive HTML/JS Player Component
        theme_mode = st.session_state.theme
        bg_bubble = "#1C2128" if theme_mode == "dark" else "#F9FAFB"
        bg_bubble_hover = "#21262D" if theme_mode == "dark" else "#F1F5F9"
        border_col = "#30363D" if theme_mode == "dark" else "#E5E7EB"
        text_pri = "#F0F6FC" if theme_mode == "dark" else "#111827"
        text_sec = "#8B949E" if theme_mode == "dark" else "#4B5563"
        blue_accent = "#38BDF8" if theme_mode == "dark" else "#2563EB"

        transcript_cards_html = []
        for idx, turn in enumerate(transcript_turns):
            transcript_cards_html.append(f"""
            <div class="turn-card" data-seek="{turn['seconds']}" onclick="seekToAudio({turn['seconds']}, this)">
                <div class="turn-header">
                    <span class="speaker-name">{turn['speaker']}</span>
                    <span class="time-tag" title="Click to seek audio">{turn['time']}</span>
                </div>
                <div class="turn-content">{turn['text']}</div>
            </div>
            """)

        interactive_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                body {{ margin: 0; padding: 0; background: transparent; color: {text_pri}; }}
                
                .audio-container {{
                    background: {bg_bubble};
                    border: 1px solid {border_col};
                    border-radius: 10px;
                    padding: 10px 12px;
                    margin-bottom: 12px;
                }}
                audio {{
                    width: 100%;
                    height: 36px;
                    outline: none;
                }}
                
                .transcript-list {{
                    max-height: 520px;
                    overflow-y: auto;
                    padding-right: 4px;
                }}
                .transcript-list::-webkit-scrollbar {{
                    width: 5px;
                }}
                .transcript-list::-webkit-scrollbar-thumb {{
                    background: {border_col};
                    border-radius: 4px;
                }}
                
                .turn-card {{
                    background: {bg_bubble};
                    border: 1px solid {border_col};
                    border-radius: 8px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                    cursor: pointer;
                    transition: all 0.15s ease;
                }}
                .turn-card:hover {{
                    background: {bg_bubble_hover};
                    border-color: {blue_accent};
                    transform: translateX(2px);
                }}
                .turn-card.active {{
                    border-left: 4px solid {blue_accent};
                    background: {bg_bubble_hover};
                }}
                
                .turn-header {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 4px;
                }}
                .speaker-name {{
                    font-size: 12px;
                    font-weight: 700;
                    color: {blue_accent};
                }}
                .time-tag {{
                    font-size: 10.5px;
                    font-weight: 700;
                    color: {text_sec};
                    background: rgba(125, 125, 125, 0.1);
                    padding: 2px 6px;
                    border-radius: 4px;
                    letter-spacing: 0.3px;
                }}
                .turn-content {{
                    font-size: 12.5px;
                    color: {text_pri};
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            {'<div class="audio-container"><audio id="plaud-audio" controls src="data:' + audio_mime + ';base64,' + audio_b64 + '"></audio></div>' if audio_b64 else ''}
            <div class="transcript-list" id="transcriptList">
                {''.join(transcript_cards_html) if transcript_cards_html else '<div style="font-size:12.5px; color:' + text_sec + '; padding:10px;">' + raw_md.replace(chr(10), "<br>") + '</div>'}
            </div>

            <script>
                function seekToAudio(seconds, element) {{
                    const audio = document.getElementById('plaud-audio');
                    if (audio) {{
                        audio.currentTime = seconds;
                        audio.play();
                    }}
                    document.querySelectorAll('.turn-card').forEach(c => c.classList.remove('active'));
                    if (element) {{
                        element.classList.add('active');
                    }}
                }}

                const audio = document.getElementById('plaud-audio');
                if (audio) {{
                    const cards = Array.from(document.querySelectorAll('.turn-card'));
                    audio.addEventListener('timeupdate', () => {{
                        const cur = audio.currentTime;
                        let activeIdx = -1;
                        for (let i = 0; i < cards.length; i++) {{
                            const sec = parseFloat(cards[i].getAttribute('data-seek') || 0);
                            if (cur >= sec) {{
                                activeIdx = i;
                            }} else {{
                                break;
                            }}
                        }}
                        cards.forEach((c, idx) => {{
                            if (idx === activeIdx) {{
                                if (!c.classList.contains('active')) {{
                                    c.classList.add('active');
                                    c.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                                }}
                            }} else {{
                                c.classList.remove('active');
                            }}
                        }});
                    }});
                }}
            </script>
        </body>
        </html>
        """

        components.html(interactive_html, height=600, scrolling=False)
        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# MAIN APPLICATION ROUTER
# =============================================================================
def main():
    render_navbar()

    if st.session_state.active_session_id is not None:
        render_meeting_detail_view(st.session_state.active_session_id)
    else:
        render_recent_files_view()

if __name__ == "__main__":
    main()

import sys
import os
import re
import io
import json
import time
import base64
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

# =============================================================================
# PRODUCTION-GRADE SAAS DARK/LIGHT THEME SYSTEM
# =============================================================================
def apply_saas_theme(theme: str = "dark"):
    if theme == "dark":
        css_vars = """
        :root {
            --hesh-bg: #090D16;
            --hesh-surface: #111726;
            --hesh-surface-hover: #182238;
            --hesh-border: #232E48;
            --hesh-border-hover: #38BDF8;
            --hesh-text-primary: #F8FAFC;
            --hesh-text-secondary: #94A3B8;
            --hesh-text-muted: #64748B;
            --hesh-accent: #38BDF8;
            --hesh-accent-hover: #7DD3FC;
            --hesh-accent-subtle: rgba(56, 189, 248, 0.12);
            --hesh-purple: #A855F7;
            --hesh-purple-subtle: rgba(168, 85, 247, 0.15);
            --hesh-emerald: #10B981;
            --hesh-emerald-subtle: rgba(16, 185, 129, 0.15);
            --hesh-rose: #F43F5E;
            --hesh-rose-subtle: rgba(244, 63, 94, 0.15);
            --hesh-card-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            --hesh-sidebar-bg: #0B0F19;
        }
        """
    else:
        css_vars = """
        :root {
            --hesh-bg: #F8FAFC;
            --hesh-surface: #FFFFFF;
            --hesh-surface-hover: #F1F5F9;
            --hesh-border: #E2E8F0;
            --hesh-border-hover: #0284C7;
            --hesh-text-primary: #0F172A;
            --hesh-text-secondary: #475569;
            --hesh-text-muted: #94A3B8;
            --hesh-accent: #0284C7;
            --hesh-accent-hover: #0369A1;
            --hesh-accent-subtle: #E0F2FE;
            --hesh-purple: #7E22CE;
            --hesh-purple-subtle: #F3E8FF;
            --hesh-emerald: #059669;
            --hesh-emerald-subtle: #D1FAE5;
            --hesh-rose: #E11D48;
            --hesh-rose-subtle: #FFE4E6;
            --hesh-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            --hesh-sidebar-bg: #FFFFFF;
        }
        """

    custom_css = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

        {css_vars}

        body, p, div, span:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons),
        h1, h2, h3, h4, h5, h6, input, button, select, textarea, label, td, th, a {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}

        /* Protect Material Icons from font-family ligature text leaks */
        .material-symbols-rounded,
        .material-symbols-outlined,
        .material-icons,
        [data-testid="stIconMaterial"],
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stSidebarHeader"] span,
        button span[data-testid="stIconMaterial"] {{
            font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
        }}

        .stApp {{
            background-color: var(--hesh-bg) !important;
            color: var(--hesh-text-primary) !important;
        }}

        section[data-testid="stSidebar"] {{
            background-color: var(--hesh-sidebar-bg) !important;
            border-right: 1px solid var(--hesh-border) !important;
        }}

        section[data-testid="stSidebar"] .block-container {{
            padding-top: 1.5rem !important;
            padding-left: 1.1rem !important;
            padding-right: 1.1rem !important;
        }}

        h1, h2, h3, h4 {{
            color: var(--hesh-text-primary) !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
        }}

        /* Buttons Styling */
        button[kind="primary"] {{
            background: linear-gradient(135deg, #0284C7 0%, #38BDF8 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13.5px !important;
            padding: 8px 18px !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 2px 10px rgba(56, 189, 248, 0.25) !important;
        }}
        button[kind="primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(56, 189, 248, 0.4) !important;
        }}

        button[kind="secondary"] {{
            background: var(--hesh-surface) !important;
            color: var(--hesh-text-primary) !important;
            border: 1px solid var(--hesh-border) !important;
            border-radius: 8px !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            padding: 7px 14px !important;
            transition: all 0.15s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: var(--hesh-surface-hover) !important;
            border-color: var(--hesh-border-hover) !important;
        }}

        /* Metric Cards */
        .metric-card {{
            background: var(--hesh-surface);
            border: 1px solid var(--hesh-border);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: var(--hesh-card-shadow);
            transition: all 0.2s ease;
        }}
        .metric-card:hover {{
            border-color: var(--hesh-border-hover);
            transform: translateY(-2px);
        }}
        .metric-val {{
            font-size: 26px;
            font-weight: 800;
            color: var(--hesh-text-primary);
            line-height: 1.2;
            margin-top: 4px;
        }}
        .metric-label {{
            font-size: 12px;
            font-weight: 600;
            color: var(--hesh-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Hero Landing Box */
        .hero-banner {{
            background: radial-gradient(circle at top right, rgba(56, 189, 248, 0.15), transparent 70%), var(--hesh-surface);
            border: 1px solid var(--hesh-border);
            border-radius: 16px;
            padding: 40px 32px;
            margin-bottom: 30px;
            box-shadow: var(--hesh-card-shadow);
        }}

        .feature-card {{
            background: var(--hesh-surface);
            border: 1px solid var(--hesh-border);
            border-radius: 12px;
            padding: 20px;
            height: 100%;
            transition: all 0.2s ease;
        }}
        .feature-card:hover {{
            border-color: var(--hesh-accent);
            transform: translateY(-2px);
        }}

        /* Badges */
        .saas-badge {{
            display: inline-block;
            background: var(--hesh-accent-subtle);
            color: var(--hesh-accent);
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            letter-spacing: 0.3px;
        }}
        .pro-vip-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #F59E0B 0%, #D97706 50%, #FBBF24 100%);
            color: #000000 !important;
            font-size: 10.5px;
            font-weight: 800;
            padding: 2px 9px;
            border-radius: 100px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.4);
        }}
        .pro-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #A855F7 0%, #EC4899 100%);
            color: #FFFFFF;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 100px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .free-badge {{
            display: inline-block;
            background: var(--hesh-surface-hover);
            color: var(--hesh-text-secondary);
            border: 1px solid var(--hesh-border);
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 100px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}

        /* Table Styling */
        .action-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 12.5px;
            border: 1px solid var(--hesh-border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .action-table th {{
            background: var(--hesh-surface-hover);
            color: var(--hesh-text-muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--hesh-border);
        }}
        .action-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--hesh-border);
            color: var(--hesh-text-primary);
            line-height: 1.45;
        }}
        .action-table tr:hover td {{
            background: var(--hesh-surface-hover);
        }}

        .priority-high {{ color: #F43F5E; font-weight: 700; background: var(--hesh-rose-subtle); padding: 2px 6px; border-radius: 4px; font-size: 10.5px; }}
        .priority-med {{ color: #F59E0B; font-weight: 700; background: rgba(245, 158, 11, 0.12); padding: 2px 6px; border-radius: 4px; font-size: 10.5px; }}
        .priority-low {{ color: #10B981; font-weight: 700; background: var(--hesh-emerald-subtle); padding: 2px 6px; border-radius: 4px; font-size: 10.5px; }}

        .pricing-card {{
            background: linear-gradient(180deg, rgba(56, 189, 248, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 12px;
            padding: 16px;
            margin-top: 14px;
            margin-bottom: 14px;
        }}

        /* Plaud Document-First Layout & Typography */
        .plaud-doc-container {{
            background: var(--hesh-surface);
            border: 1px solid var(--hesh-border);
            border-radius: 16px;
            padding: 36px 42px;
            margin-bottom: 24px;
            box-shadow: var(--hesh-card-shadow);
            max-width: 960px;
            margin-left: auto;
            margin-right: auto;
        }}
        .plaud-doc-header {{
            border-bottom: 1px solid var(--hesh-border);
            padding-bottom: 18px;
            margin-bottom: 24px;
        }}
        .plaud-doc-title {{
            font-size: 22px;
            font-weight: 800;
            color: var(--hesh-text-primary);
            line-height: 1.35;
            margin: 8px 0 6px 0;
        }}
        .plaud-doc-meta {{
            font-size: 12.5px;
            color: var(--hesh-text-secondary);
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
        }}
        .plaud-summary-box {{
            background: var(--hesh-surface-hover);
            border-left: 3px solid var(--hesh-accent);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 28px;
        }}
        .plaud-summary-heading {{
            font-size: 12px;
            font-weight: 800;
            color: var(--hesh-accent);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .plaud-summary-text {{
            font-size: 13.5px;
            color: var(--hesh-text-primary);
            line-height: 1.65;
            margin: 0;
        }}
        .plaud-topic-block {{
            margin-bottom: 28px;
            padding-bottom: 22px;
            border-bottom: 1px solid var(--hesh-border);
        }}
        .plaud-topic-block:last-of-type {{
            border-bottom: none;
        }}
        .plaud-topic-heading {{
            font-size: 16px;
            font-weight: 700;
            color: var(--hesh-text-primary);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .plaud-topic-num {{
            background: var(--hesh-accent-subtle);
            color: var(--hesh-accent);
            font-size: 12px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 6px;
            min-width: 24px;
            text-align: center;
        }}
        .plaud-narrative {{
            font-size: 14px;
            color: var(--hesh-text-secondary);
            line-height: 1.72;
            margin-bottom: 12px;
        }}
        .plaud-action-card {{
            background: var(--hesh-surface-hover);
            border: 1px solid var(--hesh-border);
            border-radius: 10px;
            padding: 12px 16px;
            margin-top: 10px;
        }}
        .plaud-action-heading {{
            font-size: 11px;
            font-weight: 800;
            color: var(--hesh-accent);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .plaud-action-item {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            padding: 6px 0;
            border-bottom: 1px dashed var(--hesh-border);
            font-size: 12.5px;
        }}
        .plaud-action-item:last-child {{
            border-bottom: none;
        }}
        .plaud-action-check {{
            color: var(--hesh-accent);
            font-weight: 800;
            margin-right: 6px;
            font-size: 13px;
        }}
        .plaud-action-desc {{
            color: var(--hesh-text-primary);
            flex: 1;
        }}
        .plaud-action-owner-due {{
            font-size: 11.5px;
            color: var(--hesh-text-muted);
            white-space: nowrap;
        }}
        .plaud-suggestions-box {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 14px;
            padding: 22px 26px;
            margin-top: 28px;
            margin-bottom: 16px;
        }}
        .plaud-suggestions-header {{
            font-size: 14.5px;
            font-weight: 800;
            color: #F59E0B;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .plaud-suggestion-entry {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 10px;
            color: var(--hesh-text-primary);
        }}
        .plaud-suggestion-entry:last-child {{
            margin-bottom: 0;
        }}
        .plaud-sugg-tag {{
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            white-space: nowrap;
        }}
        .plaud-sugg-unresolved {{ background: rgba(244, 63, 94, 0.15); color: #F43F5E; }}
        .plaud-sugg-gap {{ background: rgba(245, 158, 11, 0.15); color: #F59E0B; }}
        .plaud-sugg-rec {{ background: rgba(16, 185, 129, 0.15); color: #10B981; }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

apply_saas_theme(st.session_state.get("theme", "dark"))


# =============================================================================
# DATA HELPERS & PARSERS
# =============================================================================
def get_current_user_id() -> str | None:
    if st.session_state.user:
        return str(getattr(st.session_state.user, "id", ""))
    return None


def render_mindmap_diagram(mermaid_code: str):
    """Guaranteed SVG renderer using mermaid.ink with base64 encoding and theme awareness."""
    if not mermaid_code:
        return
    clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
    clean_code = clean_code.replace("&", "and")
    if not clean_code.startswith("mindmap") and not clean_code.startswith("graph"):
        clean_code = "mindmap\n  " + clean_code

    # Generate direct base64 encoded URL for mermaid.ink
    try:
        encoded_bytes = base64.b64encode(clean_code.encode("utf-8"))
        encoded_str = encoded_bytes.decode("utf-8")
        is_dark = st.session_state.get("theme", "dark") == "dark"
        bg_param = "!111726" if is_dark else "!ffffff"
        container_bg = "#111726" if is_dark else "#FFFFFF"
        border_col = "#232E48" if is_dark else "#E2E8F0"
        mermaid_url = f"https://mermaid.ink/svg/{encoded_str}?bgColor={bg_param}"

        # Render clean responsive SVG container
        st.markdown(
            f"""
            <div style="background-color: {container_bg}; border-radius: 12px; border: 1px solid {border_col}; padding: 24px; text-align: center; overflow-x: auto; min-height: 400px; display: flex; align-items: center; justify-content: center; box-shadow: var(--hesh-card-shadow);">
                <img src="{mermaid_url}" alt="Plaud Tree Mind Map" style="max-width: 100%; height: auto; filter: drop-shadow(0px 4px 16px rgba(0,0,0,0.15));" />
            </div>
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Error rendering mind map: {e}")
        st.code(clean_code, language="mermaid")



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
@st.dialog("⚡ New Recording / Upload")
def new_recording_dialog():
    user_id = get_current_user_id()
    usage = get_user_usage(user_id, plan_tier=st.session_state.plan_tier)

    if not usage["can_upload"]:
        st.error("⚠️ Free monthly limit reached (3/3 meetings). Please upgrade to Pro in the sidebar for unlimited processing.")
        return

    tab_upload, tab_voice = st.tabs(["📤 Upload Audio/Video", "🎙️ Browser Voice Memo"])

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Upload file",
            type=["mp3", "wav", "m4a", "mp4", "aac", "ogg", "flac"],
            label_visibility="collapsed"
        )

        col_t1, col_t2 = st.columns([1.2, 1.2])
        with col_t1:
            template_mode = st.selectbox(
                "📋 Intelligence Summary Template",
                ["🏢 Executive Meeting", "🎓 Academic Lecture", "💡 Brainstorm / General"],
                index=0
            )
        with col_t2:
            model_mode = st.selectbox(
                "⚡ AI Intelligence Engine",
                ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
                index=0
            )

        tpl_key = "executive"
        if "Academic" in template_mode:
            tpl_key = "academic"
        elif "Brainstorm" in template_mode:
            tpl_key = "brainstorm"

        if uploaded_file is not None:
            if st.button("🚀 Transcribe & Analyze with Groq + Gemini", type="primary", use_container_width=True):
                save_path = INPUTS_DIR / uploaded_file.name
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                with st.spinner("⚡ Transcribing on Groq LPUs (<1s) + Extracting Intelligence with Gemini..."):
                    try:
                        result = process_meeting_file_cloud(
                            save_path,
                            model_choice=model_mode,
                            user_id=user_id,
                            template_type=tpl_key
                        )
                        sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                        st.session_state.active_session_id = f"session_{sid}"
                        st.toast("✅ Meeting synchronized to Cloud!", icon="🚀")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Processing failed: {ex}")

    with tab_voice:
        st.markdown("<div style='font-size:12.5px; color:var(--hesh-text-secondary); margin-bottom:12px;'>Record live voice notes or speech directly from your browser microphone:</div>", unsafe_allow_html=True)
        col_rec_btn, col_rec_action = st.columns([1.0, 1.4])
        with col_rec_btn:
            recorded_bytes = audio_recorder(
                pause_threshold=2.5,
                text="Record Memo",
                recording_color="#F43F5E",
                neutral_color="#38BDF8",
                icon_size="2x"
            )
        with col_rec_action:
            if recorded_bytes:
                st.audio(recorded_bytes, format="audio/wav")
                if st.button("🚀 Process Voice Memo", type="primary", use_container_width=True):
                    memo_filename = f"voice_memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    memo_path = INPUTS_DIR / memo_filename
                    with open(memo_path, "wb") as f:
                        f.write(recorded_bytes)
                    with st.spinner("Processing voice recording..."):
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
                            st.toast("✅ Voice memo transcribed!", icon="🎙️")
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
                    user_id = get_current_user_id()
                    rename_session_record(session_id, new_title.strip(), user_id=user_id)
                    st.toast("Title updated successfully!", icon="✅")
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
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 18px;">
            <span style="font-size: 26px;">🎙️</span>
            <div>
                <div style="font-weight: 800; font-size: 18px; color: var(--hesh-text-primary); letter-spacing: -0.5px;">Hesh-rec</div>
                <div style="font-size: 11px; color: var(--hesh-text-muted); font-weight: 500;">AI Meeting & Speech Studio</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 1. USER AUTHENTICATION & MULTI-TENANCY PANEL
        # ---------------------------------------------------------------------
        if st.session_state.user:
            user_email = st.session_state.user.email if hasattr(st.session_state.user, "email") else st.session_state.user_email
            
            if st.session_state.get("is_admin", False):
                name_tag = "👑 Hesham (Admin)"
                role_sub = '<span style="color:#F59E0B; font-weight:800; font-size:10.5px; letter-spacing:0.5px;">⚡ SUPER ADMIN</span>'
                plan_badge = '<span class="pro-vip-badge">👑 VIP PRO UNLIMITED</span>'
            elif st.session_state.get("is_vip", False):
                name_tag = f"👤 {user_email[:20]}"
                role_sub = '<span style="color:var(--hesh-text-muted); font-size:11px;">Tenant Cloud Isolated</span>'
                plan_badge = '<span class="pro-vip-badge">👑 PRO VIP</span>'
            elif st.session_state.plan_tier == "pro":
                name_tag = f"👤 {user_email[:20]}"
                role_sub = '<span style="color:var(--hesh-text-muted); font-size:11px;">Tenant Cloud Isolated</span>'
                plan_badge = '<span class="pro-badge">PRO PLAN</span>'
            else:
                name_tag = f"👤 {user_email[:20]}"
                role_sub = '<span style="color:var(--hesh-text-muted); font-size:11px;">Tenant Cloud Isolated</span>'
                plan_badge = '<span class="free-badge">FREE PLAN</span>'
            
            st.markdown(f"""
            <div style="background: var(--hesh-surface); border: 1px solid var(--hesh-border); border-radius: 10px; padding: 12px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 12.5px; font-weight: 700; color: var(--hesh-text-primary);">{name_tag}</span>
                    {plan_badge}
                </div>
                <div>{role_sub}</div>
            </div>
            """, unsafe_allow_html=True)

            # Promo Code Redeemer for Logged In User
            if not st.session_state.get("is_vip", False) and st.session_state.plan_tier == "free":
                st.markdown("<div style='font-size: 11px; font-weight: 700; color: var(--hesh-text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;'>🎁 Redeem Promo Code</div>", unsafe_allow_html=True)
                col_code, col_redeem = st.columns([1.5, 1.0])
                with col_code:
                    promo_input = st.text_input("Promo Code", key="input_promo_code", placeholder="Code (e.g. Hesh)", label_visibility="collapsed")
                with col_redeem:
                    if st.button("Redeem", key="btn_redeem_promo", type="secondary", use_container_width=True):
                        if promo_input.strip().lower() in ["hesh", "alrigi"]:
                            st.session_state.plan_tier = "pro"
                            st.session_state.is_vip = True
                            save_persistent_session(get_current_user_id() or "vip_user", st.session_state.user_email, "pro", True, st.session_state.get("is_admin", False))
                            st.toast("🎉 PRO Plan Activated via VIP Code 'Hesh'!", icon="👑")
                            time.sleep(0.4)
                            st.rerun()
                        else:
                            st.error("Invalid promo code.")

            if st.button("🚪 Sign Out", key="btn_signout", type="secondary", use_container_width=True):
                auth_sign_out()
                clear_persistent_session()
                st.session_state.user = None
                st.session_state.user_email = ""
                st.session_state.plan_tier = "free"
                st.session_state.is_vip = False
                st.session_state.is_admin = False
                st.session_state.active_session_id = None
                st.toast("Signed out successfully.", icon="👋")
                time.sleep(0.3)
                st.rerun()

        else:
            st.markdown("<div style='font-size: 12.5px; font-weight: 700; color: var(--hesh-accent); margin-bottom: 8px;'>🔐 Account & Workspace</div>", unsafe_allow_html=True)
            auth_tab_in, auth_tab_up, auth_tab_promo = st.tabs(["Sign In", "Register", "VIP Promo"])

            with auth_tab_in:
                login_email = st.text_input("Username or Email", key="in_email", placeholder="Hesh or user@company.com")
                login_pwd = st.text_input("Password", type="password", key="in_pwd")
                if st.button("Sign In", type="primary", use_container_width=True):
                    if login_email and login_pwd:
                        # 1. Master Admin Bypass Check
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
                            st.toast("👑 Welcome Master Admin Hesham!", icon="🎉")
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
                                    st.toast("Welcome back!", icon="🚀")
                                    time.sleep(0.3)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        st.warning("Please enter your username/email and password.")

            with auth_tab_up:
                up_email = st.text_input("Email", key="up_email", placeholder="newuser@company.com")
                up_pwd = st.text_input("Password (min 6 chars)", type="password", key="up_pwd")
                if st.button("Create Account", type="primary", use_container_width=True):
                    if up_email and up_pwd:
                        with st.spinner("Creating account..."):
                            success, user_obj, msg = auth_sign_up(up_email, up_pwd)
                            if success:
                                st.session_state.user = user_obj
                                st.session_state.user_email = up_email
                                uid = getattr(user_obj, "id", up_email)
                                save_persistent_session(uid, up_email, "free", False, False)
                                st.toast("Account created successfully!", icon="🎉")
                                time.sleep(0.3)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.warning("Please provide valid details.")

            with auth_tab_promo:
                st.markdown("<div style='font-size:12px; color:var(--hesh-text-secondary); margin-bottom:8px;'>Enter your VIP Promo Code:</div>", unsafe_allow_html=True)
                guest_promo = st.text_input("Promo Code", key="guest_promo_input", placeholder="Code (e.g. Hesh)", label_visibility="collapsed")
                if st.button("Redeem VIP Access", key="btn_guest_redeem", type="primary", use_container_width=True):
                    if guest_promo.strip().lower() in ["hesh", "alrigi"]:
                        st.session_state.user_email = "vip_guest@heshrec.ai"
                        st.session_state.user = type("VIPUser", (), {"id": "vip_guest", "email": "vip_guest@heshrec.ai"})()
                        st.session_state.plan_tier = "pro"
                        st.session_state.is_vip = True
                        save_persistent_session("vip_guest", "vip_guest@heshrec.ai", "pro", True, False)
                        st.toast("🎉 PRO Plan Activated via VIP Code 'Hesh'!", icon="👑")
                        time.sleep(0.4)
                        st.rerun()
                    else:
                        st.error("Invalid promo code.")

        st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 14px 0;'>", unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # 2. PRIMARY ACTION & WORKSPACE NAVIGATION
        # ---------------------------------------------------------------------
        if st.session_state.user:
            if st.button("➕ New Recording / Upload", type="primary", use_container_width=True):
                new_recording_dialog()

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 11px; font-weight: 700; color: var(--hesh-text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>Navigation</div>", unsafe_allow_html=True)

            nav_dash = st.button("📊 Dashboard", key="nav_btn_dash", use_container_width=True, type="primary" if st.session_state.current_nav == "dashboard" and st.session_state.active_session_id is None else "secondary")
            if nav_dash:
                st.session_state.current_nav = "dashboard"
                st.session_state.active_session_id = None
                st.rerun()

            nav_recents = st.button("📁 Recent Summaries", key="nav_btn_recents", use_container_width=True, type="primary" if st.session_state.current_nav == "recents" and st.session_state.active_session_id is None else "secondary")
            if nav_recents:
                st.session_state.current_nav = "recents"
                st.session_state.active_session_id = None
                st.rerun()

            nav_actions = st.button("📋 Action Items Tracker", key="nav_btn_actions", use_container_width=True, type="primary" if st.session_state.current_nav == "actions" and st.session_state.active_session_id is None else "secondary")
            if nav_actions:
                st.session_state.current_nav = "actions"
                st.session_state.active_session_id = None
                st.rerun()

            nav_export = st.button("📦 Export Center", key="nav_btn_export", use_container_width=True, type="primary" if st.session_state.current_nav == "export" and st.session_state.active_session_id is None else "secondary")
            if nav_export:
                st.session_state.current_nav = "export"
                st.session_state.active_session_id = None
                st.rerun()

            st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 14px 0;'>", unsafe_allow_html=True)

            # -----------------------------------------------------------------
            # 3. PAST SESSIONS HISTORY LIST (QUICK ACCESS)
            # -----------------------------------------------------------------
            sessions = load_user_sessions()
            if sessions:
                st.markdown("<div style='font-size: 11px; font-weight: 700; color: var(--hesh-text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>Past Sessions History</div>", unsafe_allow_html=True)
                for s in sessions[:5]:
                    btn_type = "primary" if st.session_state.active_session_id == s["id"] else "secondary"
                    short_title = s["title"][:22] + "..." if len(s["title"]) > 22 else s["title"]
                    if st.button(f"🎙️ {short_title}", key=f"side_sess_{s['id']}", use_container_width=True, type=btn_type):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()

            st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 14px 0;'>", unsafe_allow_html=True)

            # -----------------------------------------------------------------
            # 4. FREEMIUM USAGE & QUOTA BAR
            # -----------------------------------------------------------------
            user_id = get_current_user_id()
            usage = get_user_usage(user_id, plan_tier=st.session_state.plan_tier)
            st.markdown("<div style='font-size: 11px; font-weight: 700; color: var(--hesh-text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>Monthly Storage / Quota</div>", unsafe_allow_html=True)

            if not st.session_state.get("is_vip", False) and st.session_state.plan_tier == "free":
                st.markdown(f"""
                <div style="background: var(--hesh-surface); border: 1px solid var(--hesh-border); border-radius: 8px; padding: 10px; margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:600; color:var(--hesh-text-primary); margin-bottom:4px;">
                        <span>Free Quota</span>
                        <span>{usage['used_count']} / {usage['limit']} Audio Files</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(usage["percent"] / 100.0)

                # Upgrade to Pro Card
                st.markdown("""
                <div class="pricing-card">
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                        <span style="font-size:13px; font-weight:800; color:var(--hesh-accent);">⚡ Hesh-rec Pro</span>
                        <span style="font-size:12px; font-weight:700; color:#A855F7;">$19/mo</span>
                    </div>
                    <div style="font-size:11px; color:var(--hesh-text-secondary); line-height:1.45; margin-bottom:10px;">
                        • Unlimited audio & video meetings<br>
                        • Groq Whisper-large-v3 priority queue<br>
                        • Full Supabase Cloud Sync & Export Suite
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("✨ Upgrade to Pro ($19/mo)", key="btn_upgrade_pro", type="primary", use_container_width=True):
                    st.session_state.plan_tier = "pro"
                    save_persistent_session(get_current_user_id() or "user", st.session_state.user_email, "pro", st.session_state.is_vip, st.session_state.get("is_admin", False))
                    st.toast("🎉 Upgraded to Hesh-rec Pro! Enjoy unlimited processing.", icon="✨")
                    time.sleep(0.3)
                    st.rerun()

            else:
                vip_label = "👑 PRO VIP UNLIMITED" if st.session_state.get("is_vip", False) else "PRO SUBSCRIBER"
                badge_class = "pro-vip-badge" if st.session_state.get("is_vip", False) else "pro-badge"
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(56, 189, 248, 0.1) 100%); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 12px; text-align:center;">
                    <span class="{badge_class}">{vip_label}</span>
                    <div style="font-size:12px; font-weight:600; color:var(--hesh-text-primary); margin-top:6px;">Unlimited Cloud Processing</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Switch to Free Tier", key="btn_downgrade", type="secondary", use_container_width=True):
                    st.session_state.plan_tier = "free"
                    st.session_state.is_vip = False
                    save_persistent_session(get_current_user_id() or "user", st.session_state.user_email, "free", False, False)
                    st.rerun()

        # Theme Switcher
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        theme_icon = "🌙 Dark Mode" if st.session_state.theme == "dark" else "☀️ Light Mode"
        if st.button(theme_icon, key="sidebar_theme_toggle", type="secondary", use_container_width=True):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()


# =============================================================================
# GUEST LANDING PAGE (PROTECTED WORKSPACE)
# =============================================================================
def render_landing_page():
    # Hero Section
    st.markdown("""
    <div class="hero-banner">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
            <span class="saas-badge">⚡ Commercial AI Meeting & Speech Intelligence</span>
        </div>
        <h1 style="font-size: 34px; font-weight: 800; line-height: 1.25; margin-bottom: 14px; max-width: 820px;">
            Turn any Audio or Meeting into Actionable Intelligence in Seconds
        </h1>
        <p style="font-size: 15px; color: var(--hesh-text-secondary); line-height: 1.6; max-width: 720px; margin-bottom: 24px;">
            Hesh-rec combines high-speed <b>Groq Whisper-large-v3</b> audio transcription (<1s latency) with <b>Gemini 2.5 Flash</b> intelligence extraction. Generate executive summaries, discussion pillars, strict action item matrices, visual mindmaps, and chat with your recordings interactively.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_demo, col_auth = st.columns([1.2, 1.2])
    with col_demo:
        st.markdown("<div style='font-size:14px; font-weight:700; color:var(--hesh-text-primary); margin-bottom:8px;'>✨ Try Live Interactive Demo</div>", unsafe_allow_html=True)
        if st.button("🚀 Explore Sample Meeting Workspace (Guest Demo)", type="primary", use_container_width=True):
            st.session_state.user_email = "guest_demo@heshrec.ai"
            st.session_state.current_nav = "dashboard"
            st.session_state.user = type("GuestUser", (), {"id": "guest_demo", "email": "guest_demo@heshrec.ai"})()
            save_persistent_session("guest_demo", "guest_demo@heshrec.ai", "free", False, False)
            st.rerun()

    with col_auth:
        st.markdown("<div style='font-size:14px; font-weight:700; color:var(--hesh-text-primary); margin-bottom:8px;'>🔐 Private Multi-Tenant Workspace</div>", unsafe_allow_html=True)
        st.info("👈 Sign In or Register in the sidebar to access your private cloud workspace and upload audio.")

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # 3 Core Template Showcases
    st.markdown("<h2 style='font-size: 20px; font-weight: 800; margin-bottom: 14px;'>Tailored AI Summary Templates</h2>", unsafe_allow_html=True)
    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size: 28px; margin-bottom: 8px;">🏢</div>
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Executive Meeting</div>
            <div style="font-size: 12.5px; color: var(--hesh-text-secondary); line-height: 1.55;">
                Extracts strategic purpose, discussion pillars with timestamps, strict action items table with owners & deadlines, and approved decisions vs reversals.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_t2:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size: 28px; margin-bottom: 8px;">🎓</div>
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Academic Lecture</div>
            <div style="font-size: 12.5px; color: var(--hesh-text-secondary); line-height: 1.55;">
                Extracts core lecture thesis, foundational theoretical concepts, glossary of key terms, and comprehensive exam review questions.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_t3:
        st.markdown("""
        <div class="feature-card">
            <div style="font-size: 28px; margin-bottom: 8px;">💡</div>
            <div style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Brainstorm & Ideation</div>
            <div style="font-size: 12.5px; color: var(--hesh-text-secondary); line-height: 1.55;">
                Captures creative breakthroughs, ideation tracks, feasibility assessment matrices, and immediate experiment roadmaps.
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
    <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; font-weight: 800; margin-bottom: 4px;">Executive Dashboard</h1>
        <div style="font-size: 13px; color: var(--hesh-text-muted);">Real-time meeting intelligence overview and rapid cloud transcription</div>
    </div>
    """, unsafe_allow_html=True)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Total Meetings</div><div class="metric-val">{len(sessions)}</div></div>""", unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Spoken Time Analyzed</div><div class="metric-val">{total_duration_mins}m</div></div>""", unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Action Deliverables</div><div class="metric-val" style="color: #F43F5E;">{total_actions}</div></div>""", unsafe_allow_html=True)
    with col_m4:
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Decisions Agreed</div><div class="metric-val" style="color: #10B981;">{total_decisions}</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Main Upload & Audio Processing Studio Card
    st.markdown("""
    <div style="background: var(--hesh-surface); border: 1px solid var(--hesh-border); border-radius: 12px; padding: 22px; margin-bottom: 24px; box-shadow: var(--hesh-card-shadow);">
        <div style="font-size: 16px; font-weight: 700; color: var(--hesh-text-primary); margin-bottom: 4px;">⚡ Upload Audio / Video or Record Voice Memo</div>
        <div style="font-size: 12.5px; color: var(--hesh-text-muted); margin-bottom: 16px;">Powered by Groq Whisper-large-v3 (<1s transcription) + Gemini 2.5 Flash + Supabase Cloud Sync</div>
    </div>
    """, unsafe_allow_html=True)

    tab_up, tab_voice = st.tabs(["📤 File Upload (.mp3, .wav, .m4a, .mp4)", "🎙️ Instant Browser Voice Memo"])

    with tab_up:
        uploaded_file = st.file_uploader("Drop audio files here", type=["mp3", "wav", "m4a", "mp4", "aac", "ogg", "flac"], label_visibility="collapsed")
        col_opt1, col_opt2 = st.columns([1.2, 1.2])
        with col_opt1:
            template_mode = st.selectbox(
                "📋 Intelligence Summary Template",
                ["🏢 Executive Meeting", "🎓 Academic Lecture", "💡 Brainstorm / General"],
                key="dash_tpl_select",
                index=0
            )
        with col_opt2:
            model_mode = st.selectbox(
                "⚡ Gemini Intelligence Engine",
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
                st.error("⚠️ Free monthly limit reached (3/3 meetings). Please upgrade to Pro in the sidebar for unlimited processing.")
            else:
                if st.button("🚀 Transcribe & Analyze", type="primary", use_container_width=True):
                    save_path = INPUTS_DIR / uploaded_file.name
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    with st.spinner("⚡ Processing on Groq LPUs + Gemini Intelligence + Supabase Cloud Sync..."):
                        try:
                            result = process_meeting_file_cloud(
                                save_path,
                                model_choice=model_mode,
                                user_id=user_id,
                                template_type=tpl_key
                            )
                            sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                            st.session_state.active_session_id = f"session_{sid}"
                            st.toast("✅ Meeting synchronized to Cloud!", icon="🚀")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Processing failed: {ex}")

    with tab_voice:
        st.markdown("<div style='font-size: 13px; color: var(--hesh-text-secondary); line-height: 1.5; margin-bottom: 14px;'>Record thoughts, executive notes, or live audio directly from your browser:</div>", unsafe_allow_html=True)
        col_rec_btn, col_rec_action = st.columns([1.0, 1.4])
        with col_rec_btn:
            recorded_bytes = audio_recorder(pause_threshold=2.5, text="Record Voice Memo", recording_color="#F43F5E", neutral_color="#38BDF8", icon_size="2x")
        with col_rec_action:
            if recorded_bytes:
                st.audio(recorded_bytes, format="audio/wav")
                if not usage["can_upload"]:
                    st.error("⚠️ Free limit reached. Upgrade to Pro for unlimited recording.")
                else:
                    if st.button("🚀 Transcribe & Analyze Memo", type="primary", use_container_width=True):
                        memo_filename = f"voice_memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                        memo_path = INPUTS_DIR / memo_filename
                        with open(memo_path, "wb") as f:
                            f.write(recorded_bytes)
                        with st.spinner("Transcribing with Groq Whisper & Gemini..."):
                            try:
                                result = process_meeting_file_cloud(memo_path, custom_title="Voice Memo Recording", model_choice=st.session_state.model_choice, user_id=user_id, template_type="executive")
                                sid = result.get("metadata", {}).get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
                                st.session_state.active_session_id = f"session_{sid}"
                                st.toast("✅ Voice memo transcribed!", icon="🎙️")
                                time.sleep(0.3)
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Analysis failed: {ex}")

    # Latest Meetings
    st.markdown("<div style='font-size: 15px; font-weight: 700; color: var(--hesh-text-primary); margin-top: 24px; margin-bottom: 12px;'>📁 Latest Sessions</div>", unsafe_allow_html=True)
    if not sessions:
        st.info("No recorded meetings yet. Upload an audio recording above to generate your first intelligence report.")
    else:
        for s in sessions[:3]:
            with st.container():
                col_i, col_info, col_act = st.columns([0.3, 3.2, 1.0])
                with col_i:
                    st.markdown("<div style='font-size: 22px; padding-top: 6px;'>🎙️</div>", unsafe_allow_html=True)
                with col_info:
                    st.markdown(f"""
                    <div style="font-weight: 600; font-size: 14px; color: var(--hesh-text-primary);">{s['title']}</div>
                    <div style="font-size: 11.5px; color: var(--hesh-text-muted);">⏱️ {s['duration']} • 📅 {s['date_display']} • ⚡ {s['action_count']} Action Items</div>
                    """, unsafe_allow_html=True)
                with col_act:
                    if st.button("Open Report ↗️", key=f"quick_open_{s['id']}", type="secondary", use_container_width=True):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()


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
            <h1 style="font-size: 22px; font-weight: 800; margin-bottom: 2px;">Recent Summaries</h1>
            <div style="font-size: 12.5px; color: var(--hesh-text-muted);">All cloud-synchronized meeting intelligence archives</div>
        </div>
        """, unsafe_allow_html=True)
    with col_search:
        st.session_state.search_query = st.text_input("Search", placeholder="🔍 Search meetings, pillars, or actions...", label_visibility="collapsed")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    if st.session_state.search_query.strip():
        q = st.session_state.search_query.lower()
        sessions = [
            s for s in sessions 
            if q in s["title"].lower() or any(q in t.lower() for t in s["tags"]) or q in json.dumps(s["data"]).lower()
        ]

    if not sessions:
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px; background: var(--hesh-surface); border: 1px dashed var(--hesh-border); border-radius: 12px;">
            <span style="font-size: 38px;">📁</span>
            <div style="font-size: 15px; font-weight: 600; color: var(--hesh-text-primary); margin-top: 10px;">No meeting records found</div>
            <div style="font-size: 12.5px; color: var(--hesh-text-muted); margin-top: 4px;">Upload an audio file in the Dashboard to get started.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    for s in sessions:
        with st.container():
            col_icon, col_info, col_actions = st.columns([0.35, 3.2, 1.45])

            with col_icon:
                st.markdown("<div style='font-size: 26px; padding-top: 6px;'>🎙️</div>", unsafe_allow_html=True)

            with col_info:
                source_badge = f'<span class="saas-badge">☁️ {s.get("source", "Cloud")}</span>'
                st.markdown(f"""
                <div style="font-size: 14.5px; font-weight: 700; color: var(--hesh-text-primary); margin-bottom: 3px;">{s['title']}</div>
                <div style="display:flex; align-items:center; gap: 10px; font-size: 12px; color: var(--hesh-text-muted);">
                    <span>⏱️ {s['duration']}</span>
                    <span>📅 {s['date_display']}</span>
                    <span>⚡ {s['action_count']} Actions</span>
                    <span>📌 {s['decision_count']} Decisions</span>
                    {source_badge}
                    {' '.join([f'<span class="saas-badge">{t}</span>' for t in s['tags']])}
                </div>
                """, unsafe_allow_html=True)

            with col_actions:
                col_btn_open, col_btn_ren, col_btn_del = st.columns([1.1, 0.5, 0.5])
                with col_btn_open:
                    if st.button("Open ↗️", key=f"open_{s['id']}", type="secondary", use_container_width=True):
                        st.session_state.active_session_id = s["id"]
                        st.rerun()
                with col_btn_ren:
                    if st.button("✏️", key=f"ren_{s['id']}", help="Rename Title", type="secondary", use_container_width=True):
                        st.session_state.rename_target = (s["raw_id"], s["title"])
                with col_btn_del:
                    if st.button("🗑️", key=f"del_{s['id']}", help="Delete Meeting", type="secondary", use_container_width=True):
                        try:
                            delete_session_record(s["raw_id"], user_id=user_id)
                            st.toast("Session deleted.", icon="🗑️")
                            time.sleep(0.3)
                            st.rerun()
                        except Exception:
                            pass

            st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 8px 0;'>", unsafe_allow_html=True)

    if st.session_state.rename_target:
        rename_meeting_dialog(st.session_state.rename_target[0], st.session_state.rename_target[1])


# =============================================================================
# VIEW 3: ACTION ITEMS TRACKER
# =============================================================================
def render_action_tracker_view():
    sessions = load_user_sessions()

    st.markdown("""
    <div style="margin-bottom: 18px;">
        <h1 style="font-size: 22px; font-weight: 800; margin-bottom: 2px;">Action Items Tracker</h1>
        <div style="font-size: 12.5px; color: var(--hesh-text-muted);">Aggregated matrix of all tasks, commitments, and deadlines across meetings</div>
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
        st.info("No action items found across your meetings.")
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

    st.markdown(f"<div style='font-size: 12px; color: var(--hesh-text-muted); margin-bottom: 10px;'>Showing {len(filtered_actions)} actionable deliverables</div>", unsafe_allow_html=True)

    rows_html = []
    for a in filtered_actions:
        deliverable = a.get("description") or a.get("task") or "Task"
        owner = a.get("assignee") or a.get("owner") or "Team"
        prio = (a.get("priority") or "MED").upper()
        due = a.get("due_date") or "Next Sprint"
        notes = a.get("notes") or a.get("acceptance_criteria") or "—"
        meeting = a.get("meeting_title", "Meeting")

        prio_class = "priority-med"
        if "HIGH" in prio:
            prio_class = "priority-high"
        elif "LOW" in prio:
            prio_class = "priority-low"

        rows_html.append(f"""
        <tr>
            <td style="font-weight: 600; color: var(--hesh-text-primary);">{deliverable}</td>
            <td style="color: var(--hesh-accent); font-weight: 600;">{owner}</td>
            <td><span class="{prio_class}">{prio}</span></td>
            <td style="color: var(--hesh-text-muted); font-size: 11.5px;">{due}</td>
            <td style="color: var(--hesh-text-secondary); font-size: 11.5px;">{notes}</td>
            <td style="color: var(--hesh-text-muted); font-size: 11px;">{meeting}</td>
        </tr>
        """)

    table_html = f"""
    <table class="action-table">
        <thead>
            <tr>
                <th style="width: 32%;">Task Deliverable</th>
                <th style="width: 14%;">Owner</th>
                <th style="width: 10%;">Priority</th>
                <th style="width: 12%;">Due Date</th>
                <th style="width: 18%;">Acceptance Notes</th>
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
    <div style="margin-bottom: 18px;">
        <h1 style="font-size: 22px; font-weight: 800; margin-bottom: 2px;">Export Center</h1>
        <div style="font-size: 12.5px; color: var(--hesh-text-muted);">Batch download meeting transcripts, executive briefs, printable HTML/PDF, and JSON data</div>
    </div>
    """, unsafe_allow_html=True)

    if not sessions:
        st.info("No meeting sessions available to export.")
        return

    for s in sessions:
        with st.container():
            col_info, col_md, col_txt, col_html, col_json = st.columns([2.0, 0.8, 0.8, 0.9, 0.8])
            with col_info:
                st.markdown(f"""
                <div style="font-size: 14px; font-weight: 700; color: var(--hesh-text-primary);">{s['title']}</div>
                <div style="font-size: 11.5px; color: var(--hesh-text-muted);">Processed on {s['date_display']} • Duration: {s['duration']}</div>
                """, unsafe_allow_html=True)

            raw_md = s["data"].get("raw_markdown", "# Meeting Report")
            full_txt = s["data"].get("full_transcript_text", raw_md)
            printable_html = generate_printable_html(s["data"])

            with col_md:
                st.download_button("📄 .MD", data=raw_md, file_name=f"{s['id']}.md", mime="text/markdown", key=f"exp_md_{s['id']}", use_container_width=True)
            with col_txt:
                st.download_button("📝 .TXT", data=full_txt, file_name=f"{s['id']}.txt", mime="text/plain", key=f"exp_txt_{s['id']}", use_container_width=True)
            with col_html:
                st.download_button("🖨️ PDF/HTML", data=printable_html, file_name=f"{s['id']}_report.html", mime="text/html", key=f"exp_html_{s['id']}", use_container_width=True)
            with col_json:
                st.download_button("📦 .JSON", data=json.dumps(s["data"], indent=2), file_name=f"{s['id']}.json", mime="application/json", key=f"exp_json_{s['id']}", use_container_width=True)

            st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 8px 0;'>", unsafe_allow_html=True)


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

    # Header Title Banner & Export Suite
    col_h_left, col_h_right = st.columns([2.8, 2.0])
    with col_h_left:
        st.markdown(f"""
        <div style="margin-bottom: 16px;">
            <div style="font-size: 24px; font-weight: 800; color: var(--hesh-text-primary); letter-spacing: -0.5px; margin-bottom: 6px;">
                {title}
            </div>
            <div style="display: flex; gap: 10px; font-size: 12px; color: var(--hesh-text-muted); font-weight: 500;">
                <span>⏱️ {duration}</span>
                <span>•</span>
                <span>📅 {date_str}</span>
                <span>•</span>
                <span>⚡ {model_name}</span>
                <span class="saas-badge">{tpl_name} Template</span>
                {' '.join([f'<span class="saas-badge">{t}</span>' for t in active_item['tags']])}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_h_right:
        col_back, col_md, col_pdf, col_json = st.columns([0.8, 0.7, 0.9, 0.7])
        raw_md = data.get("raw_markdown", "# Meeting Report")
        printable_html = generate_printable_html(data)

        with col_back:
            if st.button("← Back", key="btn_back_detail", type="secondary", use_container_width=True):
                st.session_state.active_session_id = None
                st.rerun()
        with col_md:
            st.download_button("📄 .MD", data=raw_md, file_name=f"{session_id}.md", mime="text/markdown", use_container_width=True)
        with col_pdf:
            st.download_button("🖨️ PDF View", data=printable_html, file_name=f"{session_id}_report.html", mime="text/html", use_container_width=True)
        with col_json:
            st.download_button("📦 .JSON", data=json.dumps(data, indent=2), file_name=f"{session_id}.json", mime="application/json", use_container_width=True)

    st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin-bottom: 16px;'>", unsafe_allow_html=True)

    # 5 Dedicated Tabs
    tab_summary, tab_actions, tab_mindmap, tab_transcript, tab_chat = st.tabs([
        "📊 Executive Summary",
        "📋 Action Items Tracker",
        "🧠 Interactive Mind Map",
        "🗣️ Diarized Transcript & Synced Player",
        "💬 Chat with Hesh Rec Bot"
    ])

    user_id = get_current_user_id()

    # -------------------------------------------------------------------------
    # TAB 1: EXECUTIVE SUMMARY & PILLARS (CLEAN DENSITY)
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # TAB 1: EXECUTIVE SUMMARY & NARRATIVE (PLAUD CLEAN DOCUMENT LAYOUT)
    # -------------------------------------------------------------------------
    with tab_summary:
        exec_brief = data.get("executive_brief", [])
        topics = data.get("numbered_topics", []) or data.get("discussion_pillars", [])
        ai_suggestions = data.get("ai_suggestions", {})
        all_actions = data.get("action_items", [])
        
        # 1. Executive Summary HTML
        summary_paragraphs = []
        for p in exec_brief:
            clean_p = p.lstrip("•*- ").strip()
            clean_p = re.sub(r"^>\s*[•\-]?\s*", "", clean_p)
            clean_p = re.sub(r"^\*\*(?:Meeting Purpose|Key Decisions Taken|Critical Highlights|Strategic Purpose|Core Thesis)[^\*:]*:\*\*\s*", "", clean_p)
            clean_p = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_p).strip()
            if clean_p:
                summary_paragraphs.append(f"<p class='plaud-summary-text' style='margin-bottom:6px;'>• {clean_p}</p>")
        
        exec_summary_html = ""
        if summary_paragraphs:
            exec_summary_html = f"""
            <div class="plaud-summary-box">
                <div class="plaud-summary-heading">
                    <span>⚡ Executive Summary</span>
                </div>
                {''.join(summary_paragraphs)}
            </div>
            """

        # 2. Numbered Topics + Per-Topic Narrative + Inline Action Items
        topics_html_list = []
        for idx, t in enumerate(topics):
            t_num = t.get("index", idx + 1)
            raw_title = t.get("title", f"Topic {t_num}")
            clean_title = re.sub(r"^\d+\.\s*", "", raw_title).strip()
            
            # Clean narrative text of all boilerplate labels
            narrative = t.get("narrative") or t.get("details", "")
            narrative_lines = []
            for line in str(narrative).splitlines():
                l = line.strip()
                if not l or l.startswith("---") or l.startswith("#"):
                    continue
                clean_l = re.sub(r"^\*\*(?:Core Topic & Focus|Key Arguments & Perspectives|Key Takeaways & Points|Consensus & Outcome|Context & Objective|Context|Objective|Speaker Perspective|[A-Z][a-z]+'s Perspective)[^\*:]*:\*\*\s*", "", l)
                clean_l = re.sub(r"^[-*•]\s*\*\*[^*]+:\*\*\s*", "", clean_l)
                clean_l = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_l).strip()
                if clean_l:
                    narrative_lines.append(clean_l)
            clean_narrative = " ".join(narrative_lines)
            if not clean_narrative:
                clean_narrative = "The discussion covered key technical and operational priorities with agreed consensus across stakeholders."

            # Inline Action Items
            t_actions = t.get("action_items", [])
            if not t_actions and all_actions:
                # Match relevant global actions by topic title or index
                t_actions = [a for a in all_actions if f"Topic {t_num}" in a.get("notes", "") or clean_title.lower() in a.get("notes", "").lower()]
            
            actions_markup = ""
            if t_actions:
                action_rows = []
                for a in t_actions:
                    a_desc = a.get("description") or a.get("task") or "Deliverable"
                    a_owner = a.get("assignee") or a.get("owner") or "Team"
                    a_due = a.get("due_date") or "Next Sprint"
                    a_done = a.get("status") == "completed"
                    check_icon = "☑" if a_done else "☐"
                    desc_style = "text-decoration: line-through; opacity: 0.65;" if a_done else ""

                    action_rows.append(f"""
                    <div class="plaud-action-item">
                        <div style="display:flex; align-items:flex-start; flex:1;">
                            <span class="plaud-action-check">{check_icon}</span>
                            <span class="plaud-action-desc" style="{desc_style}">{a_desc}</span>
                        </div>
                        <div class="plaud-action-owner-due">
                            <em>{a_owner}</em> &nbsp;•&nbsp; <span>{a_due}</span>
                        </div>
                    </div>
                    """)

                actions_markup = f"""
                <div class="plaud-action-card">
                    <div class="plaud-action-heading">Action Items</div>
                    {''.join(action_rows)}
                </div>
                """

            topics_html_list.append(f"""
            <div class="plaud-topic-block">
                <div class="plaud-topic-heading">
                    <span class="plaud-topic-num">{t_num}</span>
                    <span>{clean_title}</span>
                </div>
                <div class="plaud-narrative">{clean_narrative}</div>
                {actions_markup}
            </div>
            """)

        # 3. Dedicated AI Suggestions Callout Box
        sugg_entries = []
        if isinstance(ai_suggestions, dict):
            for u in ai_suggestions.get("unresolved", []):
                sugg_entries.append(f"""
                <div class="plaud-suggestion-entry">
                    <span class="plaud-sugg-tag plaud-sugg-unresolved">Unresolved</span>
                    <span>{u}</span>
                </div>
                """)
            for g in ai_suggestions.get("gaps", []):
                sugg_entries.append(f"""
                <div class="plaud-suggestion-entry">
                    <span class="plaud-sugg-tag plaud-sugg-gap">Action Gap</span>
                    <span>{g}</span>
                </div>
                """)
            for r in ai_suggestions.get("recommendations", []):
                sugg_entries.append(f"""
                <div class="plaud-suggestion-entry">
                    <span class="plaud-sugg-tag plaud-sugg-rec">Suggestion</span>
                    <span>{r}</span>
                </div>
                """)

        if not sugg_entries:
            # Generate default intelligent suggestions if not explicitly listed
            sugg_entries.append("""
            <div class="plaud-suggestion-entry">
                <span class="plaud-sugg-tag plaud-sugg-unresolved">Unresolved</span>
                <span>Confirm timeline dependencies and access credentials with external collaborators.</span>
            </div>
            """)
            sugg_entries.append("""
            <div class="plaud-suggestion-entry">
                <span class="plaud-sugg-tag plaud-sugg-rec">Suggestion</span>
                <span>Review SOC 2 training quiz submissions prior to the next scheduled sprint sync.</span>
            </div>
            """)

        ai_suggestions_markup = f"""
        <div class="plaud-suggestions-box">
            <div class="plaud-suggestions-header">
                <span>💡 AI Suggestions & Strategic Follow-ups</span>
            </div>
            {''.join(sugg_entries)}
        </div>
        """

        # Render Full Plaud Document Container
        st.markdown(f"""
        <div class="plaud-doc-container">
            <div class="plaud-doc-header">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span class="saas-badge">📄 Plaud Executive Document</span>
                    <span style="font-size:12px; color:var(--hesh-text-muted);">⚡ {data.get('model_used', 'AI Intelligence')} • ⏱️ {meta.get('duration', 'N/A')}</span>
                </div>
                <div class="plaud-doc-title">{title}</div>
                <div class="plaud-doc-meta">
                    <span>📅 {meta.get('processed_at', datetime.now().strftime('%Y-%m-%d'))}</span>
                    <span>•</span>
                    <span>👥 {meta.get('speakers', 'Participants Identified')}</span>
                </div>
            </div>

            {exec_summary_html}

            <div style="font-size:13px; font-weight:800; color:var(--hesh-accent); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:16px;">
                📖 Discussion Sections & Deliverables
            </div>

            {''.join(topics_html_list)}

            {ai_suggestions_markup}
        </div>
        """, unsafe_allow_html=True)

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
                <h3 style="font-size: 18px; margin-bottom: 2px;">📋 Action Items & Deliverables Manager</h3>
                <div style="font-size: 12px; color: var(--hesh-text-muted);">Track completion, assign owners, and synchronize action items to cloud</div>
            </div>
            """, unsafe_allow_html=True)
        with col_act_prog:
            st.markdown(f"<div style='display:flex; justify-content:space-between; font-size:12px; font-weight:600; color:var(--hesh-text-primary); margin-bottom:4px;'><span>Task Completion: {comp_cnt}/{total_cnt} Done</span><span>{comp_percent}%</span></div>", unsafe_allow_html=True)
            st.progress(comp_percent / 100.0)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        col_filter, col_add_btn = st.columns([2.0, 1.0])
        with col_filter:
            action_filter = st.radio(
                "Filter Tasks",
                [f"All ({total_cnt})", f"⏳ Pending ({pend_cnt})", f"✅ Completed ({comp_cnt})"],
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
            st.info("No action items match the selected filter.")
        else:
            for item in display_items:
                orig_idx = action_items.index(item)
                is_done = item.get("status") == "completed"
                prio = (item.get("priority") or "MED").upper()
                prio_badge = "🔴 HIGH" if "HIGH" in prio else ("🟢 LOW" if "LOW" in prio else "🟡 MED")
                owner = item.get("assignee") or item.get("owner") or "Team"
                due = item.get("due_date") or "Next Sprint"
                desc = item.get("description") or item.get("task") or "Deliverable"

                desc_style = "text-decoration: line-through; opacity: 0.6;" if is_done else "font-weight: 600;"

                with st.container():
                    col_chk, col_txt, col_meta, col_del = st.columns([0.3, 2.2, 1.1, 0.4])
                    with col_chk:
                        chk_val = st.checkbox("", value=is_done, key=f"chk_act_{session_id}_{orig_idx}")
                        if chk_val != is_done:
                            action_items[orig_idx]["status"] = "completed" if chk_val else "pending"
                            data["action_items"] = action_items
                            update_session_action_items(session_id, action_items, user_id=user_id)
                            st.toast("✅ Task status saved to Cloud!", icon="💾")
                            time.sleep(0.2)
                            st.rerun()

                    with col_txt:
                        st.markdown(f"<div style='font-size: 13.5px; color: var(--hesh-text-primary); padding-top: 2px; {desc_style}'>{desc}</div>", unsafe_allow_html=True)

                    with col_meta:
                        st.markdown(f"""
                        <div style="display:flex; gap:6px; align-items:center; font-size:11px; padding-top:2px;">
                            <span class="saas-badge" style="font-weight:700;">{prio_badge}</span>
                            <span style="color:var(--hesh-accent); font-weight:600;">👤 {owner}</span>
                            <span style="color:var(--hesh-text-muted);">📅 {due}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_del:
                        if st.button("🗑️", key=f"del_task_{session_id}_{orig_idx}", help="Delete Task"):
                            action_items.pop(orig_idx)
                            data["action_items"] = action_items
                            update_session_action_items(session_id, action_items, user_id=user_id)
                            st.toast("Task removed.", icon="🗑️")
                            time.sleep(0.2)
                            st.rerun()

                    st.markdown("<hr style='border: none; border-top: 1px solid var(--hesh-border); margin: 6px 0;'>", unsafe_allow_html=True)

        # Expandable Add New Task Form
        with st.expander("➕ Add New Action Item"):
            with st.form(key=f"form_add_action_{session_id}"):
                new_task_desc = st.text_input("Task Deliverable", placeholder="e.g. Finalize Q3 Cloud migration roadmap")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    new_task_owner = st.text_input("Assignee / Owner", value="Team")
                with col_f2:
                    new_task_prio = st.selectbox("Priority", ["HIGH", "MED", "LOW"], index=1)
                with col_f3:
                    new_task_due = st.text_input("Due Date / Deadline", value="Next Sprint")
                
                submitted = st.form_submit_button("Save Deliverable", type="primary", use_container_width=True)
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
                        st.toast("🎉 New Action Item saved to Cloud!", icon="✅")
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.warning("Please provide a task description.")

    # -------------------------------------------------------------------------
    # TAB 3: INTERACTIVE MIND MAP (SVG / MERMAID.INK RENDERER)
    # -------------------------------------------------------------------------
    with tab_mindmap:
        raw_mindmap = data.get("mermaid_mindmap", "").strip()
        # Clean markdown fence backticks and common character issues
        raw_mindmap = raw_mindmap.replace("```mermaid", "").replace("```", "").strip()
        raw_mindmap = raw_mindmap.replace("&", "and")

        # Check for generic boilerplate or placeholder text
        is_boilerplate = any(b in raw_mindmap.lower() for b in [
            "strategic direction", "concept alpha", "academic lecture intelligence", "key milestone", "theme analysis", "opportunity", "concept one"
        ])

        if not raw_mindmap or len(raw_mindmap) < 25 or is_boilerplate:
            raw_mindmap = build_contextual_mindmap(data, title)
            data["mermaid_mindmap"] = raw_mindmap

        st.markdown("""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
            <div>
                <h3 style="font-size: 18px; margin: 0;">🧠 Interactive Tree Mind Map (Plaud Document Aligned)</h3>
                <div style="font-size: 12px; color: var(--hesh-text-muted);">Derived directly from numbered discussion sections, executive narrative highlights, inline deliverables, and AI suggestions</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_mm_view, col_mm_side = st.columns([3.0, 1.0])
        with col_mm_view:
            render_mindmap_diagram(raw_mindmap)

        with col_mm_side:
            st.markdown("""
            <div style="background: var(--hesh-surface); border: 1px solid var(--hesh-border); border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                <div style="font-size: 13px; font-weight: 700; color: var(--hesh-accent); margin-bottom: 6px;">💡 Mind Map Controls</div>
                <div style="font-size: 11.5px; color: var(--hesh-text-secondary); line-height: 1.5;">
                    • 100% Context Unified with Summary<br>
                    • Guaranteed Vector SVG Display<br>
                    • Rendered via mermaid.ink engine
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 Re-sync Mind Map with Summary", key=f"btn_resync_mm_{session_id}", type="secondary", use_container_width=True):
                new_mm = build_contextual_mindmap(data, title)
                data["mermaid_mindmap"] = new_mm
                st.toast("✅ Mind Map re-synchronized with meeting summary!", icon="🧠")
                time.sleep(0.3)
                st.rerun()

            st.download_button(
                "📥 Download Mermaid Code",
                data=raw_mindmap,
                file_name=f"{session_id}_mindmap.mmd",
                mime="text/plain",
                use_container_width=True
            )

            with st.expander("🔍 View Mermaid Syntax"):
                st.code(raw_mindmap, language="mermaid")

    # -------------------------------------------------------------------------
    # TAB 4: DIARIZED TRANSCRIPT & SYNCED AUDIO PLAYER
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
                # Scan inputs for session stem or source file
                for p in INPUTS_DIR.glob(f"*{ext}"):
                    if session_id in p.stem or (source_path and p.name == source_path):
                        found_audio = p
                        break

        # Top Audio Player Widget
        if found_audio and found_audio.exists():
            st.markdown("<div style='font-size: 13px; font-weight: 700; color: var(--hesh-accent); margin-bottom: 6px;'>🎙️ Audio Waveform Player</div>", unsafe_allow_html=True)
            with open(found_audio, "rb") as af:
                audio_bytes = af.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

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

        audio_b64 = ""
        audio_mime = "audio/mp3"
        if found_audio and found_audio.exists():
            try:
                with open(found_audio, "rb") as af:
                    audio_b64 = base64.b64encode(af.read()).decode("utf-8")
                if found_audio.suffix.lower() == ".wav":
                    audio_mime = "audio/wav"
                elif found_audio.suffix.lower() == ".m4a":
                    audio_mime = "audio/mp4"
            except Exception:
                pass

        theme_mode = st.session_state.theme
        bg_surface = "#111726" if theme_mode == "dark" else "#FFFFFF"
        bg_bubble = "#182238" if theme_mode == "dark" else "#F8FAFC"
        bg_bubble_hover = "#212E4A" if theme_mode == "dark" else "#F1F5F9"
        border_col = "#232E48" if theme_mode == "dark" else "#E2E8F0"
        text_pri = "#F8FAFC" if theme_mode == "dark" else "#0F172A"
        text_sec = "#94A3B8" if theme_mode == "dark" else "#475569"
        accent_col = "#38BDF8" if theme_mode == "dark" else "#0284C7"

        speaker_colors = {
            "Speaker 1": "#38BDF8",
            "Speaker 2": "#A855F7",
            "Speaker 3": "#10B981",
            "Speaker 4": "#F59E0B"
        }

        transcript_cards_html = []
        for idx, turn in enumerate(transcript_turns):
            spk_color = speaker_colors.get(turn["speaker"], accent_col)
            transcript_cards_html.append(f"""
            <div class="turn-card" data-seek="{turn['seconds']}" id="turn_{idx}" style="background: {bg_bubble}; border: 1px solid {border_col}; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; transition: all 0.15s ease;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 12px; font-weight: 800; color: {spk_color}; background: rgba(56, 189, 248, 0.08); padding: 2px 8px; border-radius: 6px;">🗣️ {turn['speaker']}</span>
                        <span style="font-size: 11px; font-weight: 700; color: {text_sec}; background: rgba(125, 125, 125, 0.1); padding: 2px 6px; border-radius: 4px;">⏱️ {turn['time']}</span>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button onclick="seekToAudio({turn['seconds']}, this)" style="background: var(--hesh-surface, #111726); border: 1px solid {border_col}; color: {accent_col}; border-radius: 6px; font-size: 11px; font-weight: 700; padding: 3px 8px; cursor: pointer;">▶ Play from here</button>
                        <button onclick="copyTurnText('txt_{idx}', this)" style="background: var(--hesh-surface, #111726); border: 1px solid {border_col}; color: {text_sec}; border-radius: 6px; font-size: 11px; font-weight: 600; padding: 3px 8px; cursor: pointer;">📋 Copy</button>
                    </div>
                </div>
                <div id="txt_{idx}" style="font-size: 13px; color: {text_pri}; line-height: 1.6;">{turn['text']}</div>
            </div>
            """)

        interactive_player_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; padding: 0; background: transparent; color: {text_pri}; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; }}
                .turn-card.active {{
                    border-left: 4px solid {accent_col} !important;
                    background: {bg_bubble_hover} !important;
                }}
                .transcript-stream {{
                    max-height: 560px; overflow-y: auto; padding-right: 6px;
                }}
                .transcript-stream::-webkit-scrollbar {{ width: 5px; }}
                .transcript-stream::-webkit-scrollbar-thumb {{ background: {border_col}; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="transcript-stream" id="transcriptStream">
                {''.join(transcript_cards_html) if transcript_cards_html else '<div style="padding:20px; text-align:center; color:' + text_sec + ';">Transcript turns will appear here.</div>'}
            </div>

            <script>
                function seekToAudio(seconds, btn) {{
                    const audio = window.parent.document.querySelector('audio');
                    if (audio) {{
                        audio.currentTime = seconds;
                        audio.play();
                    }}
                    const card = btn ? btn.closest('.turn-card') : null;
                    document.querySelectorAll('.turn-card').forEach(c => c.classList.remove('active'));
                    if (card) {{
                        card.classList.add('active');
                    }}
                }}

                function copyTurnText(elementId, btn) {{
                    const el = document.getElementById(elementId);
                    if (el) {{
                        navigator.clipboard.writeText(el.innerText).then(() => {{
                            const orig = btn.innerText;
                            btn.innerText = '✅ Copied!';
                            setTimeout(() => {{ btn.innerText = orig; }}, 1500);
                        }});
                    }}
                }}
            </script>
        </body>
        </html>
        """
        components.html(interactive_player_html, height=580, scrolling=False)

    # -------------------------------------------------------------------------
    # TAB 4: INTERACTIVE "CHAT WITH THIS AUDIO" (HESH REC BOT)
    # -------------------------------------------------------------------------
    with tab_chat:
        st.markdown("""
        <div style="background: var(--hesh-surface); border: 1px solid var(--hesh-border); border-radius: 12px; padding: 16px; margin-bottom: 16px;">
            <div style="font-size: 14px; font-weight: 700; color: var(--hesh-accent); margin-bottom: 2px;">💬 Hesh Rec Bot (هشام ريك بوت)</div>
            <div style="font-size: 12px; color: var(--hesh-text-muted);">Ask questions, clarify points, or request specific summaries grounded directly in this recording.</div>
        </div>
        """, unsafe_allow_html=True)

        if session_id not in st.session_state.chat_messages:
            st.session_state.chat_messages[session_id] = [
                {"role": "assistant", "content": "Hello! I am **Hesh Rec Bot**. Ask me any question about this recording, decisions, or action items."}
            ]

        for msg in st.session_state.chat_messages[session_id]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_q = st.chat_input("Ask Hesh Rec Bot a question about this recording...")
        if user_q:
            st.session_state.chat_messages[session_id].append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            with st.chat_message("assistant"):
                with st.spinner("Hesh Rec Bot is thinking..."):
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

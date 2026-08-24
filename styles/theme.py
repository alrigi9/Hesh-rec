# -*- coding: utf-8 -*-
"""
Google Design System for Hesh Rec
Single source of truth for all styling, design tokens, typography, component resets, and theme handling.
Aesthetic: Ultra-fluid editorial layout, generous negative space, bold geometric typography, soft pill geometry.
"""

import re

# Design Tokens Dictionary (Google Design Inspired)
LIGHT_TOKENS = {
    "--bg": "#fcfcfd",
    "--bg-subtle": "#f4f5f8",
    "--surface": "#ffffff",
    "--surface-2": "#f0f2f6",
    "--border": "rgba(0, 0, 0, 0.08)",
    "--border-strong": "rgba(0, 0, 0, 0.16)",
    "--text": "#111215",
    "--text-2": "#5f6368",
    "--text-3": "#80868b",
    "--accent": "#ff6352",
    "--accent-soft": "rgba(255, 99, 82, 0.10)",
    "--ok": "#1e8e3e",
    "--warn": "#f9ab00",
    "--info": "#1a73e8",
    "--shadow": "0 1px 3px rgba(0, 0, 0, 0.05), 0 4px 12px rgba(0, 0, 0, 0.04)",
    "--radius-sm": "8px",
    "--radius-md": "16px",
    "--radius-lg": "20px",
    "--radius-pill": "999px",
}

DARK_TOKENS = {
    "--bg": "#121316",
    "--bg-subtle": "#0c0d0f",
    "--surface": "#1b1c20",
    "--surface-2": "#24262c",
    "--border": "rgba(255, 255, 255, 0.08)",
    "--border-strong": "rgba(255, 255, 255, 0.16)",
    "--text": "#f2f3f7",
    "--text-2": "#9aa0ac",
    "--text-3": "#6c7280",
    "--accent": "#ff6352",
    "--accent-soft": "rgba(255, 99, 82, 0.14)",
    "--ok": "#34a853",
    "--warn": "#fbbc04",
    "--info": "#8ab4f8",
    "--shadow": "0 2px 8px rgba(0, 0, 0, 0.35), 0 8px 24px rgba(0, 0, 0, 0.25)",
    "--radius-sm": "8px",
    "--radius-md": "16px",
    "--radius-lg": "20px",
    "--radius-pill": "999px",
}

# Acronym mapping for compliance and technical terminology display
ACRONYMS = ["SOC", "ISO", "DLP", "BYOD", "MFA", "API", "PDF", "UI", "VPN", "QR", "AI"]

def format_acronyms(text: str) -> str:
    """Ensures compliance and technical acronyms (SOC, ISO, DLP, BYOD, MFA, API, PDF, UI, VPN, QR, AI) are properly capitalized."""
    if not text:
        return text
    result = str(text)
    for acr in ACRONYMS:
        pattern = re.compile(rf"\b{re.escape(acr)}\b", re.IGNORECASE)
        result = pattern.sub(acr, result)
        if acr == "SOC":
            result = re.sub(r"\bSoc\s*2\b", "SOC 2", result, flags=re.IGNORECASE)
    return result


def get_token_css_variables(theme: str = "dark") -> str:
    """Returns CSS custom properties block with active theme values as primary :root variables."""
    active_tokens = DARK_TOKENS if theme == "dark" else LIGHT_TOKENS
    tokens_str = "\n".join([f"    {k}: {v};" for k, v in active_tokens.items()])
    
    light_str = "\n".join([f"    {k}: {v};" for k, v in LIGHT_TOKENS.items()])
    dark_str = "\n".join([f"    {k}: {v};" for k, v in DARK_TOKENS.items()])

    return f"""
  :root {{
{tokens_str}
  }}
  :root[data-theme="light"], [data-theme="light"] {{
{light_str}
  }}
  :root[data-theme="dark"], [data-theme="dark"] {{
{dark_str}
  }}
"""


def get_iframe_theme_css(theme: str = "dark") -> str:
    """Returns complete self-contained CSS for sandboxed iframes (Summary / Mindmap / Print)."""
    return f"""
    {get_token_css_variables(theme)}

    * {{
      box-sizing: border-box;
    }}

    html, body {{
      background: var(--bg) !important;
      color: var(--text) !important;
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 15px;
      line-height: 1.75;
      font-weight: 400;
      -webkit-font-smoothing: antialiased;
      transition: background-color 0.15s ease, color 0.15s ease;
    }}

    .document-canvas {{
      max-width: 840px;
      margin: 0 auto;
      padding: 40px 24px 80px 24px;
    }}

    /* Editorial Google Typography Scale */
    h1, .display-title {{
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      font-size: 32px;
      line-height: 1.25;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text) !important;
      margin: 0 0 16px 0;
    }}

    h2, .section-title {{
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      font-size: 22px;
      line-height: 1.35;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text) !important;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      margin: 48px 0 20px 0;
    }}

    h3 {{
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      font-size: 17px;
      line-height: 1.4;
      font-weight: 600;
      color: var(--text) !important;
      margin: 28px 0 12px 0;
    }}

    p {{
      color: var(--text);
      line-height: 1.75;
      margin: 0 0 20px 0;
    }}

    small, .meta-text {{
      font-size: 13px;
      line-height: 1.5;
      color: var(--text-2);
    }}

    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 13px;
    }}

    /* Soft Pill Metadata Chips */
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 36px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }}

    .meta-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--surface-2);
      color: var(--text-2);
      border: 1px solid var(--border);
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 500;
      padding: 4px 14px;
      line-height: 1.4;
      transition: all 0.15s ease;
    }}

    /* Open Editorial Brief */
    .editorial-brief {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px 28px;
      margin-bottom: 40px;
      box-shadow: var(--shadow);
    }}

    .brief-label {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}

    .brief-content {{
      font-size: 15.5px;
      line-height: 1.75;
      color: var(--text);
      margin: 0;
    }}

    /* Discussion Pillars */
    .section-block {{
      padding: 16px 0;
      margin-bottom: 36px;
    }}

    /* Granular Action Items Checklist */
    .section-actions {{
      margin-top: 20px;
      padding: 20px 24px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
    }}

    .section-actions-heading {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 14px;
    }}

    .action-item-pill {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      margin-bottom: 8px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 12px;
      font-size: 14px;
      color: var(--text);
      transition: all 0.15s ease;
    }}

    .action-item-pill:last-child {{
      margin-bottom: 0;
    }}

    .action-check-pill {{
      color: var(--text-3);
      font-size: 15px;
      user-select: none;
      flex-shrink: 0;
    }}

    .action-text {{
      flex-grow: 1;
    }}

    .action-owner-pill {{
      font-size: 12px;
      font-weight: 500;
      color: var(--text-2);
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 10px;
      flex-shrink: 0;
    }}

    .action-due-pill {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      color: var(--text-3);
      flex-shrink: 0;
    }}

    /* Open Questions */
    .questions-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-left: 3px solid var(--warn);
      padding: 20px 24px;
      border-radius: 16px;
      margin-top: 36px;
      margin-bottom: 28px;
    }}

    .questions-label {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 12px;
      font-weight: 700;
      color: var(--warn);
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    /* AI Suggestions */
    .ai-suggestions {{
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-left: 3px solid var(--accent) !important;
      border-radius: 16px;
      padding: 22px 26px;
      margin-top: 48px;
      margin-bottom: 32px;
    }}

    .ai-suggestions-label {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}

    .ai-suggestions-desc {{
      font-size: 13.5px;
      color: var(--text-2);
      margin-bottom: 16px;
      line-height: 1.5;
    }}

    .ai-suggestion-item {{
      font-size: 14.5px;
      line-height: 1.7;
      color: var(--text-2);
      margin-bottom: 12px;
    }}

    .ai-suggestion-title {{
      font-weight: 600;
      color: var(--text);
    }}

    /* Mind Map Rounded Canvas */
    .mindmap-container {{
      margin-top: 24px;
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 20px;
      background: var(--surface);
      position: relative;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}

    .mindmap-controls {{
      display: flex;
      gap: 8px;
      position: absolute;
      top: 20px;
      right: 20px;
      z-index: 10;
    }}

    .control-btn {{
      background: var(--surface-2);
      color: var(--text-2);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .control-btn:hover {{
      background: var(--border);
      color: var(--text);
    }}

    /* Mindmap SVG Theme Overrides */
    #mindmap {{
      background: var(--surface) !important;
      width: 100% !important;
      min-height: 700px !important;
      display: block !important;
    }}

    #mindmap text,
    #mindmap tspan,
    #mindmap foreignObject div {{
      fill: var(--text) !important;
      color: var(--text) !important;
      font-family: 'Inter', sans-serif !important;
      font-size: 13.5px !important;
      white-space: normal !important;
      word-wrap: break-word !important;
    }}

    #mindmap .markmap-node > line {{
      stroke: var(--border-strong) !important;
      stroke-width: 1.5px !important;
    }}

    #mindmap path.markmap-link {{
      stroke: var(--border-strong) !important;
      stroke-width: 1.5px !important;
      stroke-opacity: 0.75 !important;
    }}

    #mindmap circle {{
      stroke: var(--border-strong) !important;
      fill: var(--surface) !important;
    }}

    /* Transcript Badges & Buttons */
    .speaker-badge, .transcript-badge {{
      background: var(--surface-2) !important;
      color: var(--text) !important;
      border: 1px solid var(--border) !important;
      border-radius: 999px !important;
      padding: 3px 12px !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      display: inline-flex !important;
      align-items: center !important;
    }}

    .transcript-btn, .transcript-card button {{
      background: var(--surface-2) !important;
      color: var(--text-2) !important;
      border: 1px solid var(--border) !important;
      border-radius: 999px !important;
      font-size: 11.5px !important;
      font-weight: 500 !important;
      padding: 4px 12px !important;
      cursor: pointer !important;
      transition: all 0.15s ease !important;
    }}

    .transcript-btn:hover, .transcript-card button:hover {{
      background: var(--border) !important;
      color: var(--text) !important;
    }}

    .turn-card, .transcript-card {{
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: 16px !important;
      padding: 14px 18px !important;
      margin-bottom: 12px !important;
      transition: all 0.15s ease !important;
    }}

    .turn-card.active, .transcript-card.active {{
      border-left: 3px solid var(--accent) !important;
      background: var(--surface-2) !important;
    }}

    /* Buttons */
    .btn-ghost {{
      background: transparent;
      color: var(--text-2);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 18px;
      font-size: 13.5px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}

    .btn-ghost:hover {{
      background: var(--surface-2);
      color: var(--text);
      border-color: var(--border-strong);
    }}

    .btn-primary {{
      background: var(--accent);
      color: #ffffff !important;
      border: 1px solid var(--accent);
      border-radius: 999px;
      padding: 8px 20px;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s ease;
    }}

    .btn-primary:hover {{
      opacity: 0.92;
    }}

    /* PRINT SPECIFICATION */
    @media print {{
      :root, [data-theme="dark"], [data-theme="light"], html, body {{
        --bg: #ffffff !important;
        --bg-subtle: #fafafa !important;
        --surface: #ffffff !important;
        --surface-2: #f6f7f9 !important;
        --border: #e7e8ec !important;
        --border-strong: #d3d5da !important;
        --text: #16181d !important;
        --text-2: #5b616e !important;
        --text-3: #8b909b !important;
        --accent: #c0392b !important;
        --accent-soft: #fdf0ee !important;
        --ok: #0f7b4f !important;
        --warn: #a4690a !important;
        --info: #1a5fb4 !important;
        background: #ffffff !important;
        color: #16181d !important;
        padding: 0 !important;
      }}
      .no-print, .mindmap-controls {{
        display: none !important;
      }}
      @page {{
        size: A4;
        margin: 16mm;
      }}
      * {{
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }}
      h1, h2, h3 {{
        page-break-after: avoid;
        color: #16181d !important;
      }}
      .section-block {{
        page-break-inside: avoid;
      }}
      #mindmap {{
        background: #ffffff !important;
      }}
      #mindmap text, #mindmap tspan {{
        fill: #16181d !important;
      }}
    }}
"""


def inject_theme(theme: str = "dark"):
    """
    Single source of truth CSS injection for the entire Streamlit application.
    Enforces Google Design aesthetic: ultra-fluid editorial layout, bold geometric typography, soft pill geometry.
    """
    token_css = get_token_css_variables(theme)

    app_css = f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;1,400&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

      {token_css}

      /* Global Reset & Base Typography */
      *, *::before, *::after {{
        box-sizing: border-box;
      }}

      html, body, .stApp {{
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 15px !important;
        line-height: 1.75 !important;
        font-weight: 400 !important;
        -webkit-font-smoothing: antialiased;
      }}

      /* Page Container Max Width & Rhythm */
      .main .block-container {{
        max-width: 960px !important;
        padding-left: 32px !important;
        padding-right: 32px !important;
        padding-top: 36px !important;
        padding-bottom: 80px !important;
      }}

      /* Google Typography Scale */
      h1, .display-title {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 32px !important;
        line-height: 1.25 !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: var(--text) !important;
        margin-top: 0 !important;
        margin-bottom: 8px !important;
      }}

      h2, .section-title {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 22px !important;
        line-height: 1.35 !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        color: var(--text) !important;
        margin-top: 48px !important;
        margin-bottom: 16px !important;
      }}

      h3 {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 17px !important;
        line-height: 1.4 !important;
        font-weight: 600 !important;
        color: var(--text) !important;
        margin-top: 28px !important;
        margin-bottom: 12px !important;
      }}

      p, div, span, label, td, th {{
        color: inherit;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }}

      small, .text-small {{
        font-size: 13px !important;
        line-height: 1.5 !important;
        color: var(--text-2) !important;
      }}

      .mono {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
        font-size: 13px !important;
      }}

      /* Streamlit Header / Chrome Cleanup */
      header[data-testid="stHeader"] {{
        background: transparent !important;
      }}

      /* Minimal Sidebar */
      section[data-testid="stSidebar"] {{
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
      }}

      section[data-testid="stSidebar"] .block-container {{
        padding-top: 28px !important;
        padding-left: 20px !important;
        padding-right: 20px !important;
        padding-bottom: 28px !important;
      }}

      /* Focus Ring */
      button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible {{
        outline: 2px solid var(--accent) !important;
        outline-offset: 2px !important;
      }}

      /* Button Global & Soft Pill Specification */
      .stButton > button, 
      .stDownloadButton > button, 
      div[data-testid="stButton"] > button, 
      div[data-testid="stDownloadButton"] > button,
      button[kind="primary"], 
      button[kind="secondary"], 
      button[kind="tertiary"],
      .btn-primary, 
      .btn-secondary, 
      .btn-ghost {{
        white-space: nowrap !important;
        min-width: max-content !important;
        word-break: keep-all !important;
        border-radius: 999px !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.15s ease !important;
      }}

      @media (max-width: 900px) {{
        .header-actions-row {{
          display: flex !important;
          flex-wrap: wrap !important;
          gap: 8px !important;
          margin-top: 12px !important;
        }}
      }}

      /* Button Variants */
      button[kind="primary"], .btn-primary {{
        background-color: var(--accent) !important;
        color: #ffffff !important;
        border: 1px solid var(--accent) !important;
        border-radius: 999px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        height: 38px !important;
        padding: 0 20px !important;
        box-shadow: none !important;
      }}

      button[kind="primary"]:hover, .btn-primary:hover {{
        opacity: 0.92 !important;
        transform: translateY(-1px);
      }}

      button[kind="secondary"], .btn-secondary {{
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 999px !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        height: 38px !important;
        padding: 0 16px !important;
        box-shadow: none !important;
      }}

      button[kind="secondary"]:hover, .btn-secondary:hover {{
        background-color: var(--border) !important;
        border-color: var(--border-strong) !important;
        color: var(--text) !important;
      }}

      button[kind="tertiary"], .btn-ghost {{
        background: transparent !important;
        color: var(--text-2) !important;
        border: none !important;
        border-radius: 999px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        height: 38px !important;
        padding: 0 14px !important;
      }}

      button[kind="tertiary"]:hover, .btn-ghost:hover {{
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
      }}

      /* Tabs Overhaul */
      div[data-testid="stTabs"] {{
        border-bottom: 1px solid var(--border) !important;
        margin-bottom: 32px !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 12px !important;
        background: transparent !important;
        border-bottom: none !important;
        padding: 0 0 6px 0 !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab"] {{
        background: transparent !important;
        border: none !important;
        border-radius: 999px !important;
        color: var(--text-2) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        padding: 8px 18px !important;
        height: auto !important;
        transition: all 0.15s ease !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
        color: var(--text) !important;
        background: var(--surface-2) !important;
      }}

      div[data-testid="stTabs"] [aria-selected="true"] {{
        color: var(--text) !important;
        background: var(--surface-2) !important;
        font-weight: 600 !important;
      }}

      /* Sidebar Navigation Links */
      section[data-testid="stSidebar"] div.stButton > button {{
        text-align: left !important;
        justify-content: flex-start !important;
        height: 40px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        border-radius: 999px !important;
        padding: 0 16px !important;
        margin-bottom: 4px !important;
        border: none !important;
        background: transparent !important;
        color: var(--text-2) !important;
      }}

      section[data-testid="stSidebar"] div.stButton > button:hover {{
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
      }}

      /* Clean Pinned Chat Input & Bubble Styling */
      .stChatFloatingInputContainer,
      div[data-testid="stChatFloatingInputContainer"],
      div[data-testid="stChatInput"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
      }}

      div[data-testid="stChatInput"] > div {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 999px !important;
        color: var(--text) !important;
        padding: 4px 12px !important;
        transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
      }}

      div[data-testid="stChatInput"] > div:focus-within {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px var(--accent-soft) !important;
      }}

      div[data-testid="stChatInput"] textarea {{
        color: var(--text) !important;
        font-size: 14.5px !important;
        background: transparent !important;
      }}

      div[data-testid="stChatInput"] textarea::placeholder {{
        color: var(--text-3) !important;
      }}

      div[data-testid="stChatMessage"] {{
        background: transparent !important;
        padding: 12px 0 !important;
        border: none !important;
        gap: 12px !important;
      }}

      div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] {{
        background: var(--surface-2) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-2) !important;
        border-radius: 50% !important;
      }}

      .chat-pill-btn > button {{
        background: var(--surface-2) !important;
        color: var(--text-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 999px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 8px 16px !important;
        height: auto !important;
        text-align: left !important;
        transition: all 0.15s ease !important;
      }}

      .chat-pill-btn > button:hover {{
        background: var(--border) !important;
        color: var(--text) !important;
        border-color: var(--border-strong) !important;
      }}

      /* Cards & Containers */
      .card-raised, .card-flat {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: var(--shadow);
        padding: 28px;
      }}

      /* Pill badges */
      .pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--surface-2);
        color: var(--text-2);
        border: 1px solid var(--border);
        border-radius: 999px;
        font-size: 12.5px;
        font-weight: 500;
        padding: 4px 14px;
        line-height: 1.4;
      }}

      .pill-accent {{
        background: var(--accent-soft);
        color: var(--accent);
        border: 1px solid var(--accent);
      }}

      /* Meeting Rows */
      .meeting-row {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 20px 24px;
        margin-bottom: 12px;
        transition: all 0.15s ease;
      }}

      .meeting-row:hover {{
        border-color: var(--border-strong);
        background: var(--surface-2);
        transform: translateY(-1px);
      }}

      .ellipsis-text {{
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        display: block;
      }}

      /* Metric Summary Tiles */
      .metric-tile {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 20px 24px;
        box-shadow: var(--shadow);
      }}

      .metric-tile-label {{
        font-size: 12.5px;
        font-weight: 600;
        color: var(--text-2);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
      }}

      .metric-tile-value {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 26px;
        font-weight: 700;
        color: var(--text);
        line-height: 1.2;
      }}

      /* Empty State */
      .empty-state {{
        text-align: center;
        padding: 56px 24px;
        color: var(--text-2);
        font-size: 14.5px;
        background: var(--surface);
        border: 1px dashed var(--border);
        border-radius: 20px;
      }}

      .empty-state-title {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 17px;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 6px;
      }}

      /* Responsive Specifications */
      @media (min-width: 1200px) {{
        .main .block-container {{
          max-width: 960px !important;
          padding-left: 32px !important;
          padding-right: 32px !important;
        }}
      }}

      @media (min-width: 768px) and (max-width: 1199px) {{
        .main .block-container {{
          padding-left: 24px !important;
          padding-right: 24px !important;
        }}
      }}

      @media (max-width: 767px) {{
        .main .block-container {{
          padding-left: 16px !important;
          padding-right: 16px !important;
          font-size: 15px !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
          overflow-x: auto !important;
          flex-wrap: nowrap !important;
        }}
      }}

      /* PRINT ALWAYS LIGHT */
      @media print {{
        :root, [data-theme="dark"], [data-theme="light"], .stApp {{
          --bg: #ffffff !important;
          --bg-subtle: #fafafa !important;
          --surface: #ffffff !important;
          --surface-2: #f6f7f9 !important;
          --border: #e7e8ec !important;
          --border-strong: #d3d5da !important;
          --text: #16181d !important;
          --text-2: #5b616e !important;
          --text-3: #8b909b !important;
          --accent: #c0392b !important;
          --accent-soft: #fdf0ee !important;
          --ok: #0f7b4f !important;
          --warn: #a4690a !important;
          --info: #1a5fb4 !important;
          background: #ffffff !important;
          color: #16181d !important;
        }}
        section[data-testid="stSidebar"],
        header[data-testid="stHeader"],
        .no-print,
        button {{
          display: none !important;
        }}
        @page {{
          size: A4;
          margin: 16mm;
        }}
      }}
    </style>

    <script>
      (function() {{
        try {{
          const theme = "{theme}";
          document.documentElement.setAttribute('data-theme', theme);
          document.body.setAttribute('data-theme', theme);
          const stApp = document.querySelector('.stApp');
          if (stApp) {{
            stApp.setAttribute('data-theme', theme);
          }}
        }} catch(e) {{}}
      }})();
    </script>
    """
    try:
        import streamlit as st
        st.markdown(app_css, unsafe_allow_html=True)
    except Exception:
        pass

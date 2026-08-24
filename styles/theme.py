# -*- coding: utf-8 -*-
"""
Design System for Hesh Rec
Single source of truth for all styling, design tokens, typography, component resets, and theme handling.
"""

import re
import streamlit as st

# Design Tokens Dictionary
LIGHT_TOKENS = {
    "--bg": "#ffffff",
    "--bg-subtle": "#fafafa",
    "--surface": "#ffffff",
    "--surface-2": "#f6f7f9",
    "--border": "#e7e8ec",
    "--border-strong": "#d3d5da",
    "--text": "#16181d",
    "--text-2": "#5b616e",
    "--text-3": "#8b909b",
    "--accent": "#c0392b",
    "--accent-soft": "#fdf0ee",
    "--ok": "#0f7b4f",
    "--warn": "#a4690a",
    "--info": "#1a5fb4",
    "--shadow": "0 1px 2px rgba(16, 24, 40, 0.05), 0 1px 3px rgba(16, 24, 40, 0.06)",
}

DARK_TOKENS = {
    "--bg": "#0e1014",
    "--bg-subtle": "#0a0c0f",
    "--surface": "#16191f",
    "--surface-2": "#1c2027",
    "--border": "#262b33",
    "--border-strong": "#343a44",
    "--text": "#e9ecf1",
    "--text-2": "#a2a9b6",
    "--text-3": "#727a88",
    "--accent": "#ff6f5e",
    "--accent-soft": "#2a1a18",
    "--ok": "#3ec98a",
    "--warn": "#e0a63a",
    "--info": "#7cb0ff",
    "--shadow": "0 1px 2px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.25)",
}

# Acronym mapping for compliance and technical terminology display
ACRONYMS = ["SOC", "ISO", "DLP", "BYOD", "MFA", "API", "PDF", "UI", "VPN", "QR", "AI"]

def format_acronyms(text: str) -> str:
    """Ensures compliance and technical acronyms (SOC, ISO, DLP, BYOD, MFA, API, PDF, UI, VPN, QR, AI) are properly capitalized."""
    if not text:
        return text
    result = str(text)
    for acr in ACRONYMS:
        # Match case-insensitively with word boundaries (e.g. 'soc 2' or 'Soc 2' -> 'SOC 2')
        pattern = re.compile(rf"\b{re.escape(acr)}\b", re.IGNORECASE)
        result = pattern.sub(acr, result)
        # Specific check for "Soc 2" or "Soc2"
        if acr == "SOC":
            result = re.sub(r"\bSoc\s*2\b", "SOC 2", result, flags=re.IGNORECASE)
    return result


def get_token_css_variables(theme: str = "light") -> str:
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


def get_iframe_theme_css(theme: str = "light") -> str:
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
      padding: 32px;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14.5px;
      line-height: 1.7;
      font-weight: 400;
      -webkit-font-smoothing: antialiased;
      transition: background-color 0.15s ease, color 0.15s ease;
    }}

    /* Typography Scale */
    h1, .display-title {{
      font-size: 30px;
      line-height: 1.25;
      font-weight: 650;
      letter-spacing: -0.01em;
      color: var(--text) !important;
      margin: 0 0 16px 0;
    }}

    h2, .section-title {{
      font-size: 20px;
      line-height: 1.35;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text) !important;
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
      margin: 48px 0 16px 0;
    }}

    h3 {{
      font-size: 16px;
      line-height: 1.4;
      font-weight: 600;
      color: var(--text) !important;
      margin: 24px 0 12px 0;
    }}

    p {{
      color: var(--text);
      line-height: 1.7;
      margin: 0 0 16px 0;
      max-width: 78ch;
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

    /* Metadata pills */
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 32px;
      padding-bottom: 16px;
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
      font-size: 12px;
      font-weight: 500;
      padding: 4px 10px;
      line-height: 1.4;
    }}

    /* Executive TL;DR Box */
    .tldr-box {{
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-left: 3px solid var(--info);
      border-radius: 6px;
      padding: 16px 20px;
      margin-bottom: 32px;
    }}

    .tldr-label {{
      font-size: 12px;
      font-weight: 600;
      color: var(--info);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}

    .tldr-content {{
      font-size: 14.5px;
      line-height: 1.7;
      color: var(--text);
      margin: 0;
      max-width: 78ch;
    }}

    /* Action items box inside summary */
    .section-actions {{
      margin-top: 16px;
      padding: 16px 20px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 6px;
    }}

    .section-actions-heading {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 12px;
    }}

    .action-row {{
      display: flex;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 14px;
      color: var(--text);
    }}

    .action-check {{
      color: var(--text-3);
      font-size: 14px;
      user-select: none;
    }}

    .action-owner {{
      color: var(--text-2);
      font-style: italic;
    }}

    .action-due {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12.5px;
      color: var(--text-3);
    }}

    /* Open Questions */
    .questions-box {{
      border-left: 3px solid var(--warn);
      background: var(--surface-2);
      border-top: 1px solid var(--border);
      border-right: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      padding: 16px 20px;
      border-radius: 6px;
      margin-top: 32px;
      margin-bottom: 24px;
    }}

    .questions-label {{
      font-size: 13px;
      font-weight: 600;
      color: var(--warn);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    /* AI Suggestions */
    .ai-suggestions {{
      background: var(--surface-2) !important;
      border: 1px solid var(--border) !important;
      border-left: 3px solid var(--accent) !important;
      border-radius: 10px;
      padding: 20px;
      margin-top: 48px;
      margin-bottom: 32px;
    }}

    .ai-suggestions-label {{
      font-size: 12px;
      font-variant: small-caps;
      font-weight: 600;
      color: var(--accent);
      letter-spacing: 0.06em;
      margin-bottom: 4px;
    }}

    .ai-suggestions-desc {{
      font-size: 13px;
      color: var(--text-2);
      margin-bottom: 16px;
      line-height: 1.5;
    }}

    .ai-suggestion-item {{
      font-size: 14px;
      line-height: 1.65;
      color: var(--text-2);
      margin-bottom: 12px;
    }}

    .ai-suggestion-title {{
      font-weight: 600;
      color: var(--text);
    }}

    /* Mind Map Container */
    .mindmap-container {{
      margin-top: 20px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      background: var(--bg);
      position: relative;
    }}

    .mindmap-controls {{
      display: flex;
      gap: 8px;
      position: absolute;
      top: 24px;
      right: 24px;
      z-index: 10;
    }}

    .control-btn {{
      background: var(--surface);
      color: var(--text-2);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    }}

    .control-btn:hover {{
      background: var(--surface-2);
      color: var(--text);
      border-color: var(--border-strong);
    }}

    /* Mindmap SVG Theme Specificity Overrides */
    #mindmap {{
      background: var(--bg) !important;
      width: 100%;
      height: 900px;
    }}

    #mindmap text,
    #mindmap tspan,
    #mindmap foreignObject div {{
      fill: var(--text) !important;
      color: var(--text) !important;
      font-family: 'Inter', sans-serif !important;
      font-size: 13px !important;
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

    /* Buttons */
    .btn-ghost {{
      background: transparent;
      color: var(--text-2);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s ease, color 0.15s ease;
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
      border-radius: 6px;
      padding: 8px 16px;
      font-size: 13.5px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s ease;
    }}

    .btn-primary:hover {{
      opacity: 0.92;
    }}

    /* PRINT SPECIFICATION — ALWAYS LIGHT, CRISP & CLEAN */
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


def inject_theme(theme: str = "light"):
    """
    Single source of truth CSS injection for the entire Streamlit application.
    Enforces calm professional aesthetics, design tokens, typography, 4px scale, and responsiveness.
    """
    token_css = get_token_css_variables(theme)

    app_css = f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,650;0,700;1,400&display=swap');

      {token_css}

      /* Global Reset & Base Typography */
      *, *::before, *::after {{
        box-sizing: border-box;
      }}

      html, body, .stApp {{
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 14.5px !important;
        line-height: 1.7 !important;
        font-weight: 400 !important;
        -webkit-font-smoothing: antialiased;
      }}

      /* Page Container Max Width & Rhythm */
      .main .block-container {{
        max-width: 1120px !important;
        padding-left: 32px !important;
        padding-right: 32px !important;
        padding-top: 32px !important;
        padding-bottom: 64px !important;
      }}

      /* Typography Scale */
      h1, .display-title {{
        font-size: 30px !important;
        line-height: 1.25 !important;
        font-weight: 650 !important;
        letter-spacing: -0.01em !important;
        color: var(--text) !important;
        margin-top: 0 !important;
        margin-bottom: 8px !important;
      }}

      h2, .section-title {{
        font-size: 20px !important;
        line-height: 1.35 !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        color: var(--text) !important;
        margin-top: 48px !important;
        margin-bottom: 16px !important;
      }}

      h3 {{
        font-size: 16px !important;
        line-height: 1.4 !important;
        font-weight: 600 !important;
        color: var(--text) !important;
        margin-top: 24px !important;
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

      /* Sidebar Styling */
      section[data-testid="stSidebar"] {{
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
      }}

      section[data-testid="stSidebar"] .block-container {{
        padding-top: 24px !important;
        padding-left: 16px !important;
        padding-right: 16px !important;
        padding-bottom: 24px !important;
      }}

      /* Focus Ring Specification */
      button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible {{
        outline: 2px solid var(--accent) !important;
        outline-offset: 2px !important;
      }}

      /* Button Variants (3 Variants: Primary, Secondary, Ghost) */
      button[kind="primary"], .btn-primary {{
        background-color: var(--accent) !important;
        color: #ffffff !important;
        border: 1px solid var(--accent) !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13.5px !important;
        height: 36px !important;
        padding: 0 16px !important;
        box-shadow: none !important;
        transition: opacity 0.15s ease !important;
      }}

      button[kind="primary"]:hover, .btn-primary:hover {{
        opacity: 0.92 !important;
      }}

      button[kind="secondary"], .btn-secondary {{
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        height: 36px !important;
        padding: 0 14px !important;
        box-shadow: none !important;
        transition: background-color 0.15s ease, border-color 0.15s ease !important;
      }}

      button[kind="secondary"]:hover, .btn-secondary:hover {{
        background-color: var(--surface-2) !important;
        border-color: var(--border-strong) !important;
      }}

      button[kind="tertiary"], .btn-ghost {{
        background: transparent !important;
        color: var(--text-2) !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        height: 36px !important;
        padding: 0 12px !important;
        transition: background-color 0.15s ease, color 0.15s ease !important;
      }}

      button[kind="tertiary"]:hover, .btn-ghost:hover {{
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
      }}

      /* Streamlit Tabs Overhaul */
      div[data-testid="stTabs"] {{
        border-bottom: 1px solid var(--border) !important;
        margin-bottom: 24px !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 20px !important;
        background: transparent !important;
        border-bottom: none !important;
        padding: 0 0 4px 0 !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab"] {{
        background: transparent !important;
        border: none !important;
        color: var(--text-2) !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        padding: 12px 4px !important;
        height: auto !important;
        border-bottom: 2px solid transparent !important;
        transition: color 0.15s ease, border-color 0.15s ease !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
        color: var(--text) !important;
      }}

      div[data-testid="stTabs"] [aria-selected="true"] {{
        color: var(--text) !important;
        font-weight: 600 !important;
        border-bottom: 2px solid var(--accent) !important;
        background: transparent !important;
      }}

      div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
        display: none !important;
      }}

      /* Form Inputs, Selectboxes, Text Areas */
      div[data-baseweb="input"], div[data-baseweb="select"] > div, textarea {{
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        color: var(--text) !important;
        font-size: 13.5px !important;
      }}

      div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {{
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(192, 57, 43, 0.25) !important;
      }}

      /* Progress Bar (Ultra-slim 4px) */
      div[data-testid="stProgress"] > div > div {{
        background-color: var(--surface-2) !important;
        border-radius: 999px !important;
        height: 4px !important;
      }}

      div[data-testid="stProgress"] > div > div > div {{
        background-color: var(--accent) !important;
        border-radius: 999px !important;
      }}

      .storage-progress {{
        height: 4px;
        background: var(--surface-2);
        border-radius: 999px;
        overflow: hidden;
        margin: 8px 0 6px 0;
      }}

      .storage-progress-fill {{
        height: 100%;
        background: var(--accent);
        border-radius: 999px;
        transition: width 0.3s ease;
      }}

      /* Metric Summary Tiles */
      .metric-tile {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px 18px;
        transition: border-color 0.15s ease;
      }}

      .metric-tile:hover {{
        border-color: var(--border-strong);
      }}

      .metric-tile-label {{
        font-size: 11.5px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-2);
        margin-bottom: 6px;
      }}

      .metric-tile-value {{
        font-size: 24px;
        font-weight: 650;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        color: var(--text);
        line-height: 1.2;
      }}

      /* Avatars & Priority Badges */
      .avatar-circle {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        background: var(--surface-2);
        border: 1px solid var(--border);
        color: var(--text);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
      }}

      .priority-high {{
        background: var(--accent-soft) !important;
        color: var(--accent) !important;
        border: 1px solid var(--accent) !important;
        font-weight: 600;
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        display: inline-block;
      }}

      .priority-med {{
        background: var(--surface-2) !important;
        color: var(--warn) !important;
        border: 1px solid var(--border) !important;
        font-weight: 600;
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        display: inline-block;
      }}

      .priority-low {{
        background: var(--surface-2) !important;
        color: var(--text-2) !important;
        border: 1px solid var(--border) !important;
        font-weight: 500;
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        display: inline-block;
      }}

      /* Action Matrix Table */
      .action-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13.5px;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
      }}

      .action-table th {{
        background: var(--surface-2);
        color: var(--text-2);
        font-size: 11.5px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 10px 14px;
        text-align: left;
        border-bottom: 1px solid var(--border);
      }}

      .action-table td {{
        padding: 12px 14px;
        border-bottom: 1px solid var(--border);
        color: var(--text);
        line-height: 1.5;
        vertical-align: middle;
      }}

      .action-table tr:last-child td {{
        border-bottom: none;
      }}

      .action-table tr:hover td {{
        background: var(--surface-2);
      }}

      /* Summary / Meeting List Row */
      .meeting-row {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        transition: border-color 0.15s ease, background 0.15s ease;
      }}

      .meeting-row:hover {{
        border-color: var(--border-strong);
        background: var(--surface-2);
      }}

      .ellipsis-text {{
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        display: block;
      }}

      /* Sidebar Navigation Overhaul (36px ghost with 2px active bar) */
      section[data-testid="stSidebar"] div.stButton > button {{
        text-align: left !important;
        justify-content: flex-start !important;
        height: 36px !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        padding: 0 12px !important;
        margin-bottom: 2px !important;
      }}

      /* Skeleton Shimmer Loading State */
      .skeleton {{
        background: linear-gradient(90deg, var(--surface-2) 25%, var(--border) 50%, var(--surface-2) 75%);
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s infinite;
        border-radius: 6px;
      }}

      @keyframes skeleton-shimmer {{
        0% {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
      }}

      /* Cards & Containers */
      .card-raised {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: var(--shadow);
        padding: 24px;
      }}

      .card-flat {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 24px;
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
        font-size: 12px;
        font-weight: 500;
        padding: 3px 10px;
        line-height: 1.4;
      }}

      .pill-accent {{
        background: var(--accent-soft);
        color: var(--accent);
        border: 1px solid var(--accent);
      }}

      /* Empty State Pattern */
      .empty-state {{
        text-align: center;
        padding: 48px 24px;
        color: var(--text-2);
        font-size: 14px;
        background: var(--surface-2);
        border: 1px dashed var(--border);
        border-radius: 10px;
      }}

      .empty-state-title {{
        font-size: 16px;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 6px;
      }}


      /* Responsive Specifications */
      @media (min-width: 1200px) {{
        .main .block-container {{
          max-width: 1120px !important;
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
    st.markdown(app_css, unsafe_allow_html=True)

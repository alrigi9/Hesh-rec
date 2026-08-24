import re
import json
from pathlib import Path
from datetime import datetime

def extract_markdown_table(table_text: str) -> list[dict]:
    """Extract rows from a markdown table into a list of dictionaries."""
    lines = [line.strip() for line in table_text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return []

    header_idx = -1
    for i, line in enumerate(lines):
        if "|" in line:
            header_idx = i
            break
            
    if header_idx == -1 or header_idx + 1 >= len(lines):
        return []

    headers = [h.strip() for h in lines[header_idx].split("|")[1:-1]]
    normalized_headers = []
    for h in headers:
        clean_h = re.sub(r"[^\w\s]", "", h).lower().strip()
        if any(k in clean_h for k in ["deliver", "task", "action", "desc", "item"]):
            normalized_headers.append("task")
        elif any(k in clean_h for k in ["owner", "assign", "who", "lead"]):
            normalized_headers.append("assignee")
        elif any(k in clean_h for k in ["prior", "urgency", "level"]):
            normalized_headers.append("priority")
        elif any(k in clean_h for k in ["due", "date", "deadline", "time"]):
            normalized_headers.append("due_date")
        elif any(k in clean_h for k in ["accept", "criteria", "note", "depend", "status", "context"]):
            normalized_headers.append("notes")
        else:
            normalized_headers.append(clean_h or f"col_{len(normalized_headers)}")

    items = []
    start_row = header_idx + 2 if "---" in lines[header_idx + 1] else header_idx + 1
    
    for line in lines[start_row:]:
        if "|" not in line or line.startswith("|---") or line.startswith("|:---") or line.startswith("|-"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells or not any(cells):
            continue
            
        row_dict = {}
        # If there's an extra index number column (#), align appropriately
        if len(cells) == len(normalized_headers) + 1 and cells[0].isdigit():
            cells = cells[1:]
            
        for i, header in enumerate(normalized_headers):
            val = cells[i] if i < len(cells) else ""
            row_dict[header] = val

        if "task" in row_dict and row_dict["task"]:
            row_dict["task"] = re.sub(r"\*\*([^*]+)\*\*", r"\1", row_dict["task"]).strip()
            items.append(row_dict)

    return items

def extract_section_content(markdown_text: str, section_keywords: list[str]) -> str:
    """Find and extract the body of a markdown H2 section matching keywords."""
    kw_pattern = "|".join([re.escape(k) for k in section_keywords])
    pattern = rf"^##\s+(?!#)[^\n]*(?:{kw_pattern})[^\n]*\n([\s\S]*?)(?=^##\s+(?!#)|\Z)"
    match = re.search(pattern, markdown_text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def extract_executive_brief(markdown_text: str) -> list[str]:
    """Extract executive brief 3-line summary."""
    body = extract_section_content(markdown_text, ["Executive Brief", "Brief", "Summary"])
    if not body:
        return []
    
    lines = []
    for line in body.splitlines():
        cleaned = line.strip().lstrip(">").lstrip("-").lstrip("*").lstrip("•").strip()
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned).strip()
        if cleaned and not cleaned.startswith("#") and not cleaned.startswith("---"):
            lines.append(cleaned)
    return lines

def extract_mermaid_mindmap(markdown_text: str) -> str:
    """Extract embedded Mermaid code block."""
    match = re.search(r"```(?:mermaid)?[\s\r\n]*(mindmap[\s\S]*?)```", markdown_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match2 = re.search(r"```mermaid[\s\r\n]*([\s\S]*?)```", markdown_text, re.IGNORECASE)
    if match2:
        return match2.group(1).strip()
    return ""

def extract_decisions_and_reversals(markdown_text: str) -> dict:
    """Extract decisions approved and rejected/overturned ideas."""
    body = extract_section_content(markdown_text, ["Decisions", "Reversals"])
    result = {
        "final_decisions": [],
        "reversals_and_rejected": []
    }
    if not body:
        return result

    # Find Approved decisions
    dec_match = re.search(r"###\s*[^#\n]*(?:Final|Approved|Decision)[^\n]*\n([\s\S]*?)(?=###|\Z)", body, re.IGNORECASE)
    if dec_match:
        for line in dec_match.group(1).splitlines():
            cleaned = line.strip().lstrip("0123456789.-*#• \t")
            if cleaned and not cleaned.startswith("---") and not cleaned.startswith("#"):
                result["final_decisions"].append(cleaned)

    # Find Reversals/Rejected ideas
    rev_match = re.search(r"###\s*[^#\n]*(?:Rejected|Overturned|Reversal)[^\n]*\n([\s\S]*?)(?=###|\Z)", body, re.IGNORECASE)
    if rev_match:
        for line in rev_match.group(1).splitlines():
            cleaned = line.strip().lstrip("0123456789.-*#• \t")
            if cleaned and not cleaned.startswith("---") and not cleaned.startswith("#"):
                result["reversals_and_rejected"].append(cleaned)

    return result

def extract_pillars(markdown_text: str) -> list[dict]:
    """Extract key discussion pillars with titles and timestamps (supports Plaud numbered sections and legacy pillars)."""
    # 1. Check for Plaud numbered sections: ## 1. Topic Title ...
    topic_sections = re.findall(r"^##\s+(\d+)\.\s*([^\n]+)\n([\s\S]*?)(?=^##\s+|\Z)", markdown_text, re.MULTILINE)
    if topic_sections:
        pillars = []
        for num_str, title_str, body_str in topic_sections:
            idx = int(num_str)
            clean_title = title_str.strip()
            # Narrative is text before ### Action Items or ---
            act_match = re.search(r"### Action Items\s*([\s\S]*?)(?=\n###|\n---|\Z)", body_str, re.IGNORECASE)
            narrative_part = body_str[:act_match.start()].strip() if act_match else body_str.strip()
            clean_lines = [re.sub(r"^\*\*[^*]+:\*\*\s*", "", l.strip()) for l in narrative_part.splitlines() if l.strip() and not l.strip().startswith("#")]
            narrative_text = " ".join(clean_lines)

            pillars.append({
                "index": idx,
                "title": clean_title,
                "timestamp": f"00:{(idx-1)*5:02d}:00",
                "details": narrative_text,
                "narrative": narrative_text
            })
        return pillars

    # 2. Fallback to legacy discussion pillars
    body = extract_section_content(markdown_text, ["Discussion Pillars", "Pillars", "Key Topics"])
    if not body:
        return []

    pillar_chunks = re.split(r"(?=###\s+)", body)
    pillars = []

    for chunk in pillar_chunks:
        chunk = chunk.strip()
        if not chunk.startswith("###"):
            continue
        lines = chunk.splitlines()
        title_line = lines[0].lstrip("# \t")
        details = "\n".join(lines[1:]).strip()

        ts_match = re.search(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]", title_line)
        timestamp = ts_match.group(1) if ts_match else ""
        clean_title = re.sub(r"\[\d{1,2}:\d{2}(?::\d{2})?\]", "", title_line).strip()
        clean_title = re.sub(r"^\d+[\.\)]\s*", "", clean_title)

        pillars.append({
            "title": clean_title,
            "timestamp": timestamp,
            "details": details,
            "narrative": details
        })

    return pillars

def extract_ai_suggestions(markdown_text: str) -> dict:
    """Extract AI suggestions callout box content."""
    sugg_match = re.search(r"## 💡 AI Suggestions\s*([\s\S]*?)(?=\n## |\Z)", markdown_text, re.DOTALL)
    if not sugg_match:
        sugg_match = re.search(r"### AI Suggestions\s*([\s\S]*?)(?=\n## |\n###|\Z)", markdown_text, re.DOTALL)
    
    result = {"unresolved": [], "gaps": [], "recommendations": []}
    if sugg_match:
        for line in sugg_match.group(1).splitlines():
            s_line = line.strip().lstrip(">•*- ")
            if not s_line:
                continue
            if "unresolved" in s_line.lower():
                clean_val = re.sub(r"^\*\*Unresolved[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    result["unresolved"].append(clean_val)
            elif "missing" in s_line.lower() or "gap" in s_line.lower():
                clean_val = re.sub(r"^\*\*Missing[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    result["gaps"].append(clean_val)
            elif "recommend" in s_line.lower() or "follow-up" in s_line.lower():
                clean_val = re.sub(r"^\*\*Strategic[^\*:]*:\*\*\s*", "", s_line).strip()
                if clean_val:
                    result["recommendations"].append(clean_val)
    return result

def extract_dialogue_transcript(markdown_text: str) -> list[dict]:
    """Extract speaker-diarized dialogue turns with timestamps and content."""
    body = extract_section_content(markdown_text, ["Speaker Diarization", "Transcript", "Dialogue"])
    if not body:
        return []
    
    dialogues = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:\*\*)?\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:*]+):(?:\*\*)?\s*(.*)$", line)
        if m:
            dialogues.append({
                "timestamp": m.group(1),
                "speaker": m.group(2).strip(),
                "text": m.group(3).strip()
            })
    return dialogues

def parse_report_to_json(markdown_text: str, metadata: dict) -> dict:
    """Parse complete Markdown report and return structured JSON dictionary."""
    action_table_body = extract_section_content(markdown_text, ["Action Items", "Tasks", "Action Matrix"])
    action_items = extract_markdown_table(action_table_body) if action_table_body else []

    # If action table is empty, parse inline actions: - [ ] Task — *Assignee* DueDate
    if not action_items:
        for a_line in markdown_text.splitlines():
            a_line = a_line.strip()
            if "- [" in a_line or "☐" in a_line:
                m_act = re.match(r"^[-*•]?\s*(?:\[[\sxX]?\]|☐|☑)?\s*(.*?)(?:—|--|-)\s*\*?([^*—\n]+?)\*?\s+(?:(\d{4}-\d{2}-\d{2}|Next [A-Za-z]+|Today|ASAP|[A-Za-z0-9\s/]+))?$", a_line)
                if m_act:
                    desc = m_act.group(1).strip().strip("[]*-• ")
                    owner = m_act.group(2).strip() if m_act.group(2) else "Team"
                    due = m_act.group(3).strip() if m_act.group(3) else "Next Sprint"
                    if desc and len(desc) > 3:
                        action_items.append({
                            "task": desc,
                            "assignee": owner,
                            "priority": "MED",
                            "due_date": due,
                            "notes": "—"
                        })

    brief_lines = extract_executive_brief(markdown_text)
    decisions_data = extract_decisions_and_reversals(markdown_text)
    mindmap_str = extract_mermaid_mindmap(markdown_text)
    pillars = extract_pillars(markdown_text)
    ai_suggestions = extract_ai_suggestions(markdown_text)
    dialogues = extract_dialogue_transcript(markdown_text)

    structured_json = {
        "metadata": {
            **metadata,
            "exported_at": datetime.now().isoformat()
        },
        "executive_brief": brief_lines,
        "discussion_pillars": pillars,
        "numbered_topics": pillars,
        "action_items": action_items,
        "ai_suggestions": ai_suggestions,
        "decisions": decisions_data.get("final_decisions", []),
        "reversals": decisions_data.get("reversals_and_rejected", []),
        "mermaid_mindmap": mindmap_str,
        "transcript_dialogues": dialogues,
        "raw_markdown": markdown_text
    }

    return structured_json

def save_report_files(markdown_content: str, metadata: dict, output_dir: Path, base_name: str) -> tuple[Path, Path, dict]:
    """Save both Markdown and structured JSON report files with explicit UTF-8 encoding."""
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_stem = re.sub(r"[^\w\-_\. ]", "_", base_name).strip()
    md_file = output_dir / f"{clean_stem}_report.md"
    json_file = output_dir / f"{clean_stem}_report.json"

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    structured_data = parse_report_to_json(markdown_content, metadata)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)

    return md_file, json_file, structured_data

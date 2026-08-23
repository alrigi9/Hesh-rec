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
    """Extract key discussion pillars with titles and timestamps."""
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
            "details": details
        })

    return pillars

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

    brief_lines = extract_executive_brief(markdown_text)
    decisions_data = extract_decisions_and_reversals(markdown_text)
    mindmap_str = extract_mermaid_mindmap(markdown_text)
    pillars = extract_pillars(markdown_text)
    dialogues = extract_dialogue_transcript(markdown_text)

    structured_json = {
        "metadata": {
            **metadata,
            "exported_at": datetime.now().isoformat()
        },
        "executive_brief": brief_lines,
        "discussion_pillars": pillars,
        "action_items": action_items,
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

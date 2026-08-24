import os
import time
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types

from core.config import get_api_key, get_mime_type, DEFAULT_MODEL, OUTPUTS_DIR
from core.parser import save_report_files
from core.ui import console, print_step, print_error

def build_meeting_prompt(topic: str, current_date: str) -> str:
    """Build the prompt instructions for exact Plaud document-first meeting intelligence."""
    return f"""You are an elite Executive Meeting & Speech Intelligence Analyst adhering strictly to the clean, document-first Plaud methodology.
Your objective is to produce an elegant, narrative-first executive intelligence report from the provided audio/video meeting recording with ZERO redundant boilerplate labels.

Analyze the entire recording thoroughly and generate the report adhering STRICTLY to the following clean Plaud document structure:

# {topic}

## 1. [First Core Topic Title]
[A comprehensive, highly detailed executive narrative consisting of 4-7 complete sentences in past tense detailing the background context, technical trade-offs discussed, arguments raised, and decided roadmap. DO NOT include boilerplate labels like 'Core Topic & Focus:' or 'Speaker Perspective:' or 'Context:'; write clean, authoritative executive business prose.]

### Action Items
- [ ] [Fully specific, actionable deliverable with document IDs, slide numbers, or technical parameters] — *[Assignee]* [Date if available]
- [ ] [Fully specific, actionable deliverable with document IDs, slide numbers, or technical parameters] — *[Assignee]* [Date if available]

## 2. [Second Core Topic Title]
[A comprehensive, highly detailed executive narrative consisting of 4-7 complete sentences in past tense detailing what happened, technical considerations, and resolution.]

### Action Items
- [ ] [Task deliverable] — *[Assignee]* [Date if available]

## 3. [Third Core Topic Title]
[A comprehensive, highly detailed executive narrative consisting of 4-7 complete sentences in past tense detailing what happened, technical considerations, and resolution.]

### Action Items
- [ ] [Task deliverable] — *[Assignee]* [Date if available]

## AI Suggestions
> AI has identified the following issues that were not concluded in the meeting or lack clear action items; please pay attention:
1. **[Specific Risk or Gap Title]**: [Concrete explanation of the unassigned risk, missing deadline, or governance gap and recommended next step]
2. **[Specific Risk or Gap Title]**: [Concrete explanation of the unassigned risk, missing deadline, or governance gap and recommended next step]

## Visual Architecture (Mermaid Mindmap)

CRITICAL RULES FOR MERMAID:
- Format EVERY node safely with double quotes: root["Title"], ["Branch"], ["Leaf"].
- NEVER use raw '&', '<', '>', unescaped quotes, or brackets inside node text (use 'and' instead of '&').
- Strictly adhere to valid Mermaid mindmap indentation.
- Strictly mirror the numbered sections, sub-actions, and AI suggestions:
```mermaid
mindmap
  root["{topic}"]
    ["1. First Topic Title"]
      ["Narrative Focus Point"]
      ["Action: Deliverable description"]
    ["2. Second Topic Title"]
      ["Narrative Focus Point"]
      ["Action: Deliverable description"]
    ["AI Suggestions"]
      ["Unresolved Point or Gap"]
      ["Strategic Recommendation"]
```

## 🗣️ Speaker Diarization & Complete Transcript

Transcribe the dialogue faithfully with timestamps and speaker attribution:

**[00:00:02] Speaker 1 (Name if identified):** [Accurate transcript...]
**[00:00:15] Speaker 2 (Name if identified):** [Accurate transcript...]
"""

def generate_detailed_markmap_md(session_data: dict) -> str:
    """Dynamically builds deep hierarchical markdown for Markmap strictly from sections and action items, never using stale mindmap JSON."""
    # Use title or summary title
    title = session_data.get("title") or session_data.get("meeting_title") or "Meeting Summary"
    clean_title = re.sub(r"^#+\s*", "", str(title)).strip() or "Meeting Summary"
    lines = [f"# {clean_title}"]
    
    sections = session_data.get("sections") or []
    if not sections:
        sections = session_data.get("numbered_topics", []) or session_data.get("discussion_pillars", [])
        
    has_section_actions = False
    for sec in sections:
        n = sec.get("n", "") or sec.get("index", "")
        t = sec.get("title", "")
        clean_t = re.sub(r"^\d+\.\s*", "", str(t)).strip()
        header = f"## {n}. {clean_t}" if n else f"## {clean_t}"
        lines.append(header)
        
        # Narrative branch
        narrative = (sec.get("narrative") or sec.get("details") or "").strip()
        if narrative:
            clean_narrative = re.sub(r"^\*\*[^*]+:\*\*\s*", "", narrative)
            clean_narrative = re.sub(r"^[-*•]\s*", "", clean_narrative)
            # Flatten multi-line text into a single line for Markmap
            clean_narrative = " ".join(clean_narrative.split())
            if clean_narrative:
                lines.append(f"- {clean_narrative}")
            
        # Action Items branch with individual task leaves
        action_items = sec.get("action_items") or []
        if action_items:
            has_section_actions = True
            lines.append("- Action Items")
            for item in action_items:
                task = (item.get("task") or item.get("description") or "").strip()
                owner = (item.get("owner") or item.get("assignee") or "Unassigned").strip()
                due = f" -- {item.get('due_date')}" if item.get("due_date") else (f" -- {item.get('due_text')}" if item.get("due_text") else "")
                lines.append(f"  - {task} -- {owner}{due}")

    # Fallback to top-level action_items if not inside sections
    if not has_section_actions and session_data.get("action_items"):
        lines.append("## Action Items")
        for item in session_data["action_items"]:
            task = (item.get("task") or item.get("description") or "").strip()
            owner = (item.get("owner") or item.get("assignee") or "Unassigned").strip()
            due = f" -- {item.get('due_date')}" if item.get("due_date") else (f" -- {item.get('due_text')}" if item.get("due_text") else "")
            lines.append(f"- {task} -- {owner}{due}")
                
    ai_suggestions = session_data.get("ai_suggestions") or []
    if ai_suggestions:
        lines.append("## AI Suggestions")
        if isinstance(ai_suggestions, list):
            for sugg in ai_suggestions:
                if isinstance(sugg, dict):
                    lbl = sugg.get("label", "").strip()
                    det = sugg.get("detail", "").strip()
                    lines.append(f"- **{lbl}**: {det}")
                else:
                    lines.append(f"- {sugg}")
        elif isinstance(ai_suggestions, dict):
            for sugg in ai_suggestions.get("items", []):
                lbl = sugg.get("label", "").strip()
                det = sugg.get("detail", "").strip()
                lines.append(f"- **{lbl}**: {det}")
            
    return "\n".join(lines)


build_markmap_md = generate_detailed_markmap_md


class MeetingAnalyzer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or get_api_key()
        if not self.api_key:
            raise ValueError(
                "Gemini API key is not configured! Please add GEMINI_API_KEY to your .env file "
                "or set it as an environment variable."
            )
        self.model_name = model or DEFAULT_MODEL
        self.client = genai.Client(api_key=self.api_key)

    def process_file(
        self,
        file_path: Path | str,
        output_dir: Path | None = None,
        keep_remote_file: bool = False
    ) -> dict:
        """Upload audio/video file to Gemini File API, poll processing, and generate Plaud report."""
        target_path = Path(file_path).resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"Media file not found at: {target_path}")

        out_dir = output_dir or OUTPUTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        file_size_bytes = target_path.stat().st_size
        file_size_formatted = f"{file_size_bytes / (1024 * 1024):.2f} MB"
        mime_type = get_mime_type(target_path)
        base_name = target_path.stem

        print_step("Input File", f"{target_path.name} ({file_size_formatted}, {mime_type})", "info")

        start_time = time.time()
        uploaded_file = None

        try:
            # 1. Upload to Gemini File API
            with console.status(f"[bold cyan]Uploading {target_path.name} to Gemini File API...", spinner="dots"):
                upload_config = types.UploadFileConfig(
                    mime_type=mime_type,
                    display_name=target_path.name
                )
                uploaded_file = self.client.files.upload(
                    file=str(target_path),
                    config=upload_config
                )
            print_step("File Upload", f"Uploaded as '{uploaded_file.name}'", "upload")

            # 2. Poll file state until ACTIVE
            with console.status("[bold magenta]Processing media on Gemini infrastructure...", spinner="bouncingBar") as status:
                poll_start = time.time()
                while True:
                    file_info = self.client.files.get(name=uploaded_file.name)
                    state_str = getattr(file_info.state, "name", str(file_info.state)).upper()

                    if "ACTIVE" in state_str:
                        break
                    elif "FAILED" in state_str:
                        raise RuntimeError(f"Gemini file processing failed for {target_path.name}: {file_info.error}")
                    
                    if time.time() - poll_start > 600: # 10 minute timeout
                        raise TimeoutError("Gemini file processing timed out after 10 minutes.")

                    status.update(f"[bold magenta]Processing audio/video (State: {state_str})... ({int(time.time() - poll_start)}s)")
                    time.sleep(2.5)

            print_step("Media Readiness", "Audio/video track processed and indexed", "success")

            # 3. Prompt generation
            formatted_prompt = build_meeting_prompt(
                topic=base_name.replace("_", " ").title(),
                current_date=datetime.now().strftime("%Y-%m-%d %H:%M")
            )

            with console.status(f"[bold green]Generating Plaud AI Intelligence Report using [bold white]{self.model_name}[/]...", spinner="aesthetic"):
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        uploaded_file,
                        formatted_prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                    )
                )

            if not response.text:
                raise RuntimeError("Empty response received from Gemini model.")

            elapsed = time.time() - start_time
            elapsed_formatted = f"{elapsed:.1f}s"
            print_step("Inference", f"Report generated in {elapsed_formatted}", "success")

            # 4. Parse and Save Report Files
            metadata = {
                "source_file": str(target_path),
                "filename": target_path.name,
                "file_size": file_size_formatted,
                "mime_type": mime_type,
                "model": self.model_name,
                "processing_time": elapsed_formatted,
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            md_path, json_path, structured_json = save_report_files(
                markdown_content=response.text,
                metadata=metadata,
                output_dir=out_dir,
                base_name=base_name
            )

            action_items = structured_json.get("action_items", [])
            exec_brief = "\n".join(structured_json.get("executive_brief", []))

            result_summary = {
                "input_file": target_path.name,
                "file_size_formatted": file_size_formatted,
                "model": self.model_name,
                "processing_time": elapsed_formatted,
                "action_items_count": len(action_items),
                "action_items": action_items,
                "executive_brief": exec_brief,
                "md_path": str(md_path),
                "json_path": str(json_path),
                "raw_markdown": response.text,
                "structured_data": structured_json
            }

            return result_summary

        finally:
            # 5. Clean up remote file if requested
            if uploaded_file and not keep_remote_file:
                try:
                    self.client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

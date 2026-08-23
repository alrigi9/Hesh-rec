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
    """Build the prompt instructions for Plaud-style meeting intelligence."""
    return f"""You are an elite Executive Meeting Intelligence AI Analyst powered by Plaud AI methodology.
Your objective is to produce a comprehensive, structured, high-impact intelligence report from the provided audio/video meeting recording.

Analyze the entire recording thoroughly and generate the report adhering STRICTLY to the following Markdown structure and formatting guidelines:

# 🎙️ Meeting Intelligence Report: {topic}

**Generated:** {current_date}
**Duration:** [Extract estimated meeting duration, e.g. 00:45:20]
**Identified Participants:** [List all identified participants, roles/titles if discernible from speech]

---

## ⚡ Executive Brief
> • **Strategic Purpose:** [1 sentence summarizing the core objective and purpose of this session]
> • **Key Breakthrough & Consensus:** [1 sentence highlighting the major agreement, breakthrough, or conclusion]
> • **Immediate Next Step:** [1 sentence summarizing the most urgent action or critical milestone]

---

## 🏛️ Key Discussion Pillars

Divide the meeting into clear thematic pillars in chronological order with precise timestamps.

### 1. [00:00:00] [Pillar 1 Title]
- **Context & Objective:** [Summary of why this topic was brought up]
- **Key Arguments & Perspectives:**
  - **Speaker A:** [Key perspective/points]
  - **Speaker B:** [Counterpoint or supporting points]
- **Consensus & Outcome:** [What was agreed or concluded on this pillar]

### 2. [00:15:00] [Pillar 2 Title]
- **Context & Objective:** [Summary]
- **Key Arguments & Perspectives:**
  - **Speaker A:** [Details]
- **Consensus & Outcome:** [Outcome]

[Add more pillars as needed to cover the entire conversation]

---

## 📋 Action Items Matrix

Provide a complete, actionable markdown table capturing all commitments, deliverables, owners, urgency, and deadlines mentioned.
CRITICAL RULE: In the "Task Deliverable" column, NEVER write brief generic phrases like "Keep it simple" or "Follow up". You MUST specify the EXACT complete deliverable, context, and expected outcome (e.g., "Design and build a 5-question quiz for SOC 2 awareness training and distribute to all staff" or "Draft security questionnaire response for enterprise vendor review").

| # | Task Deliverable | Owner | Priority | Due Date | Acceptance Criteria & Notes |
|---|------------------|-------|----------|----------|-----------------------------|
| 1 | [Comprehensive, concrete task deliverable description] | [Specific Person or Role] | [HIGH / MED / LOW] | [YYYY-MM-DD or timeframe] | [Clear acceptance criteria or dependencies] |

---

## ⚖️ Decisions & Reversals

### ✅ Final Decisions Approved
1. **[00:00:00] [Decision Title]:** [Detailed explanation of the agreed decision and owner]

### 🔄 Rejected & Overturned Ideas (Reversals)
1. **[00:00:00] [Rejected Proposal Title]:** [What idea was proposed, why the group rejected or reversed course, and what alternative was adopted instead]

---

## 🗺️ Visual Architecture (Mermaid Mindmap)

Generate a valid Mermaid mindmap representing the meeting taxonomy, themes, decisions, and action items. Keep node texts clean without special characters or quotes that break Mermaid rendering.

```mermaid
mindmap
  root((Meeting Topic))
    Executive Brief
      Strategic Direction
      Key Milestone
    Discussion Pillars
      Pillar 1
        Point A
        Point B
      Pillar 2
        Point A
        Point B
    Decisions
      Approved Decision 1
      Approved Decision 2
    Action Items
      High Priority
        Task 1
      Medium Priority
        Task 2
```

---

## 🗣️ Speaker Diarization & Complete Transcript

Transcribe the dialogue faithfully with timestamps and speaker attribution:

**[00:00:02] Speaker 1 (Name if identified):** [Accurate transcript...]
**[00:00:15] Speaker 2 (Name if identified):** [Accurate transcript...]
"""

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

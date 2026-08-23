import time
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from core.config import is_supported_media, INPUTS_DIR
from core.analyzer import MeetingAnalyzer
from core.ui import console, print_step, print_error, display_action_items_table, display_report_summary

class MediaFileHandler(FileSystemEventHandler):
    """Event handler that detects new media files in the inputs directory."""

    def __init__(self, analyzer: MeetingAnalyzer, watch_dir: Path):
        super().__init__()
        self.analyzer = analyzer
        self.watch_dir = watch_dir
        self.processing_paths = set()
        self.completed_paths = set()

    def on_created(self, event):
        if not event.is_directory:
            self._handle_media_file(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._handle_media_file(Path(event.src_path))

    def _wait_for_file_ready(self, file_path: Path, max_wait: int = 30) -> bool:
        """Ensure file has finished copying/writing by verifying size stability and file locks."""
        last_size = -1
        stable_count = 0
        start = time.time()

        while time.time() - start < max_wait:
            try:
                if not file_path.exists():
                    return False
                current_size = file_path.stat().st_size
                if current_size > 0 and current_size == last_size:
                    # Test if file can be opened for reading exclusively
                    try:
                        with open(file_path, "rb") as f:
                            pass
                        stable_count += 1
                        if stable_count >= 2:
                            return True
                    except (IOError, PermissionError):
                        stable_count = 0
                else:
                    stable_count = 0
                    last_size = current_size
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def _handle_media_file(self, file_path: Path):
        file_path = file_path.resolve()
        if not is_supported_media(file_path):
            return

        if file_path in self.processing_paths or file_path in self.completed_paths:
            return

        self.processing_paths.add(file_path)

        try:
            print_step("New File Detected", f"[bold cyan]{file_path.name}[/]", "watch")
            
            # Wait for write completion
            with console.status(f"[bold yellow]Waiting for {file_path.name} to finish writing...", spinner="dots"):
                ready = self._wait_for_file_ready(file_path)

            if not ready:
                print_step("File Warning", f"{file_path.name} could not be locked or is empty. Skipping.", "warning")
                return

            print_step("Processing Triggered", f"Analyzing [bold green]{file_path.name}[/]...", "processing")
            
            result = self.analyzer.process_file(file_path)
            
            self.completed_paths.add(file_path)
            display_action_items_table(result.get("action_items", []))
            display_report_summary(result)
            
            console.print("\n[bold cyan]👀 Still watching for new recordings in:[/] [white]{}[/]\n".format(self.watch_dir))

        except Exception as e:
            print_error("Watch Processing Error", str(e), hint="Ensure the recording is intact and your Gemini API key is valid.")
        finally:
            self.processing_paths.discard(file_path)

def start_watching(watch_dir: Path | None = None, model: str | None = None):
    """Start background folder observer for inputs directory."""
    target_dir = (watch_dir or INPUTS_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    analyzer = MeetingAnalyzer(model=model)
    event_handler = MediaFileHandler(analyzer, target_dir)

    observer = Observer()
    observer.schedule(event_handler, path=str(target_dir), recursive=False)
    observer.start()

    console.print(f"[bold green]✔ Watchdog active![/] Monitoring folder:\n👉 [bold cyan]{target_dir}[/]")
    console.print("[dim]Drop any audio (.mp3, .wav, .m4a) or video (.mp4, .mkv) file into this folder to analyze automatically.[/]")
    console.print("[dim]Press [bold white]Ctrl + C[/] to stop watching.\n[/]")

    # Also check if there are any existing unprocessed media files in inputs directory
    existing_files = [
        f for f in target_dir.iterdir() 
        if f.is_file() and is_supported_media(f)
    ]
    if existing_files:
        console.print(f"[bold yellow]Found {len(existing_files)} existing file(s) in inputs folder.[/]")
        for f in existing_files:
            event_handler._handle_media_file(f)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]Watch mode stopped by user.[/]")
    observer.join()

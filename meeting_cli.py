import sys
import os

# Enforce UTF-8 encoding on Windows standard streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
from pathlib import Path
from datetime import datetime

from core.config import BASE_DIR, INPUTS_DIR, OUTPUTS_DIR, DEFAULT_MODEL, get_api_key, is_supported_media
from core.analyzer import MeetingAnalyzer
from core.watcher import start_watching
from core.ui import (
    console,
    print_banner,
    print_step,
    print_error,
    display_action_items_table,
    display_report_summary,
    display_reports_list,
    view_markdown_report,
)

def check_environment():
    """Verify essential environment prerequisites before executing commands."""
    api_key = get_api_key()
    if not api_key:
        print_banner()
        print_error(
            "Gemini API Key Missing",
            "No GEMINI_API_KEY found in your environment or .env file.",
            "Open 'D:\\claude word\\plaud AI\\.env' and set GEMINI_API_KEY=your_actual_key,\n"
            "or run: set GEMINI_API_KEY=your_key in PowerShell / Command Prompt."
        )
        sys.exit(1)

def resolve_input_file(file_arg: str) -> Path:
    """Resolve file path whether given as absolute, relative, or just filename in inputs directory."""
    raw_path = Path(file_arg)
    
    # 1. Direct path check
    if raw_path.exists():
        return raw_path.resolve()

    # 2. Check within inputs/ directory
    inputs_candidate = INPUTS_DIR / file_arg
    if inputs_candidate.exists():
        return inputs_candidate.resolve()

    # 3. Search with extension if omitted
    for ext in [".mp3", ".wav", ".m4a", ".mp4", ".aac", ".flac", ".ogg", ".mov", ".mkv"]:
        cand1 = Path(f"{file_arg}{ext}")
        if cand1.exists():
            return cand1.resolve()
        cand2 = INPUTS_DIR / f"{file_arg}{ext}"
        if cand2.exists():
            return cand2.resolve()

    raise FileNotFoundError(
        f"Could not find media file '{file_arg}' in current directory or in inputs folder ({INPUTS_DIR})."
    )

def handle_process(args):
    """Process a single meeting audio/video recording."""
    check_environment()
    try:
        file_path = resolve_input_file(args.file)
        if not is_supported_media(file_path):
            print_error(
                "Unsupported File Format",
                f"File '{file_path.name}' does not have a supported audio/video extension.",
                "Supported formats: .mp3, .wav, .m4a, .mp4, .aac, .flac, .ogg, .mov, .mkv, .webm, .wma"
            )
            sys.exit(1)

        print_banner()
        analyzer = MeetingAnalyzer(model=args.model)
        output_dir = Path(args.output_dir).resolve() if args.output_dir else OUTPUTS_DIR

        result = analyzer.process_file(
            file_path=file_path,
            output_dir=output_dir,
            keep_remote_file=args.keep_remote
        )

        if not args.no_preview:
            display_action_items_table(result.get("action_items", []))
        
        display_report_summary(result)

    except Exception as e:
        print_error("Processing Failed", str(e))
        sys.exit(1)

def handle_watch(args):
    """Watch the inputs directory and automatically process incoming media."""
    check_environment()
    print_banner()
    watch_dir = Path(args.dir).resolve() if args.dir else INPUTS_DIR
    try:
        start_watching(watch_dir=watch_dir, model=args.model)
    except Exception as e:
        print_error("Watchdog Error", str(e))
        sys.exit(1)

def handle_list(args):
    """List all previously generated meeting reports."""
    print_banner()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else OUTPUTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all report files
    md_files = list(output_dir.glob("*_report.md"))
    reports = []
    
    for md in md_files:
        stem = md.name.replace("_report.md", "")
        json_counterpart = output_dir / f"{stem}_report.json"
        stat = md.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = stat.st_size / 1024
        
        reports.append({
            "name": stem.replace("_", " ").title(),
            "created_at": mtime,
            "has_md": True,
            "has_json": json_counterpart.exists(),
            "size_str": f"{size_kb:.1f} KB",
            "md_path": md,
            "json_path": json_counterpart
        })

    # Sort newest first
    reports.sort(key=lambda r: r["created_at"], reverse=True)
    display_reports_list(reports)

def handle_view(args):
    """Render a report directly in the terminal."""
    print_banner()
    output_dir = OUTPUTS_DIR
    target = args.report_name
    
    target_path = Path(target)
    if not target_path.exists():
        # Try finding in outputs dir
        cand1 = output_dir / target
        cand2 = output_dir / f"{target}_report.md"
        cand3 = output_dir / f"{target}.md"
        if cand1.exists():
            target_path = cand1
        elif cand2.exists():
            target_path = cand2
        elif cand3.exists():
            target_path = cand3
        else:
            # Match by substring
            matches = list(output_dir.glob(f"*{target}*.md"))
            if matches:
                target_path = matches[0]
            else:
                print_error("Report Not Found", f"Could not find any report matching '{target}' in {output_dir}")
                sys.exit(1)

    view_markdown_report(target_path)

def interactive_menu():
    """Interactive CLI menu when meeting_cli.py is run without arguments."""
    print_banner()
    while True:
        console.print("\n[bold cyan]Select an operation:[/]")
        console.print("  [bold white]1.[/] 🚀 [bold green]Process a single audio/video file[/]")
        console.print("  [bold white]2.[/] 👀 [bold yellow]Start Watchdog folder listener (inputs/)[/]")
        console.print("  [bold white]3.[/] 📂 [bold blue]List all past meeting reports[/]")
        console.print("  [bold white]4.[/] 📄 [bold magenta]View a report in terminal[/]")
        console.print("  [bold white]5.[/] ❌ [dim]Exit[/]\n")

        choice = console.input("[bold cyan]Enter choice [1-5]: [/]").strip()

        if choice == "1":
            file_name = console.input("\n[bold white]Enter file path or filename (in inputs/): [/]").strip().strip('"\'')
            if not file_name:
                continue
            class DummyArgs:
                file = file_name
                model = DEFAULT_MODEL
                output_dir = None
                keep_remote = False
                no_preview = False
            handle_process(DummyArgs())
        elif choice == "2":
            class DummyWatchArgs:
                dir = None
                model = DEFAULT_MODEL
            handle_watch(DummyWatchArgs())
            break
        elif choice == "3":
            class DummyListArgs:
                output_dir = None
            handle_list(DummyListArgs())
        elif choice == "4":
            rep_name = console.input("\n[bold white]Enter report or meeting name to view: [/]").strip().strip('"\'')
            if not rep_name:
                continue
            class DummyViewArgs:
                report_name = rep_name
            handle_view(DummyViewArgs())
        elif choice in ("5", "q", "exit", "quit"):
            console.print("[dim]Goodbye![/]")
            break
        else:
            console.print("[yellow]Invalid option. Please choose 1-5.[/]")

def main():
    parser = argparse.ArgumentParser(
        prog="meeting_cli",
        description="🎙️ Plaud AI Meeting Studio - Google Gemini-powered executive intelligence pipeline for audio & video."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: process
    proc_parser = subparsers.add_parser("process", help="Process an audio/video recording and generate a Plaud-style report.")
    proc_parser.add_argument("file", help="Path to audio/video file (e.g. 'inputs/meeting.mp3' or 'meeting.mp4')")
    proc_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model to use (default: {DEFAULT_MODEL})")
    proc_parser.add_argument("--output-dir", default=None, help="Custom output directory")
    proc_parser.add_argument("--keep-remote", action="store_true", help="Keep uploaded file in Gemini File API")
    proc_parser.add_argument("--no-preview", action="store_true", help="Skip terminal action item table preview")

    # Command: watch
    watch_parser = subparsers.add_parser("watch", help="Watch the inputs directory and automatically analyze new recordings.")
    watch_parser.add_argument("--dir", default=None, help="Directory to watch (defaults to inputs/)")
    watch_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model to use (default: {DEFAULT_MODEL})")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List all processed meeting reports.")
    list_parser.add_argument("--output-dir", default=None, help="Custom output directory")

    # Command: view
    view_parser = subparsers.add_parser("view", help="View a markdown report directly in terminal.")
    view_parser.add_argument("report_name", help="Name or path of the report to display")

    args = parser.parse_args()

    if args.command == "process":
        handle_process(args)
    elif args.command == "watch":
        handle_watch(args)
    elif args.command == "list":
        handle_list(args)
    elif args.command == "view":
        handle_view(args)
    else:
        # If no arguments given, launch interactive menu
        interactive_menu()

if __name__ == "__main__":
    main()

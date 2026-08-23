import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.box import ROUNDED, HEAVY_EDGE, SIMPLE_HEAVY

# Initialize Rich Console
console = Console(record=False)

def print_banner():
    """Print a modern, styled ASCII banner for Plaud AI Meeting Studio."""
    banner_text = Text()
    banner_text.append("╔═════════════════════════════════════════════════════════════════╗\n", style="bold cyan")
    banner_text.append("║                   🎙️  PLAUD AI MEETING STUDIO                    ║\n", style="bold white")
    banner_text.append("║           Executive Intelligence & Multimedia Pipeline          ║\n", style="dim cyan")
    banner_text.append("╚═════════════════════════════════════════════════════════════════╝", style="bold cyan")
    
    console.print(Panel(
        banner_text,
        border_style="bright_blue",
        padding=(0, 1),
        box=ROUNDED
    ))

def print_step(step_name: str, message: str, status: str = "info"):
    """Print a clean step notification."""
    badges = {
        "info": "[bold blue]ℹ INFO[/]",
        "success": "[bold green]✔ DONE[/]",
        "warning": "[bold yellow]⚠ WARN[/]",
        "error": "[bold red]✖ ERROR[/]",
        "processing": "[bold magenta]⚡ PROCESS[/]",
        "upload": "[bold cyan]⬆ UPLOAD[/]",
        "watch": "[bold cyan]👀 WATCH[/]",
    }
    badge = badges.get(status, "[bold white]•[/]")
    console.print(f"{badge} [bold white]{step_name}:[/] {message}")

def print_error(title: str, message: str, hint: str | None = None):
    """Print an error message in a styled panel."""
    content = Text()
    content.append(f"{message}\n\n", style="bold red")
    if hint:
        content.append(f"💡 Suggestion: {hint}", style="italic yellow")
    
    console.print(Panel(
        content,
        title=f"❌ {title}",
        border_style="red",
        box=ROUNDED
    ))

def display_action_items_table(action_items: list[dict]):
    """Render a rich table for action items."""
    if not action_items:
        return
    
    table = Table(
        title="📋 Action Items Matrix",
        box=ROUNDED,
        header_style="bold cyan",
        border_style="dim blue",
        expand=True
    )
    table.add_column("#", justify="center", style="dim", width=4)
    table.add_column("Task Description", style="white", ratio=4)
    table.add_column("Assignee", style="magenta", ratio=2)
    table.add_column("Priority", justify="center", ratio=1)
    table.add_column("Due Date", justify="center", style="yellow", ratio=2)
    table.add_column("Notes", style="dim white", ratio=3)

    for idx, item in enumerate(action_items, 1):
        prio = str(item.get("priority", "MED")).upper()
        if "HIGH" in prio or "CRITICAL" in prio:
            prio_styled = f"[bold red]{prio}[/]"
        elif "LOW" in prio:
            prio_styled = f"[green]{prio}[/]"
        else:
            prio_styled = f"[yellow]{prio}[/]"
        
        table.add_row(
            str(idx),
            item.get("task", ""),
            item.get("assignee", "Unassigned"),
            prio_styled,
            item.get("due_date", "TBD"),
            item.get("notes", "-")
        )

    console.print(table)

def display_report_summary(result_info: dict):
    """Render a post-processing summary panel."""
    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style="bold cyan", justify="right")
    summary_table.add_column(style="white")

    summary_table.add_row("Input Recording:", f"[bold yellow]{result_info.get('input_file', '-')}[/]")
    summary_table.add_row("File Size:", f"{result_info.get('file_size_formatted', '-')}")
    summary_table.add_row("Gemini Model:", f"[bold green]{result_info.get('model', '-')}[/]")
    summary_table.add_row("Processing Duration:", f"{result_info.get('processing_time', '-')}")
    summary_table.add_row("Action Items Found:", f"[bold]{result_info.get('action_items_count', 0)}[/]")
    summary_table.add_row("Markdown Report:", f"[underline cyan]{result_info.get('md_path', '-')}[/]")
    summary_table.add_row("Structured JSON:", f"[underline cyan]{result_info.get('json_path', '-')}[/]")

    brief_text = result_info.get("executive_brief", "")
    if brief_text:
        brief_block = f"\n\n[bold white]Executive Brief Highlights:[/]\n[italic dim]{brief_text}[/]"
    else:
        brief_block = ""

    console.print(Panel(
        summary_table,
        title="✨ Analysis Complete",
        subtitle=f"[bold green]Ready in outputs folder[/]",
        border_style="green",
        box=ROUNDED,
        padding=(1, 2)
    ))

def display_reports_list(reports: list[dict]):
    """Render a rich table for listing all generated reports."""
    if not reports:
        console.print(Panel(
            "[yellow]No reports found in the outputs directory yet.[/]\n"
            "Run [bold cyan]python meeting_cli.py process <audio_file>[/] to analyze a meeting.",
            title="📂 Past Processed Meetings",
            border_style="yellow",
            box=ROUNDED
        ))
        return

    table = Table(
        title=f"📂 Processed Meetings Archive ({len(reports)} Reports Found)",
        box=ROUNDED,
        header_style="bold cyan",
        border_style="dim blue",
        expand=True
    )
    table.add_column("#", justify="center", style="dim", width=4)
    table.add_column("Report / Meeting Name", style="bold white", ratio=4)
    table.add_column("Date Generated", style="cyan", justify="center", ratio=2)
    table.add_column("Formats Available", justify="center", style="green", ratio=2)
    table.add_column("File Size", justify="right", style="yellow", ratio=1)

    for idx, rep in enumerate(reports, 1):
        formats = []
        if rep.get("has_md"):
            formats.append("[bold blue]MD[/]")
        if rep.get("has_json"):
            formats.append("[bold yellow]JSON[/]")
        
        table.add_row(
            str(idx),
            rep.get("name", ""),
            rep.get("created_at", ""),
            " + ".join(formats) if formats else "None",
            rep.get("size_str", "")
        )

    console.print(table)
    console.print("[dim]Tip: Use [bold white]python meeting_cli.py view <Report_Name>[/] to read any report in terminal.[/]\n")

def view_markdown_report(file_path: Path):
    """Render a full markdown report cleanly inside the terminal."""
    if not file_path.exists():
        print_error("File Not Found", f"Report does not exist at {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    md = Markdown(content)
    console.print(Panel(
        md,
        title=f"📄 {file_path.name}",
        border_style="cyan",
        box=ROUNDED,
        padding=(1, 2)
    ))

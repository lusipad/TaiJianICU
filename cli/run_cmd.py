from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from orchestrator import TaiJianOrchestrator


console = Console()
app = typer.Typer(help="运行续写流水线")


@app.command("run")
def run_command(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False, readable=True),
    chapters: int = typer.Option(1, "--chapters", min=1),
    session_name: str | None = typer.Option(None, "--session-name"),
    goal_hint: str | None = typer.Option(None, "--goal"),
    use_existing_index: bool = typer.Option(False, "--use-existing-index"),
    pause_after_skeleton: bool = typer.Option(False, "--pause-after-skeleton"),
    pause_after_draft: bool = typer.Option(False, "--pause-after-draft"),
    resume: bool = typer.Option(False, "--resume"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    start_chapter: int = typer.Option(1, "--start-chapter", min=1),
) -> None:
    orchestrator = TaiJianOrchestrator()
    total_steps = 1 + chapters * 4
    encoding = (getattr(console.file, "encoding", "") or "").lower()
    if "utf" not in encoding:
        result = asyncio.run(
            orchestrator.run(
                input_path=input_path,
                chapters=chapters,
                session_name=session_name,
                goal_hint=goal_hint,
                use_existing_index=use_existing_index,
                pause_after_skeleton=pause_after_skeleton,
                pause_after_draft=pause_after_draft,
                resume=resume,
                overwrite=overwrite,
                start_chapter=start_chapter,
                progress_callback=lambda message: console.print(message),
            )
        )
    else:
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("准备运行", total=total_steps)

            def on_progress(message: str) -> None:
                completed = min(progress.tasks[0].completed + 1, total_steps)
                progress.update(task_id, completed=completed, description=message)

            result = asyncio.run(
                orchestrator.run(
                    input_path=input_path,
                    chapters=chapters,
                    session_name=session_name,
                    goal_hint=goal_hint,
                    use_existing_index=use_existing_index,
                    pause_after_skeleton=pause_after_skeleton,
                    pause_after_draft=pause_after_draft,
                    resume=resume,
                    overwrite=overwrite,
                    start_chapter=start_chapter,
                    progress_callback=on_progress,
                )
            )
            progress.update(task_id, completed=total_steps, description=f"运行结束：{result.status}")

    summary = Table(title=f"{result.session_name} 运行结果")
    summary.add_column("章节")
    summary.add_column("状态")
    summary.add_column("成本 USD")
    summary.add_column("总 Tokens")
    summary.add_column("耗时(s)")
    for chapter in result.chapters:
        summary.add_row(
            str(chapter.chapter_number),
            chapter.status,
            f"{chapter.usage_summary.total_cost_usd:.6f}",
            str(chapter.usage_summary.total_tokens),
            f"{chapter.elapsed_seconds:.2f}",
        )
    console.print(summary)
    console.print(
        {
            "session_name": result.session_name,
            "status": result.status,
            "stage1_snapshot_path": result.stage1_snapshot_path,
            "total_cost_usd": result.total_usage.total_cost_usd,
            "total_tokens": result.total_usage.total_tokens,
            "chapters": [item.model_dump(mode="json") for item in result.chapters],
        }
    )

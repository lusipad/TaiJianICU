from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from config.settings import get_settings
from core.benchmarking.runner import run_benchmark_sync


console = Console()
app = typer.Typer(help="运行续写对照基准")


@app.command("benchmark")
def benchmark_command(
    dataset: str = typer.Option("sanguo", "--dataset"),
    prefix_chapters: int = typer.Option(50, "--prefix-chapters", min=1),
    target_chapter: int = typer.Option(51, "--target-chapter", min=2),
    session_name: str | None = typer.Option(None, "--session-name"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    source_file: Path | None = typer.Option(
        None,
        "--source-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    source_url: str | None = typer.Option(None, "--source-url"),
    source_encoding: str | None = typer.Option(None, "--source-encoding"),
) -> None:
    settings = get_settings()
    report = run_benchmark_sync(
        settings,
        dataset_name=dataset,
        prefix_chapters=prefix_chapters,
        target_chapter=target_chapter,
        session_name=session_name,
        overwrite=overwrite,
        source_path=source_file,
        source_url=source_url,
        source_encoding=source_encoding,
    )

    table = Table(title=f"{report.dataset_name} 基准结果")
    table.add_column("候选")
    table.add_column("Overall")
    table.add_column("Plot")
    table.add_column("Character")
    table.add_column("Style")
    table.add_column("Readability")
    table.add_row(
        "system",
        f"{report.system_report.score.overall:.1f}",
        f"{report.system_report.score.plot_alignment:.1f}",
        f"{report.system_report.score.character_consistency:.1f}",
        f"{report.system_report.score.style_similarity:.1f}",
        f"{report.system_report.score.readability:.1f}",
    )
    table.add_row(
        "baseline",
        f"{report.baseline_report.score.overall:.1f}",
        f"{report.baseline_report.score.plot_alignment:.1f}",
        f"{report.baseline_report.score.character_consistency:.1f}",
        f"{report.baseline_report.score.style_similarity:.1f}",
        f"{report.baseline_report.score.readability:.1f}",
    )
    console.print(table)
    console.print(
        {
            "winner": report.pairwise.winner,
            "confidence": report.pairwise.confidence,
            "reasoning": report.pairwise.reasoning,
            "total_cost_usd": report.total_usage.total_cost_usd,
            "total_tokens": report.total_usage.total_tokens,
            "report_json_path": report.report_json_path,
            "report_markdown_path": report.report_markdown_path,
            "system_output_path": report.system_output_path,
            "baseline_output_path": report.baseline_output_path,
            "reference_path": report.reference_path,
        }
    )

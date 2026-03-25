from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from config.settings import get_settings
from core.inspection import StoryGraphChapter, export_story_mermaid
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation
from core.models.lorebook import LorebookBundle
from core.llm.litellm_client import LiteLLMService
from core.models.reference_profile import ReferenceProfile
from core.models.skeleton import ChapterSkeleton
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import WorldModel
from core.storage.lightrag_store import LightRAGStore
from core.storage.session_store import SessionStore


console = Console()
app = typer.Typer(help="查看阶段产物或查询 LightRAG")


class ReferenceProfileBundle(BaseModel):
    profiles: list[ReferenceProfile] = Field(default_factory=list)


@app.command("inspect")
def inspect_command(
    session_name: str = typer.Option(..., "--session-name"),
    query: str | None = typer.Option(None, "--query"),
    chapter: int | None = typer.Option(None, "--chapter", min=1),
    export_mermaid_path: Path | None = typer.Option(None, "--export-mermaid"),
) -> None:
    settings = get_settings()
    session_store = SessionStore(settings.sessions_dir)

    if query:
        rag_store = LightRAGStore(settings, LiteLLMService(settings))
        answer = asyncio.run(rag_store.query_context(session_name, query))
        console.print(answer)
        return

    snapshot = session_store.load_model(
        session_store.stage1_snapshot_path(session_name),
        ExtractionSnapshot,
    )
    world_model = session_store.load_model(
        session_store.world_model_path(session_name),
        WorldModel,
    )
    lorebook = session_store.load_model(
        session_store.lorebook_path(session_name),
        LorebookBundle,
    )
    selected_references = session_store.load_model(
        session_store.selected_references_path(session_name),
        ReferenceProfileBundle,
    )
    manifest = session_store._read_json(session_store.run_manifest_path(session_name), {})
    threads = session_store.load_unresolved_threads(session_name)
    arc_outlines = [
        loaded
        for path in sorted((session_store.session_dir(session_name) / "arcs").glob("*.json"))
        if (
            loaded := session_store.load_model(
                path,
                ArcOutline,
            )
        )
    ]

    if export_mermaid_path is not None:
        chapter_graph: list[StoryGraphChapter] = []
        for item in manifest.get("chapters", []):
            chapter_number = int(item.get("chapter_number", 0) or 0)
            if chapter_number <= 0:
                continue
            skeleton = session_store.load_model(
                session_store.chapter_skeleton_path(session_name, chapter_number),
                ChapterSkeleton,
            )
            participants = []
            if skeleton:
                participants = sorted(
                    {
                        participant
                        for scene in skeleton.scenes
                        for participant in scene.participants
                        if participant.strip()
                    }
                )
            chapter_graph.append(
                StoryGraphChapter(
                    chapter_number=chapter_number,
                    chapter_theme=skeleton.chapter_theme if skeleton else "",
                    status=str(item.get("status", "")),
                    threads_to_advance=skeleton.threads_to_advance if skeleton else [],
                    threads_to_close=skeleton.threads_to_close if skeleton else [],
                    participants=participants,
                )
            )

        path = export_story_mermaid(
            export_mermaid_path,
            session_name,
            snapshot,
            threads,
            chapter_graph,
        )
        console.print({"mermaid_path": str(path)})

    if snapshot:
        console.print({"style_profile": snapshot.style_profile.model_dump(mode="json")})
        console.print({"story_state": snapshot.story_state.model_dump(mode="json")})
    if world_model:
        console.print({"world_model": world_model.model_dump(mode="json")})
    if lorebook:
        console.print({"lorebook": lorebook.model_dump(mode="json")})
    if selected_references:
        console.print({"selected_references": selected_references.model_dump(mode="json")})

    if arc_outlines:
        arc_table = Table(title=f"{session_name} Arc 规划")
        arc_table.add_column("Arc ID")
        arc_table.add_column("跨度")
        arc_table.add_column("主题")
        arc_table.add_column("目标")
        for outline in arc_outlines:
            span = (
                f"{outline.chapters_span[0]}-{outline.chapters_span[1]}"
                if len(outline.chapters_span) == 2
                else "-"
            )
            arc_table.add_row(outline.arc_id, span, outline.arc_theme, outline.arc_goal)
        console.print(arc_table)

    threads_table = Table(title=f"{session_name} 当前伏笔")
    threads_table.add_column("ID")
    threads_table.add_column("描述")
    threads_table.add_column("状态")
    threads_table.add_column("最近推进")
    for thread in threads:
        threads_table.add_row(thread.id, thread.description, thread.status, str(thread.last_advanced))
    console.print(threads_table)

    if chapter is not None:
        chapter_brief = session_store.load_model(
            session_store.chapter_brief_path(session_name, chapter),
            ChapterBrief,
        )
        if chapter_brief:
            console.print({"chapter_brief": chapter_brief.model_dump(mode="json")})
        skeleton = session_store.load_model(
            session_store.chapter_skeleton_path(session_name, chapter),
            ChapterSkeleton,
        )
        if skeleton:
            console.print({"chapter_skeleton": skeleton.model_dump(mode="json")})
        evaluation = session_store.load_model(
            session_store.chapter_evaluation_path(session_name, chapter),
            ChapterEvaluation,
        )
        if evaluation:
            console.print({"chapter_evaluation": evaluation.model_dump(mode="json")})
        draft_path = session_store.chapter_draft_path(session_name, chapter)
        if draft_path.exists():
            console.print({"draft_path": str(draft_path), "draft_preview": draft_path.read_text(encoding="utf-8")[:1000]})

    if manifest:
        cost_table = Table(title=f"{session_name} 成本汇总")
        cost_table.add_column("项目")
        cost_table.add_column("值")
        cost_table.add_row("status", str(manifest.get("status")))
        total_usage = manifest.get("total_usage") or {}
        cost_table.add_row("total_cost_usd", str(total_usage.get("total_cost_usd", 0.0)))
        cost_table.add_row("total_tokens", str(total_usage.get("total_tokens", 0)))
        console.print(cost_table)
        console.print(manifest)

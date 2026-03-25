from __future__ import annotations

import typer
from rich.console import Console

from config.settings import get_settings
from core.storage.session_store import SessionStore
from intervention import InterventionManager, InterventionConfig


console = Console()
app = typer.Typer(help="创建或更新人工干预脚手架文件")


@app.command("intervene")
def intervene_command(
    session_name: str = typer.Option(..., "--session-name"),
    chapter: int = typer.Option(..., "--chapter", min=1),
    must_happen: list[str] | None = typer.Option(None, "--must-happen"),
    focus_thread: list[str] | None = typer.Option(None, "--focus-thread"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    settings = get_settings()
    session_store = SessionStore(settings.sessions_dir)
    manager = InterventionManager(session_store)
    config = manager.load_or_create(session_name, chapter)
    updated = InterventionConfig(
        must_happen=must_happen if must_happen is not None else config.must_happen,
        focus_thread_ids=focus_thread if focus_thread is not None else config.focus_thread_ids,
        notes=notes if notes is not None else config.notes,
    )
    session_store.save_model(session_store.chapter_config_path(session_name, chapter), updated)
    console.print(
        {
            "config_path": str(session_store.chapter_config_path(session_name, chapter)),
            "skeleton_override_path": str(manager.skeleton_override_path(session_name, chapter)),
            "draft_override_path": str(manager.draft_override_path(session_name, chapter)),
            "config": updated.model_dump(mode="json"),
        }
    )

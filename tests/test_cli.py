from pathlib import Path

from typer.testing import CliRunner

import cli.inspect_cmd
from cli.main import app
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief
from core.models.lorebook import LorebookBundle, LorebookEntry
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.story_state import StoryThread, StoryWorldState
from core.models.world_model import WorldModel
from core.storage.session_store import SessionStore


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "benchmark" in result.stdout
    assert "web" in result.stdout
    assert "inspect" in result.stdout


def test_inspect_command_prints_v2_artifacts(tmp_path: Path, monkeypatch) -> None:
    settings = type("TestSettings", (), {"sessions_dir": tmp_path})()
    monkeypatch.setattr(cli.inspect_cmd, "get_settings", lambda: settings)

    store = SessionStore(tmp_path)
    store.save_model(
        store.stage1_snapshot_path("demo"),
        ExtractionSnapshot(
            style_profile=StyleProfile(summary="沉稳推进"),
            story_state=StoryWorldState(summary="旧案重启"),
        ),
    )
    store.save_model(
        store.world_model_path("demo"),
        WorldModel(summary="世界开始扩张"),
    )
    store.save_model(
        store.lorebook_path("demo"),
        LorebookBundle(
            entries=[
                LorebookEntry(
                    entry_id="canon-001",
                    title="修炼限制",
                    content="主角不能无代价突破",
                    hard_constraint=True,
                )
            ]
        ),
    )
    store.save_model(
        store.arc_outline_path("demo", "arc_0001_0003"),
        ArcOutline(
            arc_id="arc_0001_0003",
            arc_theme="旧案发酵",
            arc_goal="把冲突推到明面",
            chapters_span=[1, 3],
        ),
    )
    store.save_model(
        store.chapter_brief_path("demo", 1),
        ChapterBrief(chapter_number=1, chapter_goal="让主角拿到第一条硬线索"),
    )
    store.save_unresolved_threads(
        "demo",
        [StoryThread(id="T001", description="黑玉去向", introduced_at=1, last_advanced=1)],
    )

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "--session-name", "demo", "--chapter", "1"])

    assert result.exit_code == 0
    assert "world_model" in result.stdout
    assert "lorebook" in result.stdout
    assert "arc_0001_0003" in result.stdout
    assert "chapter_brief" in result.stdout

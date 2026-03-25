from pathlib import Path

from core.inspection import StoryGraphChapter, build_story_mermaid, export_story_mermaid
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile


def test_build_story_mermaid_contains_characters_and_threads() -> None:
    snapshot = ExtractionSnapshot(
        style_profile=StyleProfile(summary="沉稳叙事"),
        story_state=StoryWorldState(
            title="青石旧案",
            main_characters=[
                CharacterCard(name="沈照", role="主角"),
                CharacterCard(name="顾行舟", role="旧友"),
            ],
            major_relationships=["沈照 与 顾行舟 旧交未绝"],
        ),
    )
    threads = [StoryThread(id="T001", description="黑玉去向", status="open")]

    mermaid = build_story_mermaid(
        "demo",
        snapshot,
        threads,
        [
            StoryGraphChapter(
                chapter_number=1,
                chapter_theme="雨夜追踪",
                threads_to_advance=["T001"],
                participants=["沈照"],
            )
        ],
    )

    assert "graph TD" in mermaid
    assert "沈照" in mermaid
    assert "黑玉去向" in mermaid
    assert "第1章" in mermaid
    assert "推进" in mermaid


def test_export_story_mermaid_writes_file(tmp_path: Path) -> None:
    path = export_story_mermaid(tmp_path / "story.mmd", "demo", None, [])
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("graph TD")

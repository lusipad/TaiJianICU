from pathlib import Path

from core.models.story_state import StoryThread
from core.storage.session_store import SessionStore


def test_session_store_roundtrip_threads(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    threads = [
        StoryThread(
            id="T001",
            description="旧仇未报",
            introduced_at=3,
            last_advanced=7,
        )
    ]
    store.save_unresolved_threads("demo", threads)
    loaded = store.load_unresolved_threads("demo")

    assert loaded == threads
    assert store.unresolved_threads_path("demo").exists()


def test_session_store_revival_artifact_paths(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)

    assert store.work_skill_path("demo") == tmp_path / "demo" / "work_skill.json"
    assert store.arc_options_path("demo") == tmp_path / "demo" / "arc_options.json"
    assert store.selected_arc_path("demo") == tmp_path / "demo" / "selected_arc.json"
    assert store.revival_diagnosis_path("demo") == tmp_path / "demo" / "revival_diagnosis.json"
    assert store.blind_challenge_path("demo") == tmp_path / "demo" / "blind_challenge.json"

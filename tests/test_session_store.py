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

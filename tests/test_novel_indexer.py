from pathlib import Path

from config.settings import AppSettings
from core.storage.lightrag_store import LightRAGStore
from pipeline.stage1_extraction.novel_indexer import NovelIndexer


class DummyLLMService:
    pass


def test_novel_indexer_prefers_chapter_split(tmp_path: Path) -> None:
    settings = AppSettings()
    settings.work_dir = tmp_path
    settings.input_dir = tmp_path / "input"
    settings.output_dir = tmp_path / "output"
    settings.sessions_dir = tmp_path / "sessions"
    settings.lightrag_dir = tmp_path / "lightrag"
    settings.ensure_directories()
    indexer = NovelIndexer(settings, LightRAGStore(settings, DummyLLMService()))  # type: ignore[arg-type]

    text = "第一章 风起\n这里是第一章内容。\n第二章 云涌\n这里是第二章内容。"
    chunks = indexer.split_text(text)

    assert len(chunks) == 2
    assert chunks[0].startswith("第一章")

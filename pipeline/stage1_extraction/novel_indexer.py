from __future__ import annotations

import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

from config.settings import AppSettings
from core.storage.lightrag_store import LightRAGStore


_CHAPTER_SPLIT = re.compile(
    r"(?=^第[0-9一二三四五六七八九十百千万零两]+[章节回][^\n]*)",
    re.M,
)


class IndexingResult(BaseModel):
    source_path: str
    chunk_count: int
    character_count: int


class NovelIndexer:
    def __init__(self, settings: AppSettings, rag_store: LightRAGStore):
        self.settings = settings
        self.rag_store = rag_store
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.tuning.chunk_size,
            chunk_overlap=self.settings.tuning.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", ""],
        )

    def load_text(self, input_path: Path) -> str:
        return input_path.read_text(encoding="utf-8")

    def split_text(self, text: str) -> list[str]:
        chapters = [chunk.strip() for chunk in _CHAPTER_SPLIT.split(text) if chunk.strip()]
        if len(chapters) >= 2:
            return chapters
        return [chunk.strip() for chunk in self.splitter.split_text(text) if chunk.strip()]

    async def index_file(self, session_name: str, input_path: Path) -> tuple[IndexingResult, str]:
        novel_text = self.load_text(input_path)
        chunks = self.split_text(novel_text)
        await self.rag_store.index_text(session_name, chunks)
        return (
            IndexingResult(
                source_path=str(input_path),
                chunk_count=len(chunks),
                character_count=len(novel_text),
            ),
            novel_text,
        )

from __future__ import annotations

import re

from core.models.memory_snapshot import MemorySnapshot


_CHAPTER_SPLIT = re.compile(
    r"(?=^第[0-9一二三四五六七八九十百千万零两]+[章节回][^\n]*)",
    re.M,
)


class MemoryCompressor:
    def __init__(
        self,
        *,
        recent_chars: int = 20000,
        middle_chars: int = 12000,
        long_term_chars: int = 6000,
    ):
        self.recent_chars = recent_chars
        self.middle_chars = middle_chars
        self.long_term_chars = long_term_chars

    def split_chapters(self, text: str) -> list[str]:
        return [chunk.strip() for chunk in _CHAPTER_SPLIT.split(text) if chunk.strip()]

    def compress(self, text: str) -> MemorySnapshot:
        chapters = self.split_chapters(text)
        if not chapters:
            return MemorySnapshot(
                recent_excerpt=text[-self.recent_chars :],
                middle_summary=text[: self.middle_chars],
                long_term_summary=text[: self.long_term_chars],
            )

        recent = self._take_recent_chapters(chapters)
        middle = self._take_middle_window(chapters)
        long_term = self._take_long_term_window(chapters)
        lore_candidates = [chapter.splitlines()[0] for chapter in chapters[:3] + chapters[-3:]]
        return MemorySnapshot(
            recent_excerpt=recent,
            middle_summary=middle,
            long_term_summary=long_term,
            lore_candidates=lore_candidates,
        )

    def _take_recent_chapters(self, chapters: list[str]) -> str:
        selected: list[str] = []
        total = 0
        for chapter in reversed(chapters):
            selected.append(chapter)
            total += len(chapter)
            if total >= self.recent_chars:
                break
        return "\n\n".join(reversed(selected))

    def _take_middle_window(self, chapters: list[str]) -> str:
        if len(chapters) <= 4:
            return "\n\n".join(chapters)[: self.middle_chars]
        middle = len(chapters) // 2
        selected = chapters[max(0, middle - 1) : min(len(chapters), middle + 2)]
        return "\n\n".join(selected)[: self.middle_chars]

    def _take_long_term_window(self, chapters: list[str]) -> str:
        selected = chapters[:2]
        return "\n\n".join(selected)[: self.long_term_chars]

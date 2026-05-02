from __future__ import annotations

from pipeline.revival import ChapterSplitter, _chinese_char_count
from core.models.skeleton import ChapterSkeleton
from core.models.style_profile import StyleProfile
from core.storage.lightrag_store import LightRAGStore


class StyleSampler:
    def __init__(self, rag_store: LightRAGStore):
        self.rag_store = rag_store

    async def sample(
        self,
        session_name: str,
        skeleton: ChapterSkeleton,
        style_profile: StyleProfile,
        source_text: str | None = None,
    ) -> list[str]:
        if source_text:
            samples = self._sample_from_source_text(source_text, skeleton.chapter_theme)
            if samples:
                return samples
        query = (
            f"为主题“{skeleton.chapter_theme}”检索原著片段。"
            f"优先匹配这些风格关键词：{', '.join(style_profile.tone_keywords)}。"
            "返回适合 few-shot 的短片段。"
        )
        return await self.rag_store.sample_passages(session_name, query)

    @staticmethod
    def _sample_from_source_text(source_text: str, chapter_theme: str) -> list[str]:
        chapters = [
            chapter.text.strip()
            for chapter in ChapterSplitter().split(source_text)
            if _chinese_char_count(chapter.text) >= 8
        ]
        if not chapters:
            return []
        keywords = [word for word in chapter_theme.split() if word]
        ranked = sorted(
            chapters,
            key=lambda text: sum(text.count(keyword) for keyword in keywords),
            reverse=True,
        )
        return [StyleSampler._excerpt(text) for text in ranked[:3]]

    @staticmethod
    def _excerpt(text: str, limit: int = 800) -> str:
        return text[:limit].strip()

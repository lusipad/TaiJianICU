from __future__ import annotations

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
    ) -> list[str]:
        query = (
            f"为主题“{skeleton.chapter_theme}”检索原著片段。"
            f"优先匹配这些风格关键词：{', '.join(style_profile.tone_keywords)}。"
            "返回适合 few-shot 的短片段。"
        )
        return await self.rag_store.sample_passages(session_name, query)

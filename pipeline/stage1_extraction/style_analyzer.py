from __future__ import annotations

import re

from config.settings import AppSettings, render_prompt
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.llm.litellm_client import LiteLLMService
from core.models.style_profile import ExtractionSnapshot


_CHAPTER_SPLIT = re.compile(
    r"(?=^第[0-9一二三四五六七八九十百千万零两]+[章节回][^\n]*)",
    re.M,
)


class StyleAnalyzer:
    def __init__(self, settings: AppSettings, llm_service: LiteLLMService):
        self.settings = settings
        self.llm_service = llm_service

    def _split_chapters(self, text: str) -> list[str]:
        return [chunk.strip() for chunk in _CHAPTER_SPLIT.split(text) if chunk.strip()]

    def _build_style_excerpt(self, text: str) -> str:
        budget = self.settings.tuning.style_excerpt_chars
        chapters = self._split_chapters(text)
        if len(text) <= budget:
            return text
        if len(chapters) >= 6:
            selected = chapters[:2] + chapters[len(chapters) // 2 - 1 : len(chapters) // 2 + 1] + chapters[-2:]
            excerpt = "\n\n".join(selected)
            if len(excerpt) <= budget:
                return excerpt
            return excerpt[-budget:]
        head = text[: budget // 2]
        middle_start = max(0, len(text) // 2 - budget // 6)
        middle_end = min(len(text), middle_start + budget // 3)
        tail = text[-budget // 6 :]
        return (
            "[开头节选]\n"
            + head
            + "\n\n[中段节选]\n"
            + text[middle_start:middle_end]
            + "\n\n[尾段节选]\n"
            + tail
        )

    def _build_recent_excerpt(self, text: str) -> str:
        budget = self.settings.tuning.recent_story_excerpt_chars
        chapters = self._split_chapters(text)
        if chapters:
            recent = []
            total = 0
            for chapter in reversed(chapters):
                recent.append(chapter)
                total += len(chapter)
                if total >= budget:
                    break
            return "\n\n".join(reversed(recent))
        if len(text) <= budget:
            return text
        return text[-budget:]

    def _merge_story_state(
        self,
        base_state: StoryWorldState,
        recent_state: StoryWorldState,
    ) -> StoryWorldState:
        recent_characters = {item.name: item for item in recent_state.main_characters if item.name.strip()}
        merged_characters: list[CharacterCard] = []
        for item in base_state.main_characters:
            if item.name in recent_characters:
                merged_characters.append(recent_characters.pop(item.name))
            else:
                merged_characters.append(item)
        merged_characters.extend(recent_characters.values())

        merged_threads = recent_state.unresolved_threads or base_state.unresolved_threads
        if not merged_threads:
            merged_threads = [StoryThread(id="T001", description="主线伏笔仍待推进", introduced_at=1, last_advanced=1)]

        return StoryWorldState(
            title=recent_state.title or base_state.title,
            summary=recent_state.summary or base_state.summary,
            world_rules=base_state.world_rules or recent_state.world_rules,
            main_characters=merged_characters or base_state.main_characters,
            major_relationships=recent_state.major_relationships or base_state.major_relationships,
            active_conflicts=recent_state.active_conflicts or base_state.active_conflicts,
            unresolved_threads=merged_threads,
        )

    async def analyze(self, text: str) -> ExtractionSnapshot:
        prompt = render_prompt(
            "agents/style_extract.txt",
            novel_excerpt=self._build_style_excerpt(text),
        )
        snapshot = await self.llm_service.complete_structured(
            model=self.settings.models.style_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=ExtractionSnapshot,
            temperature=0.2,
            operation="stage1_style_analyze",
        )
        recent_prompt = render_prompt(
            "agents/story_state_refresh.txt",
            recent_excerpt=self._build_recent_excerpt(text),
        )
        recent_story_state = await self.llm_service.complete_structured(
            model=self.settings.models.style_model,
            messages=[{"role": "user", "content": recent_prompt}],
            response_model=StoryWorldState,
            temperature=0.2,
            operation="stage1_story_state_refresh",
        )
        snapshot.story_state = self._merge_story_state(snapshot.story_state, recent_story_state)
        for index, thread in enumerate(snapshot.story_state.unresolved_threads, start=1):
            if not thread.id.strip():
                thread.id = f"T{index:03d}"
            if not thread.status:
                thread.status = "open"
        if not snapshot.story_state.unresolved_threads:
            snapshot.story_state.unresolved_threads = [
                StoryThread(
                    id="T001",
                    description="主线伏笔仍待推进",
                    introduced_at=1,
                    last_advanced=1,
                )
            ]
        return snapshot

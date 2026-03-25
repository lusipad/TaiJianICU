from __future__ import annotations

from core.models.story_state import CharacterCard, StoryThread
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import (
    CanonFact,
    CharacterArc,
    ExpansionSlot,
    FactionState,
    LocationState,
    WorldModel,
)


class WorldBuilder:
    def from_snapshot(
        self,
        snapshot: ExtractionSnapshot,
        *,
        chapter_number: int = 0,
    ) -> WorldModel:
        story_state = snapshot.story_state
        return WorldModel(
            title=story_state.title,
            summary=story_state.summary or snapshot.style_profile.summary,
            canon_facts=self._build_canon_facts(story_state.world_rules),
            power_system_rules=story_state.world_rules,
            main_characters=[self._to_character_arc(item) for item in story_state.main_characters],
            active_factions=self._build_factions(story_state.major_relationships),
            known_locations=self._build_locations(story_state.summary),
            world_tensions=story_state.active_conflicts,
            open_mysteries=[item.description for item in story_state.unresolved_threads],
            expansion_slots=self._build_expansion_slots(story_state.unresolved_threads),
            active_threads=story_state.unresolved_threads,
            last_refreshed_chapter=max(0, chapter_number),
        )

    def merge(self, previous: WorldModel | None, current: WorldModel) -> WorldModel:
        if previous is None:
            return current
        return WorldModel(
            title=current.title or previous.title,
            summary=current.summary or previous.summary,
            canon_facts=current.canon_facts or previous.canon_facts,
            power_system_rules=current.power_system_rules or previous.power_system_rules,
            main_characters=self._merge_characters(previous.main_characters, current.main_characters),
            active_factions=self._merge_named(previous.active_factions, current.active_factions),
            known_locations=self._merge_named(previous.known_locations, current.known_locations),
            world_tensions=current.world_tensions or previous.world_tensions,
            open_mysteries=current.open_mysteries or previous.open_mysteries,
            expansion_slots=current.expansion_slots or previous.expansion_slots,
            active_threads=current.active_threads or previous.active_threads,
            last_refreshed_chapter=max(previous.last_refreshed_chapter, current.last_refreshed_chapter),
        )

    def _build_canon_facts(self, world_rules: list[str]) -> list[CanonFact]:
        return [
            CanonFact(
                id=f"fact_{index:03d}",
                category="world_rule",
                statement=rule,
                source_chapter=0,
                level="hard",
            )
            for index, rule in enumerate(world_rules, start=1)
            if rule.strip()
        ]

    def _to_character_arc(self, item: CharacterCard) -> CharacterArc:
        return CharacterArc(
            character_name=item.name,
            role=item.role,
            current_state=item.last_known_state,
            public_persona="、".join(item.personality_traits[:3]),
            core_wants=item.core_goals,
        )

    def _build_factions(self, relationships: list[str]) -> list[FactionState]:
        factions: list[FactionState] = []
        for index, relation in enumerate(relationships[:3], start=1):
            factions.append(
                FactionState(
                    name=f"faction_{index:03d}",
                    public_goal=relation,
                    hidden_goal="",
                    relation_map=[relation],
                )
            )
        return factions

    def _build_locations(self, summary: str) -> list[LocationState]:
        if not summary.strip():
            return []
        return [
            LocationState(
                name="current_stage",
                location_type="dynamic",
                importance="high",
                story_function="当前剧情主舞台",
                current_status=summary,
            )
        ]

    def _build_expansion_slots(self, threads: list[StoryThread]) -> list[ExpansionSlot]:
        return [
            ExpansionSlot(
                slot_id=f"slot_{index:03d}",
                slot_type="mystery",
                description=thread.description,
                trigger_hint=f"推进伏笔 {thread.id}",
                priority="high" if index <= 2 else "medium",
            )
            for index, thread in enumerate(threads, start=1)
        ]

    @staticmethod
    def _merge_characters(
        previous: list[CharacterArc],
        current: list[CharacterArc],
    ) -> list[CharacterArc]:
        merged = {item.character_name: item for item in previous}
        for item in current:
            merged[item.character_name] = item
        return list(merged.values())

    @staticmethod
    def _merge_named(previous: list, current: list) -> list:
        merged = {}
        for item in previous:
            merged[getattr(item, "name")] = item
        for item in current:
            merged[getattr(item, "name")] = item
        return list(merged.values())

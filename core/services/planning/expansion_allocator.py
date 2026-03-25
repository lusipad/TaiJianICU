from __future__ import annotations

from core.models.chapter_brief import ExpansionBudget
from core.models.world_model import WorldModel


class ExpansionAllocator:
    def allocate(
        self,
        *,
        world_model: WorldModel,
        mode: str = "balanced",
        arc_length: int = 5,
    ) -> ExpansionBudget:
        mystery_count = len(world_model.open_mysteries)
        tension_count = len(world_model.world_tensions)
        slot_count = len(world_model.expansion_slots)

        if mode == "strict":
            return ExpansionBudget(
                mode="strict",
                expansion_mode="hold",
                new_character_budget=0,
                new_location_budget=0,
                new_faction_budget=0,
                twist_budget=1 if tension_count else 0,
                reveal_budget=min(2, mystery_count),
            )

        if mode == "expansive":
            return ExpansionBudget(
                mode="expansive",
                expansion_mode="strong" if slot_count or mystery_count >= 3 else "medium",
                new_character_budget=1 if mystery_count else 0,
                new_location_budget=1 if slot_count else 0,
                new_faction_budget=1 if tension_count >= 2 else 0,
                twist_budget=1 if arc_length >= 4 else 0,
                reveal_budget=min(3, mystery_count),
            )

        return ExpansionBudget(
            mode="balanced",
            expansion_mode="light" if mystery_count <= 2 else "medium",
            new_character_budget=1 if mystery_count >= 2 else 0,
            new_location_budget=1 if slot_count >= 2 else 0,
            new_faction_budget=1 if tension_count >= 2 else 0,
            twist_budget=1 if arc_length >= 4 else 0,
            reveal_budget=min(2, mystery_count),
        )

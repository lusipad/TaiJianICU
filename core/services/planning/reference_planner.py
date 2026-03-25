from __future__ import annotations

from core.models.reference_profile import ReferenceProfile
from core.models.world_model import WorldModel


class ReferencePlanner:
    def select_profiles(
        self,
        *,
        world_model: WorldModel,
        reference_profiles: list[ReferenceProfile],
        limit: int = 2,
    ) -> list[ReferenceProfile]:
        if not reference_profiles:
            return []

        scored: list[tuple[int, ReferenceProfile]] = []
        for profile in reference_profiles:
            score = 0
            if profile.reference_type == "world" and world_model.expansion_slots:
                score += 3
            if profile.reference_type == "structure" and len(world_model.world_tensions) >= 2:
                score += 2
            if profile.reference_type == "character" and len(world_model.main_characters) >= 2:
                score += 2
            if profile.reference_type == "theme" and world_model.open_mysteries:
                score += 2
            score += len(profile.allowed_influences)
            scored.append((score, profile))

        return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]

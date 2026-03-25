from __future__ import annotations

from core.models.world_model import WorldModel
from core.models.style_profile import ExtractionSnapshot
from pipeline.stage1_extraction.world_builder import WorldBuilder


class WorldRefreshService:
    def __init__(self, builder: WorldBuilder | None = None):
        self.builder = builder or WorldBuilder()

    def refresh(
        self,
        *,
        snapshot: ExtractionSnapshot,
        previous: WorldModel | None = None,
        chapter_number: int = 0,
    ) -> WorldModel:
        current = self.builder.from_snapshot(snapshot, chapter_number=chapter_number)
        return self.builder.merge(previous, current)

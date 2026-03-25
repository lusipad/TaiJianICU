from __future__ import annotations

from core.models.lorebook import LorebookBundle, LorebookEntry, LorebookHit
from core.models.memory_snapshot import MemorySnapshot
from core.models.world_model import WorldModel


class LorebookManager:
    def build(
        self,
        *,
        world_model: WorldModel,
        memory_snapshot: MemorySnapshot,
    ) -> LorebookBundle:
        entries: list[LorebookEntry] = []
        for item in world_model.canon_facts:
            entries.append(
                LorebookEntry(
                    entry_id=item.id,
                    title=item.category,
                    entry_type="canon",
                    scope="global",
                    content=item.statement,
                    keywords=item.statement.split()[:3],
                    hard_constraint=(item.level == "hard"),
                    priority=90,
                )
            )
        for index, item in enumerate(world_model.open_mysteries, start=1):
            entries.append(
                LorebookEntry(
                    entry_id=f"mystery_{index:03d}",
                    title=f"未解谜团 {index}",
                    entry_type="mystery",
                    scope="arc",
                    content=item,
                    keywords=[item[:12]],
                    priority=75,
                )
            )
        for index, item in enumerate(memory_snapshot.lore_candidates[:6], start=1):
            entries.append(
                LorebookEntry(
                    entry_id=f"memory_{index:03d}",
                    title=f"章节记忆 {index}",
                    entry_type="tone",
                    scope="chapter",
                    content=item,
                    keywords=[item[:12]],
                    priority=40,
                )
            )
        return LorebookBundle(entries=entries)

    def match(
        self,
        *,
        lorebook: LorebookBundle,
        query_text: str,
        max_entries: int = 5,
    ) -> LorebookBundle:
        hits: list[LorebookHit] = []
        lowered = query_text.lower()
        for entry in lorebook.entries:
            keywords = [item.lower() for item in entry.keywords if item.strip()]
            if any(keyword and keyword in lowered for keyword in keywords):
                hits.append(
                    LorebookHit(
                        entry_id=entry.entry_id,
                        reason="keyword_match",
                        score=float(entry.priority),
                    )
                )
        hits = sorted(hits, key=lambda item: item.score, reverse=True)[:max_entries]
        return LorebookBundle(entries=lorebook.entries, hits=hits)

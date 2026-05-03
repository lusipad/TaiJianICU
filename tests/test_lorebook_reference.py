from pathlib import Path

from core.models.memory_snapshot import MemorySnapshot
from core.models.reference_profile import ReferenceProfile, ReferenceTrait
from core.models.world_model import CanonFact, CharacterArc, ExpansionSlot, WorldModel
from core.services.planning import ReferencePlanner
from core.services.world import LorebookManager


def build_world_model() -> WorldModel:
    return WorldModel(
        title="测试世界",
        canon_facts=[
            CanonFact(
                id="fact-001",
                category="canon",
                statement="旧案线索不能无代价公开",
            )
        ],
        main_characters=[
            CharacterArc(character_name="主角"),
            CharacterArc(character_name="同伴"),
        ],
        world_tensions=["旧城内斗", "外部窥视"],
        open_mysteries=["无名线人的身份"],
        expansion_slots=[
            ExpansionSlot(
                slot_id="slot-001",
                slot_type="location",
                description="新的外部舞台",
            )
        ],
    )


def test_lorebook_manager_builds_entries_and_hits() -> None:
    manager = LorebookManager()
    bundle = manager.build(
        world_model=build_world_model(),
        memory_snapshot=MemorySnapshot(
            lore_candidates=["第一章 雨夜追魂", "第五十章 帮？"],
        ),
    )
    matched = manager.match(lorebook=bundle, query_text="本章要处理旧案线索不能无代价公开的问题")

    assert bundle.entries
    assert any(entry.hard_constraint for entry in bundle.entries)
    assert matched.hits
    assert matched.hits[0].reason == "keyword_match"


def test_reference_planner_selects_relevant_profiles() -> None:
    profiles = [
        ReferenceProfile(
            name="世界扩张参考",
            reference_type="world",
            abstract_traits=[ReferenceTrait(label="地图扩张", description="逐步开放新世界")],
            allowed_influences=["地图", "势力"],
        ),
        ReferenceProfile(
            name="人物关系参考",
            reference_type="character",
            abstract_traits=[ReferenceTrait(label="关系张力", description="双主角互相牵制")],
            allowed_influences=["人物弧线"],
        ),
    ]

    selected = ReferencePlanner().select_profiles(
        world_model=build_world_model(),
        reference_profiles=profiles,
        limit=1,
    )

    assert len(selected) == 1
    assert selected[0].name == "世界扩张参考"


def test_reference_planner_loads_profiles_from_directory(tmp_path: Path) -> None:
    profile_path = tmp_path / "world.json"
    profile_path.write_text(
        ReferenceProfile(
            name="世界扩张参考",
            reference_type="world",
            abstract_traits=[ReferenceTrait(label="地图扩张", description="逐步开放")],
            allowed_influences=["地图"],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    loaded = ReferencePlanner().load_profiles(tmp_path)

    assert len(loaded) == 1
    assert loaded[0].name == "世界扩张参考"

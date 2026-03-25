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
                statement="修炼不能无代价越级突破",
            )
        ],
        main_characters=[
            CharacterArc(character_name="主角"),
            CharacterArc(character_name="同伴"),
        ],
        world_tensions=["家族内斗", "外部窥视"],
        open_mysteries=["神秘老师的身份"],
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
            lore_candidates=["第一章 陨落的天才", "第五十章 帮？"],
        ),
    )
    matched = manager.match(lorebook=bundle, query_text="本章要处理修炼不能无代价越级突破的问题")

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

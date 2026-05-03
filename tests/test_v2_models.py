from pathlib import Path

from core.models.arc_outline import ArcBeat, ArcOutline, PlannedIntroduction
from core.models.chapter_brief import ChapterBrief, ExpansionBudget
from core.models.evaluation import ChapterEvaluation, EvaluationFlag
from core.models.lorebook import LorebookBundle, LorebookEntry
from core.models.reference_profile import ReferenceProfile, ReferenceTrait
from core.models.world_model import (
    CanonFact,
    CharacterArc,
    ExpansionSlot,
    FactionState,
    LocationState,
    WorldModel,
)
from core.storage.session_store import SessionStore


def test_world_model_roundtrip_json() -> None:
    model = WorldModel(
        title="测试世界",
        summary="这是一个逐渐扩张的世界。",
        canon_facts=[
            CanonFact(
                id="fact-1",
                category="power",
                statement="旧案线索不可无代价公开。",
                source_chapter=3,
            )
        ],
        main_characters=[
            CharacterArc(
                character_name="林舟",
                current_state="准备追查下一条线索",
                core_wants=["查明旧案"],
                hidden_pressure=["旧城各方盯防"],
            )
        ],
        active_factions=[
            FactionState(
                name="城守司",
                public_goal="维持旧城秩序",
                hidden_goal="压制内部分裂",
            )
        ],
        known_locations=[
            LocationState(
                name="旧城",
                location_type="城市",
                story_function="主舞台",
            )
        ],
        expansion_slots=[
            ExpansionSlot(
                slot_id="slot-1",
                slot_type="location",
                description="外部学院入口",
                trigger_hint="主角完成家族阶段",
            )
        ],
    )

    restored = WorldModel.model_validate_json(model.model_dump_json())

    assert restored.title == "测试世界"
    assert restored.main_characters[0].character_name == "林舟"
    assert restored.expansion_slots[0].slot_type == "location"


def test_arc_outline_and_chapter_brief_defaults() -> None:
    outline = ArcOutline(
        arc_id="arc-001",
        arc_theme="家族权力斗争",
        arc_goal="把内斗从暗战推进到公开冲突",
        chapters_span=[51, 55],
        required_payoffs=[ArcBeat(label="冲突公开化", description="大长老一系公开施压")],
        new_character_plan=[
            PlannedIntroduction(
                plan_type="character",
                name="外来监察者",
                purpose="放大外部压力",
            )
        ],
    )
    brief = ChapterBrief(
        chapter_number=51,
        chapter_goal="让冲突第一次公开显形",
        focus_threads=["family_politics", "mysterious_teacher"],
        expansion_budget=ExpansionBudget(mode="balanced", new_character_budget=1),
    )

    assert outline.chapters_span == [51, 55]
    assert outline.new_character_plan[0].plan_type == "character"
    assert brief.expansion_budget.new_character_budget == 1
    assert brief.allowed_expansion.new_character is False


def test_reference_lorebook_and_evaluation_models() -> None:
    profile = ReferenceProfile(
        name="悲剧式群像",
        reference_type="structure",
        abstract_traits=[ReferenceTrait(label="群像推进", description="多角色命运交织")],
        allowed_influences=["卷结构", "命运张力"],
        forbidden_copying=["直接复刻角色命运"],
    )
    lorebook = LorebookBundle(
        entries=[
            LorebookEntry(
                entry_id="canon-001",
                title="修炼限制",
                content="主角不能无代价越级突破。",
                hard_constraint=True,
            )
        ]
    )
    evaluation = ChapterEvaluation(
        chapter_number=51,
        flags=[EvaluationFlag(code="LOW_NOVELTY", message="最近三章创新不足")],
        summary="连续性稳定，但新意偏弱。",
    )

    assert profile.abstract_traits[0].label == "群像推进"
    assert lorebook.entries[0].hard_constraint is True
    assert evaluation.flags[0].code == "LOW_NOVELTY"


def test_session_store_v2_paths(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)

    assert store.world_model_path("demo") == tmp_path / "demo" / "world_model.json"
    assert store.arc_outline_path("demo", "arc-001") == tmp_path / "demo" / "arcs" / "arc-001.json"
    assert store.lorebook_path("demo") == tmp_path / "demo" / "lorebook.json"
    assert (
        store.selected_references_path("demo")
        == tmp_path / "demo" / "selected_references.json"
    )
    assert store.chapter_brief_path("demo", 12) == tmp_path / "demo" / "chapter_12_brief.json"
    assert (
        store.chapter_evaluation_path("demo", 12)
        == tmp_path / "demo" / "chapter_12_evaluation.json"
    )
    assert (
        store.chapter_skeleton_candidate_path("demo", 12, 2)
        == tmp_path / "demo" / "candidates" / "chapter_12_skeleton_candidate_2.json"
    )
    assert (
        store.chapter_draft_candidate_path("demo", 12, 3)
        == tmp_path / "demo" / "candidates" / "chapter_12_draft_candidate_3.md"
    )

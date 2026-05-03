from core.models.chapter_brief import ExpansionBudget
from core.models.reference_profile import ReferenceProfile, ReferenceTrait
from core.models.story_state import StoryThread
from core.models.world_model import ExpansionSlot, WorldModel
from core.services.planning import ArcPlanner, ChapterAllocator, ExpansionAllocator


def build_world_model() -> WorldModel:
    return WorldModel(
        title="旧城夜雨",
        summary="林舟的查案正在触发旧城内部与外部势力的连锁反应。",
        world_tensions=["旧城权力斗争", "外部势力窥视"],
        open_mysteries=["无名信的真实来历", "外界为何开始关注林舟"],
        expansion_slots=[
            ExpansionSlot(
                slot_id="slot-001",
                slot_type="location",
                description="学院或外部试炼场",
                trigger_hint="主角完成家族阶段",
            ),
            ExpansionSlot(
                slot_id="slot-002",
                slot_type="character",
                description="新的观察者或竞争者",
                trigger_hint="旧冲突接近公开化",
            ),
        ],
        active_threads=[
            StoryThread(id="city_politics", description="旧城内斗", introduced_at=20, last_advanced=50),
            StoryThread(id="anonymous_letter", description="无名信", introduced_at=8, last_advanced=49),
        ],
    )


def test_expansion_allocator_balanced_and_expansive_modes() -> None:
    world_model = build_world_model()
    allocator = ExpansionAllocator()

    balanced = allocator.allocate(world_model=world_model, mode="balanced", arc_length=5)
    expansive = allocator.allocate(world_model=world_model, mode="expansive", arc_length=5)

    assert balanced.mode == "balanced"
    assert balanced.new_character_budget >= 1
    assert expansive.mode == "expansive"
    assert expansive.new_location_budget >= balanced.new_location_budget


def test_arc_planner_generates_outline() -> None:
    world_model = build_world_model()
    budget = ExpansionBudget(
        mode="balanced",
        expansion_mode="medium",
        new_character_budget=1,
        new_location_budget=1,
        new_faction_budget=1,
        twist_budget=1,
        reveal_budget=2,
    )

    outline = ArcPlanner().plan(
        world_model=world_model,
        start_chapter=51,
        arc_length=5,
        expansion_budget=budget,
    )

    assert outline.arc_id == "arc_0051_0055"
    assert outline.chapters_span == [51, 55]
    assert outline.required_setups
    assert outline.required_payoffs
    assert outline.new_character_plan
    assert outline.twist_plan


def test_chapter_allocator_produces_brief() -> None:
    world_model = build_world_model()
    budget = ExpansionBudget(
        mode="balanced",
        expansion_mode="medium",
        new_character_budget=1,
        new_location_budget=1,
        new_faction_budget=0,
        twist_budget=1,
        reveal_budget=2,
    )
    outline = ArcPlanner().plan(
        world_model=world_model,
        start_chapter=51,
        arc_length=5,
        expansion_budget=budget,
    )

    brief = ChapterAllocator().allocate(
        world_model=world_model,
        arc_outline=outline,
        chapter_number=53,
        expansion_budget=budget,
    )

    assert brief.chapter_number == 53
    assert brief.chapter_goal
    assert brief.focus_threads == ["city_politics", "anonymous_letter"]
    assert brief.allowed_expansion.new_character is True
    assert brief.constraints[0].label == "arc_alignment"


def test_chapter_allocator_injects_reference_constraints() -> None:
    world_model = build_world_model()
    budget = ExpansionBudget(
        mode="balanced",
        expansion_mode="medium",
        new_character_budget=1,
        new_location_budget=0,
        new_faction_budget=0,
        twist_budget=1,
        reveal_budget=1,
    )
    outline = ArcPlanner().plan(
        world_model=world_model,
        start_chapter=51,
        arc_length=3,
        expansion_budget=budget,
    )

    brief = ChapterAllocator().allocate(
        world_model=world_model,
        arc_outline=outline,
        chapter_number=52,
        expansion_budget=budget,
        reference_profiles=[
            ReferenceProfile(
                name="结构压强参考",
                reference_type="structure",
                abstract_traits=[ReferenceTrait(label="加压点", description="每章必须加压")],
                allowed_influences=["章节节奏"],
            )
        ],
    )

    assert "结构压强参考" in brief.chapter_note
    assert any(item.label == "reference_1" for item in brief.constraints)

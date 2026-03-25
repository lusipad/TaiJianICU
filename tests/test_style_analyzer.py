from config.settings import AppSettings
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from pipeline.stage1_extraction.style_analyzer import StyleAnalyzer


def test_merge_story_state_prefers_recent_plot_state() -> None:
    analyzer = StyleAnalyzer(AppSettings(), llm_service=None)  # type: ignore[arg-type]
    base = StoryWorldState(
        title="三国演义",
        summary="早期群雄并起。",
        world_rules=["历史演义"],
        main_characters=[
            CharacterCard(name="刘备", last_known_state="在袁绍处"),
            CharacterCard(name="曹操", last_known_state="准备北征"),
        ],
        active_conflicts=["官渡之战"],
        unresolved_threads=[StoryThread(id="T001", description="旧线索", introduced_at=1, last_advanced=20)],
    )
    recent = StoryWorldState(
        summary="赤壁之后，周瑜图南郡。",
        main_characters=[
            CharacterCard(name="刘备", last_known_state="屯兵油江口"),
            CharacterCard(name="周瑜", last_known_state="准备取南郡"),
        ],
        active_conflicts=["南郡争夺"],
        unresolved_threads=[StoryThread(id="T099", description="南郡归属", introduced_at=50, last_advanced=50)],
    )

    merged = analyzer._merge_story_state(base, recent)

    assert merged.summary == "赤壁之后，周瑜图南郡。"
    assert merged.active_conflicts == ["南郡争夺"]
    assert merged.unresolved_threads[0].id == "T099"
    assert any(item.name == "周瑜" for item in merged.main_characters)
    assert next(item for item in merged.main_characters if item.name == "刘备").last_known_state == "屯兵油江口"

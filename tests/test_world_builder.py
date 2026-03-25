from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.world_model import WorldModel
from core.services.world.memory_compressor import MemoryCompressor
from core.services.world.world_refresh import WorldRefreshService
from pipeline.stage1_extraction.world_builder import WorldBuilder


def build_snapshot() -> ExtractionSnapshot:
    return ExtractionSnapshot(
        style_profile=StyleProfile(
            narrative_person="第三人称",
            pacing="中速推进",
            tone_keywords=["压迫感", "升级感"],
            summary="整体风格偏压迫感和升级流。",
        ),
        story_state=StoryWorldState(
            title="斗破苍穹",
            summary="萧炎重新崛起，家族内部暗流涌动。",
            world_rules=["斗气修炼不能越级稳定突破"],
            main_characters=[
                CharacterCard(
                    name="萧炎",
                    role="主角",
                    core_goals=["变强", "洗刷屈辱"],
                    personality_traits=["隐忍", "倔强"],
                    last_known_state="准备冲击新阶段",
                )
            ],
            major_relationships=["萧战与大长老一系关系紧张"],
            active_conflicts=["家族权力斗争升级"],
            unresolved_threads=[
                StoryThread(
                    id="T001",
                    description="神秘老师的真实来历",
                    introduced_at=1,
                    last_advanced=50,
                )
            ],
        ),
    )


def test_world_builder_maps_snapshot_to_world_model() -> None:
    world_model = WorldBuilder().from_snapshot(build_snapshot(), chapter_number=50)

    assert world_model.title == "斗破苍穹"
    assert world_model.last_refreshed_chapter == 50
    assert world_model.main_characters[0].character_name == "萧炎"
    assert world_model.power_system_rules == ["斗气修炼不能越级稳定突破"]
    assert world_model.open_mysteries == ["神秘老师的真实来历"]


def test_world_refresh_merges_previous_state() -> None:
    previous = WorldModel(
        title="斗破苍穹",
        summary="旧摘要",
        open_mysteries=["旧谜团"],
        last_refreshed_chapter=40,
    )

    refreshed = WorldRefreshService().refresh(
        snapshot=build_snapshot(),
        previous=previous,
        chapter_number=50,
    )

    assert refreshed.last_refreshed_chapter == 50
    assert "神秘老师的真实来历" in refreshed.open_mysteries
    assert refreshed.summary == "萧炎重新崛起，家族内部暗流涌动。"


def test_memory_compressor_builds_layered_snapshot() -> None:
    text = (
        "第一章 雨夜\n林舟醒来。\n\n"
        "第二章 灯火\n他去酒馆。\n\n"
        "第三章 试探\n黑衣人现身。\n\n"
        "第四章 对峙\n危机加剧。"
    )

    snapshot = MemoryCompressor(recent_chars=20, middle_chars=40, long_term_chars=20).compress(text)

    assert "第四章 对峙" in snapshot.recent_excerpt
    assert snapshot.middle_summary
    assert "第一章 雨夜" in snapshot.long_term_summary
    assert snapshot.lore_candidates

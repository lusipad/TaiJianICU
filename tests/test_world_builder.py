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
            tone_keywords=["压迫感", "悬疑感"],
            summary="整体风格偏压迫感和悬疑推进。",
        ),
        story_state=StoryWorldState(
            title="旧城夜雨",
            summary="林舟重新查案，旧城内部暗流涌动。",
            world_rules=["城中旧案牵涉多方势力，不能公开泄露线索"],
            main_characters=[
                CharacterCard(
                    name="林舟",
                    role="主角",
                    core_goals=["查明旧案", "保护证人"],
                    personality_traits=["隐忍", "谨慎"],
                    last_known_state="准备追查新线索",
                )
            ],
            major_relationships=["林舟与城守司关系紧张"],
            active_conflicts=["旧案背后的权力斗争升级"],
            unresolved_threads=[
                StoryThread(
                    id="T001",
                    description="无名信的真实来历",
                    introduced_at=1,
                    last_advanced=50,
                )
            ],
        ),
    )


def test_world_builder_maps_snapshot_to_world_model() -> None:
    world_model = WorldBuilder().from_snapshot(build_snapshot(), chapter_number=50)

    assert world_model.title == "旧城夜雨"
    assert world_model.last_refreshed_chapter == 50
    assert world_model.main_characters[0].character_name == "林舟"
    assert world_model.power_system_rules == ["城中旧案牵涉多方势力，不能公开泄露线索"]
    assert world_model.open_mysteries == ["无名信的真实来历"]


def test_world_refresh_merges_previous_state() -> None:
    previous = WorldModel(
        title="旧城夜雨",
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
    assert "无名信的真实来历" in refreshed.open_mysteries
    assert refreshed.summary == "林舟重新查案，旧城内部暗流涌动。"


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


def test_world_refresh_updates_state_after_generated_chapter() -> None:
    previous = WorldBuilder().from_snapshot(build_snapshot(), chapter_number=50)

    refreshed = WorldRefreshService().refresh_with_chapter(
        previous=previous,
        chapter_text="林舟在夜色中现身，与线人商议后决定继续追查无名信留下的线索。",
        active_threads=[
            StoryThread(
                id="T001",
                description="无名信的真实来历",
                introduced_at=1,
                last_advanced=51,
                status="advanced",
            )
        ],
        chapter_number=51,
        chapter_goal="推进无名信线索",
    )

    assert refreshed.last_refreshed_chapter == 51
    assert refreshed.main_characters[0].recent_change == "第51章出场并推进当前情节"
    assert refreshed.open_mysteries == ["无名信的真实来历"]
    assert refreshed.known_locations[0].current_status

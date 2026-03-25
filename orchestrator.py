from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from config.settings import AppSettings, get_settings
from core.llm.litellm_client import LLMUsageSummary, LiteLLMService
from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation
from core.models.lorebook import LorebookBundle
from core.models.reference_profile import ReferenceProfile
from core.models.skeleton import ChapterSkeleton
from core.models.story_state import StoryThread
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import WorldModel
from core.services.planning import ArcPlanner, ChapterAllocator, ExpansionAllocator, ReferencePlanner
from core.services.reflection import ReflectionUpdater
from core.services.world import LorebookManager, MemoryCompressor, WorldRefreshService
from core.storage.lightrag_store import LightRAGStore
from core.storage.session_store import SessionStore
from intervention import InterventionManager
from pipeline.stage1_extraction.novel_indexer import IndexingResult, NovelIndexer
from pipeline.stage1_extraction.style_analyzer import StyleAnalyzer
from pipeline.stage2_plot.agent_nodes import AgentNodeService
from pipeline.stage2_plot.consistency_checker import ConsistencyChecker, ConsistencyReport
from pipeline.stage2_plot.debate_graph import DebateGraph
from pipeline.stage2_plot.skeleton_builder import SkeletonBuilder
from pipeline.stage3_generation.chapter_generator import ChapterGenerator
from pipeline.stage3_generation.quality_checker import QualityChecker, QualityReport
from pipeline.stage3_generation.style_sampler import StyleSampler


class ChapterRunResult(BaseModel):
    chapter_number: int
    skeleton_path: str
    draft_path: str | None = None
    output_path: str | None = None
    quality_report: QualityReport | None = None
    consistency_report: ConsistencyReport | None = None
    chapter_evaluation: ChapterEvaluation | None = None
    status: str = "completed"
    chapter_goal: str | None = None
    usage_summary: LLMUsageSummary = Field(default_factory=LLMUsageSummary)
    elapsed_seconds: float = 0.0


class PipelineRunResult(BaseModel):
    session_name: str
    input_path: str
    stage1_snapshot_path: str
    world_model_path: str | None = None
    index_result: IndexingResult
    stage1_usage: LLMUsageSummary = Field(default_factory=LLMUsageSummary)
    chapters: list[ChapterRunResult] = Field(default_factory=list)
    total_usage: LLMUsageSummary = Field(default_factory=LLMUsageSummary)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: str = "completed"


class ReferenceProfileBundle(BaseModel):
    profiles: list[ReferenceProfile] = Field(default_factory=list)


class TaiJianOrchestrator:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or get_settings()
        self.llm_service = LiteLLMService(self.settings)
        self.session_store = SessionStore(self.settings.sessions_dir)
        self.rag_store = LightRAGStore(self.settings, self.llm_service)
        self.indexer = NovelIndexer(self.settings, self.rag_store)
        self.style_analyzer = StyleAnalyzer(self.settings, self.llm_service)
        self.world_refresh = WorldRefreshService()
        self.memory_compressor = MemoryCompressor(
            recent_chars=self.settings.tuning.recent_story_excerpt_chars,
            middle_chars=max(4000, self.settings.tuning.recent_story_excerpt_chars // 2),
            long_term_chars=max(2000, self.settings.tuning.style_excerpt_chars // 4),
        )
        self.lorebook_manager = LorebookManager()
        self.expansion_allocator = ExpansionAllocator()
        self.arc_planner = ArcPlanner()
        self.chapter_allocator = ChapterAllocator()
        self.reference_planner = ReferencePlanner()
        self.reflection_updater = ReflectionUpdater()
        self.agent_service = AgentNodeService(
            self.settings,
            self.llm_service,
            self.rag_store,
        )
        self.skeleton_builder = SkeletonBuilder(self.settings, self.llm_service)
        self.consistency_checker = ConsistencyChecker(
            retry_limit=self.settings.tuning.consistency_retry_limit
        )
        self.debate_graph = DebateGraph(
            self.agent_service,
            self.skeleton_builder,
            self.consistency_checker,
        )
        self.style_sampler = StyleSampler(self.rag_store)
        self.chapter_generator = ChapterGenerator(self.settings, self.llm_service)
        self.quality_checker = QualityChecker(self.settings, self.llm_service)
        self.intervention = InterventionManager(self.session_store)

    @staticmethod
    def _emit(progress_callback: Callable[[str], None] | None, message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    def _default_session_name(self, input_path: Path) -> str:
        return input_path.stem

    @staticmethod
    def _merge_usage_summaries(*summaries: LLMUsageSummary) -> LLMUsageSummary:
        merged = LLMUsageSummary()
        for summary in summaries:
            merged.calls += summary.calls
            merged.prompt_tokens += summary.prompt_tokens
            merged.completion_tokens += summary.completion_tokens
            merged.total_tokens += summary.total_tokens
            merged.cached_tokens += summary.cached_tokens
            merged.total_cost_usd += summary.total_cost_usd
            for model_name, bucket in summary.by_model.items():
                target = merged.by_model.setdefault(
                    model_name,
                    {
                        "calls": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cached_tokens": 0,
                        "total_cost_usd": 0.0,
                    },
                )
                target["calls"] = int(target["calls"]) + int(bucket.get("calls", 0))
                target["prompt_tokens"] = int(target["prompt_tokens"]) + int(
                    bucket.get("prompt_tokens", 0)
                )
                target["completion_tokens"] = int(target["completion_tokens"]) + int(
                    bucket.get("completion_tokens", 0)
                )
                target["total_tokens"] = int(target["total_tokens"]) + int(
                    bucket.get("total_tokens", 0)
                )
                target["cached_tokens"] = int(target["cached_tokens"]) + int(
                    bucket.get("cached_tokens", 0)
                )
                target["total_cost_usd"] = float(target["total_cost_usd"]) + float(
                    bucket.get("total_cost_usd", 0.0)
                )
        merged.total_cost_usd = round(merged.total_cost_usd, 6)
        for bucket in merged.by_model.values():
            bucket["total_cost_usd"] = round(float(bucket["total_cost_usd"]), 6)
        return merged

    def _build_session_manifest(
        self,
        session_name: str,
        current_result: PipelineRunResult,
    ) -> PipelineRunResult:
        manifest_path = self.session_store.run_manifest_path(session_name)
        previous_manifest = self.session_store.load_model(manifest_path, PipelineRunResult)
        if not isinstance(previous_manifest, PipelineRunResult):
            return current_result

        merged_by_chapter = {
            chapter.chapter_number: chapter for chapter in previous_manifest.chapters
        }
        for chapter in current_result.chapters:
            if (
                chapter.status == "skipped_existing_output"
                and chapter.chapter_number in merged_by_chapter
            ):
                continue
            else:
                merged_by_chapter[chapter.chapter_number] = chapter

        merged_chapters = [
            merged_by_chapter[number] for number in sorted(merged_by_chapter.keys())
        ]
        stage1_usage = current_result.stage1_usage
        if (
            stage1_usage.calls == 0
            and current_result.index_result.chunk_count == 0
            and previous_manifest.stage1_usage.calls > 0
        ):
            stage1_usage = previous_manifest.stage1_usage

        index_result = current_result.index_result
        if index_result.chunk_count == 0 and previous_manifest.index_result.chunk_count > 0:
            index_result = previous_manifest.index_result

        return current_result.model_copy(
            update={
                "index_result": index_result,
                "stage1_usage": stage1_usage,
                "chapters": merged_chapters,
                "total_usage": self._merge_usage_summaries(
                    stage1_usage,
                    *[chapter.usage_summary for chapter in merged_chapters],
                ),
                "started_at": (
                    previous_manifest.started_at
                    if current_result.index_result.chunk_count == 0
                    else current_result.started_at
                ),
            }
        )

    def _build_chapter_goal(
        self,
        *,
        chapter_brief: ChapterBrief,
        focus_threads: list[StoryThread],
        fallback_goal: str | None = None,
    ) -> str:
        goal = chapter_brief.chapter_goal or fallback_goal or "推进主线冲突"
        lines = [f"第{chapter_brief.chapter_number}章目标：{goal}"]
        if chapter_brief.must_happen:
            lines.append(f"必须发生：{'；'.join(chapter_brief.must_happen)}")
        if focus_threads:
            lines.append(
                "优先推进伏笔："
                + "；".join(f"{thread.id}:{thread.description}" for thread in focus_threads)
            )
        if chapter_brief.must_not_break:
            lines.append(f"不可破坏设定：{'；'.join(chapter_brief.must_not_break[:3])}")
        if chapter_brief.chapter_note:
            lines.append(f"备注：{chapter_brief.chapter_note}")
        return "。".join(lines)

    def _apply_chapter_brief_overrides(
        self,
        *,
        chapter_brief: ChapterBrief,
        intervention_must_happen: list[str],
        intervention_notes: str,
        goal_hint: str | None,
    ) -> ChapterBrief:
        merged_must_happen = list(
            dict.fromkeys([*chapter_brief.must_happen, *intervention_must_happen])
        )
        note_parts = [chapter_brief.chapter_note.strip()]
        if intervention_notes.strip():
            note_parts.append(f"人工备注：{intervention_notes.strip()}")
        note = "；".join(part for part in note_parts if part)
        updates: dict[str, object] = {
            "must_happen": merged_must_happen,
            "chapter_note": note,
        }
        if goal_hint:
            updates["chapter_goal"] = goal_hint
        return chapter_brief.model_copy(update=updates)

    def _match_lorebook_for_chapter(
        self,
        *,
        lorebook: LorebookBundle,
        chapter_brief: ChapterBrief,
        focus_threads: list[StoryThread],
    ) -> LorebookBundle:
        query_parts = [
            chapter_brief.chapter_goal,
            *chapter_brief.must_happen,
            *chapter_brief.must_not_break[:3],
            *[f"{thread.id} {thread.description}" for thread in focus_threads],
        ]
        return self.lorebook_manager.match(
            lorebook=lorebook,
            query_text="\n".join(part for part in query_parts if part),
        )

    def _select_focus_threads(
        self,
        threads: list[StoryThread],
        focus_thread_ids: list[str],
    ) -> list[StoryThread]:
        if not threads:
            return []
        if focus_thread_ids:
            selected = [thread for thread in threads if thread.id in set(focus_thread_ids)]
            if selected:
                return selected
        open_threads = [thread for thread in threads if thread.status != "closed"]
        ranked = sorted(open_threads or threads, key=lambda item: (item.last_advanced, item.introduced_at))
        return ranked[:2]

    def _update_threads(
        self,
        current_threads: list[StoryThread],
        advanced: list[str],
        closed: list[str],
        chapter_number: int,
    ) -> list[StoryThread]:
        closed_ids = set(closed)
        advanced_ids = set(advanced)
        updated: list[StoryThread] = []
        for thread in current_threads:
            if thread.id in closed_ids:
                updated.append(
                    thread.model_copy(
                        update={"status": "closed", "last_advanced": chapter_number}
                    )
                )
            elif thread.id in advanced_ids:
                updated.append(
                    thread.model_copy(
                        update={"status": "advanced", "last_advanced": chapter_number}
                    )
                )
            else:
                updated.append(thread)
        return updated

    async def _stage1(
        self,
        *,
        session_name: str,
        input_path: Path,
        use_existing_index: bool,
        refresh_snapshot: bool,
    ) -> tuple[IndexingResult, ExtractionSnapshot, str]:
        snapshot_path = self.session_store.stage1_snapshot_path(session_name)
        novel_text = self.indexer.load_text(input_path)
        rag_dir = self.settings.lightrag_dir / session_name

        if use_existing_index and rag_dir.exists():
            if snapshot_path.exists() and not refresh_snapshot:
                snapshot = ExtractionSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
            else:
                snapshot = await self.style_analyzer.analyze(novel_text)
                self.session_store.save_model(snapshot_path, snapshot)
                self.session_store.save_unresolved_threads(
                    session_name,
                    snapshot.story_state.unresolved_threads,
                )
            index_result = IndexingResult(
                source_path=str(input_path),
                chunk_count=0,
                character_count=len(novel_text),
            )
            return index_result, snapshot, str(snapshot_path)

        index_result, novel_text = await self.indexer.index_file(session_name, input_path)
        snapshot = await self.style_analyzer.analyze(novel_text)
        self.session_store.save_model(snapshot_path, snapshot)
        self.session_store.save_unresolved_threads(
            session_name,
            snapshot.story_state.unresolved_threads,
        )
        return index_result, snapshot, str(snapshot_path)

    async def _prepare_skeleton(
        self,
        *,
        session_name: str,
        chapter_number: int,
        chapter_goal: str,
        world_model: WorldModel,
        chapter_brief: ChapterBrief,
        lorebook_context: LorebookBundle,
        snapshot: ExtractionSnapshot,
        focus_threads: list[StoryThread],
        resume: bool,
        overwrite: bool,
    ) -> tuple[ChapterSkeleton, ConsistencyReport]:
        skeleton_path = self.session_store.chapter_skeleton_path(session_name, chapter_number)
        if resume and skeleton_path.exists() and not overwrite:
            skeleton = self.session_store.load_model(skeleton_path, ChapterSkeleton)
            assert isinstance(skeleton, ChapterSkeleton)
            report = self.consistency_checker.check(skeleton, focus_threads)
            return skeleton, report

        skeleton, report = await self.debate_graph.plan_chapter(
            session_name=session_name,
            chapter_number=chapter_number,
            chapter_goal=chapter_goal,
            story_state=snapshot.story_state,
            world_model=world_model,
            chapter_brief=chapter_brief,
            lorebook_context=lorebook_context,
            focus_threads=focus_threads,
        )
        skeleton = self.intervention.apply_skeleton_override(
            session_name,
            chapter_number,
            skeleton,
        )
        self.session_store.save_model(skeleton_path, skeleton)
        return skeleton, report

    async def _prepare_draft(
        self,
        *,
        session_name: str,
        chapter_number: int,
        skeleton: ChapterSkeleton,
        world_model: WorldModel,
        chapter_brief: ChapterBrief,
        lorebook_context: LorebookBundle,
        snapshot: ExtractionSnapshot,
        style_samples: list[str],
        resume: bool,
        overwrite: bool,
    ) -> tuple[str, Path]:
        draft_path = self.session_store.chapter_draft_path(session_name, chapter_number)
        if resume and draft_path.exists() and not overwrite:
            return draft_path.read_text(encoding="utf-8"), draft_path

        draft_text = await self.chapter_generator.generate(
            skeleton=skeleton,
            style_profile=snapshot.style_profile,
            style_samples=style_samples,
            world_model=world_model,
            chapter_brief=chapter_brief,
            lorebook_context=lorebook_context,
        )
        draft_text = self.intervention.apply_draft_override(
            session_name,
            chapter_number,
            draft_text,
        )
        self.session_store.save_text(draft_path, draft_text)
        return draft_text, draft_path

    async def _finalize_output(
        self,
        *,
        session_name: str,
        chapter_number: int,
        skeleton: ChapterSkeleton,
        world_model: WorldModel,
        chapter_brief: ChapterBrief,
        lorebook_context: LorebookBundle,
        snapshot: ExtractionSnapshot,
        draft_text: str,
        style_samples: list[str],
    ) -> tuple[str, QualityReport]:
        final_text = await self.chapter_generator.polish(
            draft_text=draft_text,
            style_profile=snapshot.style_profile,
            world_model=world_model,
            chapter_brief=chapter_brief,
            lorebook_context=lorebook_context,
        )
        quality_report = await self.quality_checker.evaluate(
            skeleton=skeleton,
            draft_text=final_text,
            style_samples=style_samples,
        )
        retry_count = 0
        while (
            quality_report.verdict != "pass"
            and retry_count < self.settings.tuning.quality_retry_limit
        ):
            retry_count += 1
            final_text = await self.chapter_generator.revise(
                draft_text=final_text,
                style_profile=snapshot.style_profile,
                issues=quality_report.issues or ["角色一致性与节奏需要提升"],
                skeleton=skeleton,
                world_model=world_model,
                chapter_brief=chapter_brief,
                lorebook_context=lorebook_context,
            )
            quality_report = await self.quality_checker.evaluate(
                skeleton=skeleton,
                draft_text=final_text,
                style_samples=style_samples,
            )
        return final_text, quality_report

    async def run(
        self,
        *,
        input_path: Path,
        chapters: int = 1,
        session_name: str | None = None,
        goal_hint: str | None = None,
        use_existing_index: bool = False,
        refresh_snapshot: bool = False,
        pause_after_skeleton: bool = False,
        pause_after_draft: bool = False,
        resume: bool = False,
        overwrite: bool = False,
        start_chapter: int = 1,
        progress_callback: Callable[[str], None] | None = None,
    ) -> PipelineRunResult:
        session_name = session_name or self._default_session_name(input_path)
        run_started_at = datetime.now(timezone.utc)
        overall_usage_mark = self.llm_service.usage_mark()

        self._emit(progress_callback, "阶段1：索引与风格分析")
        index_result, snapshot, snapshot_path = await self._stage1(
            session_name=session_name,
            input_path=input_path,
            use_existing_index=use_existing_index or resume,
            refresh_snapshot=refresh_snapshot,
        )
        stage1_usage = self.llm_service.usage_summary(overall_usage_mark)
        current_threads = self.session_store.load_unresolved_threads(session_name)
        world_model_path = self.session_store.world_model_path(session_name)
        previous_world_model = self.session_store.load_model(world_model_path, WorldModel)
        world_model = self.world_refresh.refresh(
            snapshot=snapshot,
            previous=previous_world_model if isinstance(previous_world_model, WorldModel) else None,
            chapter_number=max(0, start_chapter - 1),
        )
        self.session_store.save_model(world_model_path, world_model)
        memory_snapshot = self.memory_compressor.compress(Path(input_path).read_text(encoding="utf-8"))
        lorebook = self.lorebook_manager.build(
            world_model=world_model,
            memory_snapshot=memory_snapshot,
        )
        self.session_store.save_model(
            self.session_store.lorebook_path(session_name),
            lorebook,
        )
        selected_references = self.reference_planner.select_profiles(
            world_model=world_model,
            reference_profiles=self.reference_planner.load_profiles(self.settings.references_dir),
            limit=2,
        )
        self.session_store.save_model(
            self.session_store.selected_references_path(session_name),
            ReferenceProfileBundle(profiles=selected_references),
        )
        arc_length = min(max(1, chapters), 5)
        expansion_budget = self.expansion_allocator.allocate(
            world_model=world_model,
            mode="balanced",
            arc_length=arc_length,
        )
        arc_outline = self.arc_planner.plan(
            world_model=world_model,
            start_chapter=start_chapter,
            arc_length=arc_length,
            expansion_budget=expansion_budget,
        )
        self.session_store.save_model(
            self.session_store.arc_outline_path(session_name, arc_outline.arc_id),
            arc_outline,
        )
        result = PipelineRunResult(
            session_name=session_name,
            input_path=str(input_path),
            stage1_snapshot_path=snapshot_path,
            world_model_path=str(world_model_path),
            index_result=index_result,
            stage1_usage=stage1_usage,
            started_at=run_started_at,
        )

        for chapter_number in range(start_chapter, start_chapter + chapters):
            chapter_usage_mark = self.llm_service.usage_mark()
            chapter_started_at = datetime.now(timezone.utc)
            intervention_config = self.intervention.load_or_create(session_name, chapter_number)
            chapter_brief = self.chapter_allocator.allocate(
                world_model=world_model,
                arc_outline=arc_outline,
                chapter_number=chapter_number,
                expansion_budget=expansion_budget,
                reference_profiles=selected_references,
            )
            chapter_brief = self._apply_chapter_brief_overrides(
                chapter_brief=chapter_brief,
                intervention_must_happen=intervention_config.must_happen,
                intervention_notes=intervention_config.notes,
                goal_hint=goal_hint,
            )
            self.session_store.save_model(
                self.session_store.chapter_brief_path(session_name, chapter_number),
                chapter_brief,
            )
            focus_threads = self._select_focus_threads(
                current_threads or snapshot.story_state.unresolved_threads,
                intervention_config.focus_thread_ids or chapter_brief.focus_threads,
            )
            chapter_goal = self._build_chapter_goal(
                chapter_brief=chapter_brief,
                focus_threads=focus_threads,
            )
            lorebook_context = self._match_lorebook_for_chapter(
                lorebook=lorebook,
                chapter_brief=chapter_brief,
                focus_threads=focus_threads,
            )

            skeleton_path = self.session_store.chapter_skeleton_path(session_name, chapter_number)
            draft_path = self.session_store.chapter_draft_path(session_name, chapter_number)
            output_path = self.settings.output_dir / session_name / f"chapter_{chapter_number}.md"

            chapter_result = ChapterRunResult(
                chapter_number=chapter_number,
                skeleton_path=str(skeleton_path),
                chapter_goal=chapter_goal,
            )

            if resume and output_path.exists() and not overwrite:
                chapter_result.output_path = str(output_path)
                chapter_result.draft_path = str(draft_path) if draft_path.exists() else None
                chapter_result.status = "skipped_existing_output"
                chapter_result.usage_summary = self.llm_service.usage_summary(chapter_usage_mark)
                chapter_result.elapsed_seconds = (datetime.now(timezone.utc) - chapter_started_at).total_seconds()
                result.chapters.append(chapter_result)
                self._emit(progress_callback, f"章节{chapter_number}：复用已有正文")
                continue

            self._emit(progress_callback, f"章节{chapter_number}：情节辩论")
            skeleton, consistency_report = await self._prepare_skeleton(
                session_name=session_name,
                chapter_number=chapter_number,
                chapter_goal=chapter_goal,
                world_model=world_model,
                chapter_brief=chapter_brief,
                lorebook_context=lorebook_context,
                snapshot=snapshot,
                focus_threads=focus_threads,
                resume=resume,
                overwrite=overwrite,
            )
            chapter_result.consistency_report = consistency_report

            if pause_after_skeleton:
                chapter_result.status = "paused_after_skeleton"
                chapter_result.usage_summary = self.llm_service.usage_summary(chapter_usage_mark)
                chapter_result.elapsed_seconds = (datetime.now(timezone.utc) - chapter_started_at).total_seconds()
                result.chapters.append(chapter_result)
                result.status = "paused_after_skeleton"
                break

            style_samples = await self.style_sampler.sample(
                session_name,
                skeleton,
                snapshot.style_profile,
            )

            self._emit(progress_callback, f"章节{chapter_number}：生成草稿")
            draft_text, saved_draft_path = await self._prepare_draft(
                session_name=session_name,
                chapter_number=chapter_number,
                skeleton=skeleton,
                world_model=world_model,
                chapter_brief=chapter_brief,
                lorebook_context=lorebook_context,
                snapshot=snapshot,
                style_samples=style_samples,
                resume=resume,
                overwrite=overwrite,
            )
            chapter_result.draft_path = str(saved_draft_path)

            if pause_after_draft:
                chapter_result.status = "paused_after_draft"
                chapter_result.usage_summary = self.llm_service.usage_summary(chapter_usage_mark)
                chapter_result.elapsed_seconds = (datetime.now(timezone.utc) - chapter_started_at).total_seconds()
                result.chapters.append(chapter_result)
                result.status = "paused_after_draft"
                break

            self._emit(progress_callback, f"章节{chapter_number}：润色与质检")
            final_text, quality_report = await self._finalize_output(
                session_name=session_name,
                chapter_number=chapter_number,
                skeleton=skeleton,
                world_model=world_model,
                chapter_brief=chapter_brief,
                lorebook_context=lorebook_context,
                snapshot=snapshot,
                draft_text=draft_text,
                style_samples=style_samples,
            )

            self._emit(progress_callback, f"章节{chapter_number}：写回会话")
            self.session_store.save_text(output_path, final_text)
            await self.rag_store.append_text(session_name, final_text)
            current_threads = self._update_threads(
                current_threads or snapshot.story_state.unresolved_threads,
                skeleton.threads_to_advance,
                skeleton.threads_to_close,
                chapter_number,
            )
            self.session_store.save_unresolved_threads(session_name, current_threads)

            chapter_result.output_path = str(output_path)
            chapter_result.quality_report = quality_report
            chapter_result.chapter_evaluation = self.reflection_updater.evaluate_chapter(
                chapter_number=chapter_number,
                chapter_brief=chapter_brief,
                world_model=world_model,
                skeleton=skeleton,
                consistency_report=consistency_report,
                quality_report=quality_report,
                final_text=final_text,
            )
            self.session_store.save_model(
                self.session_store.chapter_evaluation_path(session_name, chapter_number),
                chapter_result.chapter_evaluation,
            )
            chapter_result.status = (
                "completed"
                if quality_report.verdict == "pass" and consistency_report.passed
                else "completed_with_warnings"
            )
            chapter_result.usage_summary = self.llm_service.usage_summary(chapter_usage_mark)
            chapter_result.elapsed_seconds = (datetime.now(timezone.utc) - chapter_started_at).total_seconds()
            result.chapters.append(chapter_result)

        result.total_usage = self.llm_service.usage_summary(overall_usage_mark)
        result.finished_at = datetime.now(timezone.utc)
        if not result.status.startswith("paused"):
            result.status = "completed"
        session_manifest = self._build_session_manifest(session_name, result)
        self.session_store.save_model(self.session_store.run_manifest_path(session_name), session_manifest)
        return result

from __future__ import annotations

import asyncio
import json
import re
import threading
from concurrent.futures import Future as ConcurrentFuture
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from config.settings import AppSettings
from core.benchmarking.runner import BenchmarkReport
from core.llm.litellm_client import LiteLLMService
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation
from core.models.lorebook import LorebookBundle
from core.models.reference_profile import ReferenceProfile
from core.models.revival import (
    BlindChallenge,
    BlindChallengeRating,
    DirectorArcOptions,
    RevivalDiagnosis,
    SelectedArc,
    WorkSkill,
)
from core.models.story_state import StoryThread
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import WorldModel
from orchestrator import PipelineRunResult, RevivalAnalysisResult, TaiJianOrchestrator
from pipeline.revival import digest_payload
from webapp.builtin_examples import BUILT_IN_EXAMPLES, BuiltInExample
from webapp.errors import ApiError
from webapp.models import (
    WebDirectorPlan,
    WebDirectorPlanChapterItem,
    WebDirectorPlanUpdate,
    WebExampleDetail,
    WebExampleSummary,
    WebBenchmarkDetail,
    WebBenchmarkSummary,
    WebBlindChallenge,
    WebChapterSummary,
    WebPublicShowcase,
    WebArcSelectionRequest,
    WebBlindChallengeRatingRequest,
    WebRunArtifactPaths,
    WebRuntimeApiOverride,
    WebRuntimeConnectionTestRequest,
    WebRuntimeConnectionTestResult,
    WebRunDetail,
    WebRunMetrics,
    WebRunProgress,
    WebRunRequest,
    WebRunSourceText,
    WebRunSummary,
    WebRuntimeConfig,
)


_SESSION_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


class WebRunManager:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._runtime_lock = threading.Lock()
        self._runs: dict[str, WebRunDetail] = {}
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None
        self._async_futures: dict[str, ConcurrentFuture[None]] = {}
        self._load_existing_runs()

    def _run_file(self, run_id: str) -> Path:
        return self.settings.web_runs_dir / f"{run_id}.json"

    def _session_dir(self, session_name: str) -> Path:
        return self.settings.sessions_dir / session_name

    def _director_plan_path(self, session_name: str) -> Path:
        return self._session_dir(session_name) / "director_plan.json"

    def _benchmark_report_files(self) -> list[Path]:
        return sorted(
            self.settings.benchmarks_dir.glob("*/cases/*/report/benchmark_report.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    def _load_existing_runs(self) -> None:
        for path in sorted(self.settings.web_runs_dir.glob("*.json")):
            try:
                run = WebRunDetail.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            run = self._ensure_story_previews(run)
            run = self._ensure_arc_options_digest(run)
            self._runs[run.id] = run

    def _persist(self, run: WebRunDetail) -> None:
        self._run_file(run.id).write_text(run.model_dump_json(indent=2), encoding="utf-8")

    def _ensure_story_previews(self, run: WebRunDetail) -> WebRunDetail:
        if run.latest_source_preview and run.latest_source_preview_label:
            return run

        source_label = None
        source_preview = None
        previous_output_path = None
        if len(run.output_paths) >= 2:
            previous_output_path = Path(run.output_paths[-2])
        if previous_output_path is not None and previous_output_path.exists():
            source_label = "上文衔接"
            source_preview = self._excerpt_text(
                previous_output_path.read_text(encoding="utf-8"),
                take="tail",
                max_blocks=5,
                max_chars=1600,
            )
        elif run.input_path:
            input_path = Path(run.input_path)
            if input_path.exists():
                source_label = "原文断点"
                source_preview = self._excerpt_text(
                    input_path.read_text(encoding="utf-8"),
                    take="tail",
                    max_blocks=5,
                    max_chars=1600,
                )

        if source_label is None or source_preview is None:
            return run
        hydrated = run.model_copy(
            update={
                "latest_source_preview_label": source_label,
                "latest_source_preview": source_preview,
            }
        )
        self._persist(hydrated)
        return hydrated

    def _ensure_arc_options_digest(self, run: WebRunDetail) -> WebRunDetail:
        if run.arc_options_digest or run.arc_options is None:
            return run
        hydrated = run.model_copy(
            update={"arc_options_digest": self._arc_options_digest(run.arc_options)}
        )
        self._persist(hydrated)
        return hydrated

    def _ensure_director_plan_artifact(self, run: WebRunDetail) -> WebRunDetail:
        plan_path = self._director_plan_path(run.session_name)
        plan_path_str = str(plan_path)
        if run.artifact_paths.director_plan == plan_path_str:
            return run
        if not plan_path.exists():
            return run
        hydrated = run.model_copy(
            update={
                "artifact_paths": run.artifact_paths.model_copy(update={"director_plan": plan_path_str})
            }
        )
        self._persist(hydrated)
        return hydrated

    @staticmethod
    def _arc_options_digest(arc_options: DirectorArcOptions) -> str:
        return digest_payload(arc_options.model_dump(mode="json"))

    def _ensure_async_runtime(self) -> asyncio.AbstractEventLoop:
        with self._runtime_lock:
            if self._async_loop is not None and self._async_loop.is_running():
                return self._async_loop

            loop = asyncio.new_event_loop()
            ready = threading.Event()

            def _runner() -> None:
                asyncio.set_event_loop(loop)
                ready.set()
                loop.run_forever()

            thread = threading.Thread(target=_runner, name="web-run-loop", daemon=True)
            thread.start()
            if not ready.wait(timeout=5):
                raise RuntimeError("Web 异步运行时启动超时。")

            self._async_loop = loop
            self._async_thread = thread
            return loop

    def _schedule_run(self, run_id: str, run_settings: AppSettings | None = None) -> None:
        loop = self._ensure_async_runtime()
        future = asyncio.run_coroutine_threadsafe(self._run_pipeline_async(run_id, run_settings), loop)
        with self._runtime_lock:
            self._async_futures[run_id] = future

        def _cleanup(completed: ConcurrentFuture[None]) -> None:
            with self._runtime_lock:
                self._async_futures.pop(run_id, None)
            try:
                completed.result()
            except Exception as exc:
                current = self._runs.get(run_id)
                if current and current.status in {"queued", "running"}:
                    self._update_run(
                        run_id,
                        status="failed",
                        error_message=str(exc),
                        progress=current.progress.model_copy(update={"message": "运行失败"}),
                    )

        future.add_done_callback(_cleanup)

    def _slugify_session(self, value: str) -> str:
        cleaned = _SESSION_SAFE.sub("-", value.strip()).strip("-").lower()
        return cleaned or "novel"

    def _read_text_file(self, content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ApiError("上传的文本文件无法识别编码，请转为 UTF-8 或 GB18030。", 422, "Invalid Encoding")

    def save_uploaded_text(self, filename: str, content: bytes) -> tuple[Path, str]:
        normalized_text = self._read_text_file(content)
        safe_name = self._slugify_session(Path(filename).stem)
        upload_id = uuid4().hex[:8]
        path = self.settings.web_uploads_dir / f"{safe_name}-{upload_id}.txt"
        path.write_text(normalized_text, encoding="utf-8")
        return path, safe_name

    def list_runs(self) -> list[WebRunSummary]:
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda item: item.updated_at,
                reverse=True,
            )
            return [WebRunSummary.model_validate(item.model_dump(mode="json")) for item in runs]

    def get_run(self, run_id: str) -> WebRunDetail:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ApiError("找不到对应的运行任务。", 404, "Not Found")
            run = self._ensure_story_previews(run)
            run = self._ensure_arc_options_digest(run)
            run = self._ensure_director_plan_artifact(run)
            self._runs[run.id] = run
            return run.model_copy(deep=True)

    @staticmethod
    def _chapter_plan_status(status: str) -> str:
        normalized = status.strip().lower()
        if normalized.startswith("completed") or normalized == "skipped_existing_output":
            return "done"
        if normalized in {"running", "generating"}:
            return "writing"
        if normalized in {"awaiting_arc_selection", "analyzing"}:
            return "reviewing"
        return "planned"

    def _build_default_director_plan(self, run: WebRunDetail) -> WebDirectorPlan:
        start_chapter = run.request.start_chapter or 1
        requested_chapters = max(1, run.request.chapters or 1)
        chapter_total = max(requested_chapters, len(run.chapter_summaries))
        summary_by_chapter = {item.chapter_number: item for item in run.chapter_summaries}
        queue: list[WebDirectorPlanChapterItem] = []
        for offset in range(chapter_total):
            chapter_number = start_chapter + offset
            summary = summary_by_chapter.get(chapter_number)
            queue.append(
                WebDirectorPlanChapterItem(
                    chapter_number=chapter_number,
                    title=f"第 {chapter_number} 章" if summary else "",
                    goal=(summary.chapter_goal if summary and summary.chapter_goal else run.latest_chapter_goal or ""),
                    status=self._chapter_plan_status(summary.status) if summary else "planned",
                    notes=(
                        f"质检：{summary.quality_verdict}"
                        if summary and summary.quality_verdict
                        else ""
                    ),
                )
            )
        return WebDirectorPlan(
            session_name=run.session_name,
            updated_at=run.updated_at,
            summary=run.latest_chapter_goal or run.request.goal_hint or "",
            chapter_window_start=start_chapter,
            chapter_window_end=start_chapter + chapter_total - 1,
            notes="",
            chapter_queue=queue,
        )

    def get_director_plan(self, run_id: str) -> WebDirectorPlan:
        run = self.get_run(run_id)
        plan = self._load_json_model(self._director_plan_path(run.session_name), WebDirectorPlan)
        if isinstance(plan, WebDirectorPlan):
            return plan
        return self._build_default_director_plan(run)

    def save_director_plan(self, run_id: str, request: WebDirectorPlanUpdate) -> WebDirectorPlan:
        run = self.get_run(run_id)
        path = self._director_plan_path(run.session_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        plan = WebDirectorPlan(
            session_name=run.session_name,
            updated_at=datetime.now(timezone.utc),
            summary=request.summary.strip(),
            chapter_window_start=request.chapter_window_start,
            chapter_window_end=request.chapter_window_end,
            notes=request.notes.strip(),
            chapter_queue=request.chapter_queue,
        )
        path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        self._update_run(
            run_id,
            artifact_paths=run.artifact_paths.model_copy(update={"director_plan": str(path)}),
        )
        return plan

    async def test_runtime_connection(
        self,
        request: WebRuntimeConnectionTestRequest,
    ) -> WebRuntimeConnectionTestResult:
        run_settings = self.settings.model_copy(deep=True)
        if request.api_base_url and request.api_base_url.strip():
            run_settings.runtime_api_base_url = request.api_base_url.strip()
        if request.api_key and request.api_key.strip():
            run_settings.runtime_api_key = request.api_key.strip()
        if request.wire_api:
            run_settings.runtime_wire_api = request.wire_api

        model = (request.model or self.get_runtime_config().quality_model).strip() or self.get_runtime_config().quality_model
        llm_service = LiteLLMService(run_settings)
        try:
            response = await llm_service.complete_text(
                model=model,
                messages=[
                    {"role": "system", "content": "你只需回复四个字：连接成功。"},
                    {"role": "user", "content": "请回复连接成功。"},
                ],
                temperature=0.0,
                max_tokens=16,
                operation="runtime_connection_test",
            )
        except Exception as exc:
            raise ApiError(f"连接测试失败：{exc}", 502, "Connection Test Failed") from exc

        preview = response.text.strip() or "连接成功"
        return WebRuntimeConnectionTestResult(
            ok=True,
            model=model,
            wire_api=run_settings.runtime_wire_api,
            response_preview=preview[:200],
        )

    def get_run_source_text(self, run_id: str) -> WebRunSourceText:
        run = self.get_run(run_id)
        if not run.input_path:
            raise ApiError("当前任务没有可读取的原文文件。", 404, "Not Found")
        input_path = Path(run.input_path)
        if not input_path.exists():
            raise ApiError("找不到当前任务对应的原文文件。", 404, "Not Found")
        text_content = input_path.read_text(encoding="utf-8")
        return WebRunSourceText(
            input_filename=run.input_filename,
            text_content=text_content,
            character_count=len(text_content),
        )

    def list_benchmarks(self) -> list[WebBenchmarkSummary]:
        items: list[WebBenchmarkSummary] = []
        for path in self._benchmark_report_files():
            try:
                report = BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append(
                WebBenchmarkSummary(
                    dataset_name=report.dataset_name,
                    case_name=report.case_name,
                    target_chapter_number=report.target_chapter_number,
                    prefix_chapter_count=report.prefix_chapter_count,
                    winner=report.pairwise.winner,
                    confidence=report.pairwise.confidence,
                    report_json_path=report.report_json_path,
                    report_markdown_path=report.report_markdown_path,
                )
            )
        return items

    def get_benchmark(self, dataset_name: str, case_name: str) -> WebBenchmarkDetail:
        path = (
            self.settings.benchmarks_dir
            / dataset_name
            / "cases"
            / case_name
            / "report"
            / "benchmark_report.json"
        )
        if not path.exists():
            raise ApiError("找不到对应的 benchmark 报告。", 404, "Not Found")
        report = BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))
        return WebBenchmarkDetail(
            dataset_name=report.dataset_name,
            case_name=report.case_name,
            target_chapter_number=report.target_chapter_number,
            prefix_chapter_count=report.prefix_chapter_count,
            winner=report.pairwise.winner,
            confidence=report.pairwise.confidence,
            report_json_path=report.report_json_path,
            report_markdown_path=report.report_markdown_path,
            system_output_path=report.system_output_path,
            baseline_output_path=report.baseline_output_path,
            reference_path=report.reference_path,
            pairwise_reasoning=report.pairwise.reasoning,
            system_score=report.system_report.score.overall,
            baseline_score=report.baseline_report.score.overall,
            system_summary=report.system_report.score.summary,
            baseline_summary=report.baseline_report.score.summary,
            system_strengths=report.system_report.score.strengths,
            baseline_strengths=report.baseline_report.score.strengths,
            system_weaknesses=report.system_report.score.weaknesses,
            baseline_weaknesses=report.baseline_report.score.weaknesses,
            system_elapsed_seconds=report.system_report.elapsed_seconds,
            baseline_elapsed_seconds=report.baseline_report.elapsed_seconds,
            total_cost_usd=report.total_usage.total_cost_usd,
            total_tokens=report.total_usage.total_tokens,
        )

    def get_runtime_config(self) -> WebRuntimeConfig:
        options = list(
            dict.fromkeys(
                [
                    self.settings.models.style_model,
                    self.settings.models.plot_model,
                    self.settings.models.draft_model,
                    self.settings.models.quality_model,
                    self.settings.models.lightrag_model_name,
                    *[
                        item.strip()
                        for item in getattr(self.settings, "web_model_options", "").split(",")
                        if item.strip()
                    ],
                ]
            )
        )
        return WebRuntimeConfig(
            style_model=self.settings.models.style_model,
            plot_model=self.settings.models.plot_model,
            draft_model=self.settings.models.draft_model,
            quality_model=self.settings.models.quality_model,
            lightrag_model_name=self.settings.models.lightrag_model_name,
            api_base_url=self.settings.models.deepseek_base_url or None,
            wire_api=self.settings.runtime_wire_api,
            model_options=options,
        )

    @staticmethod
    def _get_builtin_example(example_id: str) -> BuiltInExample:
        example = BUILT_IN_EXAMPLES.get(example_id)
        if example is None:
            raise ApiError("找不到对应的示例样本。", 404, "Not Found")
        return example

    def _example_trial_limit_note(self) -> str | None:
        limit = max(0, self.settings.web_example_runs_per_ip)
        if limit <= 0:
            return None
        window_seconds = max(1, self.settings.web_example_window_seconds)
        if window_seconds % 3600 == 0:
            window_label = f"{window_seconds // 3600} 小时"
        elif window_seconds % 60 == 0:
            window_label = f"{window_seconds // 60} 分钟"
        else:
            window_label = f"{window_seconds} 秒"
        return (
            f"使用部署默认 Key 的“按当前配置重跑”默认按单 IP 限流：{window_label} 内最多 {limit} 次。"
            "快速试看不消耗额度；如果你填写了自己的 endpoint / Key，重跑也不受这个试用额度限制。"
        )

    def _example_text(self, example_id: str) -> str:
        example = self._get_builtin_example(example_id)
        source_path = self.settings.input_dir / example.input_filename
        if source_path.exists():
            return source_path.read_text(encoding="utf-8")
        return example.text_content

    def _example_input_path_for_preview(self, example: BuiltInExample, manifest_input_path: str | None) -> Path:
        if manifest_input_path:
            candidate = Path(manifest_input_path)
            if candidate.exists():
                return candidate
        source_path = self.settings.input_dir / example.input_filename
        if source_path.exists():
            return source_path
        preview_path = self.settings.web_uploads_dir / f"{Path(example.input_filename).stem}-preview.txt"
        if not preview_path.exists():
            preview_path.write_text(example.text_content, encoding="utf-8")
        return preview_path

    def _build_example_summary(self, example: BuiltInExample) -> WebExampleSummary:
        return WebExampleSummary(
            id=example.id,
            title=example.title,
            description=example.description,
            input_filename=example.input_filename,
            recommended_goal_hint=example.recommended_goal_hint,
            source_excerpt=self._excerpt_text(
                self._example_text(example.id),
                take="head",
                max_blocks=3,
                max_chars=220,
            ),
            usage_hint=example.usage_hint,
            trial_limit_note=self._example_trial_limit_note(),
        )

    def list_examples(self) -> list[WebExampleSummary]:
        return [self._build_example_summary(example) for example in BUILT_IN_EXAMPLES.values()]

    def get_example(self, example_id: str) -> WebExampleDetail:
        example = self._get_builtin_example(example_id)
        summary = self._build_example_summary(example)
        return WebExampleDetail(
            **summary.model_dump(),
            text_content=self._example_text(example_id),
        )

    @staticmethod
    def _excerpt_text(
        text: str,
        *,
        take: str = "head",
        max_blocks: int = 4,
        max_chars: int = 680,
    ) -> str:
        normalized = re.sub(r"(?m)^#{1,6}\s*", "", text)
        normalized = re.sub(r"(?m)^\s*---\s*$", "", normalized)
        blocks = [
            re.sub(r"\s+", " ", block).strip()
            for block in re.split(r"\n\s*\n", normalized)
            if block.strip()
        ]
        if not blocks:
            return "-"
        selected = blocks[:max_blocks] if take == "head" else blocks[-max_blocks:]
        excerpt = "\n\n".join(selected)
        if len(excerpt) <= max_chars:
            return excerpt
        trimmed = excerpt[: max_chars - 1].rstrip()
        if " " in trimmed:
            trimmed = trimmed.rsplit(" ", 1)[0]
        return f"{trimmed}…"

    def get_public_showcase(self) -> WebPublicShowcase | None:
        example = self._get_builtin_example("hongloumeng_120")
        sample_path = self.settings.input_dir / example.input_filename
        showcase = example.showcase
        if showcase is None:
            return None
        showcase_session_name = showcase.artifact_session_name or example.preview_session_name or ""
        chapter_number = showcase.chapter_number
        output_path = self.settings.output_dir / showcase_session_name / f"chapter_{chapter_number}.md"
        evaluation_path = (
            self.settings.sessions_dir
            / showcase_session_name
            / f"chapter_{chapter_number}_evaluation.json"
        )
        brief_path = (
            self.settings.sessions_dir
            / showcase_session_name
            / f"chapter_{chapter_number}_brief.json"
        )

        source_text = self._example_text(example.id)
        if output_path.exists():
            output_text = output_path.read_text(encoding="utf-8")
        else:
            output_text = showcase.output_excerpt
        evaluation = self._load_json_model(evaluation_path, ChapterEvaluation)
        brief = self._load_json_model(brief_path, ChapterBrief)
        score = evaluation.score if evaluation else showcase.scores
        source_stem = sample_path.stem if sample_path.exists() else Path(example.input_filename).stem

        return WebPublicShowcase(
            title=showcase.title,
            source_label=showcase.source_label or f"{source_stem} · 原著断点",
            source_excerpt=self._excerpt_text(source_text, take="tail", max_blocks=4, max_chars=620),
            output_label=showcase.output_label,
            output_excerpt=self._excerpt_text(output_text, take="head", max_blocks=6, max_chars=920),
            chapter_goal=brief.chapter_goal if brief else showcase.chapter_goal,
            evaluation_summary=evaluation.summary if evaluation else showcase.evaluation_summary,
            continuity_score=score.continuity_score if score else None,
            character_score=score.character_score if score else None,
            world_consistency_score=score.world_consistency_score if score else None,
            novelty_score=score.novelty_score if score else None,
            arc_progress_score=score.arc_progress_score if score else None,
        )

    def load_example_preview_run(self, *, example_id: str) -> WebRunSummary:
        example = self._get_builtin_example(example_id)
        if not example.preview_session_name:
            raise ApiError("当前示例没有可复用的预计算结果。", 404, "Not Found")

        manifest_path = self.settings.sessions_dir / example.preview_session_name / "run_manifest.json"
        manifest = self._load_json_model(manifest_path, PipelineRunResult)
        if not isinstance(manifest, PipelineRunResult):
            raise ApiError("当前示例的预计算结果缺失，请先重新生成。", 404, "Not Found")

        preview_input_path = self._example_input_path_for_preview(example, manifest.input_path)
        run_id = f"example-preview-{example_id}"
        existing = self._runs.get(run_id)
        chapter_count = max(1, len(manifest.chapters) or 1)
        created_at = existing.created_at if existing else (manifest.started_at or datetime.now(timezone.utc))
        preview_request = WebRunRequest(
            session_name=manifest.session_name,
            chapters=chapter_count,
            start_chapter=manifest.chapters[0].chapter_number if manifest.chapters else 1,
            goal_hint=example.recommended_goal_hint,
            use_existing_index=True,
        )
        run = WebRunDetail(
            id=run_id,
            status="completed",
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
            session_name=manifest.session_name,
            input_filename=example.input_filename,
            request=preview_request,
            progress=WebRunProgress(
                total_steps=1 + chapter_count * 4,
                completed_steps=1 + chapter_count * 4,
                message="已加载预计算样例结果",
            ),
            input_path=str(preview_input_path),
            log_messages=[
                "已加载预计算样例结果",
                "当前展示直接复用样例已保存的分析、规划和续写产物，不消耗当前 endpoint / Key。",
            ],
        )
        with self._lock:
            self._runs[run_id] = run
            self._persist(run)

        self._populate_outputs(run_id, manifest)
        detail = self.get_run(run_id)
        self._update_run(
            run_id,
            progress=detail.progress.model_copy(update={"message": "已加载预计算样例结果"}),
            log_messages=[
                "已加载预计算样例结果",
                "当前展示直接复用样例已保存的分析、规划和续写产物，不消耗当前 endpoint / Key。",
            ],
        )
        return WebRunSummary.model_validate(self.get_run(run_id).model_dump(mode="json"))

    def start_example_run(
        self,
        *,
        example_id: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ) -> WebRunSummary:
        example = self._get_builtin_example(example_id)

        saved_path, suggested_name = self.save_uploaded_text(
            example.input_filename,
            self._example_text(example_id).encode("utf-8"),
        )
        session_name = request.session_name
        if not session_name and not example.preview_session_name:
            session_name = f"{suggested_name}-demo"
        request_payload = request.model_copy(
            update={
                "session_name": session_name,
                "goal_hint": request.goal_hint or self._example_goal_hint(example_id),
            }
        )
        return self.start_run(
            input_path=saved_path,
            input_filename=example.input_filename,
            request=request_payload,
            runtime_api_override=runtime_api_override,
        )

    @staticmethod
    def _example_goal_hint(example_id: str) -> str | None:
        example = BUILT_IN_EXAMPLES.get(example_id)
        if example is not None:
            return example.recommended_goal_hint
        return None

    def _settings_for_request(
        self,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ) -> AppSettings:
        run_settings = self.settings.model_copy(deep=True)
        model_updates = {
            "style_model": request.style_model,
            "plot_model": request.plot_model,
            "draft_model": request.draft_model,
            "quality_model": request.quality_model,
            "lightrag_model_name": request.lightrag_model_name,
        }
        for field_name, field_value in model_updates.items():
            if field_value and field_value.strip():
                setattr(run_settings.models, field_name, field_value.strip())
        if runtime_api_override is not None:
            if runtime_api_override.api_base_url and runtime_api_override.api_base_url.strip():
                run_settings.runtime_api_base_url = runtime_api_override.api_base_url.strip()
            if runtime_api_override.api_key and runtime_api_override.api_key.strip():
                run_settings.runtime_api_key = runtime_api_override.api_key.strip()
            if runtime_api_override.wire_api:
                run_settings.runtime_wire_api = runtime_api_override.wire_api
        return run_settings

    def start_run(
        self,
        *,
        input_path: Path,
        input_filename: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ) -> WebRunSummary:
        run_id = uuid4().hex
        created_at = datetime.now(timezone.utc)
        session_name = request.session_name or f"{self._slugify_session(Path(input_filename).stem)}-{created_at.strftime('%Y%m%d-%H%M%S')}"
        run = WebRunDetail(
            id=run_id,
            status="queued",
            created_at=created_at,
            updated_at=created_at,
            session_name=session_name,
            input_filename=input_filename,
            request=request,
            progress=WebRunProgress(total_steps=1 + request.chapters * 4, completed_steps=0),
            input_path=str(input_path),
            log_messages=["任务已创建，等待执行"],
        )
        with self._lock:
            self._runs[run_id] = run
            self._persist(run)

        run_settings = self._settings_for_request(request, runtime_api_override)
        try:
            self._schedule_run(run_id, run_settings)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=f"任务调度失败：{exc}",
                progress=run.progress.model_copy(update={"message": "运行失败"}),
            )
        return WebRunSummary.model_validate(run.model_dump(mode="json"))

    def start_revival_analysis_run(
        self,
        *,
        input_path: Path,
        input_filename: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ) -> WebRunSummary:
        run_id = uuid4().hex
        created_at = datetime.now(timezone.utc)
        session_name = request.session_name or f"{self._slugify_session(Path(input_filename).stem)}-{created_at.strftime('%Y%m%d-%H%M%S')}"
        run = WebRunDetail(
            id=run_id,
            status="queued",
            created_at=created_at,
            updated_at=created_at,
            session_name=session_name,
            input_filename=input_filename,
            request=request.model_copy(update={"chapters": 1}),
            progress=WebRunProgress(total_steps=4, completed_steps=0),
            input_path=str(input_path),
            log_messages=["复活分析任务已创建，等待执行"],
        )
        with self._lock:
            self._runs[run_id] = run
            self._persist(run)

        run_settings = self._settings_for_request(run.request, runtime_api_override)
        try:
            self._schedule_revival_analysis(run_id, run_settings)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=f"任务调度失败：{exc}",
                progress=run.progress.model_copy(update={"message": "运行失败"}),
            )
        return WebRunSummary.model_validate(run.model_dump(mode="json"))

    def _schedule_revival_analysis(self, run_id: str, run_settings: AppSettings | None = None) -> None:
        loop = self._ensure_async_runtime()
        future = asyncio.run_coroutine_threadsafe(
            self._run_revival_analysis_async(run_id, run_settings),
            loop,
        )
        with self._runtime_lock:
            self._async_futures[run_id] = future

        def _cleanup(completed: ConcurrentFuture[None]) -> None:
            with self._runtime_lock:
                self._async_futures.pop(run_id, None)
            try:
                completed.result()
            except Exception as exc:
                current = self._runs.get(run_id)
                if current and current.status in {"queued", "running", "analyzing"}:
                    self._update_run(
                        run_id,
                        status="failed",
                        error_message=str(exc),
                        progress=current.progress.model_copy(update={"message": "运行失败"}),
                    )

        future.add_done_callback(_cleanup)

    def _schedule_revival_generation(self, run_id: str, run_settings: AppSettings | None = None) -> None:
        loop = self._ensure_async_runtime()
        future = asyncio.run_coroutine_threadsafe(
            self._run_revival_generation_async(run_id, run_settings),
            loop,
        )
        with self._runtime_lock:
            self._async_futures[run_id] = future

        def _cleanup(completed: ConcurrentFuture[None]) -> None:
            with self._runtime_lock:
                self._async_futures.pop(run_id, None)
            try:
                completed.result()
            except Exception as exc:
                current = self._runs.get(run_id)
                if current and current.status in {"queued", "running", "generating"}:
                    self._update_run(
                        run_id,
                        status="failed",
                        error_message=str(exc),
                        progress=current.progress.model_copy(update={"message": "运行失败"}),
                    )

        future.add_done_callback(_cleanup)

    def _update_run(self, run_id: str, **changes) -> None:
        with self._lock:
            current = self._runs[run_id]
            updated = current.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
            self._runs[run_id] = updated
            self._persist(updated)

    def _append_log(self, run_id: str, message: str) -> None:
        with self._lock:
            current = self._runs[run_id]
            progress = current.progress.model_copy(
                update={
                    "completed_steps": min(current.progress.total_steps, current.progress.completed_steps + 1),
                    "message": message,
                }
            )
            logs = [*current.log_messages, message][-50:]
            updated = current.model_copy(
                update={
                    "progress": progress,
                    "log_messages": logs,
                    "status": "running",
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            self._runs[run_id] = updated
            self._persist(updated)

    @staticmethod
    def _chapter_summaries(manifest: PipelineRunResult) -> list[WebChapterSummary]:
        return [
            WebChapterSummary(
                chapter_number=item.chapter_number,
                status=item.status,
                chapter_goal=item.chapter_goal,
                output_path=item.output_path,
                quality_verdict=item.quality_report.verdict if item.quality_report else None,
                quality_score=item.quality_report.score if item.quality_report else None,
                consistency_passed=item.consistency_report.passed if item.consistency_report else None,
                elapsed_seconds=item.elapsed_seconds,
            )
            for item in manifest.chapters
        ]

    @staticmethod
    def _load_json_model(path: Path, model_cls):
        if not path.exists():
            return None
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))

    def _populate_outputs(self, run_id: str, result: PipelineRunResult) -> None:
        current_run = self.get_run(run_id)
        snapshot_path = Path(result.stage1_snapshot_path)
        session_dir = self.settings.sessions_dir / result.session_name
        snapshot = self._load_json_model(snapshot_path, ExtractionSnapshot)
        world_model = self._load_json_model(session_dir / "world_model.json", WorldModel)
        lorebook = self._load_json_model(session_dir / "lorebook.json", LorebookBundle)
        work_skill = self._load_json_model(session_dir / "work_skill.json", WorkSkill)
        arc_options = self._load_json_model(session_dir / "arc_options.json", DirectorArcOptions)
        selected_arc = self._load_json_model(session_dir / "selected_arc.json", SelectedArc)
        revival_diagnosis = self._load_json_model(session_dir / "revival_diagnosis.json", RevivalDiagnosis)
        blind_challenge = self._load_json_model(session_dir / "blind_challenge.json", BlindChallenge)
        selected_references_bundle = self._load_json_model(
            session_dir / "selected_references.json",
            _ReferenceProfileBundle,
        )
        arc_outlines = [
            ArcOutline.model_validate_json(path.read_text(encoding="utf-8")).model_dump(mode="json")
            for path in sorted((session_dir / "arcs").glob("*.json"))
        ]
        manifest_path = self.settings.sessions_dir / result.session_name / "run_manifest.json"
        manifest = None
        if manifest_path.exists():
            try:
                manifest = PipelineRunResult.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
            except Exception:
                manifest = None
        latest_output_path = next(
            (
                Path(item.output_path)
                for item in reversed(result.chapters)
                if item.output_path
            ),
            None,
        )
        latest_output_preview = None
        if latest_output_path is not None and latest_output_path.exists():
            latest_output_preview = latest_output_path.read_text(encoding="utf-8")[:6000]

        latest_quality = None
        latest_consistency = None
        latest_chapter_goal = None
        latest_source_preview_label = None
        latest_source_preview = None
        latest_skeleton_path = None
        latest_brief = None
        latest_brief_path = None
        latest_evaluation = None
        latest_evaluation_path = None
        latest_skeleton_candidate_paths: list[str] = []
        latest_draft_candidate_paths: list[str] = []
        latest_draft_path = None
        latest_output_string = str(latest_output_path) if latest_output_path is not None else None
        chapter_source = manifest.chapters if manifest else result.chapters
        if chapter_source:
            last = chapter_source[-1]
            latest_quality = last.quality_report.model_dump(mode="json") if last.quality_report else None
            latest_consistency = (
                last.consistency_report.model_dump(mode="json")
                if last.consistency_report
                else None
            )
            latest_chapter_goal = last.chapter_goal
            latest_skeleton_path = last.skeleton_path
            latest_draft_path = last.draft_path
            latest_brief_path = session_dir / f"chapter_{last.chapter_number}_brief.json"
            latest_evaluation_path = session_dir / f"chapter_{last.chapter_number}_evaluation.json"
            latest_brief_model = self._load_json_model(latest_brief_path, ChapterBrief)
            latest_evaluation_model = self._load_json_model(
                latest_evaluation_path,
                ChapterEvaluation,
            )
            latest_skeleton_candidate_paths = [
                str(path)
                for path in sorted(
                    (session_dir / "candidates").glob(
                        f"chapter_{last.chapter_number}_skeleton_candidate_*.json"
                    )
                )
            ]
            latest_draft_candidate_paths = [
                str(path)
                for path in sorted(
                    (session_dir / "candidates").glob(
                        f"chapter_{last.chapter_number}_draft_candidate_*.md"
                    )
                )
            ]
            latest_brief = (
                latest_brief_model.model_dump(mode="json") if latest_brief_model else None
            )
            latest_evaluation = (
                latest_evaluation_model.model_dump(mode="json")
                if latest_evaluation_model
                else None
            )
            previous_output_path = next(
                (
                    Path(item.output_path)
                    for item in reversed(chapter_source[:-1])
                    if getattr(item, "output_path", None)
                ),
                None,
            )
            if previous_output_path is not None and previous_output_path.exists():
                latest_source_preview_label = "上文衔接"
                latest_source_preview = self._excerpt_text(
                    previous_output_path.read_text(encoding="utf-8"),
                    take="tail",
                    max_blocks=5,
                    max_chars=1600,
                )
            elif current_run.input_path:
                input_path = Path(current_run.input_path)
                if input_path.exists():
                    latest_source_preview_label = "原文断点"
                    latest_source_preview = self._excerpt_text(
                        input_path.read_text(encoding="utf-8"),
                        take="tail",
                        max_blocks=5,
                        max_chars=1600,
                    )

        unresolved_threads_path = self.settings.sessions_dir / result.session_name / "unresolved_threads.json"
        unresolved_threads: list[StoryThread] = []
        if unresolved_threads_path.exists():
            payload = json.loads(unresolved_threads_path.read_text(encoding="utf-8"))
            unresolved_threads = [
                StoryThread.model_validate(item) for item in payload.get("threads", [])
            ]

        story_graph_path = self.settings.sessions_dir / result.session_name / "story_graph.mmd"
        chapter_summaries = self._chapter_summaries(manifest or result)
        run_status = getattr(result, "status", "completed")
        if run_status not in {"completed", "completed_with_warnings", "failed"}:
            run_status = "completed"
        latest_summary = chapter_summaries[-1] if chapter_summaries else None
        metrics = WebRunMetrics(
            total_calls=(manifest.total_usage.calls if manifest else result.total_usage.calls),
            total_tokens=(manifest.total_usage.total_tokens if manifest else result.total_usage.total_tokens),
            total_cost_usd=(
                manifest.total_usage.total_cost_usd if manifest else result.total_usage.total_cost_usd
            ),
            chapter_count=len(chapter_summaries),
            completed_chapters=len(
                [
                    item
                    for item in chapter_summaries
                    if item.status.startswith("completed") or item.status == "skipped_existing_output"
                ]
            ),
            latest_chapter_number=(latest_summary.chapter_number if latest_summary else None),
            latest_chapter_status=(latest_summary.status if latest_summary else None),
            latest_elapsed_seconds=(latest_summary.elapsed_seconds if latest_summary else None),
            latest_quality_score=(latest_summary.quality_score if latest_summary else None),
            latest_quality_verdict=(latest_summary.quality_verdict if latest_summary else None),
            consistency_passed=(latest_summary.consistency_passed if latest_summary else None),
        )

        self._update_run(
            run_id,
            status=run_status,
            progress=current_run.progress.model_copy(
                update={
                    "completed_steps": current_run.progress.total_steps,
                    "message": "运行完成",
                }
            ),
            manifest_path=str(manifest_path),
            stage1_snapshot_path=result.stage1_snapshot_path,
            output_paths=[item.output_path for item in result.chapters if item.output_path],
            style_profile=snapshot.style_profile.model_dump(mode="json") if snapshot else None,
            story_state=snapshot.story_state.model_dump(mode="json") if snapshot else None,
            world_model=world_model.model_dump(mode="json") if world_model else None,
            lorebook=lorebook.model_dump(mode="json") if lorebook else None,
            work_skill=work_skill,
            arc_options=arc_options,
            arc_options_digest=self._arc_options_digest(arc_options) if arc_options else None,
            selected_arc=selected_arc,
            revival_diagnosis=revival_diagnosis,
            blind_challenge=WebBlindChallenge.from_internal(blind_challenge),
            selected_references=[
                item.model_dump(mode="json")
                for item in (selected_references_bundle.profiles if selected_references_bundle else [])
            ],
            arc_outlines=arc_outlines,
            latest_chapter_brief=latest_brief,
            latest_chapter_evaluation=latest_evaluation,
            latest_skeleton_candidate_paths=latest_skeleton_candidate_paths,
            latest_draft_candidate_paths=latest_draft_candidate_paths,
            latest_source_preview_label=latest_source_preview_label,
            latest_source_preview=latest_source_preview,
            latest_output_preview=latest_output_preview,
            latest_quality_report=latest_quality,
            latest_consistency_report=latest_consistency,
            latest_chapter_goal=latest_chapter_goal,
            unresolved_threads=unresolved_threads,
            artifact_paths=WebRunArtifactPaths(
                manifest=str(manifest_path),
                stage1_snapshot=result.stage1_snapshot_path,
                world_model=str(session_dir / "world_model.json") if (session_dir / "world_model.json").exists() else None,
                lorebook=str(session_dir / "lorebook.json") if (session_dir / "lorebook.json").exists() else None,
                selected_references=(
                    str(session_dir / "selected_references.json")
                    if (session_dir / "selected_references.json").exists()
                    else None
                ),
                revival_workspace=(
                    str(session_dir / "revival_workspace.json")
                    if (session_dir / "revival_workspace.json").exists()
                    else None
                ),
                work_skill=str(session_dir / "work_skill.json") if (session_dir / "work_skill.json").exists() else None,
                arc_options=str(session_dir / "arc_options.json") if (session_dir / "arc_options.json").exists() else None,
                selected_arc=str(session_dir / "selected_arc.json") if (session_dir / "selected_arc.json").exists() else None,
                revival_diagnosis=(
                    str(session_dir / "revival_diagnosis.json")
                    if (session_dir / "revival_diagnosis.json").exists()
                    else None
                ),
                blind_challenge=(
                    str(session_dir / "blind_challenge.json")
                    if (session_dir / "blind_challenge.json").exists()
                    else None
                ),
                latest_skeleton=latest_skeleton_path,
                latest_chapter_brief=str(latest_brief_path) if latest_brief_path and latest_brief_path.exists() else None,
                latest_chapter_evaluation=(
                    str(latest_evaluation_path)
                    if latest_evaluation_path and latest_evaluation_path.exists()
                    else None
                ),
                latest_draft=latest_draft_path,
                latest_output=latest_output_string,
                story_graph=str(story_graph_path) if story_graph_path.exists() else None,
            ),
            metrics=metrics,
            chapter_summaries=chapter_summaries,
        )

    def _populate_revival_analysis_outputs(
        self,
        run_id: str,
        result: RevivalAnalysisResult,
    ) -> None:
        session_dir = self.settings.sessions_dir / result.session_name
        snapshot_path = Path(result.stage1_snapshot_path)
        snapshot = self._load_json_model(snapshot_path, ExtractionSnapshot)
        world_model = self._load_json_model(session_dir / "world_model.json", WorldModel)
        lorebook = self._load_json_model(session_dir / "lorebook.json", LorebookBundle)
        work_skill = self._load_json_model(session_dir / "work_skill.json", WorkSkill)
        arc_options = self._load_json_model(session_dir / "arc_options.json", DirectorArcOptions)
        selected_references_bundle = self._load_json_model(
            session_dir / "selected_references.json",
            _ReferenceProfileBundle,
        )
        self._update_run(
            run_id,
            status="awaiting_arc_selection",
            progress=self.get_run(run_id).progress.model_copy(
                update={
                    "completed_steps": self.get_run(run_id).progress.total_steps,
                    "message": "请选择人物走向",
                }
            ),
            stage1_snapshot_path=result.stage1_snapshot_path,
            style_profile=snapshot.style_profile.model_dump(mode="json") if snapshot else None,
            story_state=snapshot.story_state.model_dump(mode="json") if snapshot else None,
            world_model=world_model.model_dump(mode="json") if world_model else None,
            lorebook=lorebook.model_dump(mode="json") if lorebook else None,
            work_skill=work_skill,
            arc_options=arc_options,
            arc_options_digest=self._arc_options_digest(arc_options) if arc_options else None,
            selected_references=[
                item.model_dump(mode="json")
                for item in (selected_references_bundle.profiles if selected_references_bundle else [])
            ],
            artifact_paths=WebRunArtifactPaths(
                stage1_snapshot=result.stage1_snapshot_path,
                world_model=str(session_dir / "world_model.json") if (session_dir / "world_model.json").exists() else None,
                lorebook=str(session_dir / "lorebook.json") if (session_dir / "lorebook.json").exists() else None,
                selected_references=(
                    str(session_dir / "selected_references.json")
                    if (session_dir / "selected_references.json").exists()
                    else None
                ),
                revival_workspace=(
                    str(session_dir / "revival_workspace.json")
                    if (session_dir / "revival_workspace.json").exists()
                    else None
                ),
                work_skill=str(session_dir / "work_skill.json") if (session_dir / "work_skill.json").exists() else None,
                arc_options=str(session_dir / "arc_options.json") if (session_dir / "arc_options.json").exists() else None,
            ),
            metrics=WebRunMetrics(
                total_calls=result.total_usage.calls,
                total_tokens=result.total_usage.total_tokens,
                total_cost_usd=result.total_usage.total_cost_usd,
            ),
        )

    def select_revival_arc(
        self,
        run_id: str,
        request: WebArcSelectionRequest,
    ) -> WebRunSummary:
        current = self.get_run(run_id)
        if current.status == "generating":
            selected_arc = self._load_json_model(
                self.settings.sessions_dir / current.session_name / "selected_arc.json",
                SelectedArc,
            )
            if isinstance(selected_arc, SelectedArc) and selected_arc.selected_option_id == request.selected_option_id:
                return WebRunSummary.model_validate(current.model_dump(mode="json"))
            raise ApiError("章节已开始生成，不能改选人物走向。", 409, "Conflict")
        if current.status not in {"awaiting_arc_selection", "failed"}:
            raise ApiError("当前任务还不能选择人物走向。", 409, "Conflict")

        session_dir = self.settings.sessions_dir / current.session_name
        arc_options = self._load_json_model(session_dir / "arc_options.json", DirectorArcOptions)
        if not isinstance(arc_options, DirectorArcOptions):
            raise ApiError("当前任务没有可选择的人物走向，请先重新分析。", 404, "Not Found")
        digest = self._arc_options_digest(arc_options)
        if request.arc_options_digest and request.arc_options_digest != digest:
            raise ApiError("人物走向选项已过期，请重新分析。", 409, "Conflict")
        selected_option = next(
            (option for option in arc_options.options if option.id == request.selected_option_id),
            None,
        )
        if selected_option is None:
            raise ApiError("找不到对应的人物走向。", 422, "Invalid Input")

        selected_arc = SelectedArc(
            selected_option_id=selected_option.id,
            selected_at=datetime.now(timezone.utc),
            arc_options_digest=digest,
            user_note=request.user_note.strip(),
            locked_constraints=[
                *selected_option.must_happen,
                *selected_option.must_not_break,
            ],
        )
        selected_arc_path = session_dir / "selected_arc.json"
        selected_arc_path.write_text(selected_arc.model_dump_json(indent=2), encoding="utf-8")
        updated = current.model_copy(
            update={
                "status": "generating",
                "selected_arc": selected_arc,
                "artifact_paths": current.artifact_paths.model_copy(
                    update={"selected_arc": str(selected_arc_path)}
                ),
                "progress": current.progress.model_copy(
                    update={"completed_steps": 0, "message": "已选择人物走向，开始生成章节"}
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        with self._lock:
            self._runs[run_id] = updated
            self._persist(updated)

        run_settings = self._settings_for_request(updated.request)
        try:
            self._schedule_revival_generation(run_id, run_settings)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=f"任务调度失败：{exc}",
                progress=updated.progress.model_copy(update={"message": "运行失败"}),
            )
        return WebRunSummary.model_validate(updated.model_dump(mode="json"))

    def save_blind_challenge_rating(
        self,
        run_id: str,
        request: WebBlindChallengeRatingRequest,
    ) -> WebRunDetail:
        current = self.get_run(run_id)
        challenge_path = self.settings.sessions_dir / current.session_name / "blind_challenge.json"
        challenge = self._load_json_model(challenge_path, BlindChallenge)
        if not isinstance(challenge, BlindChallenge):
            raise ApiError("当前任务还没有可评分的盲测片段。", 404, "Not Found")
        updated_challenge = challenge.model_copy(
            update={
                "ratings": BlindChallengeRating(
                    voice_match_score=request.voice_match_score,
                    rhythm_match_score=request.rhythm_match_score,
                    character_voice_score=request.character_voice_score,
                    notes=request.notes.strip(),
                ),
                "rated_at": datetime.now(timezone.utc),
                "notes": request.notes.strip(),
            }
        )
        challenge_path.write_text(updated_challenge.model_dump_json(indent=2), encoding="utf-8")
        updated = current.model_copy(
            update={
                "blind_challenge": WebBlindChallenge.from_internal(updated_challenge),
                "artifact_paths": current.artifact_paths.model_copy(
                    update={"blind_challenge": str(challenge_path)}
                ),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        with self._lock:
            self._runs[run_id] = updated
            self._persist(updated)
        return updated

    async def _run_pipeline_async(
        self,
        run_id: str,
        run_settings: AppSettings | None = None,
    ) -> None:
        current = self.get_run(run_id)
        orchestrator = TaiJianOrchestrator(run_settings or self._settings_for_request(current.request))

        try:
            self._append_log(run_id, "任务开始执行")
            result: PipelineRunResult = await orchestrator.run(
                input_path=Path(current.input_path or ""),
                chapters=current.request.chapters,
                session_name=current.session_name,
                goal_hint=current.request.goal_hint,
                planning_mode=current.request.planning_mode,
                new_character_budget=current.request.new_character_budget,
                new_location_budget=current.request.new_location_budget,
                new_faction_budget=current.request.new_faction_budget,
                skeleton_candidates=current.request.skeleton_candidates,
                draft_candidates=current.request.draft_candidates,
                use_existing_index=current.request.use_existing_index,
                overwrite=current.request.overwrite,
                start_chapter=current.request.start_chapter,
                progress_callback=lambda message: self._append_log(run_id, message),
            )
            self._populate_outputs(run_id, result)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                progress=self.get_run(run_id).progress.model_copy(update={"message": "运行失败"}),
            )

    async def _run_revival_analysis_async(
        self,
        run_id: str,
        run_settings: AppSettings | None = None,
    ) -> None:
        current = self.get_run(run_id)
        orchestrator = TaiJianOrchestrator(run_settings or self._settings_for_request(current.request))

        try:
            self._update_run(
                run_id,
                status="analyzing",
                progress=current.progress.model_copy(
                    update={"completed_steps": 1, "message": "正在分析原著"}
                ),
            )
            result = await orchestrator.prepare_revival_analysis(
                input_path=Path(current.input_path or ""),
                session_name=current.session_name,
                planning_mode=current.request.planning_mode,
                new_character_budget=current.request.new_character_budget,
                new_location_budget=current.request.new_location_budget,
                new_faction_budget=current.request.new_faction_budget,
                use_existing_index=current.request.use_existing_index,
                start_chapter=current.request.start_chapter,
                progress_callback=lambda message: self._append_log(run_id, message),
            )
            self._populate_revival_analysis_outputs(run_id, result)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                progress=self.get_run(run_id).progress.model_copy(update={"message": "运行失败"}),
            )

    async def _run_revival_generation_async(
        self,
        run_id: str,
        run_settings: AppSettings | None = None,
    ) -> None:
        current = self.get_run(run_id)
        orchestrator = TaiJianOrchestrator(run_settings or self._settings_for_request(current.request))

        try:
            self._update_run(
                run_id,
                status="generating",
                progress=current.progress.model_copy(
                    update={"completed_steps": 1, "message": "正在按所选走向生成章节"}
                ),
            )
            result = await orchestrator.run_revival_generation(
                input_path=Path(current.input_path or ""),
                session_name=current.session_name,
                goal_hint=current.request.goal_hint,
                planning_mode=current.request.planning_mode,
                new_character_budget=current.request.new_character_budget,
                new_location_budget=current.request.new_location_budget,
                new_faction_budget=current.request.new_faction_budget,
                skeleton_candidates=current.request.skeleton_candidates,
                draft_candidates=current.request.draft_candidates,
                use_existing_index=True,
                overwrite=current.request.overwrite,
                start_chapter=current.request.start_chapter,
                progress_callback=lambda message: self._append_log(run_id, message),
            )
            self._populate_outputs(run_id, result)
            if result.status == "failed":
                failed = self.get_run(run_id)
                self._update_run(
                    run_id,
                    status="failed",
                    error_message="正文未通过 clean-prose gate。",
                    progress=failed.progress.model_copy(update={"message": "正文质检失败"}),
                )
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                progress=self.get_run(run_id).progress.model_copy(update={"message": "运行失败"}),
            )


class _ReferenceProfileBundle(BaseModel):
    profiles: list[ReferenceProfile] = Field(default_factory=list)

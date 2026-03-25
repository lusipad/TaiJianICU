from __future__ import annotations

import asyncio
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config.settings import AppSettings
from core.models.story_state import StoryThread
from core.models.style_profile import ExtractionSnapshot
from orchestrator import PipelineRunResult, TaiJianOrchestrator
from webapp.errors import ApiError
from webapp.models import (
    WebChapterSummary,
    WebRunArtifactPaths,
    WebRunDetail,
    WebRunMetrics,
    WebRunProgress,
    WebRunRequest,
    WebRunSummary,
)


_SESSION_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


class WebRunManager:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._runs: dict[str, WebRunDetail] = {}
        self._load_existing_runs()

    def _run_file(self, run_id: str) -> Path:
        return self.settings.web_runs_dir / f"{run_id}.json"

    def _load_existing_runs(self) -> None:
        for path in sorted(self.settings.web_runs_dir.glob("*.json")):
            try:
                run = WebRunDetail.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            self._runs[run.id] = run

    def _persist(self, run: WebRunDetail) -> None:
        self._run_file(run.id).write_text(run.model_dump_json(indent=2), encoding="utf-8")

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
            return run.model_copy(deep=True)

    def start_run(
        self,
        *,
        input_path: Path,
        input_filename: str,
        request: WebRunRequest,
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

        thread = threading.Thread(
            target=self._run_pipeline,
            kwargs={"run_id": run_id},
            daemon=True,
        )
        thread.start()
        return WebRunSummary.model_validate(run.model_dump(mode="json"))

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

    def _populate_outputs(self, run_id: str, result: PipelineRunResult) -> None:
        snapshot_path = Path(result.stage1_snapshot_path)
        snapshot = None
        if snapshot_path.exists():
            snapshot = ExtractionSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        manifest_path = self.settings.sessions_dir / result.session_name / "run_manifest.json"
        manifest = None
        if manifest_path.exists():
            manifest = PipelineRunResult.model_validate_json(manifest_path.read_text(encoding="utf-8"))
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
        latest_skeleton_path = None
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

        unresolved_threads_path = self.settings.sessions_dir / result.session_name / "unresolved_threads.json"
        unresolved_threads: list[StoryThread] = []
        if unresolved_threads_path.exists():
            payload = json.loads(unresolved_threads_path.read_text(encoding="utf-8"))
            unresolved_threads = [
                StoryThread.model_validate(item) for item in payload.get("threads", [])
            ]

        story_graph_path = self.settings.sessions_dir / result.session_name / "story_graph.mmd"
        chapter_summaries = self._chapter_summaries(manifest or result)
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
            status="completed",
            progress=self.get_run(run_id).progress.model_copy(
                update={
                    "completed_steps": self.get_run(run_id).progress.total_steps,
                    "message": "运行完成",
                }
            ),
            manifest_path=str(manifest_path),
            stage1_snapshot_path=result.stage1_snapshot_path,
            output_paths=[item.output_path for item in result.chapters if item.output_path],
            style_profile=snapshot.style_profile.model_dump(mode="json") if snapshot else None,
            story_state=snapshot.story_state.model_dump(mode="json") if snapshot else None,
            latest_output_preview=latest_output_preview,
            latest_quality_report=latest_quality,
            latest_consistency_report=latest_consistency,
            latest_chapter_goal=latest_chapter_goal,
            unresolved_threads=unresolved_threads,
            artifact_paths=WebRunArtifactPaths(
                manifest=str(manifest_path),
                stage1_snapshot=result.stage1_snapshot_path,
                latest_skeleton=latest_skeleton_path,
                latest_draft=latest_draft_path,
                latest_output=latest_output_string,
                story_graph=str(story_graph_path) if story_graph_path.exists() else None,
            ),
            metrics=metrics,
            chapter_summaries=chapter_summaries,
        )

    def _run_pipeline(self, *, run_id: str) -> None:
        current = self.get_run(run_id)
        orchestrator = TaiJianOrchestrator(self.settings)

        async def runner() -> PipelineRunResult:
            return await orchestrator.run(
                input_path=Path(current.input_path or ""),
                chapters=current.request.chapters,
                session_name=current.session_name,
                goal_hint=current.request.goal_hint,
                use_existing_index=current.request.use_existing_index,
                overwrite=current.request.overwrite,
                start_chapter=current.request.start_chapter,
                progress_callback=lambda message: self._append_log(run_id, message),
            )

        try:
            self._append_log(run_id, "任务开始执行")
            result = asyncio.run(runner())
            self._populate_outputs(run_id, result)
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                progress=self.get_run(run_id).progress.model_copy(update={"message": "运行失败"}),
            )

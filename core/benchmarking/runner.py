from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from config.settings import AppSettings, render_prompt
from core.llm.litellm_client import LLMUsageSummary, LiteLLMService
from core.models.style_profile import ExtractionSnapshot
from orchestrator import PipelineRunResult, TaiJianOrchestrator


_CHAPTER_PATTERN = re.compile(
    r"^第[0-9一二三四五六七八九十百千万零两]+[回章节][^\n]*$",
    re.M,
)


class BenchmarkDatasetSpec(BaseModel):
    name: str
    source_url: str | None = None
    source_file_name: str
    encoding: str = "utf-8"
    description: str = ""


class ChapterSource(BaseModel):
    number: int
    title: str
    text: str


class BenchmarkCase(BaseModel):
    dataset_name: str
    case_name: str
    source_path: str
    prefix_path: str
    reference_path: str
    target_chapter_number: int
    prefix_chapter_count: int
    recent_chapters: list[ChapterSource] = Field(default_factory=list)


class CandidateScore(BaseModel):
    plot_alignment: float
    character_consistency: float
    style_similarity: float
    readability: float
    overall: float
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    summary: str


class PairwiseJudgement(BaseModel):
    winner: Literal["system", "baseline", "tie"]
    reasoning: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CandidateReport(BaseModel):
    label: str
    output_path: str
    score: CandidateScore
    usage_summary: LLMUsageSummary = Field(default_factory=LLMUsageSummary)
    elapsed_seconds: float = 0.0


class BenchmarkReport(BaseModel):
    dataset_name: str
    case_name: str
    prefix_chapter_count: int
    target_chapter_number: int
    source_path: str
    prefix_path: str
    reference_path: str
    system_session_name: str
    system_manifest_path: str
    system_output_path: str
    baseline_output_path: str
    pairwise: PairwiseJudgement
    system_report: CandidateReport
    baseline_report: CandidateReport
    total_usage: LLMUsageSummary = Field(default_factory=LLMUsageSummary)
    report_markdown_path: str
    report_json_path: str


@dataclass(slots=True)
class _CaseArtifacts:
    case: BenchmarkCase
    case_dir: Path
    report_dir: Path
    baseline_output_path: Path
    report_json_path: Path
    report_markdown_path: Path


class BenchmarkRunner:
    DATASETS = {
        "sanguo": BenchmarkDatasetSpec(
            name="sanguo",
            source_url="https://raw.githubusercontent.com/TommyZihao/zihaowordcloud/master/code/%E4%B8%89%E5%9B%BD%E6%BC%94%E4%B9%89.txt",
            source_file_name="sanguo_yanyi.txt",
            description="《三国演义》全文，来自 GitHub 公共仓库。",
        )
    }

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.llm_service = LiteLLMService(settings)

    def _dataset_dir(self, dataset_name: str) -> Path:
        path = self.settings.benchmarks_dir / dataset_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_dataset_spec(self, dataset_name: str) -> BenchmarkDatasetSpec:
        try:
            return self.DATASETS[dataset_name]
        except KeyError as exc:
            raise ValueError(f"未知数据集: {dataset_name}") from exc

    @staticmethod
    def _decode_text_bytes(content: bytes, preferred_encoding: str | None = None) -> str:
        candidates: list[str] = []
        if preferred_encoding:
            candidates.append(preferred_encoding)
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            if encoding not in candidates:
                candidates.append(encoding)
        for encoding in candidates:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("文本编码无法识别，请显式指定 --source-encoding。")

    def _download_text(self, spec: BenchmarkDatasetSpec, output_path: Path) -> Path:
        if not spec.source_url:
            raise ValueError("该数据集没有可下载的 source_url。")
        if output_path.exists():
            return output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(
                spec.source_url,
                headers={"user-agent": "Mozilla/5.0 TaiJianKiller Benchmark"},
            )
            response.raise_for_status()
        output_path.write_text(
            self._decode_text_bytes(response.content, preferred_encoding=spec.encoding),
            encoding="utf-8",
        )
        return output_path

    def _copy_source_text(
        self,
        *,
        source_path: Path,
        output_path: Path,
        encoding: str | None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self._decode_text_bytes(source_path.read_bytes(), preferred_encoding=encoding),
            encoding="utf-8",
        )
        return output_path

    def ensure_dataset(
        self,
        dataset_name: str,
        *,
        source_path: Path | None = None,
        source_url: str | None = None,
        source_encoding: str | None = None,
        source_file_name: str | None = None,
    ) -> Path:
        if source_path is not None and source_url is not None:
            raise ValueError("source_path 和 source_url 不能同时提供。")

        if source_path is not None:
            if not source_path.exists():
                raise ValueError(f"找不到数据文件: {source_path}")
            dataset_dir = self._dataset_dir(dataset_name)
            output_path = dataset_dir / (source_file_name or source_path.name)
            return self._copy_source_text(
                source_path=source_path,
                output_path=output_path,
                encoding=source_encoding,
            )

        if source_url is not None:
            dataset_dir = self._dataset_dir(dataset_name)
            parsed = urlparse(source_url)
            guessed_name = Path(parsed.path).name or f"{dataset_name}.txt"
            spec = BenchmarkDatasetSpec(
                name=dataset_name,
                source_url=source_url,
                source_file_name=source_file_name or guessed_name,
                encoding=source_encoding or "utf-8",
                description="自定义远程文本基准源。",
            )
            return self._download_text(spec, dataset_dir / spec.source_file_name)

        spec = self._load_dataset_spec(dataset_name)
        dataset_dir = self._dataset_dir(dataset_name)
        source_path = dataset_dir / spec.source_file_name
        return self._download_text(spec, source_path)

    def _parse_chapters(self, text: str) -> list[ChapterSource]:
        matches = list(_CHAPTER_PATTERN.finditer(text))
        chapters: list[ChapterSource] = []
        for index, match in enumerate(matches, start=1):
            start = match.start()
            end = matches[index].start() if index < len(matches) else len(text)
            body = text[start:end].strip()
            title = match.group(0).strip()
            chapters.append(ChapterSource(number=index, title=title, text=body))
        if not chapters:
            raise ValueError("无法从数据集中识别章节标题。")
        return chapters

    def prepare_case(
        self,
        *,
        dataset_name: str,
        prefix_chapters: int,
        target_chapter: int,
        source_path: Path | None = None,
        source_url: str | None = None,
        source_encoding: str | None = None,
        source_file_name: str | None = None,
    ) -> _CaseArtifacts:
        source_path = self.ensure_dataset(
            dataset_name,
            source_path=source_path,
            source_url=source_url,
            source_encoding=source_encoding,
            source_file_name=source_file_name,
        )
        novel_text = source_path.read_text(encoding="utf-8")
        chapters = self._parse_chapters(novel_text)
        if prefix_chapters < 1 or target_chapter <= prefix_chapters:
            raise ValueError("target_chapter 必须大于 prefix_chapters。")
        if target_chapter > len(chapters):
            raise ValueError("target_chapter 超出数据集章节总数。")

        prefix_items = chapters[:prefix_chapters]
        reference = chapters[target_chapter - 1]
        recent = chapters[max(0, prefix_chapters - 3) : prefix_chapters]
        case_name = f"{prefix_chapters}_to_{target_chapter}"
        case_dir = self._dataset_dir(dataset_name) / "cases" / case_name
        report_dir = case_dir / "report"
        baseline_dir = case_dir / "baseline"
        report_dir.mkdir(parents=True, exist_ok=True)
        baseline_dir.mkdir(parents=True, exist_ok=True)

        prefix_path = case_dir / f"prefix_{prefix_chapters}.txt"
        reference_path = case_dir / f"reference_{target_chapter}.txt"
        prefix_path.write_text("\n\n".join(item.text for item in prefix_items), encoding="utf-8")
        reference_path.write_text(reference.text, encoding="utf-8")
        metadata = {
            "dataset_name": dataset_name,
            "case_name": case_name,
            "prefix_chapter_count": prefix_chapters,
            "target_chapter_number": target_chapter,
            "recent_titles": [item.title for item in recent],
            "source_origin": source_url or str(source_path),
        }
        (case_dir / "case.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return _CaseArtifacts(
            case=BenchmarkCase(
                dataset_name=dataset_name,
                case_name=case_name,
                source_path=str(source_path),
                prefix_path=str(prefix_path),
                reference_path=str(reference_path),
                target_chapter_number=target_chapter,
                prefix_chapter_count=prefix_chapters,
                recent_chapters=recent,
            ),
            case_dir=case_dir,
            report_dir=report_dir,
            baseline_output_path=baseline_dir / f"chapter_{target_chapter}.md",
            report_json_path=report_dir / "benchmark_report.json",
            report_markdown_path=report_dir / "benchmark_report.md",
        )

    @staticmethod
    def _format_recent_chapters(chapters: list[ChapterSource]) -> str:
        return "\n\n".join(f"[{item.title}]\n{item.text}" for item in chapters)

    async def _run_system(
        self,
        *,
        case: BenchmarkCase,
        session_name: str,
        overwrite: bool,
    ) -> tuple[PipelineRunResult, ExtractionSnapshot, Path]:
        orchestrator = TaiJianOrchestrator(self.settings)
        existing_index = (self.settings.lightrag_dir / session_name).exists()
        result = await orchestrator.run(
            input_path=Path(case.prefix_path),
            chapters=1,
            session_name=session_name,
            use_existing_index=existing_index,
            refresh_snapshot=existing_index,
            overwrite=overwrite,
            start_chapter=case.target_chapter_number,
        )
        snapshot_path = orchestrator.session_store.stage1_snapshot_path(session_name)
        snapshot = ExtractionSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        output_path = self.settings.output_dir / session_name / f"chapter_{case.target_chapter_number}.md"
        return result, snapshot, output_path

    async def _run_baseline(
        self,
        *,
        case: BenchmarkCase,
        snapshot: ExtractionSnapshot,
        output_path: Path,
    ) -> CandidateReport:
        usage_mark = self.llm_service.usage_mark()
        started = perf_counter()
        prompt = render_prompt(
            "benchmark/direct_baseline.txt",
            target_chapter_number=case.target_chapter_number,
            style_profile=snapshot.style_profile.model_dump(mode="json"),
            story_state=snapshot.story_state.model_dump(mode="json"),
            recent_chapters=self._format_recent_chapters(case.recent_chapters),
        )
        response = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="benchmark_direct_baseline",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response.text, encoding="utf-8")
        return CandidateReport(
            label="baseline",
            output_path=str(output_path),
            score=CandidateScore(
                plot_alignment=0.0,
                character_consistency=0.0,
                style_similarity=0.0,
                readability=0.0,
                overall=0.0,
                strengths=[],
                weaknesses=[],
                summary="",
            ),
            usage_summary=self.llm_service.usage_summary(usage_mark),
            elapsed_seconds=perf_counter() - started,
        )

    async def _judge_candidate(
        self,
        *,
        case: BenchmarkCase,
        snapshot: ExtractionSnapshot,
        reference_text: str,
        candidate_text: str,
        label: str,
    ) -> CandidateReport:
        usage_mark = self.llm_service.usage_mark()
        started = perf_counter()
        prompt = render_prompt(
            "benchmark/candidate_judge.txt",
            target_chapter_number=case.target_chapter_number,
            story_state=snapshot.story_state.model_dump(mode="json"),
            style_profile=snapshot.style_profile.model_dump(mode="json"),
            recent_chapters=self._format_recent_chapters(case.recent_chapters),
            reference_text=reference_text,
            candidate_text=candidate_text,
        )
        score = await self.llm_service.complete_structured(
            model=self.settings.models.quality_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=CandidateScore,
            temperature=0.1,
            max_tokens=2048,
            operation=f"benchmark_judge_{label}",
        )
        return CandidateReport(
            label=label,
            output_path="",
            score=score,
            usage_summary=self.llm_service.usage_summary(usage_mark),
            elapsed_seconds=perf_counter() - started,
        )

    async def _judge_pairwise(
        self,
        *,
        case: BenchmarkCase,
        snapshot: ExtractionSnapshot,
        reference_text: str,
        system_text: str,
        baseline_text: str,
    ) -> tuple[PairwiseJudgement, LLMUsageSummary]:
        usage_mark = self.llm_service.usage_mark()
        prompt = render_prompt(
            "benchmark/pairwise_judge.txt",
            target_chapter_number=case.target_chapter_number,
            story_state=snapshot.story_state.model_dump(mode="json"),
            style_profile=snapshot.style_profile.model_dump(mode="json"),
            recent_chapters=self._format_recent_chapters(case.recent_chapters),
            reference_text=reference_text,
            candidate_a=system_text,
            candidate_b=baseline_text,
        )
        judgement = await self.llm_service.complete_structured(
            model=self.settings.models.quality_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=PairwiseJudgement,
            temperature=0.1,
            max_tokens=1024,
            operation="benchmark_pairwise_judge",
        )
        return judgement, self.llm_service.usage_summary(usage_mark)

    @staticmethod
    def _merge_usage(*summaries: LLMUsageSummary) -> LLMUsageSummary:
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
                target["prompt_tokens"] = int(target["prompt_tokens"]) + int(bucket.get("prompt_tokens", 0))
                target["completion_tokens"] = int(target["completion_tokens"]) + int(
                    bucket.get("completion_tokens", 0)
                )
                target["total_tokens"] = int(target["total_tokens"]) + int(bucket.get("total_tokens", 0))
                target["cached_tokens"] = int(target["cached_tokens"]) + int(bucket.get("cached_tokens", 0))
                target["total_cost_usd"] = float(target["total_cost_usd"]) + float(
                    bucket.get("total_cost_usd", 0.0)
                )
        merged.total_cost_usd = round(merged.total_cost_usd, 6)
        for bucket in merged.by_model.values():
            bucket["total_cost_usd"] = round(float(bucket["total_cost_usd"]), 6)
        return merged

    def _render_report_markdown(
        self,
        *,
        report: BenchmarkReport,
    ) -> str:
        return (
            f"# 基准报告：{report.dataset_name} {report.case_name}\n\n"
            f"- 前置章节：{report.prefix_chapter_count}\n"
            f"- 目标章节：{report.target_chapter_number}\n"
            f"- Pairwise Winner：{report.pairwise.winner}\n"
            f"- Pairwise Confidence：{report.pairwise.confidence:.2f}\n"
            f"- 总成本（USD）：{report.total_usage.total_cost_usd:.6f}\n"
            f"- 总 Tokens：{report.total_usage.total_tokens}\n\n"
            "## System\n\n"
            f"- plot_alignment：{report.system_report.score.plot_alignment:.1f}\n"
            f"- character_consistency：{report.system_report.score.character_consistency:.1f}\n"
            f"- style_similarity：{report.system_report.score.style_similarity:.1f}\n"
            f"- readability：{report.system_report.score.readability:.1f}\n"
            f"- overall：{report.system_report.score.overall:.1f}\n"
            f"- summary：{report.system_report.score.summary}\n\n"
            "## Baseline\n\n"
            f"- plot_alignment：{report.baseline_report.score.plot_alignment:.1f}\n"
            f"- character_consistency：{report.baseline_report.score.character_consistency:.1f}\n"
            f"- style_similarity：{report.baseline_report.score.style_similarity:.1f}\n"
            f"- readability：{report.baseline_report.score.readability:.1f}\n"
            f"- overall：{report.baseline_report.score.overall:.1f}\n"
            f"- summary：{report.baseline_report.score.summary}\n\n"
            "## Pairwise Reasoning\n\n"
            + "\n".join(f"- {item}" for item in report.pairwise.reasoning)
            + "\n"
        )

    async def run(
        self,
        *,
        dataset_name: str,
        prefix_chapters: int,
        target_chapter: int,
        session_name: str | None = None,
        overwrite: bool = False,
        source_path: Path | None = None,
        source_url: str | None = None,
        source_encoding: str | None = None,
        source_file_name: str | None = None,
    ) -> BenchmarkReport:
        artifacts = self.prepare_case(
            dataset_name=dataset_name,
            prefix_chapters=prefix_chapters,
            target_chapter=target_chapter,
            source_path=source_path,
            source_url=source_url,
            source_encoding=source_encoding,
            source_file_name=source_file_name,
        )
        case = artifacts.case
        session = session_name or f"benchmark-{dataset_name}-{case.case_name}"
        system_result, snapshot, system_output_path = await self._run_system(
            case=case,
            session_name=session,
            overwrite=overwrite,
        )
        system_text = system_output_path.read_text(encoding="utf-8")
        baseline_generation = await self._run_baseline(
            case=case,
            snapshot=snapshot,
            output_path=artifacts.baseline_output_path,
        )
        baseline_text = artifacts.baseline_output_path.read_text(encoding="utf-8")
        reference_text = Path(case.reference_path).read_text(encoding="utf-8")

        system_judge = await self._judge_candidate(
            case=case,
            snapshot=snapshot,
            reference_text=reference_text,
            candidate_text=system_text,
            label="system",
        )
        baseline_judge = await self._judge_candidate(
            case=case,
            snapshot=snapshot,
            reference_text=reference_text,
            candidate_text=baseline_text,
            label="baseline",
        )
        pairwise, pairwise_usage = await self._judge_pairwise(
            case=case,
            snapshot=snapshot,
            reference_text=reference_text,
            system_text=system_text,
            baseline_text=baseline_text,
        )

        system_manifest_path = self.settings.sessions_dir / session / "run_manifest.json"
        system_candidate = CandidateReport(
            label="system",
            output_path=str(system_output_path),
            score=system_judge.score,
            usage_summary=system_result.total_usage,
            elapsed_seconds=sum(item.elapsed_seconds for item in system_result.chapters),
        )
        baseline_candidate = CandidateReport(
            label="baseline",
            output_path=str(artifacts.baseline_output_path),
            score=baseline_judge.score,
            usage_summary=baseline_generation.usage_summary,
            elapsed_seconds=baseline_generation.elapsed_seconds,
        )
        total_usage = self._merge_usage(
            system_result.total_usage,
            baseline_generation.usage_summary,
            system_judge.usage_summary,
            baseline_judge.usage_summary,
            pairwise_usage,
        )
        report = BenchmarkReport(
            dataset_name=dataset_name,
            case_name=case.case_name,
            prefix_chapter_count=prefix_chapters,
            target_chapter_number=target_chapter,
            source_path=case.source_path,
            prefix_path=case.prefix_path,
            reference_path=case.reference_path,
            system_session_name=session,
            system_manifest_path=str(system_manifest_path),
            system_output_path=str(system_output_path),
            baseline_output_path=str(artifacts.baseline_output_path),
            pairwise=pairwise,
            system_report=system_candidate,
            baseline_report=baseline_candidate,
            total_usage=total_usage,
            report_markdown_path=str(artifacts.report_markdown_path),
            report_json_path=str(artifacts.report_json_path),
        )
        artifacts.report_json_path.write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        artifacts.report_markdown_path.write_text(
            self._render_report_markdown(report=report),
            encoding="utf-8",
        )
        return report


def run_benchmark_sync(
    settings: AppSettings,
    *,
    dataset_name: str,
    prefix_chapters: int,
    target_chapter: int,
    session_name: str | None = None,
    overwrite: bool = False,
    source_path: Path | None = None,
    source_url: str | None = None,
    source_encoding: str | None = None,
    source_file_name: str | None = None,
) -> BenchmarkReport:
    runner = BenchmarkRunner(settings)
    return asyncio.run(
        runner.run(
            dataset_name=dataset_name,
            prefix_chapters=prefix_chapters,
            target_chapter=target_chapter,
            session_name=session_name,
            overwrite=overwrite,
            source_path=source_path,
            source_url=source_url,
            source_encoding=source_encoding,
            source_file_name=source_file_name,
        )
    )

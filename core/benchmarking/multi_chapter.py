from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from config.settings import AppSettings
from core.benchmarking.runner import BenchmarkRunner, ChapterSource
from pipeline.revival import CleanProseGate, StyleBibleBuilder


_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_CHAPTER_FILE_RE = re.compile(r"chapter_(\d+)\.md$")
_CLASSIC_MARKERS = ["话说", "却说", "且说", "原来", "谁知", "不觉", "一面", "只见"]


class ChapterBaselineMetrics(BaseModel):
    chapter_number: int
    chinese_char_count: int = 0
    avg_sentence_length: float = 0.0
    dialogue_ratio: float = 0.0
    classic_marker_density: float = 0.0
    clean_gate_hits: int = 0
    repetition_ratio: float = 0.0


class ChapterBaselineScore(BaseModel):
    chapter_number: int
    reference_title: str = ""
    candidate_path: str
    overall: float
    length_score: float
    rhythm_score: float
    dialogue_score: float
    marker_score: float
    clean_score: float
    repetition_score: float
    reference_metrics: ChapterBaselineMetrics
    candidate_metrics: ChapterBaselineMetrics
    issues: list[str] = Field(default_factory=list)


class MultiChapterBenchmarkReport(BaseModel):
    dataset_name: str
    case_name: str
    source_path: str
    candidate_dir: str
    target_start_chapter: int
    chapter_count: int
    overall: float
    drift: float
    chapter_scores: list[ChapterBaselineScore] = Field(default_factory=list)
    report_json_path: str
    report_markdown_path: str


class MultiChapterBenchmarkRunner:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.single_runner = BenchmarkRunner(settings)

    def run(
        self,
        *,
        dataset_name: str,
        prefix_chapters: int,
        target_start_chapter: int,
        chapter_count: int,
        candidate_dir: Path,
        source_path: Path | None = None,
        source_url: str | None = None,
        source_encoding: str | None = None,
        source_file_name: str | None = None,
    ) -> MultiChapterBenchmarkReport:
        if chapter_count < 1:
            raise ValueError("chapter_count 必须大于 0。")
        if target_start_chapter <= prefix_chapters:
            raise ValueError("target_start_chapter 必须大于 prefix_chapters。")
        if not candidate_dir.exists() or not candidate_dir.is_dir():
            raise ValueError(f"找不到候选章节目录: {candidate_dir}")

        source = self.single_runner.ensure_dataset(
            dataset_name,
            source_path=source_path,
            source_url=source_url,
            source_encoding=source_encoding,
            source_file_name=source_file_name,
        )
        chapters = self.single_runner._parse_chapters(source.read_text(encoding="utf-8"))
        target_end = target_start_chapter + chapter_count - 1
        if target_end > len(chapters):
            raise ValueError("目标章节范围超出数据集章节总数。")

        candidates = self._load_candidates(
            candidate_dir=candidate_dir,
            start=target_start_chapter,
            count=chapter_count,
        )
        references = chapters[target_start_chapter - 1 : target_end]
        scores = [
            self._score_chapter(reference=reference, candidate_path=path, candidate_text=text)
            for reference, (path, text) in zip(references, candidates)
        ]
        overall = round(sum(item.overall for item in scores) / len(scores), 4)
        drift = self._drift(scores)

        case_name = f"{prefix_chapters}_to_{target_start_chapter}_{chapter_count}ch"
        report_dir = self.settings.benchmarks_dir / dataset_name / "cases" / case_name / "multi_report"
        report_dir.mkdir(parents=True, exist_ok=True)
        report = MultiChapterBenchmarkReport(
            dataset_name=dataset_name,
            case_name=case_name,
            source_path=str(source),
            candidate_dir=str(candidate_dir),
            target_start_chapter=target_start_chapter,
            chapter_count=chapter_count,
            overall=overall,
            drift=drift,
            chapter_scores=scores,
            report_json_path=str(report_dir / "multi_chapter_report.json"),
            report_markdown_path=str(report_dir / "multi_chapter_report.md"),
        )
        Path(report.report_json_path).write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        Path(report.report_markdown_path).write_text(
            self._render_markdown(report),
            encoding="utf-8",
        )
        return report

    @staticmethod
    def _load_candidates(
        *,
        candidate_dir: Path,
        start: int,
        count: int,
    ) -> list[tuple[Path, str]]:
        candidates: list[tuple[Path, str]] = []
        for chapter_number in range(start, start + count):
            path = candidate_dir / f"chapter_{chapter_number}.md"
            if not path.exists():
                raise ValueError(f"候选目录缺少章节文件: {path}")
            candidates.append((path, path.read_text(encoding="utf-8")))
        return candidates

    @staticmethod
    def discover_chapter_numbers(candidate_dir: Path) -> list[int]:
        numbers: list[int] = []
        for path in candidate_dir.iterdir():
            match = _CHAPTER_FILE_RE.match(path.name)
            if match:
                numbers.append(int(match.group(1)))
        return sorted(numbers)

    def _score_chapter(
        self,
        *,
        reference: ChapterSource,
        candidate_path: Path,
        candidate_text: str,
    ) -> ChapterBaselineScore:
        reference_metrics = self._measure(reference.number, reference.text)
        candidate_metrics = self._measure(reference.number, candidate_text)
        length_score = self._ratio_score(
            candidate_metrics.chinese_char_count,
            reference_metrics.chinese_char_count,
            tolerance=0.35,
        )
        rhythm_score = self._ratio_score(
            candidate_metrics.avg_sentence_length,
            reference_metrics.avg_sentence_length,
            tolerance=0.45,
        )
        dialogue_score = self._distance_score(
            candidate_metrics.dialogue_ratio,
            reference_metrics.dialogue_ratio,
            tolerance=0.2,
        )
        marker_score = self._distance_score(
            candidate_metrics.classic_marker_density,
            reference_metrics.classic_marker_density,
            tolerance=0.0015,
        )
        clean_score = max(0.0, 1.0 - candidate_metrics.clean_gate_hits * 0.2)
        repetition_score = max(0.0, 1.0 - candidate_metrics.repetition_ratio * 2.0)
        overall = round(
            (
                length_score * 0.2
                + rhythm_score * 0.2
                + dialogue_score * 0.2
                + marker_score * 0.15
                + clean_score * 0.15
                + repetition_score * 0.1
            ),
            4,
        )
        return ChapterBaselineScore(
            chapter_number=reference.number,
            reference_title=reference.title,
            candidate_path=str(candidate_path),
            overall=overall,
            length_score=round(length_score, 4),
            rhythm_score=round(rhythm_score, 4),
            dialogue_score=round(dialogue_score, 4),
            marker_score=round(marker_score, 4),
            clean_score=round(clean_score, 4),
            repetition_score=round(repetition_score, 4),
            reference_metrics=reference_metrics,
            candidate_metrics=candidate_metrics,
            issues=self._issues(
                overall=overall,
                candidate_metrics=candidate_metrics,
                reference_metrics=reference_metrics,
            ),
        )

    @staticmethod
    def _measure(chapter_number: int, text: str) -> ChapterBaselineMetrics:
        metrics = StyleBibleBuilder().measure(text)
        chinese_count = len(_CHINESE_CHAR_RE.findall(text))
        clean = CleanProseGate().check(text)
        marker_count = sum(text.count(marker) for marker in _CLASSIC_MARKERS)
        return ChapterBaselineMetrics(
            chapter_number=chapter_number,
            chinese_char_count=chinese_count,
            avg_sentence_length=metrics.avg_sentence_length,
            dialogue_ratio=metrics.dialogue_ratio,
            classic_marker_density=round(marker_count / chinese_count, 6)
            if chinese_count
            else 0.0,
            clean_gate_hits=len(clean.hits),
            repetition_ratio=MultiChapterBenchmarkRunner._repetition_ratio(text),
        )

    @staticmethod
    def _repetition_ratio(text: str) -> float:
        chars = "".join(_CHINESE_CHAR_RE.findall(text))
        if len(chars) < 40:
            return 0.0
        grams = [chars[index : index + 8] for index in range(0, len(chars) - 7)]
        if not grams:
            return 0.0
        return round(1.0 - len(set(grams)) / len(grams), 4)

    @staticmethod
    def _ratio_score(value: float, expected: float, *, tolerance: float) -> float:
        if expected <= 0:
            return 1.0 if value <= 0 else 0.0
        delta = abs(value - expected) / expected
        return max(0.0, 1.0 - delta / tolerance)

    @staticmethod
    def _distance_score(value: float, expected: float, *, tolerance: float) -> float:
        delta = abs(value - expected)
        return max(0.0, 1.0 - delta / tolerance)

    @staticmethod
    def _issues(
        *,
        overall: float,
        candidate_metrics: ChapterBaselineMetrics,
        reference_metrics: ChapterBaselineMetrics,
    ) -> list[str]:
        issues: list[str] = []
        if overall < 0.65:
            issues.append("overall_below_threshold")
        if candidate_metrics.clean_gate_hits:
            issues.append("clean_gate_hits")
        if candidate_metrics.chinese_char_count < reference_metrics.chinese_char_count * 0.5:
            issues.append("candidate_too_short")
        if candidate_metrics.repetition_ratio > 0.08:
            issues.append("high_repetition")
        return issues

    @staticmethod
    def _drift(scores: list[ChapterBaselineScore]) -> float:
        if len(scores) < 2:
            return 0.0
        xs = list(range(len(scores)))
        ys = [score.overall for score in scores]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        if denominator == 0:
            return 0.0
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
        return round(slope, 4)

    @staticmethod
    def _render_markdown(report: MultiChapterBenchmarkReport) -> str:
        rows = [
            "| Chapter | Overall | Length | Rhythm | Dialogue | Marker | Clean | Repetition | Issues |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for score in report.chapter_scores:
            rows.append(
                "| "
                f"{score.chapter_number} | "
                f"{score.overall:.2f} | "
                f"{score.length_score:.2f} | "
                f"{score.rhythm_score:.2f} | "
                f"{score.dialogue_score:.2f} | "
                f"{score.marker_score:.2f} | "
                f"{score.clean_score:.2f} | "
                f"{score.repetition_score:.2f} | "
                f"{', '.join(score.issues) or '-'} |"
            )
        payload = {
            "dataset": report.dataset_name,
            "case": report.case_name,
            "overall": report.overall,
            "drift": report.drift,
            "candidate_dir": report.candidate_dir,
        }
        return (
            f"# 多章基线评估：{report.dataset_name} {report.case_name}\n\n"
            f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n"
            + "\n".join(rows)
            + "\n"
        )


def run_multi_chapter_benchmark_sync(
    settings: AppSettings,
    *,
    dataset_name: str,
    prefix_chapters: int,
    target_start_chapter: int,
    chapter_count: int,
    candidate_dir: Path,
    source_path: Path | None = None,
    source_url: str | None = None,
    source_encoding: str | None = None,
    source_file_name: str | None = None,
) -> MultiChapterBenchmarkReport:
    return MultiChapterBenchmarkRunner(settings).run(
        dataset_name=dataset_name,
        prefix_chapters=prefix_chapters,
        target_start_chapter=target_start_chapter,
        chapter_count=chapter_count,
        candidate_dir=candidate_dir,
        source_path=source_path,
        source_url=source_url,
        source_encoding=source_encoding,
        source_file_name=source_file_name,
    )

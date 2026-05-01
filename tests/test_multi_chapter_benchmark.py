from pathlib import Path

from config.settings import AppSettings
from core.benchmarking.multi_chapter import MultiChapterBenchmarkRunner


CHAPTER_3_TEXT = (
    "第三回 风起\n"
    "原来袭人早在房中，见他神色不定，便不言语。"
    "宝玉坐了半日，只听窗外竹叶萧萧，心中又添一层疑惑。"
    "麝月端茶进来，也只低声劝他歇息。"
)


def _write_source(path: Path) -> None:
    path.write_text(
        "\n\n".join(
            [
                "第一回 起首\n话说宝玉初入园中，只见花影重重。",
                "第二回 承接\n且说黛玉听了，冷笑道：“你又来哄我。”",
                CHAPTER_3_TEXT,
                "第四回 花落\n谁知一夜秋风，吹得阶前落叶满地。",
            ]
        ),
        encoding="utf-8",
    )


def test_discover_chapter_numbers(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "out"
    candidate_dir.mkdir()
    (candidate_dir / "chapter_3.md").write_text("第三回", encoding="utf-8")
    (candidate_dir / "chapter_2.md").write_text("第二回", encoding="utf-8")
    (candidate_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    assert MultiChapterBenchmarkRunner.discover_chapter_numbers(candidate_dir) == [2, 3]


def test_multi_chapter_runner_scores_candidate_directory(tmp_path: Path) -> None:
    source_path = tmp_path / "novel.txt"
    _write_source(source_path)
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    (candidate_dir / "chapter_3.md").write_text(
        CHAPTER_3_TEXT,
        encoding="utf-8",
    )
    (candidate_dir / "chapter_4.md").write_text(
        "第四回 花落\n谁知一夜秋风，吹得阶前落叶满地。",
        encoding="utf-8",
    )
    settings = AppSettings(benchmarks_dir=tmp_path / "benchmarks")

    report = MultiChapterBenchmarkRunner(settings).run(
        dataset_name="demo",
        prefix_chapters=2,
        target_start_chapter=3,
        chapter_count=2,
        candidate_dir=candidate_dir,
        source_path=source_path,
    )

    assert report.overall > 0.95
    assert report.drift == 0.0
    assert len(report.chapter_scores) == 2
    assert Path(report.report_json_path).exists()
    assert Path(report.report_markdown_path).exists()


def test_multi_chapter_runner_flags_weak_candidate(tmp_path: Path) -> None:
    source_path = tmp_path / "novel.txt"
    _write_source(source_path)
    candidate_dir = tmp_path / "candidates"
    candidate_dir.mkdir()
    (candidate_dir / "chapter_3.md").write_text(
        "本章推进宝玉的精神崩塌。重复重复重复重复重复重复重复重复。",
        encoding="utf-8",
    )
    settings = AppSettings(benchmarks_dir=tmp_path / "benchmarks")

    report = MultiChapterBenchmarkRunner(settings).run(
        dataset_name="demo",
        prefix_chapters=2,
        target_start_chapter=3,
        chapter_count=1,
        candidate_dir=candidate_dir,
        source_path=source_path,
    )

    score = report.chapter_scores[0]
    assert score.overall < 0.8
    assert {"clean_gate_hits", "candidate_too_short"} <= set(score.issues)

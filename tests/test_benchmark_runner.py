from pathlib import Path

from config.settings import AppSettings
from core.benchmarking.runner import BenchmarkRunner


def test_parse_chapters_handles_preface() -> None:
    runner = BenchmarkRunner(AppSettings())
    text = (
        "前言\n\n"
        "第一回 桃园结义\n刘备关羽张飞。\n\n"
        "第二回 董卓入京\n群雄并起。\n\n"
        "第三回 献刀刺卓\n曹操夜逃。"
    )

    chapters = runner._parse_chapters(text)

    assert len(chapters) == 3
    assert chapters[0].title == "第一回 桃园结义"
    assert "刘备关羽张飞" in chapters[0].text
    assert chapters[2].number == 3


def test_prepare_case_writes_prefix_and_reference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = BenchmarkRunner(AppSettings(benchmarks_dir=tmp_path))
    source_path = tmp_path / "novel.txt"
    source_path.write_text(
        "第一回 桃园结义\n刘备关羽张飞。\n\n"
        "第二回 董卓入京\n群雄并起。\n\n"
        "第三回 献刀刺卓\n曹操夜逃。",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "ensure_dataset",
        lambda dataset_name, **_: source_path,
    )

    artifacts = runner.prepare_case(
        dataset_name="demo",
        prefix_chapters=2,
        target_chapter=3,
    )

    assert Path(artifacts.case.prefix_path).exists()
    assert Path(artifacts.case.reference_path).exists()
    assert "第二回 董卓入京" in Path(artifacts.case.prefix_path).read_text(encoding="utf-8")
    assert "第三回 献刀刺卓" in Path(artifacts.case.reference_path).read_text(encoding="utf-8")


def test_prepare_case_accepts_custom_source_file(tmp_path: Path) -> None:
    benchmarks_dir = tmp_path / "benchmarks"
    benchmarks_dir.mkdir(parents=True, exist_ok=True)
    runner = BenchmarkRunner(AppSettings(benchmarks_dir=benchmarks_dir))
    source_path = tmp_path / "doupo.txt"
    source_path.write_text(
        "第一章 陨落的天才\n萧炎名震乌坦城。\n\n"
        "第二章 斗气阁\n族中测试开始。\n\n"
        "第三章 客人\n贵客临门。",
        encoding="utf-8",
    )

    artifacts = runner.prepare_case(
        dataset_name="doupo",
        prefix_chapters=2,
        target_chapter=3,
        source_path=source_path,
    )

    copied_source = benchmarks_dir / "doupo" / "doupo.txt"
    assert copied_source.exists()
    assert artifacts.case.source_path == str(copied_source)
    assert "第二章 斗气阁" in Path(artifacts.case.prefix_path).read_text(encoding="utf-8")

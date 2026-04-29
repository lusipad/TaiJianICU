from pipeline.stage3_generation.chapter_generator import ChapterGenerator


def test_strip_output_shell_removes_model_wrappers() -> None:
    text = """以下为轻量润色稿：

---

话说宝玉病后初起。
"""

    assert ChapterGenerator.strip_output_shell(text) == "话说宝玉病后初起。"


def test_strip_output_shell_removes_markdown_fence() -> None:
    text = """```markdown
话说风过竹梢。
```"""

    assert ChapterGenerator.strip_output_shell(text) == "话说风过竹梢。"

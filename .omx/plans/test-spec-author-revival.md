# Test Spec: Author Revival First Stage

## Unit Tests

1. Chapter splitting
   - 输入含“第八十回 标题”的文本。
   - 断言章节编号、标题、正文和字符范围稳定。
   - 输入无标题文本时，断言 fallback 为单章。

2. Style bible / work skill
   - 输入小样本文本。
   - 断言平均句长、对白比例、虚词密度存在。
   - 断言禁词表包含现代抽象词。

3. Clean prose gate
   - 包装语命中应 fail。
   - 现代抽象词命中应 fail。
   - 繁简混杂应 fail 或 warning。
   - 文体指标偏移应产生命中。

4. Blind challenge
   - 输入生成正文和原文片段库。
   - 断言输出 4 段。
   - 断言隐藏标签不直接暴露给用户。
   - 断言 answer key 能定位生成段。

## Integration Tests

1. Revival artifact build
   - 使用临时目录和小型章回文本。
   - 构建 workspace artifacts。
   - 断言章节、style_bible、forbidden_words、blind challenge 可序列化落盘。

2. Existing revival flow compatibility
   - 保持 `WorkSkillBuilder`、`RevivalArcPlanner` 现有测试通过。
   - 保持 `orchestrator` 现有 revival 入口不因模型变更破坏。

## Verification Commands

- `python -m pytest tests/test_revival_models.py tests/test_revival_services.py tests/test_clean_prose_gate.py tests/test_chapter_generator.py`
- `python -m pytest`

## Non-Goals For This Spec

- 不要求真实 GPT-5.5 在线盲测在单元测试中执行。
- 不要求 Playwright Web 端到端验证。
- 不要求 300 万字性能压测。

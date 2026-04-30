# Ralph Context: Author Revival Pivot

## Task Statement

用户要求从原 V2 长篇连载引擎路线切换到“作者复活引擎”路线，并以 `$ralph` 模式持续执行直到完成。

## Desired Outcome

第一阶段交付一个可运行、可验证的红楼专用验证版：

- 不再把重型 LightRAG / WorldModel 当主线。
- 建立作品工作区产物：章节切分、style_bible、禁词表、人物声口卡、盲测挑战。
- 扩展机械闸门：包装语、现代抽象词、基础文体指标、繁简混杂。
- 支持 1000 字盲测挑战：生成片段 + 原文片段，隐藏来源并可用于判别。
- 保持现有测试通过。

## Known Facts / Evidence

- 新设计文档在 `docs/author-revival-engine-design.md`。
- 旧 V2 文档 `ROADMAP_V2.md` 仍强调“不推倒重来”，与新路线冲突。
- 当前已有 `core/models/revival.py`、`pipeline/revival.py`、`orchestrator.py` 中的 revival 雏形。
- 当前 `CleanProseGate` 只拦包装语和长度，不覆盖现代词、文体指标、繁简混乱。
- 当前 `BlindChallengeBuilder` 只截取生成正文，未加入 3 段原文对照和乱序。
- 当前工作树有用户未跟踪文件：红楼输入文本和 docs/reference、docs/superpowers。不得随意删除或回滚。

## Constraints

- 必须中文回复。
- 改动要小而可验证，避免无关重构。
- 不新增依赖。
- 只用 `apply_patch` 编辑文件。
- 每个阶段应测试；如能提交和推送，应遵守仓库提交约定。
- `rg.exe` 当前被 WindowsApps 路径拒绝访问，使用 PowerShell 原生命令替代。

## Unknowns / Open Questions

- OpenAI / LiteLLM 在线模型调用是否在当前环境可用。
- 远端 push 是否有凭据。
- 红楼样本是否足够干净；需先用本地程序做保守切分和指标。

## Likely Codebase Touchpoints

- `core/models/revival.py`
- `pipeline/revival.py`
- `orchestrator.py`
- `core/storage/session_store.py`
- `tests/test_revival_models.py`
- `tests/test_revival_services.py`
- `tests/test_clean_prose_gate.py`
- `docs/author-revival-engine-design.md`
- 新增 `ROADMAP_REVIVAL.md`

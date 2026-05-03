# 作者复活验证状态

本文档记录当前实现和可复现验证。README 只保留入口信息；这里保留工程状态、命令和质量门细节。

## 当前实现

- 阶段 1：原著切块、LightRAG 建索引、风格画像与故事状态抽取。
- 阶段 2：LangGraph 多 Agent 情节博弈，输出 `ChapterSkeleton`。
- 阶段 3：按骨架生成章节正文，做轻量润色，并运行质量检查。
- 阶段 3：few-shot 风格样本优先从输入源文本切章抽取，避免后续生成章节回灌污染风格采样。
- 阶段 3：写回前运行 source-voice gate；短章、现代元叙述、解释性抒情腔、繁简混杂或声口指标明显偏离时进入修订。
- 阶段 3：source-voice gate 失败会写入 `QualityReport.issues`。如果修订后仍不过门，章节和顶层 manifest 不会显示假绿。
- 阶段 3：近章开头重复会进入定向修订，修订提示要求重写当前章前两段、换入场焦点，避免连续章节复用同一开场模板。
- V2 执行层已接入 `WorldModel`、`ArcOutline`、`ChapterBrief` 与 `Lorebook` 命中结果。
- V2 参考层已接入默认 `ReferenceProfile`，只作用于规划层抽象约束，不直接要求正文模仿。
- 每章结束后会生成 `ChapterEvaluation`，供 rerank、reflection 和工作台展示使用。
- 执行层支持 skeleton / draft 多候选生成与 rerank，可通过 CLI / Web 配置候选数。
- 章节完成后会增量刷新 `WorldModel`，并把候选骨架、候选正文落盘到会话目录。
- Web 支持上传 `.txt`、提交任务、轮询进度、查看摘要、产物路径和历史任务。
- CLI 支持 `taijianicu run`、`taijianicu benchmark`、`taijianicu benchmark-multi`、`taijianicu web`、`taijianicu inspect`、`taijianicu intervene`；兼容旧命令 `taijian`。

## 质量门行为

- `CleanProseGate` 拦 AI 包装语、现代抽象词、章节元叙述、分析腔、繁简混杂、最小长度和基础声口指标漂移。
- `SourceVoiceGate` 从输入源文本切章计算章节长度基线和风格统计，写回前拦截短章、解释性抒情腔和明显声口偏移。
- 对“低于源文本章节长度基线”这类问题，修订提示会带具体 `当前/目标` 字符数，并允许最多 3 轮定向扩写。
- 扩写要求优先补当前场面的进退、对白、旧物、景物和转场，不靠开篇回顾或总结凑字。
- 写回前会检查最近章节开头，若新章与近章前几十个中文字符高度一致，会进入最多 3 轮定向修订；修订后仍重复则保持 `revise`。
- 对“对白比例偏离原文”这类声口问题，修订提示会按当前/基线比例选择增补短句往来或删减连续对白。
- 合并 `run_manifest.json` 时，如果任一章节为 `completed_with_warnings` 或失败，顶层 `status` 会同步反映。

## 红楼 81-120 回验证

复用已有红楼前 80 回索引续写 81-120 回：

```powershell
taijianicu run --input data\input\hongloumeng_front80_pg24264.txt --chapters 40 --session-name hongloumeng-front80-full40-reuse-20260501 --planning-mode strict --new-character-budget 0 --new-location-budget 0 --new-faction-budget 0 --start-chapter 81 --use-existing-index
```

评估 40 章整体基线：

```powershell
taijianicu benchmark-multi --dataset hongloumeng-full40-reuse --source-file data\input\hongloumeng_pg24264.txt --prefix-chapters 80 --target-start-chapter 81 --chapter-count 40 --candidate-dir data\output\hongloumeng-front80-full40-reuse-20260501
```

本地实测已生成 `chapter_81.md` 到 `chapter_120.md` 共 40 章；报告落在 `data\benchmarks\hongloumeng-full40-reuse\cases\80_to_81_40ch\multi_report\`。

旧流程结论：复用索引能支撑端到端 40 章生成，但整体分 `0.4693`，主要缺口是短章、对白比例不足和章回声口指标不稳。因此后续生成链路加入 source-voice gate，让这些问题在写回前进入改写循环。

## 第 120 回回归

复现命令：

```powershell
taijianicu run --input data\input\hongloumeng_front80_pg24264.txt --chapters 1 --session-name hongloumeng-front80-verify120-stylefix-20260502 --planning-mode strict --new-character-budget 0 --new-location-budget 0 --new-faction-budget 0 --start-chapter 120 --use-existing-index --resume --overwrite
```

最新验证结果：

- 输出：`data\output\hongloumeng-front80-verify120-stylefix-20260502\chapter_120.md`。
- 中文字符数：`4305/4257`。
- `SourceVoiceGate passed=True`。
- `run_manifest.status=completed`。
- 章节状态：`completed`。

这轮之前暴露过一个状态问题：正文过短时，单章可能已经是 `completed_with_warnings`，但合并后的 manifest 顶层仍显示 `completed`。现在已修正。

## 115-120 连续 smoke

复现方式：克隆 `hongloumeng-front80-verify120-stylefix-20260502` 的 session 与索引为 `hongloumeng-front80-verify115-120-continuous-20260503`，覆盖跑第 115-120 回。

```powershell
taijianicu run --input data\input\hongloumeng_front80_pg24264.txt --chapters 6 --session-name hongloumeng-front80-verify115-120-continuous-20260503 --planning-mode strict --new-character-budget 0 --new-location-budget 0 --new-faction-budget 0 --start-chapter 115 --use-existing-index --resume --overwrite
```

结果：

- `run_manifest.status=completed_with_warnings`。
- 第 115-117 回：`completed`，source-voice gate 通过。
- 第 118 回：`completed_with_warnings`，`3480/4257`，低于源文本章节长度基线。
- 第 119 回：`completed_with_warnings`，`3725/4257`，低于源文本章节长度基线。
- 第 120 回：`completed_with_warnings`，`3617/4257`，同时出现长度不足、对白比例偏离和解释性抒情腔偏离。
- 静态复查显示第 117-120 回存在近章开头重复；新写回护栏会将这类重复进入修订/告警。

结论：第 120 回单章过门不代表后段连续稳定。后续重点应放在连续章节的计划去重、开头转场多样性和后段对白密度。

二次验证 session：

```powershell
taijianicu run --input data\input\hongloumeng_front80_pg24264.txt --chapters 6 --session-name hongloumeng-front80-verify115-120-repetitionguard-20260503 --planning-mode strict --new-character-budget 0 --new-location-budget 0 --new-faction-budget 0 --start-chapter 115 --use-existing-index --resume --overwrite
```

结果：

- `run_manifest.status=completed_with_warnings`。
- 第 115 回：`completed_with_warnings`，仍有长度和对白比例问题。
- 第 116-118 回：重复开头被识别为 warning，但初版修订提示没有稳定修掉。
- 第 119 回：仍有对白比例偏离。
- 第 120 回：重复开头被识别为 warning。

结论：重复检测本身有效，但“请修订”过于泛化，模型会保留原开篇模板。本轮已把修订动作收窄为重写当前章开头前两段、换入场人物/地点/物件/转场焦点，并把重复开头修订轮数提高到最多 3 轮。一个 115-116 真实窄 smoke 曾启动，但命令超时且未产出 `run_manifest.json`，因此不把它计入通过证据。

## 当前测试基线

```powershell
.\.venv\Scripts\python -m pytest
```

当前结果：`129 passed, 3 warnings`。

## 已知缺口

- 第 120 回单章已经过 gate，但 `115-120` 连续 smoke 证明后段仍不稳定。
- 下一步应重跑 `115-120`，验证增强后的近章重复修订是否能把重复开头修掉；再扩大到 `111-120`。
- 盲测判别仍是最终目标；source-voice gate 只能拦明显机械问题，不能替代熟读者盲评。

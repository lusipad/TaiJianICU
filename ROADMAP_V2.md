# 太监杀手 V2 实施路线图

## 1. 目标

本文档把 [DESIGN_V2.md](D:\Repos\TaiJianKiller\DESIGN_V2.md) 拆成可执行的开发路线图，目标是把 V2 从设计稿完整落地为可运行、可验证、可交付的系统。

V2 完成定义：

- `WorldModel`、`ArcOutline`、`ChapterBrief`、`ReferenceProfile`、`ExpansionBudget` 等核心结构已落地
- 编排器已从“单章流水线”升级为“世界层 + 规划层 + 执行层 + 回写层”
- Web 前端已从运行面板升级为工作台
- benchmark 能验证 V2 相对 V1 / baseline 的长期优势
- 自动化测试、端到端烟测和真实长篇样本验证全部通过

---

## 2. 当前边界

### 2.1 已确认事实

- 当前目录不是 Git 仓库，无法执行 `commit` / `push`
- 当前存在可工作的 V1 / Beta 主链路
- 当前已有 Web、benchmark、session、LightRAG、质量检查等基础设施
- 当前已经有 `DESIGN_V2.md`

### 2.2 对“每完成一步都提交推送”的处理

由于当前目录缺少 `.git`，这一步在当前环境下不可执行。

因此 V2 路线图中的每个里程碑都保留以下动作：

- 完成开发
- 完成测试
- 记录交付结果
- 若仓库恢复为 Git 仓库，则立即执行 `commit` / `push`

这不是策略选择，是环境硬限制。

---

## 3. 实施原则

### 3.1 先纵向打通，再横向扩展

优先让世界层、规划层和执行层形成最小闭环，再补 UI、参考层和多候选优化。

### 3.2 不推倒重来

以现有代码为基础演进，优先复用：

- `orchestrator.py`
- `core/llm`
- `core/storage`
- `pipeline/stage1_extraction`
- `pipeline/stage2_plot`
- `pipeline/stage3_generation`
- `webapp`

### 3.3 每个 milestone 必须闭环

每个里程碑都必须完整经过：

- 设计收敛
- 代码实现
- 自动化测试
- 烟测验证
- 文档同步

### 3.4 前端阶段使用技能

前端工作台阶段明确使用：

- `fullstack-dev`
- `frontend-dev`

前者负责整体全栈结构、接口与状态流，后者负责 UI 设计语言、布局与交互动效。

---

## 4. 总体里程碑

V2 按七个大里程碑推进：

1. `M0` 基础重构与迁移准备
2. `M1` 世界层落地
3. `M2` 规划层落地
4. `M3` Lorebook 与参考层落地
5. `M4` 执行层升级
6. `M5` Web 工作台升级
7. `M6` 验证、benchmark 与发布收尾

---

## 5. M0 基础重构与迁移准备

### 5.1 目标

为 V2 建立新的结构化模型、编排边界和存储入口，但不改变现有 V1 主流程可用性。

### 5.2 主要工作

- 新增 V2 模型目录
- 引入新的状态对象但不立即替换 V1 所有对象
- 将编排器中的可拆部分抽成服务
- 为新存储层预留接口

### 5.3 计划改动

建议新增：

- `core/models/world_model.py`
- `core/models/arc_outline.py`
- `core/models/chapter_brief.py`
- `core/models/reference_profile.py`
- `core/models/lorebook.py`
- `core/models/evaluation.py`

建议重构：

- [orchestrator.py](D:\Repos\TaiJianKiller\orchestrator.py)
- [core/storage/session_store.py](D:\Repos\TaiJianKiller\core\storage\session_store.py)

建议新增服务目录：

- `core/services/world/`
- `core/services/planning/`
- `core/services/reflection/`

### 5.4 验收标准

- V2 模型文件全部建立
- V1 主命令仍可运行
- 测试无回归

### 5.5 测试

- 单元测试：模型序列化/反序列化
- 回归测试：现有 `pytest`

---

## 6. M1 世界层落地

### 6.1 目标

把当前的 `style_profile + story_state` 升级为真正的 `WorldModel`。

### 6.2 主要工作

- 从原著与续写中构建稳定世界状态
- 引入人物、势力、地点、规则、谜团等结构
- 支持周期性刷新
- 支持从历史章节回放重建世界状态

### 6.3 主要模块

- `WorldBuilder`
- `MemoryCompressor`
- `WorldSnapshotStore`

### 6.4 计划改动

建议新增：

- `pipeline/stage1_extraction/world_builder.py`
- `core/services/world/memory_compressor.py`
- `core/services/world/world_refresh.py`

建议升级：

- [pipeline/stage1_extraction/style_analyzer.py](D:\Repos\TaiJianKiller\pipeline\stage1_extraction\style_analyzer.py)

### 6.5 关键能力

- 周期性世界刷新
- 世界状态差异对比
- “硬设定”与“可扩张机会位”区分
- 角色状态与地图状态版本化

### 6.6 验收标准

- 可生成 `WorldModel`
- 连续章节写入后可回放并刷新世界状态
- 世界模型可落盘与加载

### 6.7 测试

- 新增 `tests/test_world_builder.py`
- 新增 `tests/test_memory_compressor.py`
- 新增 `tests/test_world_refresh.py`

---

## 7. M2 规划层落地

### 7.1 目标

从“按章推进”升级为“按 arc 规划，再拆章节”。

### 7.2 主要工作

- 新增 `ArcPlanner`
- 新增 `ExpansionAllocator`
- 新增 `ChapterAllocator`
- 从 `WorldModel` 自动推导中期大纲

### 7.3 主要模块

- `ArcPlanner`
- `ExpansionAllocator`
- `ChapterAllocator`
- `PlanningState`

### 7.4 计划改动

建议新增：

- `core/services/planning/arc_planner.py`
- `core/services/planning/expansion_allocator.py`
- `core/services/planning/chapter_allocator.py`

建议重构：

- [orchestrator.py](D:\Repos\TaiJianKiller\orchestrator.py)

### 7.5 关键能力

- 输出 3 到 10 章级别 `ArcOutline`
- 自动判断 `strict / balanced / expansive`
- 自动给出新人物/新地图/新势力预算
- 输出单章 `ChapterBrief`

### 7.6 验收标准

- 单次运行可以生成 `ArcOutline`
- 单章执行前必须生成 `ChapterBrief`
- 不再直接从 `story_state` 拼接章节目标

### 7.7 测试

- `tests/test_arc_planner.py`
- `tests/test_expansion_allocator.py`
- `tests/test_chapter_allocator.py`

---

## 8. M3 Lorebook 与参考层落地

### 8.1 目标

让系统具备“动态设定注入”和“抽象参考迁移”能力。

### 8.2 主要工作

- 实现 `LorebookEntry` 与动态命中
- 实现 `ReferenceProfile`
- 实现 `ReferencePlanner`
- 将参考层只作用于高层规划，不直接作用于正文模仿

### 8.3 主要模块

- `LorebookManager`
- `ReferencePlanner`
- `ReferenceMixer`

### 8.4 计划改动

建议新增：

- `core/services/world/lorebook_manager.py`
- `core/services/planning/reference_planner.py`
- `config/references/`

### 8.5 关键能力

- 作用域化设定注入
- 优先级与预算控制
- 参考源抽象建模
- 主题/结构/气质/人物弧线迁移

### 8.6 验收标准

- Lorebook 命中机制可单独测试
- ReferenceProfile 可配置、可落盘、可被规划层消费
- 明确禁止直接复制原文或桥段

### 8.7 测试

- `tests/test_lorebook_manager.py`
- `tests/test_reference_planner.py`

---

## 9. M4 执行层升级

### 9.1 目标

把 V1 的执行层从“单骨架单正文”升级为“多候选 + 重排 + 回写”。

### 9.2 主要工作

- 多候选骨架
- 多候选正文
- rerank 选优
- 增加 novelty / arc_progress / world_consistency 评分

### 9.3 主要模块

- `CandidateGenerator`
- `CandidateRanker`
- `ReflectionUpdater`

### 9.4 计划改动

建议升级：

- [pipeline/stage2_plot/debate_graph.py](D:\Repos\TaiJianKiller\pipeline\stage2_plot\debate_graph.py)
- [pipeline/stage2_plot/agent_nodes.py](D:\Repos\TaiJianKiller\pipeline\stage2_plot\agent_nodes.py)
- [pipeline/stage3_generation/chapter_generator.py](D:\Repos\TaiJianKiller\pipeline\stage3_generation\chapter_generator.py)
- [pipeline/stage3_generation/quality_checker.py](D:\Repos\TaiJianKiller\pipeline\stage3_generation\quality_checker.py)

建议新增：

- `core/services/reflection/reflection_updater.py`
- `core/services/reflection/candidate_ranker.py`

### 9.5 关键能力

- 每章允许多个 skeleton 候选
- 每章允许多个正文候选
- 评分不仅看一致性，也看新意和 arc 推进
- 章节完成后自动回写上层状态

### 9.6 验收标准

- 章节执行使用 `ChapterBrief`
- 可配置候选数
- rerank 可独立测试
- 章节完成后世界状态更新

### 9.7 测试

- `tests/test_candidate_ranker.py`
- `tests/test_reflection_updater.py`
- `tests/test_quality_checker_v2.py`

---

## 10. M5 Web 工作台升级

### 10.1 目标

把现有 Web 看板升级为真正的创作工作台。

### 10.2 技术策略

这一阶段明确使用技能：

- `fullstack-dev`
- `frontend-dev`

前者保证接口与数据流设计正确，后者负责 UI 语言、信息层级和交互表现。

### 10.3 主要工作

- 展示 `WorldModel`
- 展示 `ArcOutline`
- 展示 `ChapterBrief`
- 展示 Lorebook 与参考层
- 支持模式切换：`strict / balanced / expansive`
- 支持预算配置
- 支持人工批准/拒绝扩张项

### 10.4 计划改动

建议新增：

- `webapp/routes/world.py`
- `webapp/routes/planning.py`
- `webapp/routes/references.py`

建议升级：

- [webapp/app.py](D:\Repos\TaiJianKiller\webapp\app.py)
- [webapp/manager.py](D:\Repos\TaiJianKiller\webapp\manager.py)
- [webapp/models.py](D:\Repos\TaiJianKiller\webapp\models.py)
- [webapp/static/index.html](D:\Repos\TaiJianKiller\webapp\static\index.html)
- [webapp/static/styles.css](D:\Repos\TaiJianKiller\webapp\static\styles.css)
- [webapp/static/app.js](D:\Repos\TaiJianKiller\webapp\static\app.js)

### 10.5 页面结构

- Session Dashboard
- World Board
- Arc Board
- Chapter Workspace
- Lorebook Panel
- Reference Mixer
- Benchmark Lab

### 10.6 验收标准

- 前端可查看世界状态与中期大纲
- 前端可配置扩张预算与模式
- 前端可展示章节计划与候选结果
- 前端可展示 benchmark 结果

### 10.7 测试

- `tests/test_web_app.py`
- `tests/test_web_manager.py`
- 新增前端接口测试
- 必要时补 Playwright 烟测

---

## 11. M6 验证、benchmark 与发布收尾

### 11.1 目标

验证 V2 在真实长篇样本上优于当前 V1 / baseline，并完成交付文档。

### 11.2 主要工作

- 增加 V2 benchmark 维度
- 对比 V1 / V2 / baseline
- 跑真实长篇样本
- 更新 README / DESIGN / 运行手册

### 11.3 验证样本

建议至少覆盖：

- 《斗破苍穹》前 50 章续写第 51 章
- 更长跨度续写，如前 50 章续写后续 5 到 10 章
- 一个非升级流样本，避免过拟合单一题材

### 11.4 验收标准

- V2 在世界一致性、新意、arc 推进上整体优于 V1
- Web 工作台可支撑完整流程
- 测试、文档、benchmark 全同步

### 11.5 测试与验证

- 全量 `pytest`
- Web 端到端烟测
- 真实 benchmark
- 长文本连续运行验证

---

## 12. 模块级依赖顺序

实施顺序必须遵循以下依赖：

1. 模型层
2. 世界层
3. 规划层
4. Lorebook / 参考层
5. 执行层升级
6. Web 工作台
7. benchmark 与发布

不能先做的事情：

- 不能先做前端后补世界层
- 不能先做参考层而没有规划层承接
- 不能先做多候选而没有新的评估体系

---

## 13. 每个 milestone 的交付模板

每个 milestone 完成时必须满足以下清单：

### 13.1 代码

- 新模块实现完成
- 旧模块重构完成
- 接口接通

### 13.2 测试

- 新增测试通过
- 回归测试通过
- 关键烟测通过

### 13.3 文档

- README 更新
- 设计文档更新
- 新配置项写入 `.env.example`

### 13.4 版本动作

- 若 Git 可用：立即 `commit` + `push`
- 当前环境下：记录为“待仓库恢复后补提交”

---

## 14. 配置项规划

V2 需要新增以下关键配置：

- `TAIJIAN_MODE=strict|balanced|expansive`
- `TAIJIAN_ARC_LENGTH`
- `TAIJIAN_WORLD_REFRESH_INTERVAL`
- `TAIJIAN_NEW_CHARACTER_BUDGET`
- `TAIJIAN_NEW_LOCATION_BUDGET`
- `TAIJIAN_NEW_FACTION_BUDGET`
- `TAIJIAN_TWIST_BUDGET`
- `TAIJIAN_REFERENCE_MODE=off|assist|strong`
- `TAIJIAN_REFERENCE_SCOPE=theme|structure|world|character`
- `TAIJIAN_CANDIDATE_COUNT`

---

## 15. 风险控制

### 15.1 技术风险

- 编排器复杂度急剧上升
- LLM 成本增加
- 世界状态与实际正文漂移
- 参考层用得过重导致“拼贴感”

### 15.2 控制方案

- 每层保持明确边界
- 增量引入，先验证再扩
- 每个里程碑单独跑 benchmark
- 所有上层状态都必须回写并可复盘

---

## 16. 推荐实际执行顺序

实际开发时按下面顺序推进：

1. `M0` 建模与基础重构
2. `M1` 世界层
3. `M2` 规划层
4. `M4` 执行层升级
5. `M3` Lorebook 与参考层
6. `M5` Web 工作台
7. `M6` benchmark 与收尾

原因：

- 执行层必须尽早接上 `ChapterBrief`
- 参考层必须在规划层稳定后接入
- 前端必须建立在稳定数据模型之上

---

## 17. 第一阶段立即动作

按本路线图，下一步立即执行：

1. 新增 V2 模型文件
2. 把现有阶段 1 升级为可输出 `WorldModel`
3. 给编排器加入世界刷新入口
4. 保持 V1 命令可运行
5. 为 `ArcPlanner` 预留接入点

---

## 18. 一句话总结

V2 的开发方式不是“想到什么做什么”，而是严格按：

> 世界层 -> 规划层 -> 执行层 -> 参考层 -> 工作台 -> benchmark

这个顺序逐步推进，直到 [DESIGN_V2.md](D:\Repos\TaiJianKiller\DESIGN_V2.md) 中定义的能力全部落地。

# 太监杀手 V2 整体设计

## 1. 文档目标

本文档定义 `TaiJianKiller V2` 的整体设计，作为当前 V1/MVP 之后的下一阶段架构基线。

V2 的目标不是简单把现有单章续写做得更快，而是把系统升级为一个可长期运行的“连载引擎”：

- 能持续生成多章，而不是只擅长单章续写
- 能在保持一致性的前提下，引入新人物、新地图、新势力和新阶段
- 能从前文自动抽取世界状态与中期大纲，而不是永远围绕旧伏笔保守打转
- 能接入“参考层”，借主题、结构、气质与人物弧线做高层迁移，而不是直接复制文本
- 能给前端提供真正的“创作工作台”能力，而不是仅仅上传文件和看结果

---

## 2. V1 现状与问题

### 2.1 V1 已有能力

V1 已经完成以下核心链路：

- 原著文本导入
- 风格画像提取
- 当前剧情状态抽取
- LightRAG 索引与检索
- 多 Agent 情节博弈
- 章节骨架生成
- 正文生成与润色
- 质量检查与会话持久化
- benchmark 对照评测
- Web 上传与运行看板

### 2.2 V1 的结构性短板

V1 的主要短板不在“能不能生成”，而在“能不能长期生成得好”：

- 规划粒度过低：核心仍是单章级 `Chapter Goal`
- 世界状态更新不足：连续跑多章时，`story_state` 只在运行开头刷新一次
- 自动策略过保守：默认只会围绕旧伏笔和旧冲突推进
- 缺少中期大纲层：没有 3 到 10 章级别的规划器
- 缺少世界扩张机制：新人物、新地图、新势力没有稳定的生成出口
- 缺少参考层：系统只能从前文检索，不擅长高层灵感迁移
- 缺少“新意”评价：当前质检主要奖励连续性，不奖励阶段升级和结构突破

### 2.3 V2 需要解决的核心问题

V2 要解决的，不是“写一章更像原著”，而是下面四个问题：

1. 如何避免长期续写越来越保守
2. 如何自动决定何时收旧线、何时开新盘
3. 如何让世界扩张自然发生，而不是靠手工提示
4. 如何让“参考”成为结构与气质迁移，而不是内容拼贴

---

## 3. V2 产品定位

`TaiJianKiller V2` 定位为：

> 一个面向中文长篇连载小说的世界建模 + 中期规划 + 单章执行一体化创作引擎。

它不是：

- 纯聊天式酒馆产品
- 单纯的 prompt 集合
- 只会补全一章的文本续写器
- 只追求风格模仿的“模仿器”

它应该更像：

- 一个具有世界状态、规划能力、参考能力和回写能力的小说导演系统

---

## 4. 设计原则

### 4.1 分层而非混写

世界事实、角色状态、中期规划、单章目标、正文生成必须分层。

### 4.2 默认自动，允许强配置

默认不要求用户手工写大纲；但允许用户控制扩张强度、新人物预算、新地图预算等高层策略。

### 4.3 一致性优先，但不以保守换一致性

V2 仍然把一致性视为底线，但不能因为追求不崩而拒绝世界扩张。

### 4.4 参考只能作用于抽象层

参考层只能迁移主题、结构、气质和弧线，不能直接迁移文本或可识别桥段。

### 4.5 每章生成都要能回写上层状态

章节不是输出即结束，必须更新世界模型、角色弧线、伏笔状态和中期大纲。

### 4.6 面向长篇运行优化

V2 的默认目标是连续生成 20 到 100 章仍然具备可控性。

---

## 5. 总体架构

V2 从 V1 的“三阶段流水线”升级为“五层架构”。

### 5.1 五层结构

1. `Canon Layer`
- 原著正文
- 已生成章节
- 风格画像
- 不可违背的硬设定

2. `World Layer`
- 世界模型
- 角色状态
- 势力状态
- 地图状态
- 规则体系
- 长期未解谜团

3. `Planning Layer`
- 卷级大纲
- 中期规划
- 扩张预算分配
- 参考层规划
- 单章任务拆解

4. `Execution Layer`
- 多 Agent 博弈
- 骨架生成
- 正文生成
- 多候选重采样
- 章节质检

5. `Reflection Layer`
- 世界状态回写
- 角色弧线更新
- 伏笔推进统计
- 新意评估
- 下一轮重规划触发

### 5.2 数据流

```text
原著 + 已生成章节
  -> 世界建模
  -> 中期规划
  -> 单章拆解
  -> 情节博弈
  -> 正文生成
  -> 质检与重排
  -> 回写世界与大纲
```

---

## 6. 核心模块

### 6.1 World Builder

负责从原著与续写中构建 `WorldModel`。

职责：

- 抽取稳定世界事实
- 维护主要人物状态
- 维护主要势力关系
- 维护已知地图与活动区域
- 维护修炼/规则体系
- 维护长期未解谜团
- 输出可供规划层使用的结构化状态

### 6.2 Memory Compressor

负责把长篇文本拆成不同层级的记忆：

- 最近章节：保留近原文
- 中期内容：摘要压缩
- 长期内容：进入世界模型
- 专项设定：进入 Lorebook

职责：

- 减少上下文污染
- 避免所有历史内容一起塞给模型
- 保持“近、中过去、远过去”三层时间感

### 6.3 Lorebook Manager

借鉴酒馆体系中的世界书设计，但服务于小说生产。

职责：

- 管理设定条目
- 支持优先级与作用域
- 支持动态命中
- 区分硬设定与软氛围
- 控制注入预算

### 6.4 Arc Planner

负责生成 `ArcOutline`，即 3 到 10 章级别的中期大纲。

职责：

- 定义当前小卷/小阶段目标
- 定义需要回收的伏笔
- 定义需要埋设的新伏笔
- 定义新人物、新地图、新势力的进入窗口
- 定义 twist、升级和卷终收束点

### 6.5 Expansion Allocator

负责自动决定何时允许“结构性新引入”。

职责：

- 分配新人物预算
- 分配新地图预算
- 分配新势力预算
- 分配反转预算
- 判断当前处于收束期还是扩张期

### 6.6 Reference Planner

负责把外部参考转换成抽象影响，而非具体内容。

职责：

- 管理参考源
- 抽取主题/结构/气质/人物弧线
- 生成当前 arc 的参考混合方案
- 输出允许影响的维度与禁止复用的边界

### 6.7 Chapter Allocator

把 `ArcOutline` 拆成单章级 `ChapterBrief`。

职责：

- 生成单章目标
- 生成本章 Author’s Note / Chapter Note
- 标记 must happen / may happen / must not break
- 决定本章是否允许引入新内容

### 6.8 Chapter Executor

继承 V1 的优势，继续负责：

- 多 Agent 辩论
- 骨架生成
- 正文生成
- 质量检查

但它不再直接从“当前剧情摘要”开写，而是严格消费 `ChapterBrief`。

### 6.9 Reflection Updater

负责把每章结果回写上层状态。

职责：

- 更新世界模型
- 更新角色状态
- 更新地图状态
- 更新势力状态
- 更新伏笔状态
- 判断是否需要重做 `ArcOutline`

---

## 7. 核心数据模型

### 7.1 WorldModel

```json
{
  "title": "string",
  "canon_facts": [],
  "power_system_rules": [],
  "main_characters": [],
  "active_factions": [],
  "known_locations": [],
  "world_tensions": [],
  "open_mysteries": [],
  "expansion_slots": []
}
```

字段说明：

- `canon_facts`
  硬设定，不可随意违反
- `power_system_rules`
  修炼体系、世界规则、限制条件
- `main_characters`
  角色当前状态、目标、关系、阶段位置
- `active_factions`
  当前活跃势力和势力间张力
- `known_locations`
  当前可用地图节点与地图层级
- `world_tensions`
  目前世界层面的高压矛盾
- `open_mysteries`
  长期悬而未决的问题
- `expansion_slots`
  允许未来扩张的机会位

### 7.2 CharacterArc

```json
{
  "character_name": "string",
  "current_state": "string",
  "core_wants": [],
  "hidden_pressure": [],
  "recent_change": "string",
  "arc_direction": "string",
  "taboos": []
}
```

### 7.3 FactionState

```json
{
  "name": "string",
  "public_goal": "string",
  "hidden_goal": "string",
  "current_resources": [],
  "relation_map": [],
  "threat_level": "low|medium|high"
}
```

### 7.4 LocationState

```json
{
  "name": "string",
  "location_type": "string",
  "importance": "string",
  "connected_locations": [],
  "current_risk": [],
  "story_function": "string"
}
```

### 7.5 ArcOutline

```json
{
  "arc_id": "string",
  "arc_theme": "string",
  "arc_goal": "string",
  "chapters_span": [1, 5],
  "required_payoffs": [],
  "required_setups": [],
  "new_character_plan": [],
  "new_location_plan": [],
  "new_faction_plan": [],
  "twist_plan": [],
  "exit_condition": "string"
}
```

### 7.6 ChapterBrief

```json
{
  "chapter_number": 51,
  "chapter_goal": "string",
  "chapter_note": "string",
  "must_happen": [],
  "may_introduce": [],
  "must_not_break": [],
  "tone_target": "string",
  "focus_threads": [],
  "allowed_expansion": {
    "new_character": false,
    "new_location": true,
    "new_faction": false
  }
}
```

### 7.7 ReferenceProfile

```json
{
  "name": "string",
  "reference_type": "theme|structure|world|character",
  "abstract_traits": [],
  "allowed_influences": [],
  "forbidden_copying": [],
  "use_scope": "arc|chapter"
}
```

### 7.8 ExpansionBudget

```json
{
  "mode": "strict|balanced|expansive",
  "new_character_budget": 1,
  "new_location_budget": 1,
  "new_faction_budget": 0,
  "twist_budget": 1,
  "reveal_budget": 2
}
```

---

## 8. 自动分配机制

### 8.1 设计目标

自动分配器负责回答：

- 接下来几章该收线还是开线
- 这一段是否允许世界扩张
- 该扩张到什么程度

### 8.2 输入信号

- 未解伏笔数量
- 未解伏笔老化程度
- 最近 3 到 5 章是否重复
- 最近是否长期没有新人物/新地图
- 当前冲突是否接近结束
- 角色关系是否停滞
- 世界边界是否过于封闭
- 当前 arc 是否缺少升级点

### 8.3 输出策略

输出以下决策：

- `arc_phase`: `setup / escalation / collision / payoff / cooldown`
- `expansion_mode`: `hold / light / medium / strong`
- `new_character_budget`
- `new_location_budget`
- `new_faction_budget`
- `twist_budget`
- `replanning_required`

### 8.4 默认模式

#### strict

- 优先回收旧伏笔
- 极少引入新地图
- 极少引入新人物
- 适合贴原著补完

#### balanced

- 默认模式
- 每 3 到 5 章允许一次结构性新引入
- 优先自然扩张，不追求大爆炸式拓展

#### expansive

- 主动扩世界
- 主动给出新人物、新地图、新势力窗口
- 但必须保证与旧主线有因果连接

---

## 9. 参考层设计

### 9.1 目标

参考层不是为了“模仿某部作品”，而是为了让系统具备：

- 主题迁移
- 结构迁移
- 世界气质迁移
- 人物弧线迁移

### 9.2 可借鉴内容

- 主题张力
- 卷结构
- 群像调度
- 社会层次感
- 命运感
- 世界氛围
- 人物成长弧线

### 9.3 禁止内容

- 直接引用原文
- 直接复刻桥段
- 直接复刻角色关系
- 可识别的情节映射

### 9.4 参考的作用位置

参考层应主要作用于：

- `WorldModel` 的扩张机会定义
- `ArcOutline` 的主题与结构
- `ChapterBrief` 的基调与约束

不应直接把参考文本塞进正文生成 prompt。

---

## 10. 酒馆经验映射

V2 应吸收酒馆体系中最有价值的工程经验。

### 10.1 Lorebook

从全量设定改为动态命中设定。

### 10.2 Author’s Note

为每章或每几章提供导演注释。

### 10.3 多层记忆

- 最近章节：原文
- 中期章节：摘要
- 长期状态：世界模型

### 10.4 角色卡增强

角色卡从“摘要”升级为“行为驱动器”。

### 10.5 多候选与重排

允许：

- 多个骨架候选
- 多个开头候选
- 多个正文候选
- rerank 选优

---

## 11. 生成流程

V2 的单次运行建议如下：

1. 读取原著与已有续写
2. 刷新 `WorldModel`
3. 压缩记忆并更新 `Lorebook`
4. 判断是否需要生成或重做 `ArcOutline`
5. 生成 `ExpansionBudget`
6. 生成当前章节的 `ChapterBrief`
7. 运行情节博弈
8. 生成 `ChapterSkeleton`
9. 生成正文候选
10. 执行质检与重排
11. 选择最终候选
12. 回写世界状态与角色状态
13. 判断是否触发下一轮中期规划

---

## 12. 评估体系

V2 的评估不再只看一致性。

### 12.1 五维评分

- `continuity_score`
- `character_score`
- `world_consistency_score`
- `novelty_score`
- `arc_progress_score`

### 12.2 新增检测项

- 最近 N 章是否高度重复
- 是否长期无世界扩张
- 是否始终围绕同一伏笔打转
- 新人物/新地图是否自然接入
- 当前章节是否服务于 arc 目标

### 12.3 阈值策略

可配置：

- 最低连续性阈值
- 最低世界一致性阈值
- 最低新意阈值
- 最低 arc 推进阈值

如果连续性达标但新意长期低于阈值，应触发 `replanning_required`。

---

## 13. 存储方案

### 13.1 设计方向

V2 建议从“纯 JSON 文件系统”升级为“结构化元数据 + 文件产物”混合存储。

### 13.2 建议方案

- `SQLite`
  存 session、world model、arc outline、chapter brief、evaluation 结果
- `文件系统`
  存正文、草稿、骨架、报告
- `LightRAG`
  存检索索引与知识图谱

### 13.3 原则

- JSON 仍然保留导出能力
- 所有关键状态可以回放
- 所有世界状态变更都应有版本快照

---

## 14. 前端工作台

V2 前端应从运行面板升级为创作工作台。

### 14.1 主要页面

- `Session Dashboard`
- `World Board`
- `Arc Board`
- `Chapter Workspace`
- `Lorebook`
- `Reference Mixer`
- `Benchmark Lab`

### 14.2 用户能力

- 上传原著
- 选择模式：`strict / balanced / expansive`
- 配置新人物/新地图预算
- 锁定硬设定
- 查看世界状态演进
- 查看当前 arc 大纲
- 人工批准或否决扩张项
- 查看 benchmark 对照结果

---

## 15. 与现有代码的演进路径

V2 不建议推倒重来，应基于现有代码逐步演进。

### 15.1 可以直接复用的模块

- `LightRAGStore`
- `LiteLLMService`
- `ChapterGenerator`
- `QualityChecker`
- `Web API` 基础结构
- `benchmark` 基础框架

### 15.2 优先重构的模块

- `style_analyzer.py`
  从风格分析器升级为 `world_builder`
- `orchestrator.py`
  从单流水线升级为层级式编排器
- `agent_nodes.py`
  注入 `ChapterBrief`、更强角色卡与导演注释
- `quality_checker.py`
  增加新意、世界一致性、arc 推进三类评分

---

## 16. 分阶段实施计划

### Phase 1: 世界层

- 新增 `WorldModel`
- 新增 `CharacterArc / FactionState / LocationState`
- 引入周期性世界刷新

### Phase 2: 规划层

- 新增 `ArcOutline`
- 新增 `ChapterBrief`
- 新增 `ExpansionAllocator`

### Phase 3: 参考层

- 新增 `ReferenceProfile`
- 新增 `ReferencePlanner`
- 新增参考注入配置

### Phase 4: 执行层升级

- 多候选骨架
- 多候选正文
- rerank 机制

### Phase 5: 工作台

- 世界面板
- arc 面板
- 参考层面板
- benchmark 实验台

---

## 17. 风险与边界

### 17.1 风险

- 世界模型过硬，导致新的锁死
- 参考层过强，导致拼贴感
- 扩张预算过高，导致跑偏
- 规划层过重，导致成本和延迟显著上升

### 17.2 边界控制

- 硬设定与软机会必须严格区分
- 参考层只能输出抽象影响
- 扩张必须有因果连接
- 每一章都要回写并重新校验世界状态

---

## 18. 成功标准

V2 的成功不等于“写得更像原著”，而是同时满足：

- 连续生成 20 到 50 章不明显塌陷
- 可以自然出现新人物、新地图、新势力
- 中期剧情有可见阶段升级
- 前后文设定不明显矛盾
- benchmark 中系统版长期优于直接单模型续写
- 前端可以直接展示世界状态、arc 状态和章节计划

---

## 19. 一句话总结

`TaiJianKiller V2 = 世界模型 + 中期大纲 + 自动扩张预算 + 参考层 + 单章执行引擎`

它的目标不是只把当前这一章写好，而是把未来几十章写得既稳又能长出新东西。

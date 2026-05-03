# TaiJianICU 实现计划

## Context

用户沉迷网络小说，希望用 AI 续写被腰斩的小说。纯文本续写会导致内容发散，参考 MiroFish 的群体智能思路，引入多 Agent 情节博弈层来锚定故事方向，再由文本生成层负责文笔还原。

**核心分层原则：**
- 层1（情节模拟）解决一致性问题
- 层2（文本生成）解决可读性问题

---

## 架构总览

```
原著文本
  ↓
[阶段1] 知识提取 → LightRAG 知识图谱（Gemini 2.5 Pro 大上下文）
  → 自动提取：人物/关系/世界观/情节事件/伏笔
  → 文风特征（StyleProfile）
  ↓
[阶段2] 情节生成（多 Agent 辩论）
  → Character Agent（每个主角一个）
  → Author Agent（上帝视角仲裁）
  → 3轮辩论：宣告目标 → 交锋 → 仲裁
  → 每轮从 LightRAG 按需检索相关记忆
  → ChapterSkeleton（结构化骨架）
  ↓
[阶段3] 文本生成（Claude Sonnet 4.6）
  → 按场景逐个生成草稿
  → 从 LightRAG 检索相似原著段落作 few-shot（风格对齐）
  → 质量评估 + 输出
  → 新生成章节增量写入 LightRAG（供后续章节检索）
```

---

## 技术选型（最大化使用现有库）

### 总览

| 自建 ❌ | 现成库 ✅ | 省掉的工作 |
|--------|---------|-----------|
| 各 LLM Client（4个文件） | **LiteLLM** | 统一接口，自动 token 计费，错误处理 |
| 知识图谱+向量检索 | **LightRAG** | 图谱构建、双层检索、增量更新 |
| 多 Agent 辩论框架 | **LangGraph** | 状态管理、循环控制 |
| LLM 结构化输出解析 | **Instructor** | 自动将 LLM 输出解析为 Pydantic 模型，自动重试 |
| 输出质量评估 | **DeepEval (G-Eval)** | 自定义评估标准，LLM-as-judge |
| 文本分块 | **LangChain TextSplitter** | 章节识别、滑窗切割 |

---

### 1. LiteLLM：统一 LLM 接口

替代 `gemini_client.py` + `deepseek_client.py` + `claude_client.py` + `token_tracker.py`（4个文件 → 0）

```python
from litellm import completion, acompletion

# 切换模型只改字符串，接口完全一致
resp = await acompletion(model="deepseek/deepseek-chat", messages=[...])
resp = await acompletion(model="gemini/gemini-2.5-pro", messages=[...])
resp = await acompletion(model="anthropic/claude-sonnet-4-6", messages=[...])

# 自动 Token 成本追踪
print(resp.usage.total_tokens)
```

LiteLLM 自动处理：各厂商 API 差异、错误重试、token 计费、流式输出。

---

### 2. LangGraph：辩论引擎 + 状态管理

替代 `debate_engine.py` + `character_agent.py` + `author_agent.py`（核心逻辑复杂度大幅降低）

**选 LangGraph 而非 AutoGen 的原因：**
- AutoGen 已转为维护模式（Microsoft 转向 Microsoft Agent Framework）
- LangGraph v1.0（2025年底）是 production-grade，状态管理精确可控
- 我们的 3 轮辩论是**有固定结构的流图**，非自由对话——LangGraph 的图节点模型完美匹配

**辩论流图设计：**
```
[start]
  → [load_context]      # 从 LightRAG 检索每个 Agent 需要的记忆
  → [round1_propose]    # 每个 CharacterAgent 提出行动方案
  → [round2_debate]     # Agent 互相阅读并反驳
  → [round3_arbitrate]  # AuthorAgent 仲裁
  → [build_skeleton]    # 结构化输出 ChapterSkeleton
  → [consistency_check] # 检查是否违规
  → [end] 或 [round1_propose] (违规时循环，最多2次)
```

---

### 3. Instructor：结构化输出（最关键的新增）

替代 `skeleton_builder.py` 中所有手动 JSON 解析逻辑。这是最容易出 bug 的环节（LLM 输出不规范、字段缺失、格式错误），Instructor 自动处理重试和验证：

```python
import instructor
from pydantic import BaseModel

class SceneNode(BaseModel):
    scene_type: str
    participants: list[str]
    scene_purpose: str
    estimated_word_count: int

class ChapterSkeleton(BaseModel):
    scenes: list[SceneNode]
    threads_to_close: list[str]
    chapter_theme: str

# 直接得到类型安全的 ChapterSkeleton，失败自动重试
client = instructor.from_litellm(completion)
skeleton = client.chat.completions.create(
    model="deepseek/deepseek-chat",
    response_model=ChapterSkeleton,
    messages=[{"role": "user", "content": debate_result}],
)
```

**影响：** `core/models/skeleton.py` 的所有数据结构直接用 Pydantic BaseModel（而非 dataclass），与 Instructor 无缝集成。

---

### 4. DeepEval：输出质量评估

替代自定义 `quality_checker.py`，使用 G-Eval 自定义评估标准：

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase

# 定义小说续写专用评估标准
consistency_metric = GEval(
    name="角色一致性",
    criteria="续写内容中，角色的行为是否符合其在原著中建立的性格和动机？",
    evaluation_steps=["检查主要角色的行为决策", "对照原著性格描述验证一致性"],
)
```

---

### 知识图谱：LightRAG（不自己造轮子）

**HKUDS/LightRAG**（28K+ stars，MIT license）原生实现了我们需要的全部能力：

| 我们的需求 | LightRAG 的对应能力 |
|-----------|-------------------|
| 提取人物/关系/世界观 | 自动实体+关系抽取，构建图谱 |
| 检索相关情节/伏笔 | 双层检索：实体精确查询（低层）+ 主题语义查询（高层）|
| 新章节生成后增量更新 | 支持 `ainsert()` 增量插入，不重建整个图 |
| 风格样例 few-shot 检索 | 内置向量相似检索 |

**选 LightRAG 而非 Microsoft GraphRAG 的原因：**
- GraphRAG 每次查询消耗 610,000 tokens，LightRAG 只需 100 tokens
- GraphRAG 不支持低成本增量更新（每次加新章节要重建社区图）
- LightRAG 的双层检索恰好对应两种查询：精确实体查询 + 主题检索

**接入方式（示例）：**
```python
from lightrag import LightRAG, QueryParam

rag = LightRAG(
    working_dir="./data/lightrag",
    llm_model_func=deepseek_complete,          # DeepSeek 做图谱构建（省成本）
    embedding_func=EmbeddingFunc(
        embedding_dim=1536,
        max_token_size=8192,
        func=openai_embedding,                  # text-embedding-3-small
    ),
)
await rag.ainsert(novel_text)                  # 首次插入全文
await rag.ainsert(new_chapter_text)            # 后续增量插入

# 检索（hybrid = 图谱 + 向量）
await rag.aquery("主角与反派之间的未解决仇恨？", param=QueryParam(mode="hybrid"))
```

### LLM 分工策略

> ⚠️ Gemini 2.0 Flash 将于 2026年6月1日停用，不得使用。

| 任务 | 推荐模型 | 原因 |
|------|---------|------|
| LightRAG 图谱构建（一次性） | **Gemini 2.5 Pro** | 1M context，$1.25/M，一次处理整部小说 |
| Agent 辩论轮次（高频） | **DeepSeek V3.2** | 中文第一，$0.28/M input，成本约为 GPT 的 1/10 |
| AuthorAgent 仲裁 | **DeepSeek V3.2** | 中文叙事逻辑，成本极低 |
| 最终文本生成 | **Claude Sonnet 4.6** | 写作最像人类，"几乎无 AI 味" |
| 质量检查/分类 | **GPT-5.4 nano** | $0.20/M，最便宜，简单判断足够 |

**OpenAI GPT-5 系列（2026年3月）：**
- `gpt-5.4` — $2.50/$15，1.05M context，旗舰
- `gpt-5.4-mini` — $0.75/$4.50，400K context，2×更快
- `gpt-5.4-nano` — $0.20/$1.25，分类/简单任务
- `gpt-5` — $1.25/$10，上一代旗舰，性价比仍强

**预估每章成本：** ~$0.02
- LightRAG 图谱检索：~1,000 tokens × $0.28/M × N次 ≈ **$0.001**
- 辩论3轮×4 Agent：~8,000 tokens × $0.28/M ≈ **$0.002**
- 最终文本生成（3,000字）：~6,000 tokens × $3/M ≈ **$0.018**

---

## 项目目录结构

```
TaiJianICU/
├── pyproject.toml
├── .env.example
├── config/
│   ├── settings.py                 # 全局配置（模型路由、路径）
│   └── prompts/                    # 所有 Prompt 模板（与代码分离）
│       ├── agents/
│       │   ├── character_agent.txt
│       │   ├── author_agent.txt
│       │   └── style_extract.txt
│       └── generation/
│           ├── chapter_draft.txt
│           └── style_polish.txt
├── core/
│   ├── models/                     # 核心数据结构（只保留自定义部分）
│   │   ├── skeleton.py             # ChapterSkeleton, SceneNode, TurnPoint（Pydantic）
│   │   └── style_profile.py        # StyleProfile（文风特征）
│   └── storage/
│       ├── lightrag_store.py       # LightRAG 封装（知识图谱+向量）
│       └── session_store.py        # JSON 会话/断点状态
├── pipeline/
│   ├── stage1_extraction/
│   │   ├── novel_indexer.py        # 调用 LightRAG 建图（LangChain splitter 切块）
│   │   └── style_analyzer.py       # 文风特征提取 → StyleProfile
│   ├── stage2_plot/                # 情节生成（LangGraph 驱动）
│   │   ├── debate_graph.py         # LangGraph 图定义（节点+边）
│   │   ├── agent_nodes.py          # 各 Agent 节点函数（CharacterAgent/AuthorAgent）
│   │   ├── skeleton_builder.py     # 辩论结果 → ChapterSkeleton（Instructor 解析）
│   │   └── consistency_checker.py
│   └── stage3_generation/
│       ├── style_sampler.py        # 从 LightRAG 检索相似原著段落
│       ├── chapter_generator.py
│       └── quality_checker.py      # DeepEval G-Eval
├── orchestrator.py                 # 主流水线（三阶段串联 + 干预节点）
├── intervention.py                 # 人工干预接口
├── cli/
│   ├── main.py
│   ├── run_cmd.py
│   ├── inspect_cmd.py
│   └── intervene_cmd.py
├── data/
│   ├── input/                      # 放置原著 TXT
│   ├── lightrag/                   # LightRAG 图谱数据（自动维护）
│   ├── sessions/                   # 运行会话状态
│   └── output/                     # 生成的续写章节
└── tests/
```

---

## 参考：SillyTavern 的 Prompt 设计经验

酒馆类应用（SillyTavern 等）与本项目的核心机制高度重合，可直接借鉴其社区积累的 Prompt 工程经验：

| SillyTavern 概念 | 我们的对应 | 借鉴点 |
|----------------|----------|-------|
| **角色卡（Character Card）** | `agent_nodes.py` 的 Prompt | 角色定义格式（人格/目标/说话习惯）经过社区大量验证 |
| **世界书（World Lorebook）** | LightRAG 知识图谱 | 语义触发注入的设计思路（我们用向量检索实现） |
| **Author's Note** | AuthorAgent 的系统 Prompt | 在消息历史特定深度注入"导演指令"影响生成方向 |
| **群聊模式** | LangGraph 辩论图 | 多角色按顺序发言的协调机制 |

**角色 Prompt 模板参考（`config/prompts/agents/character_agent.txt`）：**
```
[{{char}}的角色定义]
性格: {{personality_traits}}
核心目标: {{core_goals}}
口吻习惯: {{speech_style}}
当前状态: {{last_known_state}}
已知信息: {{recalled_memories}}

[行为约束]
- 严格遵守以上性格，不能做出与之矛盾的决定
- 以第一人称思考"我在这一章想达成什么"
- 输出格式：JSON，字段 goal/action_proposal/reasoning
```

---

## 核心数据结构

### ChapterSkeleton（情节骨架，两层之间的接口契约）
```python
from pydantic import BaseModel

class SceneNode(BaseModel):
    scene_type: str                 # "对话" | "战斗" | "内心独白" | "叙述"
    participants: list[str]         # 角色名列表
    scene_purpose: str              # 此场景在情节中的作用
    estimated_word_count: int

class ChapterSkeleton(BaseModel):
    chapter_number: int
    chapter_theme: str
    scenes: list[SceneNode]
    threads_to_advance: list[str]   # 本章推进的伏笔 ID
    threads_to_close: list[str]     # 本章收束的伏笔 ID
    agent_consensus_log: list[dict] # 辩论过程记录（可溯源）
    was_human_revised: bool = False
```

---

## 伏笔追踪机制

LightRAG 图谱记录实体间关系。额外维护 `data/sessions/unresolved_threads.json`：

```json
{
  "threads": [
    {"id": "T001", "desc": "旧案证人的下落", "introduced_at": 12, "last_advanced": 45},
    {"id": "T002", "desc": "黑衣人的真实目的", "introduced_at": 30, "last_advanced": 30}
  ]
}
```

`consistency_checker` 检查超过 N 章未推进的伏笔，自动注入下一章辩论议题，防止伏笔遗忘。

---

## 人工干预节点（4个）

1. **图谱确认**（阶段1完成后）— 运行 `taijianicu inspect`，查看并补充遗漏的伏笔/关系
2. **辩论议题注入**（每章辩论前）— 在 `data/sessions/chapter_N_config.json` 预设"本章必须发生的事"
3. **骨架审阅**（`--pause-after-skeleton`）— 直接编辑 `ChapterSkeleton` JSON
4. **初稿审阅**（`--pause-after-draft`）— 手动修改文本后程序继续润色

---

## 实现顺序

### MVP（目标：跑通一章续写）
1. `pyproject.toml` + `settings.py`（配置 LiteLLM 模型映射）
2. `core/models/skeleton.py`（ChapterSkeleton Pydantic 数据结构）
3. LightRAG 集成：`novel_indexer.py`（Gemini 2.5 Pro 建图）
4. LangGraph 辩论图：`debate_graph.py` + `agent_nodes.py`（2轮简化，DeepSeek）
5. 文本生成：`chapter_generator.py`（Claude Sonnet 4.6，无风格感知）
6. CLI 入口 `taijianicu run` + 端到端测试

### Beta（完善核心）
7. 风格感知：`style_analyzer.py` + `style_sampler.py`（LightRAG hybrid 检索 few-shot）
8. LangGraph 状态持久化（LangGraph 内置 checkpointer）
9. 一致性校验 + 违规触发循环（LangGraph conditional edge）
10. 断点续写 + 会话恢复
11. 新章节增量写入 LightRAG

### 完整版
12. 人工干预流程（4个节点完整实现）
13. 质量评分 + 自动重试（DeepEval G-Eval）
14. `taijianicu inspect` 可视化图谱
15. Rich 进度条 + 成本报告

---

## 关键文件（首先实现）

- `core/storage/lightrag_store.py` — LightRAG 封装，所有图谱操作的统一接口
- `core/models/skeleton.py` — 情节层与生成层的接口契约（Pydantic）
- `pipeline/stage2_plot/debate_graph.py` — LangGraph 辩论图，最核心的差异化模块
- `config/settings.py` — 模型路由和 Token 预算中心
- `orchestrator.py` — 三阶段串联 + 干预节点触发

---

## 验证方式

1. 准备一部有明确伏笔且授权边界清晰的小说前 50 章
2. 运行 `taijianicu run --input data/input/novel.txt --chapters 3`
3. 检查输出：
   - `data/lightrag/` 中是否正确建立了知识图谱
   - `data/sessions/chapter_N_skeleton.json` 骨架是否合理
   - `data/output/` 续写是否保持角色一致性、是否回收伏笔
4. 对比验证：直接 Claude 续写 vs 本系统输出，评估一致性提升程度

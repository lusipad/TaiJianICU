# 太监杀手

基于 `DESIGN.md` 落地的首版 DeepSeek 优先 MVP。目标是把原著索引、情节辩论、骨架生成、正文生成串成一个可运行的命令行流水线。

设计文档：

- `DESIGN.md`：V1 / MVP 设计
- `DESIGN_V2.md`：V2 整体设计
- `ROADMAP_V2.md`：V2 实施路线图

## 当前实现

- 阶段 1：原著切块、LightRAG 建索引、风格画像与故事状态抽取
- 阶段 2：LangGraph 多 Agent 情节博弈，输出 `ChapterSkeleton`
- 阶段 3：按骨架生成章节正文，做一次轻量润色，并运行质量检查
- V2 执行层已接入 `WorldModel`、`ArcOutline`、`ChapterBrief` 与 `Lorebook` 命中结果，不再只把它们落盘而不参与主链路
- V2 参考层已接入默认 `ReferenceProfile`，只作用于规划层抽象约束，不直接要求正文模仿
- 每章结束后会生成 `ChapterEvaluation`，为后续 rerank / reflection / 工作台展示提供结构化评估
- 执行层支持 skeleton / draft 多候选生成与 rerank，可通过 CLI / Web 配置候选数
- 章节完成后会增量刷新 `WorldModel`，并把候选骨架 / 候选正文落盘到会话目录
- 基准：内置“系统 vs 单模型 baseline vs 真实后续”对照实验
- Web：上传 `.txt`、提交任务、轮询进度、查看摘要/产物路径/历史任务
- Web：侧边栏可直接查看 Benchmark Lab 对照报告、胜负结论、分项摘要和落盘路径
- Web：新建任务时可直接配置 `style/plot/draft/quality/LightRAG` 模型路由，支持“下拉候选 + 自定义输入”
- CLI：`taijian run` / `taijian benchmark` / `taijian web` / `taijian inspect` / `taijian intervene`
- 会话：保存阶段 1 快照、每章骨架、草稿、输出正文、伏笔状态

## 运行环境

- Python 3.11 - 3.14
- 建议使用项目内 `.venv`

## 安装

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
```

## 配置

复制 `.env.example` 到 `.env`，至少填入：

```env
DEEPSEEK_API_KEY=...
```

默认模型路由已经指向 DeepSeek：

- 情节规划：`deepseek/deepseek-chat`
- 正文生成：`deepseek/deepseek-chat`
- 质量评估：`deepseek/deepseek-chat`
- LightRAG 内部 LLM：`deepseek-chat`

当前默认 embedding 后端是 `local-hash`，这样只用 DeepSeek Key 就能先跑通 MVP。后续如果切到 `openai`，再补 `OPENAI_API_KEY`。

如果要把 Web 版公开到公网，建议额外设置最小门禁：

```env
TAIJIAN_WEB_USERNAME=admin
TAIJIAN_WEB_PASSWORD=change_me
TAIJIAN_WEB_MODEL_OPTIONS=deepseek/deepseek-chat,deepseek/deepseek-reasoner,openai/gpt-4.1-mini
TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP=3
TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS=3600
```

设置后，除 `/health` 和 `/ready` 外，其余页面和 API 都会启用 HTTP Basic Auth。

`TAIJIAN_WEB_MODEL_OPTIONS` 用来给 Web 表单提供候选模型列表；用户仍然可以直接输入任意 LiteLLM 支持的模型名覆盖默认路由。

`TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP` 和 `TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS` 用来限制公开站点上“内置样例一键试跑”的单 IP 额度；用户自己上传文本、或先把内置样例填入上传区后再使用自定义 endpoint / Key，不受这个入口限制。

如需调整 DeepSeek 调用容错，可额外配置：

```env
TAIJIAN_LLM_TIMEOUT_SECONDS=180
TAIJIAN_LLM_RETRY_ATTEMPTS=4
TAIJIAN_LLM_RETRY_BACKOFF_SECONDS=2
```

## 使用

运行一章：

```powershell
taijian run --input data/input/novel.txt --chapters 1
```

配置规划模式、预算和候选数：

```powershell
taijian run --input data/input/novel.txt --chapters 1 --planning-mode expansive --new-character-budget 2 --skeleton-candidates 2 --draft-candidates 3
```

续跑或断点恢复：

```powershell
taijian run --input data/input/novel.txt --chapters 3 --resume --use-existing-index
```

查看阶段产物：

```powershell
taijian inspect --session-name novel
```

针对已建立的会话查询 LightRAG：

```powershell
taijian inspect --session-name novel --query "主角和反派当前最大的矛盾是什么？"
```

导出当前故事图的 Mermaid：

```powershell
taijian inspect --session-name novel --export-mermaid data/sessions/novel/story_graph.mmd
```

创建人工干预脚手架：

```powershell
taijian intervene --session-name novel --chapter 1
```

运行内置对照基准：

```powershell
taijian benchmark --dataset sanguo --prefix-chapters 50 --target-chapter 51
```

对任意本地 TXT 做对照基准：

```powershell
taijian benchmark --dataset doupo --source-file data\input\doupo_50.txt --prefix-chapters 50 --target-chapter 51
```

对远程 TXT 直跑基准：

```powershell
taijian benchmark --dataset custom --source-url https://example.com/novel.txt --prefix-chapters 50 --target-chapter 51
```

启动 Web 工作台：

```powershell
taijian web
```

Web 工作台默认内置一个原创悬疑样例：

- 可以直接点「一键试跑原创样例」
- 也可以点「先填入样例文本」，把示例塞进上传区后，再改当前页面的 endpoint / Key 自己跑
- 总览里的正文预览会同时显示原文断点 / 上文衔接 和 AI 续写正文，方便直接看衔接是否顺

Web 表单里的模型配置与 API 覆盖都按“单次运行”生效，不会改写服务器全局默认值，也不会把当前页面输入的 API Key 落盘。

默认地址：

- `http://127.0.0.1:8000`
- `GET /`：landing 页面，展示原创示例与公开样例实证
- `GET /studio`：进入实际工作台
- `GET /health`
- `GET /ready`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/examples`
- `GET /api/examples/{example_id}`
- `GET /api/showcase`
- `GET /api/benchmarks`
- `GET /api/benchmarks/{dataset_name}/{case_name}`
- `POST /api/runs`
- `POST /api/examples/{example_id}/runs`

landing 页只使用仓库内原创样例 `data/input/sample_novel.txt` 及其本地公开续写结果；首页不再展示外部 benchmark 内容，避免把第三方作品片段作为公开宣传素材。

## 免费公网部署

当前仓库已经补了 [render.yaml](D:/Repos/TaiJianKiller/render.yaml) 和 [Dockerfile](D:/Repos/TaiJianKiller/Dockerfile)，可直接部署到 Render，也可复用到 Hugging Face Docker Spaces。

### Render

1. 把仓库导入 Render，创建 `Web Service`
2. Render 会自动识别 [render.yaml](D:/Repos/TaiJianKiller/render.yaml)
3. 至少配置这些环境变量：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
TAIJIAN_WEB_PASSWORD=change_me
TAIJIAN_WEB_ALLOWED_ORIGINS=https://your-service.onrender.com
```

4. 部署完成后访问 Render 分配的公网域名

注意：

- 免费实例会休眠
- `data/` 下的本地文件在平台重启后可能丢失
- 当前方案适合演示，不适合长期保存用户续写记录

### Hugging Face Spaces

1. 新建 `Docker Space`
2. 把当前仓库内容推到 Space 仓库
3. 在 Space Secrets 里配置：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
TAIJIAN_WEB_PASSWORD=change_me
TAIJIAN_WEB_ALLOWED_ORIGINS=https://<your-space>.hf.space
```

4. Space 会直接使用仓库内的 [Dockerfile](D:/Repos/TaiJianKiller/Dockerfile)

容器默认监听 `7860` 端口，也兼容 Render 注入的 `PORT`。

## 会话目录

- `data/sessions/<session>/stage1_snapshot.json`
- `data/sessions/<session>/selected_references.json`
- `data/sessions/<session>/chapter_N_config.json`
- `data/sessions/<session>/chapter_N_brief.json`
- `data/sessions/<session>/chapter_N_skeleton.json`
- `data/sessions/<session>/chapter_N_draft.md`
- `data/sessions/<session>/chapter_N_evaluation.json`
- `data/sessions/<session>/run_manifest.json`
- `data/output/<session>/chapter_N.md`
- `data/web/uploads/*.txt`
- `data/web/runs/*.json`
- `data/benchmarks/<dataset>/cases/<prefix>_to_<target>/report/benchmark_report.json`
- `data/benchmarks/<dataset>/cases/<prefix>_to_<target>/report/benchmark_report.md`

`run_manifest.json` 表示当前会话的累计清单。即使后续用 `--resume` 跳过已有章节，也会保留之前的质检结果、章节成本和阶段 1 成本汇总。

## 测试

```powershell
.\.venv\Scripts\python -m pytest
```

## 已验证链路

- 真实调用 DeepSeek 完成 `sample_novel.txt` 的 1 章续写
- `consistency_report.passed == true`
- `--resume --use-existing-index` 会跳过已有正文，同时保留会话累计成本清单
- `taijian inspect --export-mermaid ...` 可正常导出 Mermaid 故事图
- Web 首页、健康检查、上传接口与历史任务接口已通过自动化测试
- 已跑通 `taijian benchmark --dataset sanguo --prefix-chapters 50 --target-chapter 51`
- 对照结果：系统版胜过单模型 baseline，pairwise `winner=system`，`confidence=0.85`
- 该轮基准总成本约 `0.04183 USD`，总 tokens `212110`

## 基准说明

- 当前内置公开可复现数据集是 `sanguo`，会自动下载 GitHub 上的《三国演义》文本，取前 50 回续写第 51 回，并用真实第 51 回做评测。
- 评测输出包含单候选分项打分、pairwise 胜负、成本统计，以及系统版 / baseline / 真实参考章节的落盘路径。
- 长篇文本的阶段 1 已改为“双通道抽取”：风格从全局样本提取，当前剧情状态从最近章节单独刷新，避免续写时被早期剧情拖偏。

## 已知取舍

- 设计稿里的 Gemini / Claude / OpenAI 分工暂时统一收敛到 DeepSeek，先把主流程跑通。
- LightRAG 的 embedding 先用本地哈希向量兜底，避免在 MVP 阶段强依赖第二套密钥。
- 质量检查优先走 DeepEval，失败时自动降级为启发式规则检查。
- CLI 现在会输出每章 token 和成本汇总，成本统计基于 LiteLLM 的计费模型表。

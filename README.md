# TaiJianICU

TaiJianICU 是一个中文长篇续写实验系统。当前主线是“作者复活引擎”：不只生成后续剧情，而是用原文声口、章节节奏、人物状态、质量门和盲测闭环，评估续写到底像不像原作者。

这个仓库还在快速实验阶段。README 只放安装、运行和当前可信边界；实现细节和验证记录放在 `docs/` 与路线图里。

## 文档导览

- `docs/author-revival-engine-design.md`：作者复活引擎设计方案，解释为什么要从“剧情完整度”转向“作者相似度”。
- `ROADMAP_REVIVAL.md`：当前主线和下一步验证路线。
- `docs/revival-validation-status.md`：当前实现、红楼验证命令、质量门行为和已知缺口。
- `DESIGN.md`：V1 / MVP 设计。
- `DESIGN_V2.md`：V2 整体设计。
- `ROADMAP_V2.md`：V2 实施路线图，已降级为辅助参考。

## 当前状态

- CLI 和 Web 工作台都可以运行续写、查看会话产物和跑基准。
- 当前默认模型路由收敛到 DeepSeek，embedding 默认用本地哈希兜底。
- 红楼前 80 回到第 120 回的长链路已经跑通过一次，但旧流程暴露出短章、对白比例不足和后段声口漂移。
- 最新修复后，第 120 回单章回归通过 source-voice gate；连续后段 smoke 仍暴露出近章开头重复和 118-120 告警，详见验证状态文档。
- 当前全量 `pytest` 通过。

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

`TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP` 和 `TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS` 用来限制公开站点上“按当前配置重跑”的单 IP 额度；默认的“快速试看”直接复用仓库内预计算结果，不消耗当前页面填写的 endpoint / Key，也不占用试用额度。用户自己上传文本、或填写自定义 endpoint / Key 后重跑样例，同样不受这个默认试用额度限制。

如需调整 DeepSeek 调用容错，可额外配置：

```env
TAIJIAN_LLM_TIMEOUT_SECONDS=180
TAIJIAN_LLM_RETRY_ATTEMPTS=4
TAIJIAN_LLM_RETRY_BACKOFF_SECONDS=2
```

## 使用

运行一章：

```powershell
taijianicu run --input data/input/novel.txt --chapters 1
```

配置规划模式、预算和候选数：

```powershell
taijianicu run --input data/input/novel.txt --chapters 1 --planning-mode expansive --new-character-budget 2 --skeleton-candidates 2 --draft-candidates 3
```

续跑或断点恢复：

```powershell
taijianicu run --input data/input/novel.txt --chapters 3 --resume --use-existing-index
```

查看阶段产物：

```powershell
taijianicu inspect --session-name novel
```

针对已建立的会话查询 LightRAG：

```powershell
taijianicu inspect --session-name novel --query "主角和反派当前最大的矛盾是什么？"
```

导出当前故事图的 Mermaid：

```powershell
taijianicu inspect --session-name novel --export-mermaid data/sessions/novel/story_graph.mmd
```

创建人工干预脚手架：

```powershell
taijianicu intervene --session-name novel --chapter 1
```

运行内置对照基准：

```powershell
taijianicu benchmark --dataset sanguo --prefix-chapters 50 --target-chapter 51
```

对任意本地 TXT 做对照基准：

```powershell
taijianicu benchmark --dataset custom --source-file data\input\novel_50.txt --prefix-chapters 50 --target-chapter 51
```

对远程 TXT 直跑基准：

```powershell
taijianicu benchmark --dataset custom --source-url https://example.com/novel.txt --prefix-chapters 50 --target-chapter 51
```

对已生成的连续章节做多章基线评估：

```powershell
taijianicu benchmark-multi --dataset hongloumeng --source-file data\input\hongloumeng_pg24264.txt --prefix-chapters 80 --target-start-chapter 81 --chapter-count 4 --candidate-dir data\output\hongloumeng-front80-gpt55-81-20260429-064255
```

红楼长链路验证、复用索引命令和第 120 回回归记录见 [docs/revival-validation-status.md](docs/revival-validation-status.md)。

启动 Web 工作台：

```powershell
taijianicu web
```

Web 工作台默认内置一个原创悬疑样例：

- 可以直接点「快速试看原创样例」，秒开预计算好的分析、规划和续写结果
- 如果要验证当前页面填写的 endpoint / Key 和模型配置，再点「按当前配置重跑」
- 总览里的原文区域默认显示原文断点 / 上文衔接，也可以切到“原始正文”查看整段原文，再和下方 AI 续写正文直接对照

Web 表单里的模型配置与 API 覆盖都按“单次运行”生效，不会改写服务器全局默认值，也不会把当前页面输入的 API Key 落盘。

默认地址：

- `http://127.0.0.1:8000`
- `GET /`：landing 页面，展示原创示例与红楼公开实证
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
- `POST /api/examples/{example_id}/preview-run`
- `POST /api/examples/{example_id}/runs`

landing 页只展示原创样例和公版文本短片段；首页不再展示外部版权作品的 benchmark 内容，避免把第三方作品片段作为公开宣传素材。

## 免费公网部署

当前仓库已经补了 [render.yaml](render.yaml) 和 [Dockerfile](Dockerfile)，可直接部署到 Render，也可复用到 Hugging Face Docker Spaces。

### Render

1. 把仓库导入 Render，创建 `Web Service`
2. Render 会自动识别 [render.yaml](render.yaml)
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

4. Space 会直接使用仓库内的 [Dockerfile](Dockerfile)

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

`run_manifest.json` 表示当前会话的累计清单。即使后续用 `--resume` 跳过已有章节，也会保留之前的质检结果、章节成本和阶段 1 成本汇总。若合并后的任一章节为 `completed_with_warnings` 或失败，顶层 `status` 也会同步反映，避免长章验证时只看顶层状态误判。

## 测试

```powershell
.\.venv\Scripts\python -m pytest
```

## 已验证链路

- 真实调用 DeepSeek 完成 `sample_novel.txt` 的 1 章续写
- `consistency_report.passed == true`
- `--resume --use-existing-index` 会跳过已有正文，同时保留会话累计成本清单
- `taijianicu inspect --export-mermaid ...` 可正常导出 Mermaid 故事图
- Web 首页、健康检查、上传接口与历史任务接口已通过自动化测试
- 已跑通 `taijianicu benchmark --dataset sanguo --prefix-chapters 50 --target-chapter 51`
- 对照结果：系统版胜过单模型 baseline，pairwise `winner=system`，`confidence=0.85`
- 红楼第 120 回 source-voice 回归已通过；完整记录见 [docs/revival-validation-status.md](docs/revival-validation-status.md)
- 当前全量 `pytest` 通过

## 基准说明

- 当前内置公开可复现数据集是 `sanguo`，会自动下载 GitHub 上的《三国演义》文本，取前 50 回续写第 51 回，并用真实第 51 回做评测。
- 评测输出包含单候选分项打分、pairwise 胜负、成本统计，以及系统版 / baseline / 真实参考章节的落盘路径。
- 多章基线评估可读取 `chapter_N.md` 连续输出目录，用真实后续章节做 holdout，并报告逐章分数、整体均分与漂移趋势。
- 长篇文本的阶段 1 已改为“双通道抽取”：风格从全局样本提取，当前剧情状态从最近章节单独刷新，避免续写时被早期剧情拖偏。

## 已知取舍

- 设计稿里的 Gemini / Claude / OpenAI 分工暂时统一收敛到 DeepSeek，先把主流程跑通。
- LightRAG 的 embedding 先用本地哈希向量兜底，避免在 MVP 阶段强依赖第二套密钥。
- 质量检查优先走 DeepEval，失败时自动降级为启发式规则检查。
- CLI 现在会输出每章 token 和成本汇总，成本统计基于 LiteLLM 的计费模型表。

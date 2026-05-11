# TaiJianICU

TaiJianICU 是一个面向中文长篇创作者的续写工作台。它不是简单补一段文字，而是把原稿拆成可追踪的创作上下文：世界观、人物状态、伏笔、章节推进、导演计划和单章评审，帮助你判断下一章是否真的接得住原作。

当前核心体验是 Studio 工作台：它可以作为网站运行，也可以打包成 Windows / macOS 桌面应用。README 只保留用户上手、配置和开发入口；实现细节、验证记录和路线图放在 `docs/`。

## 使用方式

- 网站版：部署或本地启动 Web 服务后进入 `/studio`，适合在线演示和持续迭代。
- 桌面版：下载 Release 里的 Windows / macOS zip，双击打开同一套 Studio 工作台。
- CLI：开发者可以直接用 `taijianicu run`、`inspect`、`benchmark` 跑单章和验证链路。

## 桌面版下载

最新 Release 提供 Windows 和 macOS 桌面版：

| 平台 | 下载 |
| --- | --- |
| Windows x64 | [TaiJianICU-windows-x64.zip](https://github.com/lusipad/TaiJianICU/releases/latest/download/TaiJianICU-windows-x64.zip) |
| macOS Apple Silicon | [TaiJianICU-macos-arm64.zip](https://github.com/lusipad/TaiJianICU/releases/latest/download/TaiJianICU-macos-arm64.zip) |
| macOS Intel | [TaiJianICU-macos-x64.zip](https://github.com/lusipad/TaiJianICU/releases/latest/download/TaiJianICU-macos-x64.zip) |

也可以打开 [GitHub Releases](https://github.com/lusipad/TaiJianICU/releases/latest) 查看所有版本。

## 桌面版快速开始

1. 下载并解压对应平台的 zip。
2. 把解压目录里的 `.env.example` 复制成 `.env`。
3. 在 `.env` 里填写模型 Key，至少需要：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

4. Windows 双击 `TaiJianICU.exe`，macOS 双击 `TaiJianICU.app`。
5. 进入 Studio 后，可以先点「快速试看」，也可以导入自己的原稿开始新任务。

桌面版仍然需要联网访问你配置的模型 API。用户上传的文本、会话、索引和输出会写在应用旁边的 `data/` 目录。macOS 当前未做签名和公证，首次打开可能需要在系统安全设置里允许运行。

## Studio 工作流

Studio 的主线按创作下一步组织：

1. `开始任务`：快速试看、上传原稿、设置目标章节数。
2. `工作台`：查看当前任务、下一步动作和最近结果。
3. `导演计划`：确认阶段目标、章节推进表、人物走向和必要约束。
4. `章节队列`：查看提纲候选、正文候选和章节产物。
5. `单章评审`：对照原稿和续写，检查质检、一致性和未收束问题。
6. `资料库`：只读查看世界观、人物、伏笔、统计和产物。
7. `设置`：配置 API Endpoint、Key、模型路由和连接测试。

如果你只是想先体验，不需要准备原稿，直接打开 Studio 的「快速试看」即可。

## API 配置

最小配置是 `DEEPSEEK_API_KEY`。默认模型路由使用 DeepSeek：

```env
TAIJIAN_PLOT_MODEL=deepseek/deepseek-chat
TAIJIAN_DRAFT_MODEL=deepseek/deepseek-chat
TAIJIAN_STYLE_MODEL=deepseek/deepseek-chat
TAIJIAN_QUALITY_MODEL=deepseek/deepseek-chat
TAIJIAN_EMBEDDING_BACKEND=local-hash
```

在 Studio 的「设置」页可以检查连接状态，也可以为单次任务覆盖 API Endpoint、Key 和模型配置。页面输入的 Key 用于当前运行，不会写回服务器全局配置。

如果要把 Web 版放到公网，建议额外设置：

```env
TAIJIAN_WEB_USERNAME=admin
TAIJIAN_WEB_PASSWORD=change_me
TAIJIAN_WEB_ALLOWED_ORIGINS=https://your-domain.example
```

公网演示请注意：`data/` 是本地文件存储，免费平台重启后可能丢失，不适合保存长期创作记录。

## 本地开发

需要 Python 3.11 到 3.14。Windows 下建议使用项目内 `.venv`：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
copy .env.example .env
```

启动 Web/Studio：

```powershell
taijianicu web
```

默认地址：

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/studio`

常用 CLI：

```powershell
taijianicu run --input data/input/novel.txt --chapters 1
taijianicu inspect --session-name novel
taijianicu benchmark --dataset sanguo --prefix-chapters 50 --target-chapter 51
```

构建桌面版：

```powershell
.\scripts\build-standalone.ps1
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 文档

- [文档地图](docs/README.md)
- [桌面版下载与打包](docs/user/desktop-release.md)
- [复活路线图](docs/product/revival-roadmap.md)
- [作者复活引擎设计](docs/product/author-revival-engine-design.md)
- [当前验证状态](docs/engineering/revival-validation-status.md)

## 当前边界

- TaiJianICU 仍处于快速实验阶段，适合创作辅助和质量评审，不应把输出直接当成最终稿。
- 真实续写需要可用的模型 API Key；桌面版不是离线大模型。
- 公开部署适合演示，不适合长期保存用户作品。
- 详细验证命令、质量门结果和已知缺口请看 [当前验证状态](docs/engineering/revival-validation-status.md)。

# 桌面版下载与打包

目标用户不是开发者时，推荐使用 GitHub Release 里的桌面版：用户解压后双击应用，直接打开 TaiJianICU Studio 工作台。

## 用户使用方式

普通用户优先从 GitHub 最新 Release 下载对应平台的 zip：

| 平台 | 文件 |
| --- | --- |
| Windows x64 | `TaiJianICU-windows-x64.zip` |
| macOS Apple Silicon | `TaiJianICU-macos-arm64.zip` |
| macOS Intel | `TaiJianICU-macos-x64.zip` |

下载并解压后，把 `.env.example` 复制成 `.env`，并至少填写：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

Windows 双击 `TaiJianICU.exe`，macOS 双击 `TaiJianICU.app`。当前 Studio 第一体验是 Revival 可信评审：导入原稿、分析作者声纹、选择人物走向、编辑导演内部化约束、生成章节，再查看可信报告和盲测反馈。

桌面版仍会调用用户配置的外部模型 API。原稿片段、导演提示、章节上下文和评审提示会随模型请求发送到该 API；Studio 表单里临时填写的 API Key 只用于本次运行，不写回全局 `.env`。用户上传的文本、会话、输出、索引、导演约束、可信报告和运行记录都会写到应用旁边的 `data/` 目录。本轮只做清晰说明，不提供一键删除本地数据控件。

macOS 当前未做签名和公证，首次打开可能需要在系统安全设置里允许运行。

## 构建方式

在开发机上运行：

```powershell
.\scripts\build-standalone.ps1
```

主要产物位置：

```text
dist/TaiJianICU.exe
dist/TaiJianICU.app
dist/.env.example
```

发布给用户时，把 `dist/.env.example` 复制成 `.env` 并填好 Key，或让用户自行填写。

## 当前边界

- 桌面版仍然需要联网访问所配置的模型 API。
- 桌面版不要求用户安装 Python 或运行 `pip install`。
- Studio 主线是 Revival 可信评审；旧 `taijianicu run`、`benchmark`、`benchmark-multi` CLI 仍保留兼容。
- 当前没有引入 Electron；桌面窗口使用 Qt WebEngine 嵌入现有工作台。
- 如端口 `8000` 被占用，双击启动会自动改用一个空闲本机端口。
- 如需固定端口，可从命令行启动：`TaiJianICU.exe standalone --port 8010`。
- 如需排障内部服务，可从命令行启动：`TaiJianICU.exe standalone --server-only`。

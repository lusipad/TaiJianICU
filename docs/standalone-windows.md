# Windows 单机版打包说明

目标用户不是开发者时，推荐交付 `TaiJianICU.exe`：用户双击后启动本机 Web 工作台，并自动打开浏览器访问 `http://127.0.0.1:8000/studio`。

## 用户使用方式

把下面两个文件放在同一个目录：

- `TaiJianICU.exe`
- `.env`

`.env` 至少填写：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

双击 `TaiJianICU.exe` 后会出现一个控制台窗口。这个窗口就是本地服务进程，关闭窗口即可停止服务。用户上传的文本、会话、输出、索引和 Web 运行记录都会写到 exe 旁边的 `data/` 目录。

## 构建方式

在开发机上运行：

```powershell
.\scripts\build-standalone.ps1
```

产物位置：

```text
dist\TaiJianICU.exe
dist\.env.example
```

发布给用户时，把 `dist\.env.example` 复制成 `.env` 并填好 Key，或让用户自行填写。

## 当前边界

- 单机版仍然需要联网访问所配置的模型 API。
- 单机版不要求用户安装 Python 或运行 `pip install`。
- 当前没有引入 Electron 或桌面壳；本地浏览器就是 UI 容器，复杂度最低，也最容易排障。
- 如端口 `8000` 被占用，可从命令行启动：`TaiJianICU.exe standalone --port 8010`。

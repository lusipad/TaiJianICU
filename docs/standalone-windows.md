# Windows 单机版打包说明

目标用户不是开发者时，推荐交付 `TaiJianICU.exe`：用户双击后直接打开 TaiJianICU 桌面窗口，窗口内就是工作台。

## 用户使用方式

把下面两个文件放在同一个目录：

- `TaiJianICU.exe`
- `.env`

`.env` 至少填写：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

双击 `TaiJianICU.exe` 后会打开桌面应用窗口。用户上传的文本、会话、输出、索引和运行记录都会写到 exe 旁边的 `data/` 目录。

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
- 当前没有引入 Electron；桌面窗口使用 Qt WebEngine 嵌入现有工作台。
- 如端口 `8000` 被占用，可从命令行启动：`TaiJianICU.exe standalone --port 8010`。
- 如需排障内部服务，可从命令行启动：`TaiJianICU.exe standalone --server-only`。

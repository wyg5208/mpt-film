---
name: changofilm-video
description: 当用户希望使用 ChangoFilm 从主题、标题、创意、提示词或脚本生成一支成品视频时，使用本 Skill。这包括短视频、配音解说、教育类、营销类、社交媒体类以及素材库画面的视频。当用户提到 ChangoFilm、提供本 Skill 的 URL、要求 AI 智能体安装或配置 ChangoFilm、需要识别缺失的 API 密钥、希望修复失败的生成任务，或需要定位并交付已生成的 MP4 文件时，也应使用本 Skill。当预期结果是最终视频文件而非安装说明时，使用本 Skill。
compatibility: 需要具备终端、网络、文件系统以及长时间运行命令支持的 AI 智能体。支持 macOS 和 Windows，并完全使用 uv。
metadata:
  author: "harry0703@hotmail.com"
  version: "1.3.2"
  upstream: "https://github.com/harry0703/MoneyPrinterTurbo"
---

# ChangoFilm 视频生成

用户只需提供一个视频主题或脚本即可。自动完成安装、配置复用、生成、等待以及最终 MP4 交付。不要只给出说明或命令后就停止。

## 必需行为

1. 仅就缺失、被拒绝或不可用的必需 API 凭证向用户询问。将所有必需凭证合并为一次请求。
2. 在开始安装、生成、等待、使用默认值或返回结果之前，不要请求确认。
3. 对于标准生成请求，不要创建或反复更新详细计划。发送一条简短的进度更新后直接执行。
4. 以一个前台命令运行辅助脚本，超时时间至少 20 分钟。
5. 绝不使用 `sleep`、`echo`、`ps`、反复 `ls` 或反复 `tail` 进行轮询。如果终端返回一个可恢复的会话 ID，请在同一会话上继续等待。
6. 成功后不要读取完整日志。仅在失败后读取简短的错误报告或相关的日志末尾内容。
7. 绝不打印 API 密钥、令牌、完整的 `config.toml`，或任何带有凭证的配置片段。

## 默认值

除非用户另有要求，否则生成一支中文 `9:16` 竖屏视频，使用 Pexels 素材、默认中文 Edge TTS 语音、字幕以及背景音乐。将 ChangoFilm 安装在用户的主目录下。

## 执行

### 1. 定位辅助脚本

从本 `SKILL.md` 文件解析出 `SKILL_DIR`。辅助脚本是相邻的 `changofilm_agent.py`。将终端工具的工作目录设置为 `SKILL_DIR`，并通过相对文件名调用辅助脚本。不要在命令中放入辅助脚本的绝对路径，也不要额外运行 `ls` 或 `dir` 检查。

这在 Windows 上是必需的，因为某些智能体的终端校验器会移除命令中嵌入的绝对路径里的反斜杠。使用 `changofilm_agent.py` 并配合 `workdir=SKILL_DIR` 可以规避该故障，并且在 macOS 和 Windows 上都能工作。

如果客户端只加载了远程的 `SKILL.md`，则从官方仓库把辅助脚本下载到临时目录，然后把该临时目录作为命令的工作目录：

```text
https://raw.githubusercontent.com/wyg5208/changofilm/main/docs/skill/changofilm_agent.py
```

### 2. 运行辅助脚本

不要单独运行 `uv --version` 预检查。直接运行辅助脚本。如果 shell 明确报告 uv 缺失，安装 uv 并将同一条辅助脚本命令重试一次。

macOS uv 安装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell uv 安装：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

使用下面这条前台命令，设置 `workdir=SKILL_DIR`，超时时间至少 20 分钟：

```bash
uv run --no-project --python 3.11 python changofilm_agent.py --subject "<video topic>"
```

在 Windows 上，在这条相对命令之前，不要尝试绝对反斜杠路径、绝对正斜杠路径，或先在工作区中放置副本。如果终端工具报告 `referenced_script_path_missing`，确认其工作目录正好是 `SKILL_DIR`，然后将相对命令重试一次。不要在不同路径变体之间反复尝试。

不要使用 Docker、Conda、系统 pip 或手动管理的虚拟环境。

## 退出处理

### 退出码 0：交付结果

成功输出形如：

```text
CHANGOFILM_RESULT
VIDEO_FILE=<absolute path>/final-1.mp4
TASK_DIR=<absolute path>/storage/tasks/<task_id>
LOG_FILE=<absolute path>/run-<task_id>.log
RESULT_FILE=<absolute path>/latest-result.json
```

`changofilm_agent.py` 仅在确认文件存在且非空之后才输出 `VIDEO_FILE`。不要再运行其他 `ls`、`stat` 或文件校验命令。

如果终端报告 `exitCode=0`，但输出被截断，或返回了一个不含 `CHANGOFILM_RESULT` 的历史文件引用，不要推断为失败，也不要检查旧日志。只读取这一个文件：

```text
~/ChangoFilm/.agent-logs/changofilm-video/latest-result.json
```

将 `status=completed` 视为成功。只返回视频的绝对路径和简要描述，例如：

```text
The video is ready.
Topic: ...
Video file: /absolute/path/to/final-1.mp4
Summary: Chinese portrait video with voice-over, subtitles, and background music.
```

### 退出码 10：一次性请求凭证

`CHANGOFILM_NEEDS_INPUT` 只包含必需字段、推荐的 LLM 服务商及注册链接、自定义 OpenAI 兼容接口要求，以及素材服务商的注册链接。只询问所列出的值，不要请求已在 `config.toml` 中找到的凭证。

用户响应后，只带上所需的环境变量重新运行同一条前台命令：

```text
CHANGOFILM_LLM_PROVIDER
CHANGOFILM_LLM_API_KEY
CHANGOFILM_LLM_BASE_URL
CHANGOFILM_LLM_MODEL_NAME
CHANGOFILM_PEXELS_API_KEY
CHANGOFILM_VOLCENGINE_ARK_API_KEY
CHANGOFILM_OFOX_API_KEY
CHANGOFILM_METASO_MINIMAX_API_KEY
CHANGOFILM_MUAPI_API_KEY
CHANGOFILM_INFISTAR_VIDEO_API_KEY
CHANGOFILM_JALAPENO_VIDEO_API_KEY
```

当出现 `SEEDANCE_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 Seedance 片段都会创建一个付费的 Ark 任务。只有在用户明确确认后，才带 `--confirm-seedance-charge` 重新运行；绝不静默添加此标志。

当出现 `WAVESPEED_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 WaveSpeed 片段都会由 WaveSpeed 按请求计费。只有在用户明确确认后，才带 `--confirm-wavespeed-charge` 重新运行；绝不静默添加此标志。

当出现 `OFOX_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 OFox 片段都会创建一个付费任务。只有在用户明确确认后，才带 `--confirm-ofox-charge` 重新运行；绝不静默添加此标志。

当出现 `METASO_MINIMAX_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 MiniMax H3 片段都会创建一个付费的 Metaso 任务。只有在用户明确确认后，才带 `--confirm-metaso-minimax-charge` 重新运行；绝不静默添加此标志。

当出现 `MUAPI_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 MuAPI 片段都会创建一个付费任务。只有在用户明确确认后，才带 `--confirm-muapi-charge` 重新运行；绝不静默添加此标志。

当出现 `INFISTAR_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 Infistar 片段都会创建一个付费任务。只有在用户明确确认后，才带 `--confirm-infistar-charge` 重新运行；绝不静默添加此标志。请使用专用的视频密钥，与 Infistar 的 LLM 密钥区分开。

当出现 `JALAPENO_CHARGE_CONFIRMATION_REQUIRED` 时，说明每生成一个 Jalapeno Cloud 片段都会创建一个付费任务。在用户确认后，带 `--confirm-jalapeno-charge` 重新运行。视频密钥为空时会复用已配置的 Jalapeno Cloud LLM 密钥；专用视频密钥优先。

### 退出码 1：修复或报告

使用 `CHANGOFILM_ERROR` 和 `LOG_FILE` 来修复可恢复的问题并重试一次。仅当修复需要一个新的 API 密钥时才向用户询问。如果重试失败，报告失败的阶段、简短的错误信息以及日志路径。

终端工具的路径校验错误并不是视频生成失败，因为辅助脚本根本没有启动。纠正工作目录并将相对命令重试一次。绝不要要求用户复制 `changofilm_agent.py`、手动运行命令，或确认智能体是否应继续。

## 配置与后台回退

辅助脚本可以读取完整的本地 `config.toml` 以复用已有设置，但绝不能打印其内容。它会自动复用一个可用的 LLM 服务商，并在生成前通过带认证的 My Collections 接口校验已配置的 Pexels 密钥。

仅当智能体平台无法等待前台进程时，才使用后台模式。等待平台的进程完成通知，而不要轮询，然后只读取一次 `latest-result.json`。

## 适用范围

- 仅支持 macOS 和 Windows。
- 只使用 uv 和 ChangoFilm CLI。
- 不要启动 Docker、WebUI 或 API 服务。
- 不要并发运行多个视频任务。
- 将额外的视频需求放在 `--` 之后传递。只有在必须验证某个不熟悉的选项时，才运行一次 `cli.py --help`。

<div align="center">

# ChangoFilm 🎬

### 专业系列短剧 · 本地 AI 制片工作室

只需提供一个<b>主题</b>或<b>脚本</b>，ChangoFilm 即可完成文案、画面、配音、字幕与配乐，并在你自己的机器上合成整集成片。

[![Version](https://img.shields.io/badge/version-1.13.0-blue)](https://github.com/wyg5208/changofilm)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/wyg5208/changofilm)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

简体中文 | [English](README-en.md) | [日本語](README-ja.md)

</div>

---

## 产品简介

ChangoFilm 是一个**本地优先（local-first）**的系列短剧生产工具。它面向连续剧集的内容生产：
从选题、脚本方案、分集素材到配音合成，全流程在本机完成，素材与密钥不出本地。

创作入口分为两条清晰的路线：

- **快速成片**：输入主题或关键词，一条流水线自动产出单支短视频，适合快速试产。
- **专业短剧**：以脚本方案（Script Plan）驱动分集生产，支持系列化项目、逐集脚本与
  素材管理；**每个项目拥有独立的图片 / 视频 / 音频 / 字幕设置**，互不串扰。

提供 **WebUI、API、CLI 和 AI Agent Skill** 四种使用方式，界面支持 14 种语言。

## 核心能力 🎯

### 脚本与模型服务

- AI 自动生成或改写多语言视频脚本，也可直接使用自定义脚本与自定义系统提示词
- 支持 Kimi / Moonshot、OpenAI、Anthropic Claude、Google Gemini、DeepSeek、通义千问、
  Azure OpenAI、火山引擎方舟、xAI Grok、MiniMax、小米 MiMo 等主流模型服务
- 兼容 OpenRouter、Ollama、LiteLLM、OneAPI、Cloudflare AI Gateway 等统一网关，
  以及 llama.cpp 等本地推理环境；支持 Claude Code / ChatGPT / Codex 订阅凭据接入

### 画面素材

- 上传本地图片和视频；从 [Pexels](https://www.pexels.com/api/)、[Pixabay](https://pixabay.com/api/docs/)、
  [Coverr](https://coverr.co/developers) 获取高清**库存视频**
- **库存图片**下载源（Pexels / Pixabay）与 AI 生图并列可选，按项目独立配置
- AI 文生视频：火山引擎 Seedance、秘塔 MiniMax H3（768P / 2K）、WaveSpeed、OFox、
  MuAPI、胜算云等；AI 文生图兼容 OpenAI 协议及自定义网关
- 本地 ComfyUI 引擎：文生图 / 文生视频工作流在本机 GPU 上运行

### 配音、字幕与配乐

- 自动配音、上传配音、无配音三种模式，音色试听与整段预览
- 集成 **Edge TTS（免费、无需 Key）**、Azure Speech、SiliconFlow、Gemini、MiMo、
  MiniMax、ElevenLabs、Chatterbox、Kokoro、Fish Audio、VoxCPM 等配音服务
- faster-whisper 自动字幕，字体、位置、颜色、描边、背景样式可调
- 随机 / 本地 / AI 生成背景音乐，音量独立控制

### 成片与发布

- 竖屏 `9:16`、横屏 `16:9`、方形 `1:1` 三种画幅
- 批量生成、任务历史与断点恢复；生成设置预设与 API Key 备份的导出 / 导入
- 一键跨平台发布：TikTok、Instagram、YouTube Shorts

## 配置要求 📦

- Windows 10+、macOS 11+ 或主流 Linux 发行版
- Python **3.11+**（推荐 3.11）
- GPU 非必需；启用本地 Whisper 转录、ComfyUI 引擎或批量生成时建议 4GB+ 显存

| 项目 | 最低配置 | 推荐配置 |
| ---- | -------- | -------- |
| CPU  | 4 核     | 8 核及以上 |
| RAM  | 4 GB     | 16 GB 及以上 |
| GPU  | 非必须   | 4 GB 显存及以上 |

## 快速开始 🚀

### 方式一：源码部署（推荐，uv 管理依赖）

```sh
git clone https://github.com/wyg5208/changofilm.git
cd changofilm
uv sync
```

启动 WebUI：

- Windows：双击 `webui.bat`
- macOS / Linux：`./webui.sh`

启动 API 服务（FastAPI，默认 `http://127.0.0.1:8080`）：

```sh
uv run python main.py
```

### 方式二：pip 安装

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install changofilm
changofilm webui
changofilm cli --help
```

### 方式三：Docker

```sh
docker compose up -d
```

WebUI 监听 `127.0.0.1:8501`，API 监听 `127.0.0.1:8080`。
GPU 部署使用 `docker-compose.gpu.yml`；发行镜像见 `docker-compose.release.yml`
（`ghcr.io/wyg5208/changofilm`）。

### 方式四：AI Agent Skill

如果你的 AI Agent 支持读取 Skill 文档并操作本地终端，直接发送：

```text
使用这个 Skill：https://raw.githubusercontent.com/wyg5208/changofilm/main/docs/skill/SKILL.md
帮我生成一个主题为“人工智能如何改变普通人的日常生活”的视频。
```

Agent 会自动完成安装、配置与生成，仅在缺少必要 API Key 时向你询问。
详见 [docs/skill/SKILL.md](docs/skill/SKILL.md)（[中文版](docs/skill/SKILL-zh.md)）。

## 配置与数据目录 ⚙️

- 复制 `config.example.toml` 为 `config.toml`，或直接在 WebUI 设置弹窗中配置模型、
  素材源、配音与字幕参数
- 安装版数据默认位于用户目录（macOS `~/Library/Application Support/ChangoFilm`、
  Windows `%LOCALAPPDATA%\ChangoFilm`、Linux `~/.local/share/ChangoFilm`）
- 通过环境变量 `CHANGOFILM_HOME` 自定义数据目录；旧版 `MPT_HOME` 仍被兼容接受，
  旧品牌数据目录会在首次启动时自动迁移，用户数据不会丢失

## 文档 📚

- [pip 安装包与 PyPI 发布](docs/packaging.md)
- [Agent Skill 使用文档](docs/skill/SKILL.md)
- [迭代记录](docs/迭代记录文档/)：本分支的变更日志与验证证据

## 服务商与专属优惠 🤝

以下为 ChangoFilm 已集成或推荐的服务入口，部分为专属推荐链接（注册可获赠送额度）：

| 服务商 | 能力 | 入口 |
| ------ | ---- | ---- |
| Kimi / Moonshot | 文案与素材理解大模型 | [开放平台](https://platform.kimi.com?track_id=track-6eec1e56a4494e52adcaebbcbbefce59&aff=moneyprinterturbo) |
| 火山引擎方舟 | Seedance 视频生成、国模套餐 | [活动页](https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=MoneyPrinterTurbo) |
| 秘塔科技 | MiniMax H3 视频生成 API | [专属链接](https://metaso.cn/minimax-h3/?s=MPT) |
| APIMart | AI 图片 / 视频异步 API | [注册](https://go.apimart.ai/gh-moneyprinterturbo) |
| OFox | 多模型文生视频 / 文生图 | [官网](https://ofox.ai/?utm_source=github&utm_medium=sponsorship&utm_content=moneyprinterturbo) |
| 胜算云 | 模型 API 聚合平台 | [注册](https://www.shengsuanyun.com/?from=CH_XUQ4OTSK) |
| Infistar 无限星河 | 大模型 / 生图 API | [注册](https://infistar.cc/register?aff=6T4EYXP2&ref_source=link) |
| 星图 AstraFlow | 视频 / 大模型聚合调用 | [活动页](https://www.ucloud.cn/site/active/astraflow?ytag=geo_waituo_Money) |
| RunningHub | ComfyUI 工作流与模型 API | [接口](https://www.runninghub.ai/call-api?source=github) |
| Jalapeno Cloud | 多模型统一接入 | [注册](https://www.jalapeno-cloud.ai/MoneyPrinterTurbo) |

## 致谢与参考项目 ❤️

ChangoFilm 在创作管线、素材编排与工程实践上**参考借鉴了多个开源项目**，包括但不限于：

- [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)（harry0703）——
  一键式 AI 短视频生成工具，本仓库最初由此 fork 而来
- [openfilm](https://github.com/openfilm/openfilm) —— HTML 动效渲染与确定性出帧管线，
  其并行渲染与校验思路被借鉴用于本地成片质量保障

ChangoFilm 已在上述项目基础上**大幅重构并独立演进**：双路线创作信息架构、系列短剧
项目管理、逐项目独立设置、库存图片源、本地 ComfyUI 引擎与完整的回归测试体系均为
本项目的独立实现。感谢所有原作者与开源社区的贡献。

## 许可证

[MIT](LICENSE)
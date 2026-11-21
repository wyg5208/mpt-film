<div align="center">

# ChangoFilm 🎬

### Professional Series Short Dramas · Local-First AI Studio

Provide a <b>topic</b> or a <b>script</b>, and ChangoFilm produces the copy, visuals,
voiceover, subtitles and music — then composes a finished episode on your own machine.

[![Version](https://img.shields.io/badge/version-1.8.1-blue)](https://github.com/wyg5208/changofilm)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/wyg5208/changofilm)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[简体中文](README.md) | English | [日本語](README-ja.md)

</div>

---

## Overview

ChangoFilm is a **local-first** studio for series short-drama production. It targets
episodic content: from topic selection and script plans to per-episode materials and
final composition, the whole pipeline runs on your machine — materials and API keys
never leave it.

Two clearly separated creation routes:

- **Quick Video**: enter a topic or keywords and a single pipeline produces one short
  video — ideal for fast experiments.
- **Professional Short Drama**: script-plan-driven episodic production with series
  projects, per-episode scripts and materials. **Every project keeps its own
  image / video / audio / subtitle settings**, fully isolated from other projects.

Four ways to use it: **WebUI, API, CLI and an AI Agent Skill**. The UI ships in
14 languages.

## Features 🎯

### Scripts & model providers

- AI-generated or rewritten multilingual scripts, or bring your own script and
  custom system prompt
- Kimi / Moonshot, OpenAI, Anthropic Claude, Google Gemini, DeepSeek, Qwen,
  Azure OpenAI, Volcengine Ark, xAI Grok, MiniMax, Xiaomi MiMo and more
- Unified gateways such as OpenRouter, Ollama, LiteLLM, OneAPI and Cloudflare AI
  Gateway, plus local inference via llama.cpp; Claude Code / ChatGPT / Codex
  subscription credentials are supported

### Visual materials

- Upload local images and videos; fetch HD **stock footage** from
  [Pexels](https://www.pexels.com/api/), [Pixabay](https://pixabay.com/api/docs/)
  and [Coverr](https://coverr.co/developers)
- **Stock image** sources (Pexels / Pixabay) alongside AI image generation,
  configurable per project
- AI text-to-video: Volcengine Seedance, Metaso MiniMax H3 (768P / 2K), WaveSpeed,
  OFox, MuAPI, Shengsuanyun; OpenAI-compatible text-to-image with custom gateways
- Local ComfyUI engines: text-to-image / text-to-video workflows on your own GPU

### Voiceover, subtitles & music

- Auto voiceover, uploaded narration, or no voice; voice previews and full narration
  playback
- **Edge TTS (free, no API key)**, Azure Speech, SiliconFlow, Gemini, MiMo, MiniMax,
  ElevenLabs, Chatterbox, Kokoro, Fish Audio, VoxCPM and more
- Automatic subtitles via faster-whisper with font, position, color, outline and
  background styling
- Random / local / AI-generated background music with independent volume

### Output & publishing

- Portrait `9:16`, landscape `16:9` and square `1:1`
- Batch generation, task history and restore; export / import of settings presets
  and API-key backups
- One-click cross-posting to TikTok, Instagram and YouTube Shorts

## Requirements 📦

- Windows 10+, macOS 11+ or a mainstream Linux distribution
- Python **3.11+** (3.11 recommended)
- GPU optional; 4GB+ VRAM recommended for local Whisper transcription, ComfyUI
  engines or heavy batch generation

| Item | Minimum | Recommended |
| ---- | ------- | ----------- |
| CPU  | 4 cores | 8+ cores |
| RAM  | 4 GB    | 16 GB+ |
| GPU  | not required | 4 GB+ VRAM |

## Quick Start 🚀

### Option 1: from source (recommended, uv-managed)

```sh
git clone https://github.com/wyg5208/changofilm.git
cd changofilm
uv sync
```

Start the WebUI:

- Windows: double-click `webui.bat`
- macOS / Linux: `./webui.sh`

Start the API service (FastAPI, default `http://127.0.0.1:8080`):

```sh
uv run python main.py
```

### Option 2: pip install

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install changofilm
changofilm webui
changofilm cli --help
```

### Option 3: Docker

```sh
docker compose up -d
```

The WebUI listens on `127.0.0.1:8501` and the API on `127.0.0.1:8080`.
Use `docker-compose.gpu.yml` for GPU deployments; the release image
(`ghcr.io/wyg5208/changofilm`) is wired in `docker-compose.release.yml`.

### Option 4: AI Agent Skill

If your AI agent can read Skill documents and operate a local terminal, send:

```text
Use this skill: https://raw.githubusercontent.com/wyg5208/changofilm/main/docs/skill/SKILL.md
Create a video about "How AI changes everyday life".
```

The agent installs, configures and generates automatically, asking only for missing
API keys. See [docs/skill/SKILL.md](docs/skill/SKILL.md)
([Chinese version](docs/skill/SKILL-zh.md)).

## Configuration & data directory ⚙️

- Copy `config.example.toml` to `config.toml`, or configure providers, material
  sources, voice and subtitles directly in the WebUI settings dialog
- Installed builds keep data in your user directory (macOS
  `~/Library/Application Support/ChangoFilm`, Windows `%LOCALAPPDATA%\ChangoFilm`,
  Linux `~/.local/share/ChangoFilm`)
- Set `CHANGOFILM_HOME` to choose another directory; the legacy `MPT_HOME` variable
  is still accepted, and legacy brand data directories are migrated automatically
  on first launch — no user data is lost

## Documentation 📚

- [pip packaging & PyPI release](docs/packaging.md)
- [Agent Skill guide](docs/skill/SKILL.md)
- [Iteration records](docs/迭代记录文档/): this branch's changelog and verification evidence

## Service providers & referral offers 🤝

Integrated or recommended service entry points; some links are referral links that
grant bonus credits on sign-up:

| Provider | Capability | Entry |
| -------- | ---------- | ----- |
| Kimi / Moonshot | Copy & material understanding LLMs | [Platform](https://platform.kimi.ai?track_id=track-9e3b711aa2594e378f6fe5b8de718a76&aff=moneyprinterturbo) |
| Volcengine Ark | Seedance video generation, model plans | [Offer](https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=MoneyPrinterTurbo) |
| Metaso | MiniMax H3 video generation API | [Referral](https://metaso.cn/minimax-h3/?s=MPT) |
| APIMart | Async AI image / video APIs | [Sign up](https://go.apimart.ai/gh-moneyprinterturbo) |
| OFox | Multi-model text-to-video / image | [Site](https://ofox.ai/?utm_source=github&utm_medium=sponsorship&utm_content=moneyprinterturbo) |
| Shengsuanyun | Model API aggregation | [Sign up](https://www.shengsuanyun.com/?from=CH_XUQ4OTSK) |
| Infistar | LLM / image generation APIs | [Sign up](https://infistar.cc/register?aff=6T4EYXP2&ref_source=link) |
| AstraFlow | Video / LLM aggregation | [Offer](https://www.ucloud.cn/site/active/astraflow?ytag=geo_waituo_Money) |
| RunningHub | ComfyUI workflows & model APIs | [API](https://www.runninghub.ai/call-api?source=github) |
| Jalapeno Cloud | Unified multi-model access | [Sign up](https://www.jalapeno-cloud.ai/MoneyPrinterTurbo) |

## Acknowledgments & referenced projects ❤️

ChangoFilm's production pipeline, material orchestration and engineering practices
**reference multiple open-source projects**, including but not limited to:

- [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (harry0703) —
  a one-stop AI short-video generator; this repository originally forked from it
- [openfilm](https://github.com/openfilm/openfilm) — HTML motion-graphics rendering
  with a deterministic frame pipeline, whose parallel rendering and verification
  ideas informed our local composition quality guarantees

ChangoFilm has been **substantially refactored and evolves independently** on top of
these projects: the dual-route creation architecture, series project management,
per-project isolated settings, stock image sources, local ComfyUI engines and the
full regression-test system are original implementations of this project. Thanks to
all original authors and the open-source community.

## License

[MIT](LICENSE)
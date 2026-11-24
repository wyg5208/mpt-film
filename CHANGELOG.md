# Changelog

本文件记录本项目（MoneyPrinterTurbo fork / ChangoFilm）所有值得注意的变更。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本（主.次.修订）。

> **双项目版本体系互为独立**：本仓库（外层，Python）的版本由 `app/__init__.py` 与 `pyproject.toml` 双写升版（v1.x）。工作区内嵌套的独立子仓库 `opensources/changovideo`（ChangoVideo，Node/pnpm）由 changesets 管理（0.x），其变更日志见该仓库内 `packages/changovideo/CHANGELOG.md`、`apps/desktop/CHANGELOG.md`、`packages/shared/CHANGELOG.md`；`opensources/social-auto-upload`（sau）子仓库另有自己的提交记录。两套版本号互不相关。部分迭代的代码变更落在嵌套仓库（外层仅承载文档与升版），相应条目注明"变更归属"。

## [Unreleased]

## [1.12.1] - 2026-11-24

### 新增

- 建立双项目变更日志机制：外层新增本 CHANGELOG.md（Keep a Changelog 风格，回填 1.3.9–1.12.0 全部版本条目），迭代升版流程新增 CHANGELOG 同步步骤（iteration-doc agent 第 3 步）。

### 变更

- ChangoVideo 子仓库：三份 CHANGELOG 头部包名由 openfilm 系更正为 changovideo 系，新增离线升版字节校验门禁 `scripts/verify-changelog.mjs`（推送前强制执行），离线 bump 非字符损坏修复模式固化进两个 agent 文档。

## [1.12.0] - 2026-11-23

### 新增

- API 任务队列路径实时日志修复：工作线程安装线程级 loguru sink，右侧日志列改造为悬浮 LogDock 组件。
- 素材库 / 成片库入口与三个后端端点（目录、详情、签名），可浏览历史素材与成片。
- 一键重启启动脚本 `start-web.bat`（按端口与进程身份安全清理后重启并打开浏览器）。

### 修复

- 无鉴权 Mode A 部署下 `get_media_secret()` 直接抛错导致签名媒体整体 500；修复为落盘随机兜底密钥。

## [1.11.1] - 2026-11-22

### 修复

- `webui.bat` 删除 `uv run` / PATH `streamlit` 两条全局环境回落路径，强制使用项目内置解释器。
- 专业短剧旁白校验由"每个场景都必须有旁白"放宽为"至少一个场景有"，对齐 `plan_compiler` 允许静音空镜的既有设计。

## [1.11.0] - 2026-11-22

### 新增

- 浅色主题：dark/light 双模式，浅色模式以品牌 var 驱动规则覆盖 Streamlit 1.66 Emotion 硬编码样式。

### 变更

- 侧边栏精简：移除左导航品牌 lockup 与常驻主题面板；主题设置迁入设置页第五个「品牌主题」TAB。

## [1.10.0] - 2026-11-22

### 新增

- 僵尸发布进程探测器（`app/services/publish_zombies.py`，零新增依赖）：识别重启 WebUI 后遗留的 sau.exe 发布进程树（孤儿），任务管理面板警示区支持单个/全部一键整树杀灭；判定贯彻"宁可漏杀，不可误杀"。

## [1.9.0] - 2026-11-22

### 新增

- 抖音全流程拟人化：逐字符打字、三阶贝塞尔鼠标轨迹、钟形随机停顿，以及上传前预热 / 等待期微动作 / 发布后管理页浏览三个随机浏览场景；拟人层异常自动回退原生行为。（变更归属：`opensources/social-auto-upload` 子仓库）

## [1.8.1] - 2026-11-22

### 修复

- 抖音自动发布表单折叠根因修复：抗干扰清浮层代码盲删被新版 UI 复用的 `publish-mention-wrapper-*` 类名所包裹的表单容器；三处清理守卫修复后 headed 真发全程无人工干预成功。（变更归属：sau 子仓库）

## [1.8.0] - 2026-11-21

### 新增

- 统一服务商配置页：散落各处的服务商 Key 表单收敛一处，能力矩阵只声明真实已接线能力。
- 三槽备用源体系：素材来源、配音、LLM 三条链支持"第一优先 + 备用 1 + 备用 2"，主源未配置时预检/调用点自动切换，不再直接失败。

## [1.7.0] - 2026-11-20

### 新增

- 脚本方案专业模式生产实施（B2–B8）：ScriptPlan fail-closed 模型与 LLM 方案生成、ComfyUI/ACE-Step 本地引擎 provider、方案驱动执行与确定性渲染门禁、首尾帧衔接与边界跳变审查、系列/对白持久化、创作向导/脚本方案/系列管理三个新页、逐场景转场与 ASS 字幕烧录。专业模式 opt-in，无方案时快速流水线行为零变化。

## [1.6.0] - 2026-11-20

### 新增

- 脚本方案（ScriptPlan）专业模式完整解决方案文档与可交互 Demo（简单/专业双轨 + 五步创作向导 + 低成本 AI 短剧系列方案），本轮不改生产逻辑代码。

## [1.5.0] - 2026-11-20

### 变更

- WebUI 重构为三列布局（左导航 11 页 + 中功能页 + 右生成日志，两列独立收起）；设置子页提升为一级页。

### 新增

- 任务↔参数绑定（params.json 快照、顶栏项目切换器、脏检测三选确认、complete 锁定另存）与预设库（保存/导入导出/一键应用）。

## [1.4.0] - 2026-11-19

### 新增

- 国内平台免费自动发布通道：封装 bundled social-auto-upload 的 `sau` CLI 子进程，与既有 Upload-Post 通道形成双通道路由（抖音/视频号/小红书/B站），共用发布状态机、有界队列与 owner/恢复机制。
- 发布历史 TAB：追加式 JSONL 持久化每一次发布尝试，支持逐平台结果回看与一键重新发布。

## [1.3.9] - 2026-11-09 至 2026-11-14

### 修复

- TTS：`NoAudioReceived`（声音语言 ≠ 脚本语言）快速失败并点名声音，不再浪费 3 次重试；`zh-` 系声音置顶，避免字母序把 af 声音排到最前（2026-11-09）。
- `webui.bat` 单实例重启：新增 `webui_port.ps1` 端口探测与残留实例识别，外部占用者绝不误杀（2026-11-09）。

### 新增

- 以下三项代码变更归属 ChangoVideo 子仓库（`opensources/changovideo`）：
  - ChangoVideo Studio 公网访问（Cloudflare Tunnel，`video.` / `film.weclass.school` 双源公网接缝）（2026-11-13）。
  - Web 创作对话接入 Web Studio 并做成自适应 PWA（BYOK 模型设置、公网工具收紧）（2026-11-14）。
  - 公网助手自省能力：`changovideo status` 聚合命令，助手先查能力再作答（2026-11-14）。

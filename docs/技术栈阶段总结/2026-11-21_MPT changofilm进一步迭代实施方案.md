# MPT（changofilm）进一步迭代实施方案：v1.7.0 之后的专业系列短剧生产化路线

- 日期：2026-11-21
- 基线：v1.6.0（B1 文档+Demo）与 v1.7.0（B2–B8 生产实施）均已交付，**全部变更尚未提交**
- 产品定位（已定决策）：外层 MPT 更名 **changofilm**，闭源商业产品，定位**专业系列短剧**
  （Series→Episode→ScriptPlan→Scene）；changovideo 定位专业商业广告片，另见其独立方案文档
  `opensources/changovideo/docs/技术栈阶段总结/2026-11-21_changovideo商业广告片平台进一步迭代实施方案.md`
- 前序文档：[需求与方案（B1–B8 路线图）](2026-11-20_MPT脚本方案专业模式与本地AI短剧系列需求与方案.md) ·
  [v1.6.0 迭代记录](../迭代记录文档/v1.6.0_2026-11-20_脚本方案专业模式与本地AI短剧系列Demo.md) ·
  [v1.7.0 迭代记录](../迭代记录文档/v1.7.0_2026-11-20_脚本方案专业模式与本地AI短剧系列生产实施.md) ·
  [openfilm 借鉴方案（融合路线 A→C→B）](../2026-11-17-openfilm借鉴方案.md)
- 调研输入：`opensources/` 第一批六仓库克隆与许可证审计（2026-11-20/21，详见 §3）

---

## 1. 基线盘点：v1.7.0 已交付能力与遗留缺口

### 1.1 已交付（B2–B8，全部有测试门禁）

| 能力 | 生产锚点 | 门禁证据 |
| --- | --- | --- |
| ScriptPlan fail-closed 模型 + LLM 方案生成 + `stop_at="plan"` + REST | `app/models/schema.py`（16 模型）、`llm.py`、`task.py`、`controllers/v1/video.py` | B2 75 passed |
| 本地引擎 provider（ComfyUI t2i/FL2V + ACE-Step） | `comfy_local.py`（requestKey 缓存/WS 进度/`/free`+OOM 重试）、`acestep_local.py`（300s 预热） | B3 73 passed |
| 方案驱动执行（cue 切窗→timeline→逐场景绑定） | `plan_compiler.py`、`video.py combine_videos(timeline=)`、`material.py` | B4 47 passed，含真实 ffmpeg 同 seed 逐字节确定门禁 |
| 首尾帧链 + 边界跳变审查 | `keyframe_chain.py`（共享边界帧同文件复用）、`review.py scene_boundary_jump`（阈值 40/30 实测校准） | B5 真机 E2E 三门禁通过（lowvram，760s/两场景） |
| 系列持久化 + 参考图锁 + 对白时间轴 | `series_store.py`、`dialogue_timeline.py` | B6 25 passed |
| 生产 WebUI 三新页 + 草稿库 + llamacpp | `webui/Main.py`（render-all 壳）、`plan_store.py`、`llm_provider.py` | B7 13 passed（AppTest） |
| 增量渲染：逐场景转场 + ASS 字幕烧录 + ffprobe 降级 | `video_project.py`（指纹向后兼容，`RENDERER_VERSION` 不变） | B8 10 passed，含增量重渲门禁 |
| 全套件零新增回归 | `.tmp-ui-impl/final-gate-diff.txt` | GATE PASS，NEW failures (0) |

### 1.2 遗留缺口（本方案的驱动来源）

1. **提交治理**：B1（v1.6.0）+ B2–B8（v1.7.0）+ 升版产物全部未提交，且与外族 WIP
   （auto-publish demo、字体文件）混存——任何后续迭代前必须先分批入库（C0）。
2. **真机证据只覆盖两场景**：B5 E2E 是两场景共享帧链；**整集（6+ 场景）×多集**的
   系列级真机生产尚未跑通；lowvram 下单场景约 6 分钟，整集耗时/排队/失败恢复无实测数据。
3. **叙事质量无机器门禁**：现有 review 是画面/音频层（边界跳变、frozen_sequence 等）；
   短剧商业核心——钩子密度、付费点位置、集尾悬念、爽点节奏——完全依赖 LLM 自觉，无检查。
4. **角色一致性只有"参考图锁"，没有"漂移检测"**：跨集主角换脸只能人工发现；
   IPAdapter 强度/seed 参数包未系列化冻结。
5. **编剧知识未资产化**：`build_script_plan_prompt` 是单一通用 prompt；题材×叙事弧×
   分镜技法没有结构化技能库，本地 26B 模型输出质量波动大。
6. **多音色对白仅 v1**：分轨装配已有，口型/画面同步、对白演出后置项未设计。
7. **基线 61 个既有失败**（字体资源缺失等）+ 9 个 flaky 未收敛，长期侵蚀门禁信噪比。
8. **llama.cpp 端口待用户确认**（不阻塞 Ollama 主路径）。
9. **changofilm 更名未执行**（独立决策已记录，执行是单独任务）。

---

## 2. 总体路线与版本政策

- 下一迭代目标版本 **v1.8.0**（minor：新增功能），按"每次迭代必升版"政策同步
  `app/__init__.py` 与 `pyproject.toml`，Grep 清理旧版本硬编码（codex_oauth User-Agent、
  packaging.md、uv.lock 自条目、Demo 徽章），历史快照不改。
- 批次编号续接 B 系列，用 **C0–C8**；每批次独立门禁（新增 pytest 全绿 + 全套件失败集
  diff 对基线零新增），真机批次附证据目录（`.tmp-ui-impl/evidence-c*`）。
- 依赖关系：C0 先行 → C1/C2/C3/C4 可并行 → C5 依赖 C1+C3 → C6 依赖 C1–C4 →
  C7 独立穿插 → C8 最后（更名涉及面广，避免与功能批次混批）。
- 总估时 18–26 个工作日（不含 C8 更名与用户确认等待）。

---

## 3. 调研成果吸收矩阵（许可证合规前置）

第一批克隆审计结论（LICENSE 均从磁盘核验）：

| 仓库 | 许可证 | 吸收方式 | 目标批次 |
| --- | --- | --- | --- |
| zenstory-ai/drama-skills | MIT ✅ | **代码级**：全链路技能定义（拆小说/开发/剧本/角色资产/分镜/提示词/审查）移植为本地技能库 | C4 |
| lixiaoxiao9888-create/short-drama-factory | MIT ✅ | **代码级**：E1~E26 机器检查模式 + 付费点/钩子/悬念模型移植为叙事审查器 | C2 |
| Forget-C/Jellyfish | Apache-2.0 ✅ | **代码级**（保留署名）：`core/contracts` 一致性契约思想 → 角色/地点一致性档案与漂移检测 | C3 |
| UnderleveledBuilder/awesome-short-drama-skills | CC0-1.0 ✅ | 素材级：P1 克隆候选清单（manju-laoli-skill、ai-manju-skills、OnlyShot 等）；嵌入第三方内容逐字复制前抽查原始出处 | C4/C6 |
| HBAI-Ltd/Toonflow-app | MIT ✅ | **思想级为主**：节点编排/多平台 provider 聚合参考；**不引入节点画布 UI**（B1 §9 拒绝项 1 维持） | C6 队列参考 |
| xixihhhh/clipforge | **AGPL-3.0 ❌** | **仅限思路参考，净室重写**：发布门禁（广告法词表/素材署名/AIGC 标注）思想用于 changovideo 侧；changofilm 侧仅借鉴"成片 QC 清单"组织方式，**禁止复制任何代码/文本资产** | — |

合规红线（闭源产品）：
- MIT/Apache 借鉴文件保留原始版权声明；Apache 代码若上游无 NOTICE 则自建 attribution 段落。
- clipforge 目录仅作阅读参考；任何实现不得参照其源码逐行改写（净室：先写规格，再独立实现）。
- 新增第三方依赖前查 SPDX；AGPL/GPL 一律拒绝（先例：edge-tts-universal→msedge-tts）。

---

## 4. 批次详案

### C0 提交治理与基线冻结（前置，0.5–1 天）

- 交 `version-release` 流程按归属分批入库：
  1. B1 批次（v1.6.0 Demo/方案/记录）先行或并入各自批次；
  2. B2–B8 按 v1.7.0 记录 §2 分组；`release: v1.7.0` 批纳入升版产物与两篇记录；
  3. **外族 WIP 严禁混入**：`docs/ui-demo/auto-publish-cn.html`（+1 注释）、
     `auto-publish-cv-v2*`（属 changovideo 嵌套仓）、`resource/fonts/MicrosoftYaHeiBold.ttc`。
- 入库后重跑全套件，把失败集冻结为 **C 系列新基线**（`.tmp-ui-impl/pytest-c-baseline.txt`），
  替代 B 系列基线（61 failed 口径）。
- 门禁：`git status` 干净（除本地运行态）；新基线落盘。

### C1 系列级真机生产硬化（3–4 天）

目标：从"两场景演示"到"一整集×连续两集"可复现生产。

- 文件：`app/services/task.py`（系列批量入口）、`comfy_local.py`（排队/取消/断点续跑）、
  `keyframe_chain.py`（场景级失败隔离）、新 `app/services/series_run.py`（集级编排器）。
- 内容：
  1. 整集草稿档（minimax-draft 4-step）一键生成：失败场景隔离重试，不拖垮整集；
     每场景产物 requestKey 缓存命中即跳过（已有能力，补集级编排）。
  2. 集级断点续跑：`storage/series/{id}/runs/{run_id}.json` 记录逐场景状态
     （pending/running/done/failed），中断后从 failed/pending 续跑。
  3. 耗时/显存实测档案：lowvram 约束写入 `docs/`（24GB 设备禁 `--highvram`，
     19.53GiB UNet+1.82GiB LoRA 常驻即 OOM——v1.7.0 §3.3 已验证）；
     草稿档单场景耗时、整集耗时、`/queue` 深度播报实测回填。
  4. 云端升级路径真机验证：`volcengine_seedance` first/last_frame 条件化衔接
     至少一场景真跑（付费确认门禁已就位）。
- 门禁：**真机整集（≥6 场景）草稿成片** + 第二集复用第一集角色参考图；
  边界审查全切点统计落盘；失败注入测试（mock ComfyUI 中途断线）续跑正确。
- 风险：单 GPU 串行整集耗时长（草稿档预估 30–45 分钟/集）——夜间批跑 + 进度播报缓解。

### C2 叙事结构机器审查（short-drama-factory 移植，3–4 天）

目标：把短剧商业规则变成 fail-closed 机器门禁，对齐既有 review 通道。

- 文件：新 `app/services/narrative_review.py`、`app/services/review.py`（注册新 finding）、
  `app/models/schema.py`（ScriptPlan 增可选 `narrative` 标注块，extra=forbid 惯例）、
  `plan_compiler.py`（审查前置）、新测试 `test_narrative_review.py`。
- 移植内容（MIT，保留署名；先读 `opensources/short-drama-factory/` 的 E1~E26 检查清单
  与付费点/钩子/悬念模型，逐条映射为 Python 检查器，**不照搬其项目结构**）：
  1. **钩子密度**：前 3 秒/前 15 秒冲突强度检查（开场即冲突，warn/block 分级）；
  2. **付费点位置**：`cost.tier=="paid"` 场景必须落在悬念峰值后（与 exec_plan 确认门禁联动）；
  3. **集尾悬念**：Series 模式下每集末场景必须含 cliffhanger 标注（LLM 生成时强制字段，
     缺失 fail-closed 拒绝而非静默补全）；
  4. **爽点节奏**：压制→反转间隔的场景数上限；连续同情绪场景告警；
  5. **时长结构**：±10% 容差仪表已有，补"每场景时长分布"检查（单场景不超总长 40%）。
- 分级策略：block 级仅对 fail-closed 结构缺陷（缺 cliffhanger 字段等）；
  创作质量类一律 warn 走既有 `warnings` 通道，**不新增任务状态字段**（v1.7.0 惯例）。
- 门禁：E 系列检查器单测（正/反例各一）；对《灯火之上》ep1–ep3 种子方案跑审查，
  输出 findings 报告人工复核；无 plan 快速路径零回归。

### C3 角色一致性契约与漂移检测（Jellyfish 借鉴，3–4 天）

目标：跨集"主角不换脸"从人工验收升级为机器辅助门禁。

- 文件：`series_store.py`（一致性档案）、新 `app/services/consistency.py`、
  `keyframe_chain.py`（参数包冻结）、`review.py`（新 finding `character_drift`）、
  新测试 `test_consistency.py`。
- 借鉴内容（Apache-2.0，保留署名；读 `opensources/Jellyfish/backend/app/core/contracts/`
  与 `services/film/` 的一致性管理组织方式，Python 侧独立实现）：
  1. **一致性契约档案**：角色级冻结 `{reference_images(locked), seed, ipadapter_strength,
     prompt_suffix, palette}` 为 `consistency_contract`，跨集生成强制读取，
     修改需显式 unlock（已有参考图锁扩展为参数包锁）；
  2. **漂移检测**：同角色跨场景关键帧的人脸/主色直方图相似度（ffmpeg 抽帧 +
     现有图像处理依赖，不引重型新依赖）；低于阈值 warn `character_drift`，
     阈值先打印真实 fixture 统计再定（B5 校准惯例）；
  3. **地点一致性**：SeriesLocation 同契约化（场景背景漂移同样 warn）；
  4. 免训练边界明示：v1 仍是 IPAdapter+固定 seed，**LoRA 训练维持拒绝项**（B1 §9.7），
     仅在契约档案预留 `lora_mount` 空字段。
- 门禁：同角色跨两集关键帧相似度实测报告；契约篡改（改 seed/强度）fail-closed 拒绝；
  漂移检测对"换脸"负例 fixture 报警、对正常续集不误报。

### C4 编剧技能库资产化（drama-skills 移植，2–3 天）

目标：本地 26B 模型的方案生成质量从"靠运气"到"靠技能库"。

- 文件：新 `app/services/skill_library.py`、`storage/skills/`（JSON 技能包）、
  `llm.py`（`build_script_plan_prompt` 按题材×叙事弧装配技能片段）、
  `config.example.toml`（技能库开关）、新测试 `test_skill_library.py`。
- 移植内容（MIT，保留署名；读 `opensources/drama-skills/` 的技能定义结构——
  当前打开的 `docs/character-consistency-across-shots.md` 即其一致性技法文档）：
  1. 技能包 schema：`{id, stage(改编/开发/剧本/分镜/提示词/审查), genre_tags,
     arc_tags, prompt_fragments, checks}`，fail-closed 校验；
  2. 首批入库：GENRES×5 题材 × WIZ_ARC×6 叙事弧的提示词片段（Demo 已有模板，
     生产化）+ drama-skills 的分镜/角色一致性技法（与 C3 契约联动）；
  3. 装配规则：向导所选题材/弧 → 技能片段注入 plan prompt；用户可关（回退通用 prompt）；
  4. awesome 清单的 P1 仓库（manju-laoli-skill 等）克隆后按同一 schema 扩充，
     嵌入内容先查原始许可证。
- 门禁：技能包畸形输入 fail-closed；同题材同弧两次生成方案的结构稳定性对比
  （场景数/标注完整度）优于通用 prompt 基线；Ollama json_mode 路径不回归。

### C5 多音色对白演出 v2（2–3 天，依赖 C1+C3）

- 文件：`dialogue_timeline.py`（口型时间窗预留）、`schema.py`（speaker 演出字段）、
  `keyframe_chain.py`（说话人镜头提示词）、`plan_compiler.py`。
- 范围（克制）：逐说话人分轨已就位；本轮补**说话人镜头绑定**（对白场景自动切换
  说话人特写/过肩镜头提示词）与**口型时间窗标注**（cue 级 speaker 起止写入
  subtitle_cues 扩展字段，为将来口型驱动预留，不做实际口型生成）。
- 明确后置：真实口型同步（需额外模型，另立调研）；旁白主路径契约不动
  （B1 §9.2 拒绝项维持：整篇一次 TTS + cue 切窗）。
- 门禁：多音色方案端到端（两角色对白一集）真机或 stub 全链；旁白主路径回归零变化。

### C6 系列批量生产与成本仪表（3–4 天，依赖 C1–C4）

- 文件：新 `app/services/series_batch.py`、`webui/Main.py`（系列页批量入口）、
  `plan_store.py`（批量草稿）、`task.py`（队列）、i18n 14 locale。
- 内容：
  1. "生成下一集"生产化：大纲→方案→审查（C2）→确认→整集渲染（C1）一条龙，
     付费场景逐集确认（不一次性 blanket 确认）；
  2. 批量队列：多集串行（与 MPT 全局串行队列哲学一致），集间可暂停/取消，
     断点续跑复用 C1 run 记录；Toonflow 的队列/重试组织方式仅作思想参考（MIT 可查）；
  3. 成本仪表：本地引擎零边际成本 vs 云端升级场景的累计费用估算，
     系列详情页显示"本系列已花费/预估"；
  4. 系列级导出：整系列方案 JSON 打包导出/导入（plan_store 往返已有，补系列包装）。
- 门禁：三集系列批量 stub 全链（含中途取消/续跑）；成本累计单测；
  AppTest 壳新控件序列化契约（format_func 预算标签惯例）；14 locale 键集 diff 对齐。

### C7 测试基线收敛（独立穿插，2–3 天）

- 范围：61 个既有失败按根因分组（字体资源缺失为主）——可修复的修复
  （如 bundled 字体路径断言），环境依赖的标记 skip 并注明原因；9 个 flaky
  逐个定位（顺序依赖/资源竞争），修复或隔离。
- 门禁：收敛后全套件失败数显著下降且**零新增**；flaky 清单落盘；
  不改动生产逻辑语义（纯测试/资源修复）。
- 价值：后续所有批次门禁信噪比提升；建议 C1 之后立即穿插一轮。

### C8 changofilm 更名执行（独立批次，1–2 天，最后执行）

- 依据已记录决策：结构性魔改已深，弃用上游名；更名 changofilm，定位专业系列短剧。
- 范围清单（执行时先全量 Grep 审计再动刀）：`pyproject.toml` name/description、
  `app/__init__.py`、README 三语、`docs/packaging.md`、User-Agent、CLI 入口文案、
  WebUI 品牌/i18n 品牌键、Demo 徽章；**历史迭代记录/快照不改**；
  远程仓库名（mpt-film）与包发布名变更需用户单独确认。
- 门禁：全局 Grep 旧名残留仅存历史快照；pytest 全套件零新增；品牌截图留证。
- 注意：与功能批次严格分离，单独 `release:` 批提交。

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| lowvram 整集耗时过长（30–45 分钟/集草稿） | 用户等待体验差 | 草稿档先行+夜间批跑+进度播报；final 档仅确认后的付费/精品场景 |
| 本地 26B 模型叙事标注（cliffhanger 等）漏填 | C2 fail-closed 频繁拒绝 | 修复重试+技能库强约束（C4）+降级 legacy 三层（既有机制） |
| 漂移检测误报（正常光影变化） | warn 噪音 | 先打印 fixture 统计再定阈值（B5 惯例）；只 warn 不 block |
| MIT/Apache 移植夹带 copyleft 片段 | 闭源合规事故 | 移植前逐文件查上游 LICENSE/NOTICE；clipforge 净室红线；依赖 SPDX 审查 |
| 技能库 prompt 膨胀超本地模型上下文 | 生成质量下降 | 片段按题材/弧裁剪，总长预算门禁；超限回退通用 prompt |
| 更名波及打包/升级检查 | 老用户升级断裂 | C8 独立批次+版本检查器兼容旧名读取；远程名变更需用户确认 |
| 基线 flaky 干扰批次门禁 | 误判回归 | C7 提前穿插；门禁一律失败集 diff 而非绝对计数 |

## 6. 验收总纲

1. 每批次：新增 pytest 全绿 + 全套件失败集 diff 零新增（对 C0 冻结基线）。
2. 真机批次（C1/C3/C5）：证据目录 `.tmp-ui-impl/evidence-c*/`（report.json + 关键帧/切点统计），
   ComfyUI 以 `--lowvram` 启动为前置条件。
3. 迭代记录：`docs/迭代记录文档/v1.8.0_<日期>_<主题>.md`，升版产物随 `release: v1.8.0` 批。
4. 合规：所有移植文件带原始署名；clipforge 零代码接触证明（实现规格先行文档）。
5. 专业模式 opt-in 铁律不变：无 plan 快速流水线行为零变化（`timeline=None` 原路径逐字节守卫测试每批次复跑）。

## 7. 开放项（需用户确认，不阻塞主路径）

1. llama-server 实际端口/模型（B1 遗留，确认后仅改本地配置）。
2. C8 更名的包发布名/远程仓库名是否同步变更。
3. 云端升级场景的预算上限（C6 成本仪表的默认告警阈值）。
4. P1 克隆批次启动时机（awesome 清单：manju-laoli-skill、ai-manju-skills、OnlyShot、
   huobao-drama、CineGen-ShortDrama 等；沿用已验证的网络生存克隆方案）。
# ChangoVideo 制作流程（Guided Flows）实施方案

## 方案定位

在 ChangoVideo Studio 中新增「制作流程」：面向广告片等目标，把一次创作拆成可引导、可迭代、可回溯的步骤（简报 → 素材生成 → 入时间线/导出），每一步有独立的迭代历史，跨步共享一个资产池，并通过绑定槽把上游产物自动喂给下游。执行后端全部复用 Studio 现有能力（媒体动词、导出管线、项目时间线），不引入新的生成通道。

已确定的两项取舍：
- **范围**：产品级引导工作流（目录 Hub + 分步编排 + 资产池 + 迭代历史 + 一键导出）。不做 Agent 技能章节编排层。
- **路线**：借鉴 OpenMotion 工作流机制的状态契约与交互模式，在 ChangoVideo 现有能力上重新实现引擎；不移植其引擎与项目体系。

## 借鉴来源与边界

OpenMotion 的产品级工作流由五部分组成：流程目录（`shared/scenarios.ts`）、目录 Hub、分步工作区（`studio/src/scenario/*`）、命令式运行引擎（`gateway/scenario-runs.ts`）、bundle 导出。

| 借鉴（按 ChangoVideo 惯例重实现） | 不借鉴 |
|---|---|
| 状态契约：run / step / iteration / pool / binding | OpenMotion 的 design/motion 项目体系 |
| 命令式 mutate API、`requestId` 幂等、`expectedRevision` 乐观并发 | MCP 技能章节层（`shared/workflow.ts`） |
| 默认绑定自动计算、步依赖 `dependsOn` / `optional` | 其 gateway 引擎与 scenario UI 源码文件本体 |
| 资产池绑定槽、每步迭代历史、运行摘要列表 | 其封面素材（stage-art） |

许可：OpenMotion 为 Apache-2.0，允许吸收进闭源产品。本方案为 clean-room 重实现（server `.mjs` + `@ts-check` JSDoc，UI React TS）；若最终出现逐字复制的类型或文案，在 `THIRD_PARTY_NOTICES.md` 登记一条。

命名：产品名中文「制作流程」/ 英文 "Guided flows"，代码与 i18n 命名空间统一 `flows.*` / `flow-*` / `Flows*`。原因：`workflow` 在 ChangoVideo 中已是 skill 的一种 kind（库过滤 chip 英文 "Workflows"、中文「场景」），且 `recreate.workflow` 译作「工作流」，需避开。

所有新文件位于 `opensources/changovideo/packages/changovideo/`（下称 CV）。

## 分阶段范围

| 阶段 | 范围 |
|---|---|
| 第一阶段（MVP） | 1 个流程「产品广告片」× 3 类步：简报 → 产品图 → 入时间线/导出。工作量按「1 个引擎 + 3 类步面板」计。 |
| 第二阶段 | 视频步、配音/配乐步、默认绑定自动计算、Saved 库素材自动引入、迭代产物下载、导出来源标记 |
| 后置（另立计划） | Agent 代跑、口播解说与短剧切片包两个流程、封面系统、社媒文案生成、运行历史分页 |

## 第一阶段：服务端

### 1. 状态契约 `studio/server/flow-runs.mjs`（纯函数 + JSDoc typedef）

```js
// FlowRun
{ schemaVersion: 1, id, flowId, title, projectPath, activeStepId, revision, locale,
  createdAt, updatedAt, archivedAt: null | number, steps: StepState[], pool: PoolItem[] }
// StepState
{ stepId, status: 'todo' | 'in-progress' | 'done' | 'skipped', iterations: StepIteration[],
  activeIterationId, bindings: Record<string, string[]>, draft: Record<string, unknown>, placedClipIds: string[] }
// StepIteration
{ id, number, createdAt, source: 'generated' | 'local' | 'manual' | 'upload', prompt, settings, inputs,
  outputs: ({ type: 'pool', poolItemId } | { type: 'brief', values } | { type: 'script', text })[],
  job: { state: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled', verb, model, error } | null,
  note, requestId }
// PoolItem
{ id, kind: 'image' | 'video' | 'audio' | 'text',
  ref: { type: 'project-file', rel } | { type: 'saved', rel } | { type: 'text', stepId, iterationId },
  label, source: 'upload' | 'generated' | 'step-output' | 'library', stepId, tags, pinned, addedAt }
```

- 限额：pool 500、每步迭代 50、run 2MB、brief 4000 字、文案 5000 字、列表 200、bundle 500MB。
- 纯 transition 函数（fail-closed，风格同 `ad-workflow.mjs`）：绑定槽 kind 校验、迭代激活、步骤完成门槛（至少一个 completed 迭代或显式 skip）、`expectedRevision` 不符返回冲突。
- 路径约定：`projectPath` 比较沿用 `tasks.mjs` 的 `resolve()`；`rel` 统一使用 `/`。

### 2. 流程目录 `studio/server/flow-catalog.mjs`

MVP 只定义 `product-ad`：

| 步 | kind | 动词 | 依赖 | 说明 |
|---|---|---|---|---|
| `brief` 创意简报 | brief | — | — | 复用 `createBriefs()`，已确认的 brief 存于项目 `.film/`，不平行再存一份 |
| `product-images` 产品图 | media | `image` | brief | prompt 模板复用 `ad-brief.mjs` 的 `beatPrompt` / `storyboardSet` |
| `assemble` 入时间线 / 导出 | assemble | — | product-images | 写入时间线并提交导出 |

步定义结构：`{ id, kind, verb?, dependsOn, optional, slots: [{ key, kinds, max }], presets }`。
能力就绪态由 `get.mjs` 的 `catalog()` / `chooseProvider(verb, settings)` 推导；未就绪的步显示配置引导。媒体模型沿用 Settings 里按媒体种类的全局选择（`use/model[kind]`），流程内不做模型选择器；「高级」折叠里才允许用 `shownChoices(settings)` 覆盖 `via + model`。

### 3. 运行引擎 `studio/server/flows.mjs`

```js
export function createFlows({ home, exports, tasks, machine, busyProject, emit, makingMedia, readPrefs, projectRoot })
```

由 `server.mjs` 注入现有单例：`exports`（导出管线）、`tasks`、`machine`（跨实例 lease）、`busyProject = agentIn`、`emit = toPages`（全局事件流）、`readPrefs`。

命令：`ensureRun / step.start / step.cancel / step.retry / iteration.activate / pool.add / pool.remove / pool.pin / binding.set / step.skip / step.complete / assemble.place / run.export / run.archive / run.delete`。

关键规则：

- **异步执行**：`step.start` 立即落盘 `job.state = 'running'` 并返回 202；`runGet` 在后台运行并持有 AbortController 供 `step.cancel`；关页、刷新、隧道超时都不影响已开始的生成。
- **进度事件**：经全局流发送 `{ type: 'flow', runId, stepId, iterationId, phase, done, total }`，节流 ≥200ms；`ui/src/api.ts` 的 `FolderEvent` 联合类型同步扩展。
- **迭代产物不互相覆盖**：每次生成使用唯一输出名 `out = \`${runId.slice(0, 6)}-${stepId}-${n}\`.slice(0, 120)`（满足 `get.mjs` 对 out 的正则：无扩展名、无路径）。
- **结构化收据**：给 `runGet` 增加 `{ raw: true }` 选项，返回 `{ text, receipt, args }`（向后兼容，现有调用不变）；引擎用 `receipt.src ?? receipt.images[].src` 注册 pool item。
- **并发守卫**：mutex 为 `Map<projectPath, Promise>`（同一项目同一时刻只跑一个媒体步）；`busyProject(path) || machine.held('agent', path)` 为真时返回 409 `code: 'agent-running'`（复用现有文案）。
- **忙碌计数与关停**：`makingMedia(fn)` 封装生成调用（与 `/api/get` 路由共用同一计数），`quit?whenIdle` 据此等待；`shutDown` 调用 `flows.stopAll()`（abort 全部 running 步、标 failed、落盘）。
- **费用同意**：仅视频步需要——步内勾选后以 `yes: true` 调用；`readPrefs().autoAllowVideoSpend` 为真时免勾选；需要询问时通过自定义 `ask` 回调经全局流弹到流程页自己的确认框。图片/配音/配乐步不做额外询问。
- **Saved 库素材**：绑定到首帧/参考图槽时，对 `{ type: 'saved' }` 项先 `takeSaved(root, path)` 复制进项目，并把 pool item 的 ref 回写为 `project-file`。
- **入时间线** `assemble.place`：按槽序生成 ops 调 `editProjectFilm(root, base, ops)`；再次 place 先 `remove` 上次的 `placedClipIds`；写入记为人的编辑（person-edits 保留，不被 agent 覆盖）。
- **导出** `run.export`：调用注入的 `exports.start(project, ask, { folder, source: 'workflow' })`；bundle 用 `zip.mjs` 打包（brief + 各步激活迭代产物）。
- **自动发布边界**：`publish.mjs` 的 `submitAuto` 对 `source: 'workflow'` 的导出跳过；Assemble 步在 `publish.enabled && autoUpload` 时显示提示并二次确认。流程本身不自动上传。
- **幂等**：`step.start` 必带 `requestId`，重复提交返回同一迭代；付费生成以 `derivedRequestId(requestId)` 去重。
- **持久化**：`<CHANGOVIDEO_HOME>/flows/<runId>.json`，串行化 save chain（同 `tasks.mjs` / `schedules.mjs`）；启动时把遗留的 running 标为 failed；列表与广播只发 summary（不含 pool 全量）。
- **项目删除/移动**：监听现有项目事件，把对应 run 标 `archivedAt`，Hub 显示「项目已删除」并提供归档/删除。

### 4. 路由 `studio/server/flow-routes.mjs` + `server.mjs` 挂载

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/flows` | 目录 + 各步能力就绪态 |
| GET | `/api/flows/runs?offset&limit` | 运行摘要列表 |
| POST | `/api/flows/runs` | 新建（`flowId, projectPath` 或 `newProject: name`） |
| GET | `/api/flows/runs/:id` | 单个 run 全量 |
| POST | `/api/flows/runs/:id/command` | `{ intent, args, requestId, expectedRevision }` → 202 |
| GET | `/api/flows/runs/:id/bundle` | 下载 bundle |

挂载方式仿 `task-routes.mjs`；`hostEffect` 不会拦截 `/api/flows*`。

### 5. 服务端测试（node:test）

- `flow-runs.test.mjs`：transition、限额、绑定校验、revision 冲突。
- `flows.test.mjs`：异步 start、requestId 幂等、取消、重启恢复、按项目 mutex、409、`assemble.place` 幂等、export bundle、`stopAll`。
- `flow-routes.test.mjs`：路由契约、202、404/409。
- `get.test.mjs` 增补 `{ raw: true }` 回归用例；`publish.test.mjs` 增补 `source: 'workflow'` 跳过用例。

## 第一阶段：UI

挂载模式仿 `SchedulesPage`（`createPortal` + `role="dialog"` + `fixed inset-0`，Escape 关闭）；入口按钮加在 `ProjectsLibrary.tsx` 与 `ProjectView.tsx` 工具栏。

### `ui/src/components/FlowsPage.tsx`（流程中心）
- 顶部：返回、标题「制作流程」、主按钮「新建流程」。
- 目录卡：图标 + CSS 渐变底（与 SkillsLibrary 的 kind 图标同一套）、标题、一句话、步数徽章、能力徽章（就绪 / 未连接，点开 `onOpenSettings`）。
- 运行历史表：标题、流程、项目（点开 `onOpenProject`）、进度 `1/3`、状态（运行中/已完成/已中断/已归档）、更新时间；行尾「继续 / 导出 / 删除」；删除后 8 秒 Undo。
- 新建对话框：选流程 + 项目，支持「新建项目」（`createProject(name)`）；一个 run 对应一个新项目，避免生成物混入已有项目。

### `ui/src/components/FlowWorkspace.tsx`（三栏工作区）
- 左栏 220px Stepper：步序号圆点 + 标题 + 状态；可选步用虚线圆点；底部「导出 bundle」。
- 中栏步面板（按 kind 路由）：
  - Brief：分组表单（字段样式同 `SchedulesDialog`）。
  - 产品图：prompt 文本域（预填简报对应拍的模板）+ 预设 chip + 绑定槽（空槽虚线框，点开 `requestPick` 对话框）+「生成」「生成并继续」；进度条来自 `flow` 事件。
  - 入时间线/导出：导出预设下拉 + 进度条（复用导出中心的 `phase / framesDone / rate / etaMs`）+「打开导出中心」+ 自动发布提示。
- 右栏 300px：资产池（kind 过滤 chip、pin 星标、缩略图网格、「从项目媒体 / 从 Saved 库 / 上传」添加）；迭代历史（版本、时间、激活标记、备注行内编辑、单步下载）。
- 顶部运行摘要：流程名 › 项目名 › 进度。

### 其他 UI 改动
- `ui/src/lib/flow-view.ts`：stepper 状态、进度、摘要等纯函数 + `lib/flow-view.test.ts`（仿 `schedule-view.ts`；仓库 UI 测试为 node:test，只匹配 `lib/*.test.ts` 与 `components/*.test.ts`，不在子目录放测试，不做 DOM 单测）。
- `ui/src/api.ts`：flow client + `FolderEvent` 扩展。
- i18n `flows.*` 五语言（en / zh-CN / ja / ko / es）。

## 第二阶段内容

- `defaultBindings(run, flow)`：上游 image 的激活输出 → video 的 `firstFrame` 槽；audio → `soundtrack`；brief 文本 → TTS 的 `script`。
- 视频步：行内勾选费用同意 → `yes: true`。
- 配音/配乐步：先调用 `voice` 动词列出声音并选择（`tts` 的 `voice` 为必填）。
- Saved 库素材绑定时自动 `takeSaved`；迭代产物下载。

## 验证与收尾

- 门禁：CV `package.json` 的 `test` 脚本（node:test）+ tsc server / ui / desktop；对照已知环境基线零新增回归。
- Playwright 实测（强制 localStorage `changovideo.language = 'en'`）：新建项目 run → 简报 → 产品图真实生成 → 绑定 → place 入时间线 → 导出；重启后 run 恢复；截图留证 `.tmp-byok/`。
- 收尾按 fork 规则：changeset（minor）+ `docs/迭代记录文档/vX.Y.Z_日期_制作流程.md` + 同一 pass 重写 `whats-new.ts` 五语言；提交/推送另走发布流程。

## 假设与风险

- 媒体步不进入全局 tasks 队列（该队列管 agent turn）；并发由按项目 mutex + `agentIn` / `machine.held` 约束。跨实例「另一 Studio 的流程写同一项目」暂不互斥，需要时给 machine lease 增加 `flow` 种类。
- 公网隧道约 100s 响应超时与 100MB 请求体上限依据 Cloudflare 公开文档，代码中未核实；异步 202 + 事件流已规避响应超时，bundle 走下载响应不受请求体上限影响。
- `runGet` 的 `{ raw: true }`、`exports.start` 的 `source` 参数是对现有模块的小改，各补回归用例。
- Agent 代跑需要 agent → run 的步骤级回写工具、tasks 的 `source: 'workflow'` 与 `onEnd` 组合，且无人值守 turn 会预批准全部媒体花费，须在 UI 明示；不在本方案范围内。

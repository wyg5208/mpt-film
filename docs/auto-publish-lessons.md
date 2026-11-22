# 国内平台自动发布集成：踩坑与经验总结

> 日期：2026-11-19 · 范围：MoneyPrinterTurbo × social-auto-upload（sau）四平台（抖音 / 视频号 / 小红书 / B站）自动发布联调
> 定位：可分享给其它项目的通用经验。每节按「现象 → 根因 → 修复 → 可复用教训」组织，文末附通用检查清单。

## 0. 背景与架构一句话

视频生成完成后，经既有 cross-post 状态机（pending/processing/complete/failed + 有界队列）路由到发布通道：
国内走 sau CLI 子进程（MIT，Playwright/patchright 浏览器自动化 + cookie 会话），海外走 Upload-Post API。
发布永不阻塞视频生成；队列满降级为可查询的 failed 状态。本轮联调暴露的问题全部集中在**浏览器自动化与国内网络环境**这两层。

## 1. 问题总览

| # | 现象 | 根因层 | 一句话根因 |
|---|------|--------|-----------|
| 1 | 发布卡在 5%，实时日志面板空白 | 子进程日志 | sau 的 loguru 控制台 sink 是 **stdout**，泵只回调了 stderr |
| 2 | 抖音上传反复失败重试 | 风控/进程 | 无头浏览器 + 重启后残留的孤儿浏览器进程，同账号双开 |
| 3 | 进了发布页、填了标题，视频却没上传 | 页面状态 | 失败尝试留下草稿，页面落到 `enter_from=draft`，文件注入丢失 + 引导浮层干扰 |
| 4 | 视频"上传解析中"后整个发布失败 | 等待预算 | 标题表单要等上传+解析完成才渲染，固定 120s 等待不够 |
| 5 | 手工在自动化浏览器里上传也失败 | 账号/IP 风控 | 高频失败触发账号级标记；浏览器指纹（临时 profile + en-US）加重嫌疑 |
| 6 | 视频号登录报 `Chromium distribution 'chrome' is not found` | 启动配置 | 该平台兜底用 `channel="chrome"`（系统 Chrome），机器未安装 |
| 7 | 小红书登录二维码 30s 超时，`img src=""` | DOM 状态判断 | 用"文字存在"判断面板已激活，手机号登录模式下切换按钮文字同样可见 |
| 8 | B站登录报 `RemoteDisconnected` | 工具链下载 | 不是 B站问题：biliup 二进制从 GitHub 下载被墙，从未安装成功 |

## 2. 子进程日志流：stdout / stderr 都要泵

**现象**：WebUI 发布进度永远 5%，日志展开面板空白，但 sau 自己的 `logs/douyin.log` 在活跃滚动。

**根因**：sau 的 `utils/log.py` 执行 `logger.remove()` 后 `logger.add(sys.stdout, ...)`——loguru 控制台输出走 **stdout**。
宿主侧的子进程流式泵只把 stderr 回调给 UI，stdout 只攒着等退出，于是实时面板全空。

**修复**：stdout 与 stderr 两个泵都接 `on_output` 回调；测试用真实子进程同时打印两路验证。

**教训**：
- 集成任何 CLI 前，先确认它的日志 sink 到底写哪一路（loguru/logging 可配置任意 sink，"日志=stderr"是假设不是事实）。
- 实时日志面板空白 ≠ 子进程没干活；先找子进程自己的日志文件交叉验证。

## 3. 无头浏览器、孤儿进程与国内风控

**现象**：抖音上传每 30 秒失败重试一次，持续十几分钟。

**根因**（两个叠加）：
1. sau `upload-video` 默认 `headless=True`；国内创作者平台对无头浏览器敏感，且验证码/短信弹窗用户看不见。
2. 重启 WebUI 只杀了 WebUI 进程，**上一轮的 sau.exe + chromium 进程树还活着**，同账号两个浏览器同时上传——风控诱因。

**修复**：
- 新增 `social_publish_headed` 配置（默认 true），发布命令显式传 `--headed/--headless`；配置在入队时快照，UI 高级设置可切换。
- 例外：B站上传走 biliup（无浏览器），**不接受** headed/headless 参数，传了会 argparse 崩溃——按平台豁免。
- 排查残留：`Get-CimInstance Win32_Process` 过滤 sau/chrome，`taskkill /F /T /PID` 杀整棵树。

**教训**：
- 桌面部署的国内平台自动化，默认有头；无头只留给无桌面服务器，并接受更高风控概率。
- "重启应用"不等于"重启自动化"：子进程树独立于宿主生命周期，重试前先查残留进程。
- 给子进程传平台相关参数前，逐个核对各平台的参数表，别假设统一。

## 4. 草稿恢复与引导浮层：把"异常页面状态"当一等公民

**现象**：浏览器停在 `creator-micro/content/post/video?enter_from=draft`，标题描述都填了，视频始终没上传，等待循环无限空转。

**根因**：上传失败后抖音自动存草稿；再次进入时页面落在**草稿编辑态**，原本在 `/content/upload` 做的文件注入已丢失；
新手引导（shepherd）浮层进一步拦截交互。上游代码只认 `enter_from=publish_page`，且对"上传完成"标记无限等待。

**修复**（本地补丁，五层防护）：
1. URL 匹配改 glob，接受任意 `enter_from`（含 draft）；
2. 关键节点移除已知引导浮层（`.shepherd-element` 等），**不动**短信验证等业务弹窗；
3. 空闲自愈：无上传进度条且存在文件 input 时，重新 `set_input_files` 注入视频（15s 节流）；
4. 被踢出内容页时自动导航回上传页重注入；
5. 所有等待加显式 deadline（进页 5 分钟 / 上传 10 分钟），超时抛 RuntimeError——**失败要响，不要挂**。

**教训**：
- 浏览器自动化的等待循环必须带 deadline；无限等待把"失败"伪装成"进行中"，是最贵的故障形态。
- 平台会把失败尝试沉淀为草稿/恢复态；自动化要能识别并自愈这些状态，而不是假设每次都从干净页面开始。
- 浮层分两类：装饰性引导（可删）与业务验证（必须留给人工/专门流程），删除清单要精确。

## 5. 表单渲染依赖上传解析：等待要"状态感知"

**现象**：视频真的传上去了（页面显示"上传解析中"），但发布随后失败。

**根因**：抖音发布页的标题/描述表单**要等视频上传+解析全部完成才渲染**。账号因当天约 20 次失败被风控拖慢解析，
固定 120s 的表单等待超时 → TimeoutError 杀死整个流程。日志止于"开始填标题"，成功标志日志从未出现。

**修复**：表单等待改分轮 polling（每轮 30s、总预算约 6 分钟），轮间清浮层并打日志（`解析中=True/False`），
让实时面板能看到"在等解析"而非假死；超时报错明确提示清草稿、低频重试。

**教训**：
- 固定超时是对"正常耗时"的猜测；风控/降级场景下耗时会数量级变化。等待应感知页面状态（解析中/上传中）并弹性预算。
- 诊断"卡住"时，先定位日志止于哪一步、缺了哪条成功标志日志，比盯着进度百分比有效得多。

## 6. 真实用户身份：持久化 profile + 一致的本地化画像

**现象**：用户在自动化浏览器里**手工**上传也失败——说明封锁在账号/IP 层，但浏览器指纹仍在加重嫌疑。

**根因**：每次发布都开全新临时 profile（无历史/缓存/localStorage）+ 上下文默认 en-US——两个强机器人信号。

**修复**（抖音视频+图文两条路径共用 `_launch_real_user_context`）：
- `launch_persistent_context`，每账号独立 profile（`browser_profiles/<账号>/`），人工干预与自动化共用同一身份，互相"养号"；
- `locale=zh-CN`、`languages=['zh-CN','zh']`、`timezone_id=Asia/Shanghai`、常见笔记本分辨率，与国内住宅 IP 画像一致；
- cookie 文件仍是登录态唯一事实源：启动注入、结束回写；
- 保留 patchright + stealth.min.js + 禁用 AutomationControlled。

**有意的副作用**：profile 的 ProcessSingleton 锁使同账号并发发布第二个立即报错——正是期望的约束。

**边界（务必诚实告知用户）**：身份完善降低**未来**被标记的概率，解不开**当前**的账号/IP 级封锁；后者只能冷却或换网络。
拒绝的方案：UA 覆盖（与真实 Chromium 版本不符反而更假）、机房代理（风控更严）。

**教训**：
- 反检测不是堆 stealth 脚本，而是让画像**自洽**：语言/时区/IP/历史行为一致。
- 临时 profile 是强信号；持久化 profile 同时解决了"人工干预成果无法沉淀"的问题。
- 用文件系统锁天然防同账号并发，比在业务层加锁更可靠。

## 7. 浏览器 channel：`chrome` ≠ `chromium`

**现象**：视频号登录报 `Chromium distribution 'chrome' is not found at C:\...\chrome.exe`。

**根因**：Playwright 的 `channel="chrome"` 找**系统安装的 Google Chrome**；`channel="chromium"` 用随附/下载的 Chromium。
同一仓库里抖音/快手用 chromium，视频号兜底却用 chrome——机器没装 Chrome 就崩。

**修复**：兜底统一 `channel="chromium"`；一个共享 launch helper 覆盖登录/体检/视频/图文四处。

**教训**：多平台自动化仓库里，各上传器的启动配置是**复制漂移**的重灾区；收敛到共享 helper，一处修处处修。

## 8. 面板激活判断：状态驱动，而非文字存在

**现象**：小红书登录二维码 30s 超时，locator 命中 `hidden <img src="">`。

**根因**：`_open_xhs_qrcode_panel` 见"含'扫一扫'文字的 div"就提前返回。`has-text` 匹配祖先——手机号登录模式下
"APP扫一扫登录"**切换按钮**的文字同样可见，于是永远不点切换，二维码面板一直收起，img 空 src。

**修复**：以"二维码 img 可见且 src 非空"为激活判据；未激活则点切换图标 + JS 点击切换文字（绕过 `pointer-events:none`），
重试数轮；src 异步填充再 poll 10s。

**教训**：
- "某文字存在"≠"某面板已激活"；验证**实际载荷**（img src、列表内容）而不是标签文字。
- `has-text`/`get_by_text` 的祖先匹配特性经常让 `.first` 命中外层容器，写 locator 时要意识到。

## 9. 工具链 bootstrap 下载：先怀疑工具没装上，再怀疑平台

**现象**：B站登录报 `('Connection aborted.', RemoteDisconnected(...))`，二维码都没出现。

**根因**：错误来自 **biliup 运行时下载**而非 B站。首次使用需从 GitHub releases 下载 biliup.exe；
实测 `api.github.com` 可达但 `github.com` 资源下载超时（国内网络典型），二进制从未装成（目录为空）。

**修复**：
- 重试 + `(connect, read)` 分离超时（连接 15s 快速失败，不傻等 120s）；
- 镜像兜底（ghfast.top / gh-proxy.com，`SAU_GITHUB_MIRRORS` 可覆盖），**仅当 GitHub API 提供官方 sha256 digest 时才走镜像，
  下载后逐字节校验**，不符拒绝——第三方镜像下载可执行文件必须验供应链；
- 失败报错说人话：附手动下载地址与二进制放置路径。

**教训**：
- 平台登录期的原始连接错误，可能是**工具链 bootstrap** 失败；先确认期望的二进制/依赖真的存在。
- 国内网络要区分 API 域名与资源下载的可达性（api.github.com 通 ≠ github.com 通）。
- 镜像加速可执行文件 = 供应链风险，digest 校验是底线；拿不到 digest 就只走直连。

## 10. 可观测性与登录验收

- **进度模型**：sau 无细粒度百分比，按"平台×视频"单元粗粒度推进（5 + 90×完成数/总数），阶段 queued/metadata/uploading/done；
  日志尾 30 行、每秒节流写一次。粗进度 + 实时日志 + 阶段徽标，比假精确百分比更有用。
- **失败原因上卡片**：失败徽标后直接附错误尾部最后一行（异常消息），用户不必翻控制台。
- **排队天然成立**：复用既有有界线程池，发布中再触发自动排队，无需新队列。
- **登录验收三件套**：终端成功行 + `cookies/<平台>_<账号>.json` 生成 + `sau <平台> check` 返回 valid。
  手机端扫码确认**不等于** CLI 登录完成（二维码有 ~2 分钟轮询窗口，扫旧截图/关窗后扫都无效）。
- **终端二维码**：老 PowerShell 字符画会残缺；优先 `--headed` 扫窗口原生二维码（抖音/视频号/小红书支持），
  B站走 biliup 终端二维码，残缺时扫进程运行期间生成的 `./qrcode.png`。

## 11. 风控操作纪律（代码绕不过的部分）

1. 低频发布；同账号绝不并发浏览器（profile 锁已强制）。
2. 多次失败后**先清草稿箱**再重试——草稿恢复态是后续失败的温床。
3. 仍失败则冷却 30–60 分钟；账号级标记只能等它过期。
4. 换网络（如手机热点）可区分 IP 级 vs 账号级封锁。
5. 新持久 profile 首跑可能触发一次短信验证（新设备画像），有头窗口 + `verify_code.txt` 通道兜底。

## 12. 通用检查清单（分享给其它项目）

集成"CLI 子进程 + 浏览器自动化 + 国内平台"时，逐项过：

- [ ] 子进程日志 sink 确认（stdout/stderr/文件），两路都泵
- [ ] 每个等待循环有 deadline；失败抛可查询的错误，不无限挂起
- [ ] 等待状态感知（页面阶段文案/进度元素），超时预算弹性
- [ ] 异常页面状态（草稿恢复/引导浮层/被踢出）有识别与自愈
- [ ] 默认有头（桌面部署）；无头作为显式降级选项
- [ ] 重试前查残留进程树；同账号并发有硬约束
- [ ] 浏览器画像自洽：持久 profile、locale/timezone/languages 与 IP 属地一致
- [ ] 各平台启动参数/浏览器 channel 逐个核对，收敛共享 helper
- [ ] 面板/Tab 激活用实际载荷判断，不用文字存在判断
- [ ] 工具链 bootstrap 下载：重试 + 分离超时 + 镜像（带 digest 校验）+ 手动兜底说明
- [ ] 登录验收 = 会话文件 + check 命令，不以手机端表现为准
- [ ] 失败原因直达 UI；进度/阶段/日志可见
- [ ] 风控纪律写进用户文档：低频、清草稿、冷却、换网

## 2026-11-21 补充：抖音 CSP 依赖 BUG 与小红书风控加固

### 抖音上传卡 0%：patchright 1.58.2 的 CSP 改写 BUG（非风控）

上游 [social-auto-upload#307](https://github.com/dreammis/social-auto-upload/issues/307)：2026-11-05 起抖音上传页返回不含
`script-src`/`default-src` 的 CSP；patchright 1.58.2 注入 stealth 时会补一条
`script-src 'self' 'unsafe-eval' 'unsafe-inline' *`，而 `*` 不含 `blob:`，抖音上传组件的
blob Worker 被拦 → 卡「文件解析中 0%」约 60 秒后失败。

本地修复（与上游官方 commit bb99e5b 同逻辑，首个含修复的 Python 版本是 1.61.2，PR #308 升 1.64.4 尚未合并）：
改 `.venv/Lib/site-packages/patchright/driver/package/lib/server/chromium/crNetworkManager.js` 的 `_fixCSP`：
新增 `hasDefaultSrc` 跟踪，仅当原策略含 `default-src` 时才补 `script-src`。
**注意：补丁在 .venv 内，重装/升级 patchright 后会丢失，需重新应用或直接升级到 ≥1.61.2。**
验证脚本：`temp/verify_csp_patch.py`（A/B 对照：未补丁 blob Worker 被拦，补丁后正常；stealth 仍生效）。

### 小红书风控警告：指纹层 + 行为层双重加固

背景：xiaohongshu-mcp#674 记录了 2026 年中的封号潮，v2.1.1 落地反检测后测试账号持续正常。
我们的 XHS 上传器此前每次启动都是全新临时 profile + 机械化节奏，正好命中检测面。

- **指纹层**：`_launch_real_user_context` 移植自抖音侧（每账号持久化 profile、zh-CN、Asia/Shanghai、
  cookie 注入/回写），视频与图文两条上传路径均改用；登录/cookie 体检仍用轻量临时上下文（避免 profile 锁冲突）。
- **行为层**：新增 `uploader/xiaohongshu_uploader/humanize.py`——钟形分布随机延迟、逐字符打字（标点停顿/思考停顿）、
  贝塞尔轨迹点击（元素内随机落点 + 随机按压时长）、发布前预热浏览发现页。任何一步失败自动回退原生行为。
  环境变量开关：`SAU_XHS_HUMANIZE=0` / `SAU_XHS_WARMUP=0`。
- **附带修复**：抖音 main.py 缺模块级 `import json`，导致持久化上下文的 cookie 注入一直静默失败（被宽泛 except 吞掉）。
- **账号级标记无法用技术解除**：被警告账号需冷却 1–2 周（人工养号），再低频恢复自动化。
- 验证：`temp/smoke_persistent.py`（两平台持久化上下文 + cookie 注入 + webdriver 无泄漏）；
  XHS 相关 21/21 测试通过（含新增 humanize 专项 11 例）。

### 抖音上传完成后“没有任何后续动作”：会话失效被踢去登录页，表单等待盲等（2026-11-21 深夜实测）

现象：视频上传完成，但封面/AI 声明/发布按钮全都没动。日志显示
`标题表单还没渲染（解析中=False 上传中=False）` 连续刷到 6 分钟 deadline。

排查（只读 DOM 探针 + 真实视频全周期复现）：
- 当前发布页 `input[placeholder*=填写作品标题]` 选择器**未漂移**，上传全程及完成后标题框均可见可点；
  “表单要等上传完才渲染”的旧假设不成立，表单一开始就在。
- 事故 run 里 `上传中` 文本（含发布按钮旁静态提示文案）在 22:58 从 DOM 消失——整个表单区被替换，
  随后 23:03 cookie 体检判失效并扫码重登。结论：**会话中途失效/风控把页面踢去登录或验证页**，
  而等待循环只盯标题输入框、不看 URL，对着登录页盲等 6 分钟。

修复（`uploader/douyin_uploader/main.py`）：
- `_is_login_or_verify_url`：表单等待与上传完成等待两个循环每轮先查 URL，命中 login/passport/sso/verification/verify/captcha
  立即报错（不再空等），提示重新扫码后低频重试。
- `_dump_form_timeout_diagnostics`：任何表单超时/踢出都截图 + 记录 URL + 页面文本摘要到 logs/，下次失败有据可查。
- `_warmup_creator_home`：上传前先自然浏览创作者首页几秒（随机停留/移动/滚轮），视频与图文两路均接入，异常不阻断。
- 等待日志补上当前 URL，便于实时面板直接看出是否被踢出。
- 验证：新增 `tests/test_douyin_form_wait.py` 6/6 通过；双平台持久化冒烟 PASS；
  真实视频全周期探针确认正常路径标题框全程可点（诊断脚本 `temp/diag_douyin_upload.py`）。
- 教训：**CN 创作者平台的每个等待循环都必须状态感知（URL/登录/验证）+ 有 deadline + 失败留证**；
  “表单未渲染”不一定是 DOM 漂移，也可能是页面已被整体替换。

## 2026-11-22 补充：抖音表单折叠死状态自愈、解析等待与发布后核验

### 模式二死状态：上传完成但表单被折叠成“快速填写”入口

苏州视频真发实测（23:44–23:51）：上传完成、AI 封面已生成，但 post/video 页
（enter_from=publish_page）**只有“快速填写”按钮**（点开是以往视频复用弹框），
标题输入框不渲染；纯等 6 分钟无效。用户手动点“暂存离开”再重进编辑页后表单立即渲染
（草稿恢复态 enter_from=draft），运行中的脚本随即完成填写并发布成功。
同账号同晚的只读探针又见过表单直接渲染的变体 A → 死状态是**服务端下发的 UI 变体**，
不是选择器漂移，只能状态感知 + 自愈。

修复（`uploader/douyin_uploader/main.py` `_recover_stuck_form`，2026-11-22 用户纠偏后定稿）：
- 触发：上传完成标记（long-card 内“重新上传”）在 + 标题框 20s 不渲染；最多 2 次。
- **绝不点击/触发“快速填写”**（用户明确指示：复用弹框没有用；早期版本曾尝试
  弹框内手动/跳过入口，实测无效且弹框遮罩会拦截后续所有点击，已整段删除）。
- 唯一救援路径：底部“发布”按钮右侧的**暂存离开**（+确认弹框）→ 直连
  `post/video?enter_from=draft`（探针实测表单稳定渲染 60s+）；兜底：上传页
  “你还有上次未发布的视频”横幅→继续编辑。**不走内容管理页**：有草稿时管理页
  会重定向到上传页，列表里没有草稿，按钮文案是“编辑作品”而非“编辑”，审核状态也没有草稿筛选项。
- 残留弹框先关（Escape→关闭钮→点遮罩三重兜底），否则暂存离开被 semi-modal-wrap 拦截。
- 关键节点截图留证 `logs/douyin_form_recover_*.png`；失败不抛异常，回退继续等至 deadline。

### 先填基本信息，再走上传/解析核验（互联网方案对齐）

用户提示 + 开源参考（oil-oil/video-publisher-skill 的“上传中预填 + 草稿身份恢复”
模式）：不要等上传/解析全部完成才找表单，而是**表单一旦可用就立即填基本信息**；
表单折叠时先暂存成草稿、从草稿恢复态重进（表单稳定）再填，填完才走上传完成/解析核验。
本项目流程本就是“进发布页→先填标题/描述/话题→等上传完成→等解析→声明/封面/发布”，
本轮补齐的是折叠态下的“暂存→草稿重进→立即填”闭环。

### 表单“瞬态折叠”真根因：抗干扰清理盲删了表单容器（run5/run6 事故，探针定罪）

headed 真发 run5/run6：自愈恢复表单成功（截图可见完整表单）后 ~1s 标题输入框消失，
填写循环空等；headless 时序探针（`temp/probe_draft_timeline.py`）却全程稳定。
headed 每秒采样探针（`temp/probe_headed_collapse.py`）定罪：新版 UI 的
`publish-mention-wrapper-*` **包裹整个基础信息表单**（标题 input + 简介
contenteditable，且不在 semi-portal 内）；`_dismiss_guide_overlays` /
`_clear_blocking_overlays` / 发布循环三处“抗干扰清理”盲删
`[class*="mention-wrapper"]` → 表单容器被删 → React 下一轮重渲染折叠成
快速填写态。dismiss 调用后 1s 内输入框必消失；headless 探针不调 dismiss 故稳定；
用户手动救援不删 DOM 故有效——三个现象同一根因。
修复：三处清理均加守卫——含 `input[placeholder*=填写作品标题]` 或
`[contenteditable=true]` 的 wrapper/portal 一律跳过；残留话题下拉交给
semi-portal 非模态清理与 Escape/blur。修复后 headed 探针 47/47 采样全程可见、
0 折叠（dismiss 照常调用）。另保留防御纵深：标题 fill 后回读 input_value
核验落地，落空则暂存→草稿重进重填（最多 3 轮）。
教训：**“抗干扰/清浮层”的删除清单必须随平台改版重新验证；类名复用
（dropdown wrapper → 表单容器）会把抗干扰变成自毁**；删除型清理要带
“不得含业务控件”守卫；headed/headless 行为差异要用同条件探针定罪，不靠猜。

### 上传完成 ≠ 解析完成：下一步前必须等解析结束

用户实测反馈：“重新上传”标记只代表字节传完，页面仍可能“解析中”；
原流程传完立即走声明/发布易失败。新增解析等待段：`text=解析中` 存在则每 3s 轮询
（URL 守卫 + 5 分钟 deadline + 超时留证 + 仿人微动作），解析结束才继续。

### 发布后核验：跳管理页不再是“没有任何后续动作”

原流程把 `wait_for_url(content/manage)` 当成功信号后直接回写 cookie 关浏览器。
现新增：发布后在作品列表等新作品标题出现（15s，含审核中）并写日志；
看不到仅警告，不推翻成功判定。

### 其它本轮加固

- 表单等待/上传等待 deadline 统一提至 15 分钟（服务端变体/慢解析不再误杀）；
  等待轮日志带 long-card 进度文本，并加仿人鼠标移动/滚轮微动作。
- **解释器坑**：sau 的测试/发布必须用 `opensources/social-auto-upload/.venv` 的解释器
  （patchright 1.58.2 + CSP 补丁在那里）；宿主主 `.venv` 由 uv lock 管理，
  `uv sync` 会卸掉不在 lock 里的 patchright/playwright（本轮实测 ModuleNotFoundError 踩坑）。
- 验证：`tests/test_douyin_form_wait.py` 扩至 15 例全过（快速填写绝不点击守卫 + 三处清理表单容器守卫 +
  暂存→草稿救援 mock + 残留弹框 Escape + 标题落地核验/重填 + 循环接线 +
  解析等待/发布后核验源码守卫）；苏州视频已于 23:51 真实发布成功（用户救援协助）。
  根因修复后 headed 真发 run7 于 2026-11-22 01:05:57 发布成功
  《一句话，就是一支电影：ChangoVideo》（ChangoVideo自动视频创作 · 视频号.mp4，
  27.6 MB；标题/描述/5 话题/AI 声明全填，全程无人工干预，用户确认发布成功）。
- 教训：**把用户手动救援路径当成一等公民自动化**；平台 UI 变体随机下发时，
  选择器修正无效，状态感知 + 已验证救援路径才是治本。

## 2026-11-22 补充：抖音全流程拟人化层（用户两次提醒后补全）

- 背景：此前抖音只有上传前预热 + 等待轮鼠标微动作，标题仍是瞬时 `.fill()`、
  全部原生点击、发布后秒退出——用户两次提醒“要加入拟人化操作，包括适当的随机浏览”。
- 原语共享：新增 `uploader/humanize_core.py`（钟形延迟/逐字打字/三阶贝塞尔点击/
  分段滚动浏览），小红书 humanize.py 改薄包装（模块级名字与 SAU_XHS_* 开关、
  测试 patch 契约不变），抖音新增 `uploader/douyin_uploader/humanize.py`
  （SAU_DOUYIN_HUMANIZE / SAU_DOUYIN_WARMUP 开关）。
- 随机浏览三场景：warmup_browse 上传前逛创作者首页；idle_browse 等待期只在当前页
  移动/滚动/偶尔回看/停留（**绝不导航**，离开上传页会丢进度）；post_publish_browse
  发布后在内容管理页滚动作品列表再回写 cookie/关浏览器，打散“发布→秒退出”。
- 接线点：标题=贝塞尔点击聚焦+全选清空+逐字打字（保留 input_value 落地核验与
  3 轮折叠重填）；描述/话题逐字+话题间停顿；声明/合集/发布按钮贝塞尔点击
  （发布回退保留 force=True）；步骤间钟形停顿。
- 纪律：救援路径（_recover_stuck_form）保持原生点击——可靠性与速度优先；
  拟人层任何异常回退原生，绝不因拟人失败中断发布；测试加接线守卫防回退。
- 顺手修复：upload() 拆出 _upload_flow(context)，外层 try/finally 保证声明/发布
  中途失败也关浏览器（旧 declaration 测试因此复活，另两例 stale 测试适配当前架构）。
- 验证：五套相关测试 67/67 绿；headed 干跑（不发布）预热 6.9s、拟人填标题 4.4s、
  描述+2 话题 17.9s，标题回读一致、截图表单完好，暂存离开后“放弃”丢弃草稿，0 错误。
- 教训：**拟人化是全程行为形状，不是几个 sleep**：输入/点击/等待/收尾都要覆盖；
  共享原语时保住各平台测试的 patch 契约（asyncio 是同一模块对象，patch 全局生效）。

## 2026-11-22 补充：僵尸发布进程探测器（桌面端一键杀灭）

- 背景：重启/杀掉 WebUI 只终止 WebUI 本身，它派生的 sau.exe → node → chromium
  进程树变孤儿继续后台上传（2026-11-19 小红书僵尸任务实测遗留 3 天，14 个进程，
  同账号双开抬高风控概率）。用户要求：桌面端自己探测提醒，按钮直接杀灭。
- 实现（外层仓库，零新增 Python 依赖）：`app/services/publish_zombies.py`
  一次 PowerShell CIM 快照取全量 PID/父PID/名称/命令行/创建时间（缓存 20s，
  不拖慢 2s fragment）；`social_auto_upload._run_command` 增加活子进程 PID
  注册表（try/finally 登记/注销）作双保险。
- 判定纪律（宁可漏报不可误杀）：只认 `sau.exe <平台> upload-video/upload-note`
  命令行身份；只看**直接父进程**是否已死（或父 PID 被复用：现持有者出生晚于
  子进程）——沿祖先链上溯会把用户终端手动发布误判成孤儿（几乎每条链都终止于
  已退出的 userinit）；父进程健在的外部任务一律不碰；60s 宽限期防瞬态误判。
- 杀灭纪律：kill_zombie 先按 PID 重拉命令行重新核验身份（PID 复用/身份不符
  拒绝执行），再 `taskkill /F /T` 整树清理；杀后失效缓存。视频文件不受影响，
  Chrome profile 单例锁随进程死亡自动释放。
- UI：任务管理面板顶部警示区（先于空列表早退——重启后任务列表为空但孤儿仍在），
  每行标题/平台/账号/PID/存活时长 + 终止按钮，另有全部终止；14 语言 7 新键。
- 编码坑（实测踩坑）：PowerShell 5.1 重定向 stdout 的代码页随环境漂移，CIM 脚本
  必须显式 `[Console]::OutputEncoding=UTF8` 再 ConvertTo-Json，否则中文标题乱码；
  taskkill 输出按 `encoding="oem"` 解码。外层 GBK 控制台管道显示乱码不代表数据
  损坏——以落盘 JSON 文件为准。
- 验证：21 新测试 + 25 既有 sau 测试 + 7 WebUI 契约测试全绿；真机端到端实证
  （csc 编译无害 sleeper 伪装 sau.exe 发布命令行，经立即退出的 powershell 派生
  成真孤儿）：宽限期内不报 → 精确探测并解析全部字段 → 整树杀灭（含 conhost
  子进程）→ 杀后归零 → 对无关活进程拒绝杀灭（temp/probe_zombie_detector.json）。
- 教训：**杀进程自动化必须身份先行**：映像名/端口都不足以定身份，命令行模式 +
  父进程状态 + 杀前重核验三层缺一不可；孤儿判定只看直接父进程，祖先链上溯必误报。

## 附录：本地补丁清单（上游更新时需重查）

bundled 检出 `opensources/social-auto-upload` 内的本地修改（外层仓库 gitignore，不随提交）：

| 文件 | 修改 |
|------|------|
| `uploader/douyin_uploader/main.py` | 引导浮层清除、draft 页接受、空闲重注入、离页回归、15 分钟 deadline、解析感知表单等待、持久化真实用户身份（视频+图文）、模块级 `import json` 修复、登录/验证页踢出即时报错+超时截图留证、上传前预热浏览、表单死状态自愈（不点快速填写，暂存离开→草稿态重进，触发阈值 60s→20s）、三处抗干扰清理表单容器守卫（mention-wrapper 含表单控件不删）、标题落地核验+瞬态折叠重填、上传后解析等待、发布后核验、全流程拟人化（逐字打字/贝塞尔点击/随机停顿/等待期与发布后随机浏览）、upload() try/finally 中途失败也关浏览器 |
| `uploader/humanize_core.py` | 新增：平台中立拟人原语，小红书/抖音共用，异常回退原生 |
| `uploader/douyin_uploader/humanize.py` | 新增：抖音拟人层开关 + 预热/等待期/发布后三个随机浏览场景 |
| `uploader/tencent_uploader/main.py` | 启动兜底 `channel="chrome"` → `"chromium"` |
| `uploader/xiaohongshu_uploader/main.py` | 二维码面板状态驱动激活 + src 异步填充容忍、持久化真实用户身份（视频+图文）、拟人行为层接入 |
| `uploader/xiaohongshu_uploader/humanize.py` | 新增：随机延迟/逐字打字/贝塞尔点击/预热浏览，环境变量开关，失败自动回退；原语抽到 humanize_core 后为薄包装 |
| `.venv/.../patchright/driver/package/lib/server/chromium/crNetworkManager.js` | `_fixCSP` 仅在原策略含 default-src 时补 script-src（抖音 blob Worker 修复；**重装 patchright 后需重新应用**） |
| `uploader/bilibili_uploader/runtime.py` | 下载重试、分离超时、镜像兜底 + sha256 校验、友好报错 |
| `tests/test_xiaohongshu_uploader.py` | 话题等待超时断言 2000→4000（对齐既有代码漂移）；fill_meta 断言对齐拟人层原生路径（关开关保确定性） |
| `tests/test_xiaohongshu_humanize.py` | 新增：拟人层开关/延迟分布/逐字打字/贝塞尔点击/回退/预热专项测试 |
| `tests/test_biliup_runtime.py` | 新增：镜像 URL 选择与 digest 门槛测试 |
| `tests/test_douyin_form_wait.py` | 新增：登录/验证页踢出即时失败、超时留证、预热浏览、死状态自愈（快速填写禁点守卫）、标题落地核验、解析等待、发布后核验、三处清理表单容器守卫、拟人化接线守卫、try/finally 关浏览器守卫（22 例） |
| `tests/test_douyin_humanize.py` | 新增：抖音拟人层开关/逐字打字/贝塞尔点击/force 兜底/浏览不导航专项测试（17 例） |
| `tests/test_douyin_declaration.py` | 适配持久化上下文与当前构造签名（7 例） |

宿主侧（MoneyPrinterTurbo，随正常提交）：stdout+stderr 双流回调、`social_publish_headed` 配置/快照/UI/14 语言、
发布队列面板与阶段徽标、失败原因上任务卡。详见 [auto-publish-cn.md](auto-publish-cn.md)。
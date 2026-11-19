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

## 附录：本地补丁清单（上游更新时需重查）

bundled 检出 `opensources/social-auto-upload` 内的本地修改（外层仓库 gitignore，不随提交）：

| 文件 | 修改 |
|------|------|
| `uploader/douyin_uploader/main.py` | 引导浮层清除、draft 页接受、空闲重注入、离页回归、5/10 分钟 deadline、解析感知表单等待（6 分钟）、持久化真实用户身份（视频+图文） |
| `uploader/tencent_uploader/main.py` | 启动兜底 `channel="chrome"` → `"chromium"` |
| `uploader/xiaohongshu_uploader/main.py` | 二维码面板状态驱动激活 + src 异步填充容忍 |
| `uploader/bilibili_uploader/runtime.py` | 下载重试、分离超时、镜像兜底 + sha256 校验、友好报错 |
| `tests/test_xiaohongshu_uploader.py` | 话题等待超时断言 2000→4000（对齐既有代码漂移） |
| `tests/test_biliup_runtime.py` | 新增：镜像 URL 选择与 digest 门槛测试 |

宿主侧（MoneyPrinterTurbo，随正常提交）：stdout+stderr 双流回调、`social_publish_headed` 配置/快照/UI/14 语言、
发布队列面板与阶段徽标、失败原因上任务卡。详见 [auto-publish-cn.md](auto-publish-cn.md)。
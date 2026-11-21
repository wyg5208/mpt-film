/* ============================================================
   ChangoFilm · Three-Column Studio Console — demo app
   Plain JS, zero dependencies. All data embedded (file:// safe).
   ============================================================ */
"use strict";

/* ---------------- i18n (labels sourced from webui/i18n/*.json) ---------------- */
const I18N = {
  zh: {
    "nav.tasks": "任务管理", "nav.script": "文案", "nav.audio": "音频", "nav.video": "视频",
    "nav.subtitle": "字幕", "nav.history": "发布历史", "nav.llm": "大模型", "nav.material": "素材来源",
    "nav.channels": "发布渠道", "nav.presets": "设置预设", "nav.settings": "设置",
    "group.create": "创作", "group.publish": "发布", "group.config": "配置",
    "collapse.nav": "收起菜单", "expand.nav": "展开菜单",
    "gen.title": "生成日志", "gen.rail": "生成日志",
    "gen.empty": "暂无生成任务", "gen.emptyHint": "在下方操作栏点击「生成视频」，进度与日志将实时显示在这里。",
    "gen.jump": "回到最新", "gen.fail": "模拟失败", "gen.failHint": "演示失败路径：素材阶段将报错",
    "gen.elapsed": "已用时", "gen.progress": "进度", "gen.failed": "视频生成失败",
    "gen.download": "下载视频", "gen.viewTask": "查看任务", "gen.reviewWarn": "成片审查警告（1）",
    "gen.logHidden": "日志已在「设置」中隐藏",
    "action.generate": "生成视频", "action.generating": "正在生成视频…",
    "action.export": "导出设置", "action.import": "导入设置",
    "ready.source": "来源", "ready.voice": "配音", "ready.subtitle": "字幕", "ready.count": "数量",
    "top.idle": "空闲", "top.running": "{n} 个任务生成中",
    "phase.queued": "排队中", "phase.preparing": "准备中", "phase.script": "正在准备文案",
    "phase.terms": "正在准备关键词", "phase.audio": "正在生成配音", "phase.subtitle": "正在生成字幕",
    "phase.materials": "正在准备视频素材", "phase.rendering": "正在合成最终视频",
    "phase.complete": "视频生成完成", "phase.failed": "视频生成失败",
    "page.tasks.sub": "查看生成任务与发布队列", "page.script.sub": "主题 → AI 文案 → 关键词，一屏完成",
    "page.audio.sub": "配音与背景音乐", "page.video.sub": "素材来源与画面参数",
    "page.subtitle.sub": "字幕样式与实时预览", "page.history.sub": "各平台发布记录",
    "page.llm.sub": "文案生成服务商配置", "page.material.sub": "库存与 AI 素材 API",
    "page.channels.sub": "国内平台与海外聚合", "page.presets.sub": "独立参数表 · 一键应用 · JSON 导入导出", "page.settings.sub": "常规 · 界面 · 密钥 · 缓存",
    "script.settings": "文案设置", "script.subject": "视频主题",
    "script.subjectPh": "例如：人工智能如何改变日常生活",
    "script.script": "视频文案（可选）", "script.scriptPh": "留空时由 AI 根据主题自动生成",
    "script.terms": "视频关键词（可选，英文逗号分隔）", "script.termsPh": "AI, lifestyle, technology",
    "script.lang": "生成视频脚本的语言", "script.autoDetect": "自动检测",
    "script.advanced": "高级脚本设置", "script.paragraphs": "文案段落数量",
    "script.requirements": "自定义文案要求", "script.requirementsPh": "例如：语气更轻松，适合小红书风格，面向年轻用户",
    "script.systemPrompt": "系统提示词", "script.resetPrompt": "恢复默认提示词",
    "script.promptPreview": "预览最终提示词", "script.promptReset": "已恢复默认系统提示词",
    "script.configureLlm": "配置大模型",
    "script.aiTitle": "AI 生成", "script.aiBtn": "点击使用AI生成视频文案和关键词",
    "script.previewTitle": "AI 文案预览", "script.previewEmpty": "点击上方按钮，AI 将根据主题生成文案与关键词。",
    "script.keywords": "视频关键词", "script.generating": "AI 正在创作文案…",
    "script.done": "文案已生成，可直接编辑", "script.needSubject": "请先填写视频主题",
    "audio.settings": "音频设置", "audio.mode": "配音方式",
    "audio.tts": "自动配音", "audio.upload": "上传音频", "audio.none": "无配音",
    "audio.service": "配音服务", "audio.voice": "配音声音（与文案语言保持一致）",
    "audio.volume": "配音音量", "audio.rate": "配音语速",
    "audio.preview": "试听", "audio.previewHint": "演示环境：模拟试听播放",
    "audio.uploadBtn": "选择音频文件", "audio.uploaded": "已上传",
    "audio.noneHint": "将生成无声视频（仅背景音乐与字幕）。",
    "audio.bgm": "背景音乐", "audio.bgmType": "音乐类型", "audio.bgmVolume": "音乐音量",
    "audio.bgmRandom": "随机推荐", "audio.bgmNone": "无音乐", "audio.bgmCustom": "本地上传",
    "audio.providerKey": "服务商密钥",
    "video.settings": "视频设置", "video.source": "视频来源",
    "video.stock": "库存视频", "video.aiVideo": "AI 视频", "video.aiImage": "AI 图片", "video.local": "本地文件",
    "video.configureMaterial": "配置素材来源",
    "video.aspect": "视频比例", "video.portrait": "竖屏 9:16（抖音视频）", "video.landscape": "横屏 16:9（西瓜视频）",
    "video.concat": "视频拼接模式", "video.sequential": "顺序拼接", "video.random": "随机拼接（推荐）",
    "video.matchOrder": "按文案顺序匹配画面", "video.transition": "视频转场模式",
    "video.transNone": "无", "video.transShuffle": "随机", "video.transFadeIn": "淡入", "video.transFadeOut": "淡出",
    "video.transSlideIn": "滑入", "video.transSlideOut": "滑出", "video.transZoomIn": "放大", "video.transZoomOut": "缩小",
    "video.fit": "素材画面适配", "video.fitCover": "填满（居中裁剪）", "video.fitContain": "完整显示（黑边）",
    "video.motion": "图片动态效果", "video.motionStatic": "静止", "video.motionZoom": "缓慢放大",
    "video.clipDuration": "单个片段最大时长（秒）", "video.clipSpeed": "片段播放速度",
    "video.count": "同时生成视频数量", "video.advanced": "高级视频设置",
    "video.encoder": "视频编码器", "video.encoderDefault": "默认（libx264）",
    "video.seed": "视频种子", "video.seedPh": "留空则随机",
    "video.materialConcurrency": "库存素材并发", "video.renderConcurrency": "片段渲染并发",
    "video.billing": "该来源按量计费，生成前请确认费用。",
    "video.billingConfirm": "我已了解并确认计费",
    "video.upload": "上传本地文件", "video.uploadHint": "支持 mp4 / mov / avi / mkv，可多选",
    "video.uploadedFiles": "已选择 {n} 个文件",
    "subtitle.settings": "字幕设置", "subtitle.enable": "启用字幕",
    "subtitle.font": "字幕字体", "subtitle.position": "字幕位置",
    "subtitle.posTop": "顶部", "subtitle.posCenter": "中间", "subtitle.posBottom": "底部（推荐）",
    "subtitle.posTwoThirds": "底部 2/3 处", "subtitle.posCustom": "自定义",
    "subtitle.customPos": "自定义位置（距顶部 %）",
    "subtitle.display": "字幕显示方式", "subtitle.sentence": "整句显示", "subtitle.word": "逐词显示",
    "subtitle.animation": "字幕入场动画", "subtitle.animNone": "无（直接显示）", "subtitle.animPop": "弹出（弹簧）", "subtitle.animFade": "淡入",
    "subtitle.fontSize": "字幕大小", "subtitle.fontColor": "字幕颜色",
    "subtitle.strokeColor": "描边颜色", "subtitle.strokeWidth": "描边粗细",
    "subtitle.bgEnable": "启用字幕背景", "subtitle.bgColor": "字幕背景颜色", "subtitle.rounded": "启用圆角半透明字幕背景",
    "subtitle.preview": "实时预览", "subtitle.previewText": "预览文本",
    "subtitle.sample": "人工智能正在悄悄改变我们的日常生活",
    "subtitle.reset": "恢复默认字幕设置", "subtitle.resetDone": "已恢复默认字幕设置",
    "tasks.queue": "发布队列", "tasks.queueAuto": "自动发布已开启",
    "tasks.search": "搜索任务主题…",
    "tasks.all": "全部", "tasks.processing": "生成中", "tasks.complete": "已完成", "tasks.failed": "失败",
    "tasks.col.state": "状态", "tasks.col.subject": "主题", "tasks.col.time": "创建时间",
    "tasks.col.source": "来源", "tasks.col.actions": "操作",
    "tasks.play": "播放", "tasks.load": "加载", "tasks.restore": "恢复配置", "tasks.folder": "打开目录", "tasks.delete": "删除任务",
    "tasks.draft": "草稿", "tasks.current": "当前项目",
    "tasks.deleted": "已删除任务", "tasks.undo": "撤销",
    "tasks.restored": "已恢复任务配置，跳转到文案页",
    "tasks.loaded": "已加载任务参数，跳转到文案页",
    "tasks.folderOpened": "已在资源管理器中打开任务目录（演示）",
    "tasks.empty": "暂无任务", "tasks.preview": "任务预览",
    "history.video": "视频", "history.time": "时间", "history.platform": "平台",
    "history.result": "结果", "history.duration": "耗时",
    "history.republish": "重新发布", "history.republished": "已重新发布",
    "history.success": "成功", "history.failed": "失败",
    "history.allPlatforms": "全部平台", "history.allResults": "全部结果",
    "llm.current": "当前使用", "llm.configured": "已配置", "llm.notConfigured": "未配置",
    "llm.test": "测试连接", "llm.testing": "测试中…", "llm.testOk": "连接成功", "llm.testBad": "连接失败：密钥无效",
    "llm.saveUse": "保存并启用", "llm.saved": "已保存，立即生效，无需重启",
    "llm.keyPh": "请输入 API Key", "llm.model": "模型名称",
    "material.useSource": "设为当前来源", "material.keySet": "密钥已保存", "material.using": "已切换素材来源",
    "channels.login": "登录", "channels.logout": "退出", "channels.loggedIn": "已登录",
    "channels.notLoggedIn": "未登录", "channels.loggingIn": "登录中…",
    "channels.loginOk": "登录成功，Cookie 已保存",
    "channels.uploadPost": "Upload-Post 海外聚合", "channels.enable": "启用集成",
    "channels.autoPublish": "渲染完成后自动发布",
    "channels.domestic": "国内平台", "channels.overseas": "海外平台",
    "settings.general": "常规", "settings.interface": "界面设置", "settings.keys": "密钥备份", "settings.cache": "缓存管理",
    "settings.openFolder": "完成后自动打开任务目录", "settings.hideLog": "隐藏生成日志",
    "settings.theme": "主题", "settings.themeDark": "深色", "settings.themeLight": "浅色",
    "settings.language": "语言", "settings.defaultPage": "默认落地页",
    "settings.keysExport": "导出密钥", "settings.keysImport": "导入密钥",
    "settings.keysExported": "密钥备份已导出", "settings.keysImported": "密钥已导入",
    "settings.cacheFiles": "缓存文件", "settings.cacheSize": "占用空间", "settings.cacheOldest": "最早文件",
    "settings.cacheRefresh": "刷新", "settings.cacheClean": "清理缓存",
    "settings.cacheCleaned": "缓存清理完成", "settings.cacheRefreshed": "缓存统计已刷新",
    "toast.presetExported": "设置预设已导出", "toast.presetImported": "设置预设已导入", "toast.presetBad": "预设文件格式无效",
    "toast.genBlocked.empty": "请先填写视频主题或文案",
    "toast.genBlocked.key": "当前素材来源未配置 API Key",
    "toast.genBlocked.billing": "请先确认 AI 来源计费",
    "toast.genBlocked.local": "请先上传本地素材",
    "toast.genBlocked.audio": "请先上传配音文件",
    "toast.genStarted": "任务已提交，正在生成…", "toast.genDone": "视频生成完成", "toast.genFailed": "视频生成失败",
    "toast.downloaded": "已开始下载（演示）",
    "project.untitled": "未命名项目", "project.new": "新建空白项目", "project.switcher": "切换项目",
    "project.loadMore": "加载更多（剩余 {n}）", "project.allLoaded": "已加载全部 {n} 个项目",
    "project.save": "保存", "project.saved": "项目已保存", "project.dirty": "参数已更改，未保存",
    "project.unsavedTitle": "参数已更改，是否保存？",
    "project.unsavedBody": "当前项目「{name}」的参数尚未保存，直接切换将丢失未保存的修改。",
    "project.saveSwitch": "保存并切换", "project.discard": "放弃更改", "project.cancel": "取消",
    "project.locked": "参数已锁定", "project.lockedHint": "已生成视频的任务参数不可更改，可编辑副本并另存为新任务。",
    "project.saveAsNew": "编辑副本 · 另存为新任务", "project.savedAsNew": "已另存为新任务",
    "project.loaded": "已加载项目", "project.created": "已创建空白项目",
    "presets.menu": "预设参数", "presets.apply": "应用到当前项目", "presets.applied": "已应用预设",
    "presets.saveAs": "将当前参数存为预设", "presets.namePh": "预设名称，例如：竖屏口播",
    "presets.saved": "预设已保存", "presets.deleted": "预设已删除", "presets.builtin": "内置",
    "presets.export": "导出", "presets.exportAll": "导出全部", "presets.import": "导入 JSON",
    "presets.exported": "预设已导出", "presets.imported": "已导入 {n} 个预设", "presets.bad": "预设文件格式无效",
    "presets.nameRequired": "请先填写预设名称", "presets.delete": "删除预设",
    "presets.stripHint": "预设不包含 API 密钥与本地上传文件（密钥请使用「设置 · 密钥备份」）。",
    "theme.toggle": "切换主题", "common.save": "保存", "common.close": "关闭", "demo.tag": "演示数据",
    "nav.wizard": "创作向导", "nav.plan": "脚本方案", "nav.series": "系列管理",
    "page.wizard.sub": "一句话拍短剧 · 五步从想法到成片", "page.plan.sub": "分镜故事板 · 逐场景可控的专业模式", "page.series.sub": "剧集 · 角色档案 · 风格圣经",
    "mode.simple": "简单", "mode.pro": "专业", "mode.toggle": "切换简单/专业模式",
    "mode.simpleOn": "简单模式：只保留向导与系列，适合新手", "mode.proOn": "专业模式：完整参数与分镜台已展开",
    "engines.title": "本地引擎", "engines.comfy": "本地画面引擎", "engines.acestep": "本地音乐引擎", "engines.ollama": "本地编剧引擎",
    "engines.online": "在线·免费", "engines.offline": "离线", "engines.toggleHint": "点击模拟在线/离线（演示降级策略）",
    "engines.allLocal": "本地全家桶", "engines.allLocalDone": "已切换为全本地免费方案",
    "engines.degrade": "引擎离线：对应选项已置灰，可降级为库存素材或云端付费源", "engines.queueHint": "本地引擎单显卡串行排队，草稿档更快",
    "wizard.step1": "故事想法", "wizard.step2": "角色卡", "wizard.step3": "分集大纲", "wizard.step4": "分镜脚本", "wizard.step5": "预览生成",
    "wizard.idea": "用一句话描述你的短剧", "wizard.ideaPh": "例如：被裁员的女生靠一份被否决的方案逆风翻盘",
    "wizard.genre": "题材模板（预绑风格/音色/音乐）", "wizard.duration": "每集目标时长（秒）", "wizard.episodes": "集数",
    "wizard.next": "下一步", "wizard.back": "上一步", "wizard.needIdea": "先用一句话描述你的故事",
    "wizard.tpl.urban": "都市逆袭", "wizard.tpl.urbanDesc": "职场翻盘 · 冷调霓虹 · 紧张渐强",
    "wizard.tpl.period": "古风甜宠", "wizard.tpl.periodDesc": "庭院灯会 · 暖金青绿 · 轻快国风",
    "wizard.tpl.suspense": "悬疑反转", "wizard.tpl.suspenseDesc": "雨夜迷局 · 低照度青灰 · 心跳低音",
    "wizard.tpl.healing": "治愈日常", "wizard.tpl.healingDesc": "小店烟火 · 奶油暖光 · 舒缓钢琴",
    "wizard.tpl.scifi": "科幻未来", "wizard.tpl.scifiDesc": "星际都市 · 紫蓝辉光 · 合成器浪潮",
    "wizard.charsTitle": "角色卡（参考图一次生成，跨集复用）",
    "wizard.charsExtract": "AI 抽取角色", "wizard.charsBusy": "本地编剧引擎正在抽取角色…", "wizard.charsDone": "角色已抽取，可编辑或删除",
    "wizard.charsHint": "每个角色绑定外貌描述 + 参考图 + 固定种子 + 音色，后续每集关键帧都注入同一套参考，保证长相一致。",
    "wizard.charAdd": "新增角色", "wizard.charDelete": "删除角色", "wizard.charDeleted": "角色已删除",
    "wizard.charName": "姓名", "wizard.charPersona": "性格/人设", "wizard.charAppearance": "外貌描述（注入每次生成）", "wizard.charVoice": "音色",
    "wizard.charRegen": "重新生成形象", "wizard.charRegenDone": "参考图已重新生成（新种子）",
    "wizard.outlineTitle": "分集大纲（拖拽调序）", "wizard.outlineHint": "每集一句故事梗概 + 集尾悬念，悬念是短剧留存的关键。",
    "wizard.epLogline": "本集梗概", "wizard.epHook": "集尾悬念", "wizard.epAdd": "加一集", "wizard.epDelete": "删除本集",
    "wizard.boardTitle": "分镜脚本（精简视图）", "wizard.boardHint": "小白只看四列：画面 / 台词 / 时长 / 衔接；引擎与成本折叠在「高级」。",
    "wizard.boardGen": "生成分镜脚本", "wizard.boardBusy": "正在把大纲拆成分镜…", "wizard.boardDone": "分镜已生成，可在专业模式精修",
    "wizard.colVisual": "画面", "wizard.colLine": "台词/旁白", "wizard.colDur": "时长", "wizard.colLink": "衔接", "wizard.advanced": "高级（引擎与成本）",
    "wizard.openPro": "在专业模式打开完整分镜台", "wizard.previewTitle": "预览与生成",
    "wizard.tier": "画质档位", "wizard.tierDraft": "快速预览 · 几分钟", "wizard.tierDraftDesc": "turbo 4 步 · 768p，先看效果不心疼",
    "wizard.tierFinal": "精细成片 · 较久", "wizard.tierFinalDesc": "完整模型 · 1080p，确认后一键升级",
    "wizard.costTitle": "成本汇总", "wizard.costLocal": "本地免费项", "wizard.costCloud": "云端付费项", "wizard.costFree": "全部本地生成，零边际成本",
    "wizard.start": "开始生成", "wizard.needChars": "请先抽取或新增至少一个角色", "wizard.needPlan": "请先生成分镜脚本",
    "plan.status.draft": "草稿", "plan.status.confirmed": "已确认", "plan.scenes": "场景", "plan.scene": "场景",
    "plan.meter.target": "目标", "plan.meter.planned": "计划", "plan.meter.measured": "实测", "plan.meter.over": "超出 ±10% 容差", "plan.meter.ok": "在 ±10% 容差内",
    "plan.aiBtn": "AI 生成方案", "plan.aiBusy": "方案生成中…", "plan.export": "导出 JSON", "plan.import": "导入",
    "plan.imported": "脚本方案已导入", "plan.importBad": "方案文件格式无效", "plan.exported": "脚本方案已导出",
    "plan.confirm": "确认方案并生成", "plan.confirmed": "方案已确认，按分镜逐场景执行", "plan.confirmNeed": "请先生成或导入脚本方案",
    "plan.empty": "还没有脚本方案", "plan.emptyHint": "脚本方案是文案与生成之间的可见分镜脚本：逐场景编辑、锁定、导出，确认后才进入生成。", "plan.emptyCta": "用 AI 生成一份方案",
    "plan.filmTitle": "片名", "plan.logline": "一句话故事", "plan.style": "风格一致性（注入每个生成 prompt）",
    "plan.styleTone": "色调", "plan.stylePalette": "色彩", "plan.styleCamera": "镜头语言",
    "plan.cast": "出场角色", "plan.voice": "旁白配音", "plan.bgm": "背景音乐计划", "plan.bgmMood": "情绪", "plan.bgmPrompt": "音乐描述", "plan.bgmVolume": "音量", "plan.bgmFadeIn": "淡入（秒）", "plan.bgmFadeOut": "淡出（秒）",
    "plan.bgmLocal": "本地 ACE-Step 作曲", "plan.timeline": "时间线", "plan.timelineHint": "点击选中场景，拖拽色块调序（调序后衔接标注待复核）", "plan.bgmTrack": "BGM 轨", "plan.cues": "字幕刻度",
    "plan.storyboard": "分镜故事板", "plan.lock": "锁定此段（AI 不得覆盖）", "plan.unlock": "解除锁定", "plan.locked": "已锁定，AI 重生成将跳过此段", "plan.unlocked": "已解除锁定",
    "plan.narration": "旁白/台词", "plan.visual": "画面描述", "plan.keywords": "关键词", "plan.engine": "生成引擎",
    "plan.engine.local_fl2v": "本地 · 首尾帧动画化", "plan.engine.local_i2v": "本地 · 图生视频", "plan.engine.stock": "库存素材", "plan.engine.cloud_ai": "云端 AI（付费）",
    "plan.engineOffline": "引擎离线，选项已置灰", "plan.cost.free": "免费", "plan.cost.paid": "≈¥{n}",
    "plan.material": "素材绑定", "plan.candidates": "候选", "plan.in": "入点", "plan.out": "出点", "plan.swap": "换素材", "plan.swapped": "已切换候选素材",
    "plan.transition": "到下一段转场", "plan.trans.none": "直切", "plan.trans.fade": "淡入淡出", "plan.trans.slide": "滑动", "plan.trans.zoom": "缩放", "plan.trans.match_cut": "匹配剪辑",
    "plan.regen": "重生成此段", "plan.regenDone": "此段已重生成（保留场景 id）", "plan.regenLocked": "此段已锁定，AI 不可覆盖",
    "plan.kfGen": "本地生成关键帧", "plan.kfFirst": "首帧", "plan.kfLast": "尾帧", "plan.kfShared": "共享边界帧：本段首帧 = 上段尾帧", "plan.kfBusy": "关键帧生成中…", "plan.kfDone": "关键帧已生成", "plan.kfOffline": "本地画面引擎离线，无法生成关键帧", "plan.kfQueue": "ComfyUI 排队：前方 {n} 个任务", "plan.kfStep": "KSampler {a}/{b} 步", "plan.kfCache": "此画面已生成过，直接复用（requestKey 命中）",
    "plan.details": "详情", "plan.drawerTitle": "场景详情", "plan.kfPair": "关键帧对预览", "plan.prevLast": "上段尾帧", "plan.thisFirst": "本段首帧", "plan.diffScore": "差异评分", "plan.firstPrompt": "首帧提示词", "plan.lastPrompt": "尾帧提示词",
    "plan.relation": "与上段关联", "plan.rel.establish": "开场建立", "plan.rel.continue": "承接", "plan.rel.contrast": "对比", "plan.rel.escalate": "递进", "plan.rel.match_cut": "匹配剪辑", "plan.rel.unknown": "待复核", "plan.relNote": "关联说明",
    "plan.boundary": "切点健康", "plan.bh.ok": "衔接良好", "plan.bh.warn": "突变风险", "plan.bh.unknown": "待审查",
    "plan.reordered": "已调序：衔接标注置为待复核，共享帧关系已重算", "plan.genLog": "方案生成日志",
    "plan.genOllama": "本地编剧引擎 Ollama · gemma4:26b · format:json", "plan.genOutline": "故事大纲 → 角色 → 分镜，结构化输出中…",
    "plan.genScene": "场景 {a}/{b} 分镜写入…", "plan.genLockedSkip": "场景 {a} 已锁定，保留人工修改", "plan.genFallback": "本地编剧引擎离线，降级为模板方案（快速模式不受影响）", "plan.genDone": "方案生成完成，可逐场景编辑后确认",
    "plan.degradeStock": "降级为库存素材", "plan.degraded": "已降级为库存素材，衔接改用转场遮蔽", "plan.estDur": "预估时长（秒）", "plan.sharedFrame": "共享帧",
    "plan.needNarration": "场景 {a} 的旁白为空，请先补写再生成", "plan.localOffline": "本地画面引擎离线：请上线引擎，或把相关场景降级为库存素材",
    "plan.paidTitle": "付费场景确认", "plan.paidBody": "本方案含 {n} 个云端付费场景，预计 ≈¥{c}。其余场景全部本地免费生成。确认后按方案逐场景执行。", "plan.paidGo": "确认付费并生成",
    "series.library": "系列库", "series.new": "新建系列", "series.newHint": "从创作向导开始一个新系列", "series.back": "返回系列库",
    "series.episodes": "剧集", "series.characters": "角色档案", "series.style": "风格圣经", "series.ep": "第 {n} 集",
    "series.epOpen": "打开分镜", "series.epNext": "生成下一集", "series.epNextBusy": "正在为下一集生成分镜…", "series.epNextDone": "下一集分镜已生成", "series.epOpened": "已加载分镜",
    "series.epStatus.outline": "大纲", "series.epStatus.draft": "分镜草稿", "series.epStatus.confirmed": "已确认", "series.epStatus.rendered": "已渲染",
    "series.hook": "集尾悬念", "series.charRefs": "参考图画廊（跨集复用）", "series.charListen": "试听音色", "series.charSeed": "固定种子", "series.charConsistency": "同一套参考图 + 固定种子注入每集关键帧，角色长相跨集一致；人工锁定后 AI 不得覆盖。",
    "series.styleEra": "时代/世界观", "series.styleHint": "风格圣经在系列级持久化，每集分镜引用而非重写；修改后影响后续生成，已渲染集不受影响。", "series.coverEps": "{n} 集",
  },
  en: {
    "nav.tasks": "Task Manager", "nav.script": "Script", "nav.audio": "Audio", "nav.video": "Video",
    "nav.subtitle": "Subtitles", "nav.history": "Publish History", "nav.llm": "LLM", "nav.material": "Material Sources",
    "nav.channels": "Publish Channels", "nav.presets": "Presets", "nav.settings": "Settings",
    "group.create": "Create", "group.publish": "Publish", "group.config": "Configure",
    "collapse.nav": "Collapse menu", "expand.nav": "Expand menu",
    "gen.title": "Generation Log", "gen.rail": "GENERATION LOG",
    "gen.empty": "No generation task yet", "gen.emptyHint": "Click “Generate Video” in the action bar below; progress and logs stream here.",
    "gen.jump": "Jump to latest", "gen.fail": "Simulate failure", "gen.failHint": "Demo failure path: materials phase will error",
    "gen.elapsed": "Elapsed", "gen.progress": "Progress", "gen.failed": "Video Generation Failed",
    "gen.download": "Download Video", "gen.viewTask": "View task", "gen.reviewWarn": "Review warnings (1)",
    "gen.logHidden": "Logs hidden in Settings",
    "action.generate": "Generate Video", "action.generating": "Generating…",
    "action.export": "Export Settings", "action.import": "Import Settings",
    "ready.source": "Source", "ready.voice": "Voice", "ready.subtitle": "Subtitles", "ready.count": "Count",
    "top.idle": "Idle", "top.running": "{n} task(s) running",
    "phase.queued": "Queued", "phase.preparing": "Preparing", "phase.script": "Preparing the script",
    "phase.terms": "Preparing keywords", "phase.audio": "Generating narration", "phase.subtitle": "Generating subtitles",
    "phase.materials": "Preparing video materials", "phase.rendering": "Rendering the final video",
    "phase.complete": "Video Generation Completed", "phase.failed": "Video Generation Failed",
    "page.tasks.sub": "Generation tasks & publish queue", "page.script.sub": "Subject → AI script → keywords, one screen",
    "page.audio.sub": "Voiceover & background music", "page.video.sub": "Material source & frame parameters",
    "page.subtitle.sub": "Subtitle style & live preview", "page.history.sub": "Publishing records across platforms",
    "page.llm.sub": "Script generation provider", "page.material.sub": "Stock & AI material APIs",
    "page.channels.sub": "Domestic platforms & overseas aggregator", "page.presets.sub": "Standalone parameter sets · one-click apply · JSON import/export", "page.settings.sub": "General · Interface · Keys · Cache",
    "script.settings": "Script Settings", "script.subject": "Video Subject",
    "script.subjectPh": "Example: How AI is changing everyday life",
    "script.script": "Video Script (Optional)", "script.scriptPh": "Leave empty to let AI write from the subject",
    "script.terms": "Video Keywords (optional, comma separated)", "script.termsPh": "AI, lifestyle, technology",
    "script.lang": "Script Language", "script.autoDetect": "Auto Detect",
    "script.advanced": "Advanced Script Settings", "script.paragraphs": "Script Paragraph Count",
    "script.requirements": "Custom Script Requirements", "script.requirementsPh": "e.g. lighter tone, Xiaohongshu style, young audience",
    "script.systemPrompt": "System Prompt", "script.resetPrompt": "Restore Default Prompt",
    "script.promptPreview": "Preview Final Prompt", "script.promptReset": "Default system prompt restored",
    "script.configureLlm": "Configure AI model",
    "script.aiTitle": "AI Generation", "script.aiBtn": "Generate Script & Keywords with AI",
    "script.previewTitle": "AI Script Preview", "script.previewEmpty": "Click the button above; AI writes the script & keywords from your subject.",
    "script.keywords": "Video Keywords", "script.generating": "AI is writing…",
    "script.done": "Script generated — edit freely", "script.needSubject": "Enter a video subject first",
    "audio.settings": "Audio Settings", "audio.mode": "Voiceover Mode",
    "audio.tts": "Auto", "audio.upload": "Upload", "audio.none": "None",
    "audio.service": "Voiceover Service", "audio.voice": "Voice (match script language)",
    "audio.volume": "Voiceover Volume", "audio.rate": "Voiceover Speed",
    "audio.preview": "Preview", "audio.previewHint": "Demo: simulated playback",
    "audio.uploadBtn": "Choose audio file", "audio.uploaded": "Uploaded",
    "audio.noneHint": "Produces a silent video (BGM and subtitles only).",
    "audio.bgm": "Background Music", "audio.bgmType": "Music Type", "audio.bgmVolume": "Music Volume",
    "audio.bgmRandom": "Random pick", "audio.bgmNone": "No music", "audio.bgmCustom": "Local upload",
    "audio.providerKey": "Provider Key",
    "video.settings": "Video Settings", "video.source": "Video Source",
    "video.stock": "Stock Video", "video.aiVideo": "AI Video", "video.aiImage": "AI Image", "video.local": "Local Files",
    "video.configureMaterial": "Configure material sources",
    "video.aspect": "Video Aspect Ratio", "video.portrait": "Portrait 9:16", "video.landscape": "Landscape 16:9",
    "video.concat": "Video Concatenation Mode", "video.sequential": "Sequential", "video.random": "Random (Recommended)",
    "video.matchOrder": "Match Visuals to Script Order", "video.transition": "Video Transition Mode",
    "video.transNone": "None", "video.transShuffle": "Shuffle", "video.transFadeIn": "Fade In", "video.transFadeOut": "Fade Out",
    "video.transSlideIn": "Slide In", "video.transSlideOut": "Slide Out", "video.transZoomIn": "Zoom In", "video.transZoomOut": "Zoom Out",
    "video.fit": "Source Frame Fit", "video.fitCover": "Fill (center crop)", "video.fitContain": "Fit (black bars)",
    "video.motion": "Image Motion", "video.motionStatic": "Static", "video.motionZoom": "Slow Zoom",
    "video.clipDuration": "Maximum Clip Duration (seconds)", "video.clipSpeed": "Clip Playback Speed",
    "video.count": "Videos per Run", "video.advanced": "Advanced Video Settings",
    "video.encoder": "Video Encoder", "video.encoderDefault": "Default (libx264)",
    "video.seed": "Video Seed", "video.seedPh": "Empty = random",
    "video.materialConcurrency": "Stock Footage Concurrency", "video.renderConcurrency": "Clip Rendering Concurrency",
    "video.billing": "This source is pay-per-use. Confirm charges before generating.",
    "video.billingConfirm": "I understand and confirm the charges",
    "video.upload": "Upload Local Files", "video.uploadHint": "mp4 / mov / avi / mkv, multiple allowed",
    "video.uploadedFiles": "{n} file(s) selected",
    "subtitle.settings": "Subtitle Settings", "subtitle.enable": "Enable Subtitles",
    "subtitle.font": "Font", "subtitle.position": "Position",
    "subtitle.posTop": "Top", "subtitle.posCenter": "Center", "subtitle.posBottom": "Bottom (Recommended)",
    "subtitle.posTwoThirds": "2/3 from Bottom", "subtitle.posCustom": "Custom",
    "subtitle.customPos": "Custom position (% from top)",
    "subtitle.display": "Subtitle display", "subtitle.sentence": "Whole sentence", "subtitle.word": "Word by word",
    "subtitle.animation": "Entrance animation", "subtitle.animNone": "None", "subtitle.animPop": "Pop Up (Spring)", "subtitle.animFade": "Fade In",
    "subtitle.fontSize": "Font Size", "subtitle.fontColor": "Color",
    "subtitle.strokeColor": "Outline", "subtitle.strokeWidth": "Outline Width",
    "subtitle.bgEnable": "Background", "subtitle.bgColor": "Background Color", "subtitle.rounded": "Rounded Background",
    "subtitle.preview": "Live Preview", "subtitle.previewText": "Preview Text",
    "subtitle.sample": "AI is quietly changing our everyday life",
    "subtitle.reset": "Restore Subtitle Defaults", "subtitle.resetDone": "Subtitle defaults restored",
    "tasks.queue": "Publish Queue", "tasks.queueAuto": "Auto-publish enabled",
    "tasks.search": "Search task subject…",
    "tasks.all": "All", "tasks.processing": "Processing", "tasks.complete": "Completed", "tasks.failed": "Failed",
    "tasks.col.state": "State", "tasks.col.subject": "Subject", "tasks.col.time": "Created",
    "tasks.col.source": "Source", "tasks.col.actions": "Actions",
    "tasks.play": "Play", "tasks.load": "Load", "tasks.restore": "Restore Config", "tasks.folder": "Open Folder", "tasks.delete": "Delete Task",
    "tasks.draft": "Draft", "tasks.current": "Current project",
    "tasks.deleted": "Task deleted", "tasks.undo": "Undo",
    "tasks.restored": "Task config restored — jumped to Script",
    "tasks.loaded": "Task parameters loaded — jumped to Script",
    "tasks.folderOpened": "Task folder opened in Explorer (demo)",
    "tasks.empty": "No tasks yet", "tasks.preview": "Task Preview",
    "history.video": "Video", "history.time": "Time", "history.platform": "Platform",
    "history.result": "Result", "history.duration": "Duration",
    "history.republish": "Republish", "history.republished": "Republished",
    "history.success": "Success", "history.failed": "Failed",
    "history.allPlatforms": "All platforms", "history.allResults": "All results",
    "llm.current": "In use", "llm.configured": "Configured", "llm.notConfigured": "Not configured",
    "llm.test": "Test Connection", "llm.testing": "Testing…", "llm.testOk": "Connection OK", "llm.testBad": "Failed: invalid key",
    "llm.saveUse": "Save & Enable", "llm.saved": "Saved — takes effect immediately, no restart",
    "llm.keyPh": "Enter API key", "llm.model": "Model Name",
    "material.useSource": "Use as source", "material.keySet": "Key saved", "material.using": "Material source switched",
    "channels.login": "Log in", "channels.logout": "Log out", "channels.loggedIn": "Logged in",
    "channels.notLoggedIn": "Not logged in", "channels.loggingIn": "Logging in…",
    "channels.loginOk": "Login OK — cookies saved",
    "channels.uploadPost": "Upload-Post (overseas)", "channels.enable": "Enable integration",
    "channels.autoPublish": "Auto-publish after render",
    "channels.domestic": "Domestic Platforms", "channels.overseas": "Overseas",
    "settings.general": "General", "settings.interface": "Interface", "settings.keys": "Key Backup", "settings.cache": "Cache Management",
    "settings.openFolder": "Auto-open task folder on completion", "settings.hideLog": "Hide generation logs",
    "settings.theme": "Theme", "settings.themeDark": "Dark", "settings.themeLight": "Light",
    "settings.language": "Language", "settings.defaultPage": "Default landing page",
    "settings.keysExport": "Export Keys", "settings.keysImport": "Import Keys",
    "settings.keysExported": "Key backup exported", "settings.keysImported": "Keys imported",
    "settings.cacheFiles": "Files", "settings.cacheSize": "Size", "settings.cacheOldest": "Oldest",
    "settings.cacheRefresh": "Refresh", "settings.cacheClean": "Clean Cache",
    "settings.cacheCleaned": "Cache cleaned", "settings.cacheRefreshed": "Cache stats refreshed",
    "toast.presetExported": "Settings preset exported", "toast.presetImported": "Settings preset imported", "toast.presetBad": "Invalid preset file",
    "toast.genBlocked.empty": "Enter a subject or script first",
    "toast.genBlocked.key": "Current source has no API key",
    "toast.genBlocked.billing": "Confirm AI source charges first",
    "toast.genBlocked.local": "Upload local materials first",
    "toast.genBlocked.audio": "Upload a voiceover file first",
    "toast.genStarted": "Task submitted — generating…", "toast.genDone": "Video generation completed", "toast.genFailed": "Video generation failed",
    "toast.downloaded": "Download started (demo)",
    "project.untitled": "Untitled project", "project.new": "New blank project", "project.switcher": "Switch project",
    "project.loadMore": "Load more ({n} remaining)", "project.allLoaded": "All {n} projects loaded",
    "project.save": "Save", "project.saved": "Project saved", "project.dirty": "Parameters changed, unsaved",
    "project.unsavedTitle": "Parameters changed — save first?",
    "project.unsavedBody": "Project “{name}” has unsaved changes. Switching now discards them.",
    "project.saveSwitch": "Save & switch", "project.discard": "Discard changes", "project.cancel": "Cancel",
    "project.locked": "Parameters locked", "project.lockedHint": "Generated tasks are read-only. Edit a copy and save it as a new task.",
    "project.saveAsNew": "Edit copy · Save as new task", "project.savedAsNew": "Saved as a new task",
    "project.loaded": "Project loaded", "project.created": "Blank project created",
    "presets.menu": "Presets", "presets.apply": "Apply to current project", "presets.applied": "Preset applied",
    "presets.saveAs": "Save current parameters as preset", "presets.namePh": "Preset name, e.g. Portrait talk",
    "presets.saved": "Preset saved", "presets.deleted": "Preset deleted", "presets.builtin": "Built-in",
    "presets.export": "Export", "presets.exportAll": "Export all", "presets.import": "Import JSON",
    "presets.exported": "Preset exported", "presets.imported": "{n} preset(s) imported", "presets.bad": "Invalid preset file",
    "presets.nameRequired": "Enter a preset name first", "presets.delete": "Delete preset",
    "presets.stripHint": "Presets exclude API keys and local uploads (use Settings · Key Backup for keys).",
    "theme.toggle": "Toggle theme", "common.save": "Save", "common.close": "Close", "demo.tag": "Demo data",
    "nav.wizard": "Creator Wizard", "nav.plan": "Script Plan", "nav.series": "Series Studio",
    "page.wizard.sub": "One sentence to a short drama · five steps from idea to film", "page.plan.sub": "Storyboard · scene-level control, pro mode", "page.series.sub": "Episodes · character bible · style bible",
    "mode.simple": "Simple", "mode.pro": "Pro", "mode.toggle": "Toggle Simple/Pro mode",
    "mode.simpleOn": "Simple mode: wizard & series only, beginner friendly", "mode.proOn": "Pro mode: full parameters & storyboard unlocked",
    "engines.title": "Local engines", "engines.comfy": "Local visual engine", "engines.acestep": "Local music engine", "engines.ollama": "Local writer engine",
    "engines.online": "Online · free", "engines.offline": "Offline", "engines.toggleHint": "Click to simulate online/offline (demo of fallback strategy)",
    "engines.allLocal": "All-local bundle", "engines.allLocalDone": "Switched to the all-local free pipeline",
    "engines.degrade": "Engine offline: options disabled; fall back to stock footage or paid cloud sources", "engines.queueHint": "Local engines queue serially on one GPU; draft tier is faster",
    "wizard.step1": "Story Idea", "wizard.step2": "Characters", "wizard.step3": "Episodes", "wizard.step4": "Storyboard", "wizard.step5": "Preview & Run",
    "wizard.idea": "Describe your short drama in one sentence", "wizard.ideaPh": "e.g. A laid-off woman turns a rejected proposal into her comeback",
    "wizard.genre": "Genre template (pre-binds style / voice / music)", "wizard.duration": "Target duration per episode (s)", "wizard.episodes": "Episodes",
    "wizard.next": "Next", "wizard.back": "Back", "wizard.needIdea": "Describe your story in one sentence first",
    "wizard.tpl.urban": "Urban Comeback", "wizard.tpl.urbanDesc": "Office revenge · cold neon · rising tension",
    "wizard.tpl.period": "Period Romance", "wizard.tpl.periodDesc": "Lantern court · warm gold & jade · playful folk",
    "wizard.tpl.suspense": "Suspense Twist", "wizard.tpl.suspenseDesc": "Rainy-night maze · low-key teal · heartbeat bass",
    "wizard.tpl.healing": "Healing Slice-of-Life", "wizard.tpl.healingDesc": "Corner-shop warmth · cream light · gentle piano",
    "wizard.tpl.scifi": "Sci-Fi Future", "wizard.tpl.scifiDesc": "Stellar city · violet-blue glow · synthwave",
    "wizard.charsTitle": "Character cards (reference images generated once, reused across episodes)",
    "wizard.charsExtract": "Extract characters with AI", "wizard.charsBusy": "Local writer engine extracting characters…", "wizard.charsDone": "Characters extracted — edit or delete freely",
    "wizard.charsHint": "Each character binds an appearance prompt + reference images + fixed seed + voice. Every episode's keyframes inject the same references so faces stay consistent.",
    "wizard.charAdd": "Add character", "wizard.charDelete": "Delete character", "wizard.charDeleted": "Character deleted",
    "wizard.charName": "Name", "wizard.charPersona": "Personality", "wizard.charAppearance": "Appearance prompt (injected into every generation)", "wizard.charVoice": "Voice",
    "wizard.charRegen": "Regenerate look", "wizard.charRegenDone": "Reference images regenerated (new seed)",
    "wizard.outlineTitle": "Episode outline (drag to reorder)", "wizard.outlineHint": "One logline + one end-of-episode hook per episode; hooks drive retention.",
    "wizard.epLogline": "Logline", "wizard.epHook": "Ending hook", "wizard.epAdd": "Add episode", "wizard.epDelete": "Delete episode",
    "wizard.boardTitle": "Storyboard (compact view)", "wizard.boardHint": "Beginners see four columns: visual / line / duration / link. Engine & cost live under Advanced.",
    "wizard.boardGen": "Generate storyboard", "wizard.boardBusy": "Breaking the outline into shots…", "wizard.boardDone": "Storyboard generated — refine it in Pro mode",
    "wizard.colVisual": "Visual", "wizard.colLine": "Line / narration", "wizard.colDur": "Duration", "wizard.colLink": "Link", "wizard.advanced": "Advanced (engine & cost)",
    "wizard.openPro": "Open the full storyboard in Pro mode", "wizard.previewTitle": "Preview & Generate",
    "wizard.tier": "Quality tier", "wizard.tierDraft": "Fast preview · minutes", "wizard.tierDraftDesc": "turbo 4-step · 768p — check the look cheaply",
    "wizard.tierFinal": "Final render · slower", "wizard.tierFinalDesc": "Full model · 1080p — upgrade in one click once approved",
    "wizard.costTitle": "Cost summary", "wizard.costLocal": "Local free items", "wizard.costCloud": "Paid cloud items", "wizard.costFree": "Everything generated locally — zero marginal cost",
    "wizard.start": "Start generating", "wizard.needChars": "Extract or add at least one character first", "wizard.needPlan": "Generate the storyboard first",
    "plan.status.draft": "Draft", "plan.status.confirmed": "Confirmed", "plan.scenes": "Scenes", "plan.scene": "Scene",
    "plan.meter.target": "Target", "plan.meter.planned": "Planned", "plan.meter.measured": "Measured", "plan.meter.over": "Outside ±10% tolerance", "plan.meter.ok": "Within ±10% tolerance",
    "plan.aiBtn": "Generate plan with AI", "plan.aiBusy": "Generating plan…", "plan.export": "Export JSON", "plan.import": "Import",
    "plan.imported": "Script plan imported", "plan.importBad": "Invalid plan file", "plan.exported": "Script plan exported",
    "plan.confirm": "Confirm plan & generate", "plan.confirmed": "Plan confirmed — executing scene by scene", "plan.confirmNeed": "Generate or import a script plan first",
    "plan.empty": "No script plan yet", "plan.emptyHint": "The script plan is the visible storyboard between your idea and generation: edit, lock and export scene by scene; generation starts only after confirmation.", "plan.emptyCta": "Generate a plan with AI",
    "plan.filmTitle": "Title", "plan.logline": "Logline", "plan.style": "Style consistency (injected into every generation prompt)",
    "plan.styleTone": "Tone", "plan.stylePalette": "Palette", "plan.styleCamera": "Camera language",
    "plan.cast": "Cast", "plan.voice": "Narration voice", "plan.bgm": "BGM plan", "plan.bgmMood": "Mood", "plan.bgmPrompt": "Music prompt", "plan.bgmVolume": "Volume", "plan.bgmFadeIn": "Fade in (s)", "plan.bgmFadeOut": "Fade out (s)",
    "plan.bgmLocal": "Local ACE-Step composition", "plan.timeline": "Timeline", "plan.timelineHint": "Click to select a scene; drag blocks to reorder (links become pending review)", "plan.bgmTrack": "BGM track", "plan.cues": "Subtitle cues",
    "plan.storyboard": "Storyboard", "plan.lock": "Lock this scene (AI must not overwrite)", "plan.unlock": "Unlock", "plan.locked": "Locked — AI regeneration will skip this scene", "plan.unlocked": "Unlocked",
    "plan.narration": "Narration / line", "plan.visual": "Visual description", "plan.keywords": "Keywords", "plan.engine": "Engine",
    "plan.engine.local_fl2v": "Local · first-last-frame animation", "plan.engine.local_i2v": "Local · image-to-video", "plan.engine.stock": "Stock footage", "plan.engine.cloud_ai": "Cloud AI (paid)",
    "plan.engineOffline": "Engine offline — option disabled", "plan.cost.free": "Free", "plan.cost.paid": "≈¥{n}",
    "plan.material": "Material binding", "plan.candidates": "Candidates", "plan.in": "In", "plan.out": "Out", "plan.swap": "Swap footage", "plan.swapped": "Candidate footage switched",
    "plan.transition": "Transition to next", "plan.trans.none": "Cut", "plan.trans.fade": "Fade", "plan.trans.slide": "Slide", "plan.trans.zoom": "Zoom", "plan.trans.match_cut": "Match cut",
    "plan.regen": "Regenerate scene", "plan.regenDone": "Scene regenerated (id preserved)", "plan.regenLocked": "Scene locked — AI cannot overwrite it",
    "plan.kfGen": "Generate keyframes locally", "plan.kfFirst": "First frame", "plan.kfLast": "Last frame", "plan.kfShared": "Shared boundary frame: this first frame = previous last frame", "plan.kfBusy": "Generating keyframe…", "plan.kfDone": "Keyframe generated", "plan.kfOffline": "Local visual engine offline — cannot generate keyframes", "plan.kfQueue": "ComfyUI queue: {n} job(s) ahead", "plan.kfStep": "KSampler {a}/{b} steps", "plan.kfCache": "This frame was generated before — reusing it (requestKey hit)",
    "plan.details": "Details", "plan.drawerTitle": "Scene details", "plan.kfPair": "Keyframe pair preview", "plan.prevLast": "Previous last frame", "plan.thisFirst": "This first frame", "plan.diffScore": "Difference score", "plan.firstPrompt": "First-frame prompt", "plan.lastPrompt": "Last-frame prompt",
    "plan.relation": "Relation to previous", "plan.rel.establish": "Establish", "plan.rel.continue": "Continue", "plan.rel.contrast": "Contrast", "plan.rel.escalate": "Escalate", "plan.rel.match_cut": "Match cut", "plan.rel.unknown": "Pending review", "plan.relNote": "Relation note",
    "plan.boundary": "Cut health", "plan.bh.ok": "Smooth", "plan.bh.warn": "Jump risk", "plan.bh.unknown": "Unreviewed",
    "plan.reordered": "Reordered: links marked pending review, shared-frame relations recomputed", "plan.genLog": "Plan generation log",
    "plan.genOllama": "Local writer engine Ollama · gemma4:26b · format:json", "plan.genOutline": "Outline → characters → shots, structured output…",
    "plan.genScene": "Scene {a}/{b} written…", "plan.genLockedSkip": "Scene {a} locked — manual edits preserved", "plan.genFallback": "Local writer engine offline — fell back to template plan (fast mode unaffected)", "plan.genDone": "Plan generated — edit scenes, then confirm",
    "plan.degradeStock": "Fall back to stock", "plan.degraded": "Fell back to stock footage; continuity via transition masking", "plan.estDur": "Estimated duration (s)", "plan.sharedFrame": "Shared frame",
    "plan.needNarration": "Scene {a} has no narration — write it before generating", "plan.localOffline": "Local visual engine offline: bring it online or fall back to stock for the affected scenes",
    "plan.paidTitle": "Confirm paid scenes", "plan.paidBody": "This plan contains {n} cloud paid scene(s), ≈¥{c} estimated. All other scenes generate locally for free. Execution follows the plan scene by scene.", "plan.paidGo": "Confirm charges & generate",
    "series.library": "Series library", "series.new": "New series", "series.newHint": "Start a new series from the Creator Wizard", "series.back": "Back to library",
    "series.episodes": "Episodes", "series.characters": "Character Bible", "series.style": "Style Bible", "series.ep": "Episode {n}",
    "series.epOpen": "Open storyboard", "series.epNext": "Generate next episode", "series.epNextBusy": "Generating the next episode's storyboard…", "series.epNextDone": "Next episode storyboard generated", "series.epOpened": "Storyboard loaded",
    "series.epStatus.outline": "Outline", "series.epStatus.draft": "Draft board", "series.epStatus.confirmed": "Confirmed", "series.epStatus.rendered": "Rendered",
    "series.hook": "Ending hook", "series.charRefs": "Reference gallery (reused across episodes)", "series.charListen": "Preview voice", "series.charSeed": "Fixed seed", "series.charConsistency": "The same references + fixed seed are injected into every episode's keyframes so faces stay consistent; locked scenes are never overwritten by AI.",
    "series.styleEra": "Era / world", "series.styleHint": "The style bible persists at series level; episodes reference it instead of rewriting. Edits affect future generations, not rendered episodes.", "series.coverEps": "{n} episodes",
  },
};

/* ---------------- inline SVG icons ---------------- */
const IC = {
  tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 5.5l1 1 2-2M4 11.5l1 1 2-2M4 17.5l1 1 2-2"/>',
  script: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
  audio: '<path d="M3 10v4M7 6v12M11 3v18M15 8v8M19 5v14M23 10v4"/>',
  video: '<rect x="2" y="5" width="14" height="14" rx="2"/><path d="M16 10l6-3v10l-6-3"/>',
  subtitle: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 12h5M13 12h5M6 16h9"/>',
  history: '<path d="M3 12a9 9 0 109-9 9.7 9.7 0 00-6.7 2.8L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 3"/>',
  llm: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/><circle cx="12" cy="12" r="2.5"/>',
  material: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
  channels: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.6 1.6 0 00-1-1.5 1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 110-4h.1a1.6 1.6 0 001.5-1 1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3h.1a1.6 1.6 0 001-1.5V3a2 2 0 114 0v.1a1.6 1.6 0 001 1.5h.1a1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8v.1a1.6 1.6 0 001.5 1H21a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z"/>',
  chevLeft: '<path d="M15 18l-6-6 6-6"/>',
  chevRight: '<path d="M9 18l6-6-6-6"/>',
  chevDown: '<path d="M6 9l6 6 6-6"/>',
  play: '<path d="M8 5.5v13l11-6.5z"/>',
  download: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
  upload: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>',
  folder: '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
  restore: '<path d="M3 12a9 9 0 109-9 9.7 9.7 0 00-6.7 2.8L3 8"/><path d="M3 3v5h5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
  eye: '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M17.9 17.9A10.8 10.8 0 0112 19c-7 0-11-7-11-7a19.8 19.8 0 015.1-5.9M9.9 4.2A10 10 0 0112 5c7 0 11 7 11 7a19.9 19.9 0 01-3.2 4.2"/><path d="M1 1l22 22"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z"/>',
  flask: '<path d="M9 3h6M10 3v6l-5.5 9A2 2 0 006.2 21h11.6a2 2 0 001.7-3L14 9V3"/><path d="M7.5 15h9"/>',
  clapper: '<rect x="2" y="6" width="20" height="14" rx="2"/><path d="M2 10h20M6 6l2 4M11 6l2 4M16 6l2 4"/>',
  log: '<path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  send: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 010 18 15 15 0 010-18z"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="M10.7 12.3L21 2M15 8l3 3M18 5l3 3"/>',
  broom: '<path d="M19 3l-7 7"/><path d="M12 10l-8 8a2.8 2.8 0 004 4l8-8"/><path d="M9 13l4 4"/>',
  refresh: '<path d="M21 12a9 9 0 11-2.6-6.4"/><path d="M21 3v6h-6"/>',
  presets: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/><path d="M1 14h6M9 8h6M17 16h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>',
  board: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16M3 12h18"/>',
  series: '<rect x="3" y="7" width="14" height="14" rx="2"/><path d="M7 3h14v14"/>',
  link: '<path d="M10 13a5 5 0 007.5.5l3-3a5 5 0 00-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 00-7.5-.5l-3 3a5 5 0 007 7l1.7-1.7"/>',
  grip: '<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M5 21v-1a7 7 0 0114 0v1"/>',
  wand: '<path d="M15 4V2M15 10V8M11 6h2M17 6h2M20 20L6 6l2-2 14 14z"/>',
};
function icon(name, size) {
  const s = size || 17;
  return `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[name] || ""}</svg>`;
}
function iconFill(name, size) {
  const s = size || 17;
  return `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="currentColor" stroke="none" aria-hidden="true">${IC[name] || ""}</svg>`;
}

/* ---------------- helpers ---------------- */
const $ = (sel) => document.querySelector(sel);
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function t(key) { return (I18N[state.lang] && I18N[state.lang][key]) || I18N.zh[key] || key; }
function tf(key, vars) { let s = t(key); for (const k in vars) s = s.replace("{" + k + "}", vars[k]); return s; }
function getPath(obj, path) { return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj); }
function setPath(obj, path, val) {
  const keys = path.split("."); let o = obj;
  for (let i = 0; i < keys.length - 1; i++) { if (o[keys[i]] == null) o[keys[i]] = {}; o = o[keys[i]]; }
  o[keys[keys.length - 1]] = val;
}
function uid() { return Math.random().toString(16).slice(2, 10); }
function pad(n) { return String(n).padStart(2, "0"); }
function clock(d) { d = d || new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; }
function fmtDateTime(ts) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fmtElapsed(ms) { const s = Math.max(0, Math.floor(ms / 1000)); return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; }
function downloadJSON(filename, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 400);
}

/* ---------------- state ---------------- */
const DEFAULT_SYSTEM_PROMPT = "你是一名短视频文案专家。根据主题撰写口播文案：开头 3 秒抛出悬念，正文分段叙述，结尾引导互动。语言自然口语化，避免书面腔。";
const SUBTITLE_DEFAULTS = {
  subtitleEnabled: true, font: "MicrosoftYaHeiBold.ttf", fontSize: 60, fontColor: "#FFFFFF",
  position: "bottom", displayMode: "sentence", animation: "none",
  strokeColor: "#000000", strokeWidth: 2, subtitleBgEnabled: false, subtitleBgColor: "#000000",
  roundedBg: true, customPosition: 66,
};
function defaultParams() {
  return Object.assign({
    subject: "", script: "", terms: "", scriptLang: "zh-CN",
    paragraphNumber: 3, customRequirements: "", systemPrompt: DEFAULT_SYSTEM_PROMPT,
    voiceMode: "tts", ttsServer: "edge", voiceName: "zh-CN-XiaoxiaoNeural",
    voiceVolume: 1.0, voiceRate: 1.0, bgmType: "random", bgmVolume: 0.2,
    videoSource: "pexels", aspect: "portrait", concatMode: "random", matchOrder: false,
    transition: "none", fitMode: "cover", imageMotion: "zoom",
    clipDuration: 3, clipSpeed: 1.0, videoCount: 1,
    encoder: "libx264", seed: "", materialConcurrency: 3, renderConcurrency: 2,
    chargeConfirmed: false,
    llmProvider: "openai", llmModel: "gpt-4o-mini",
    providerKeys: { openai: "sk-demo-12345678", pexels: "px-demo-87654321", loomloom: "ll-demo-24681357" },
    llmBaseUrl: "",
    uploadedAudio: "", uploadedMaterials: [], uploadedBgm: "",
  }, SUBTITLE_DEFAULTS);
}
const state = {
  lang: "zh", theme: "dark",
  activePage: "script", leftCollapsed: false, rightCollapsed: false,
  formError: "",
  params: defaultParams(),
  /* project binding: every task record IS a project (unique id + params snapshot) */
  currentProjectId: "", baseline: "", dirty: false,
  projectMenuOpen: false, projectLimit: 20,
  presetMenuOpen: false, presetName: "", presets: [],
  settings: { openFolderOnCompletion: true, hideLog: false, defaultPage: "script" },
  channels: { douyin: true, wechat: true, xiaohongshu: false, bilibili: true, uploadPostEnabled: false, uploadPostAuto: false, uploadPostKey: "" },
  tasks: [], history: [], publishQueue: [
    { subject: "三分钟看懂黑洞", platforms: ["抖音", "视频号"] },
    { subject: "咖啡拉花入门教程", platforms: ["小红书"] },
  ],
  taskFilter: "all", taskSearch: "",
  historyPlatform: "all", historyResult: "all",
  previewText: "",
  aiScript: { busy: false, text: "", keywords: [] },
  voicePreview: { playing: false },
  cacheStats: { files: 128, sizeMB: 1240, oldestDays: 12 },
  llmTest: {},
  run: { status: "idle", phase: "", progress: 0, logs: [], startedAt: 0, taskId: "", subject: "", failMode: false, steps: [], stepIndex: 0, result: null },
  /* short-drama studio: dual-track mode + local engines + series/plan/wizard */
  mode: "pro",
  engines: { comfy: true, acestep: true, ollama: true },
  seriesList: [], activeSeriesId: "", seriesView: "library", seriesTab: "episodes",
  plans: {}, plan: null, selectedScene: "",
  planBusy: { active: false, revealed: 0, logs: [] },
  kfBusy: {},
  wizard: { step: 1, idea: "", genre: "urban", duration: 60, episodes: 3, chars: [], outline: [], tier: "draft", charsBusy: false, boardBusy: false, planReady: false },
};
let engineTimer = null;
let aiTimer = null;
let voiceTimer = null;

/* ---------------- seed data ---------------- */
function seed() {
  const now = Date.now();
  const H = 3600 * 1000, D = 24 * H;
  const mk = (subject, st, ago, source, extra) => Object.assign({
    id: uid(), subject, state: st, createdAt: now - ago, updatedAt: now - ago, source,
    duration: "00:42", videos: 1,
    params: { subject, videoSource: source, voiceName: "zh-CN-XiaoxiaoNeural", aspect: "portrait", videoCount: 1 },
  }, extra || {});
  state.tasks = [
    mk("人工智能如何改变日常生活", "processing", 2 * 60 * 1000, "pexels"),
    mk("三分钟看懂黑洞", "complete", 5 * H, "pexels", { duration: "01:12" }),
    mk("咖啡拉花入门教程", "complete", 1 * D + 3 * H, "pixabay", { duration: "00:58" }),
    mk("量子计算简史", "failed", 2 * D, "pexels", { error: "Pexels API Key 无效" }),
    mk("城市夜景延时摄影", "complete", 3 * D + 2 * H, "coverr", { duration: "00:36" }),
    mk("健康早餐五种做法", "complete", 4 * D, "pexels", { duration: "01:05" }),
    mk("深海生物奇观", "failed", 5 * D + 6 * H, "pixabay", { error: "素材时长不足" }),
    mk("Python 自动化办公技巧", "complete", 6 * D, "pexels", { duration: "00:51" }),
    /* same subject as above — unique ids keep them distinguishable */
    mk("三分钟看懂黑洞", "draft", 7 * D, "pexels", { params: { subject: "三分钟看懂黑洞", videoSource: "pexels", aspect: "landscape", voiceName: "zh-CN-YunxiNeural", videoCount: 2 } }),
    mk("智能家居避坑指南", "complete", 7 * D + 4 * H, "pixabay", { duration: "00:47" }),
    mk("新能源车选购攻略", "complete", 8 * D, "pexels", { duration: "01:20" }),
    mk("居家健身十分钟", "complete", 9 * D + 2 * H, "coverr", { duration: "00:39" }),
    mk("手冲咖啡器具清单", "failed", 10 * D, "pixabay", { error: "素材下载超时" }),
    mk("宋代美学入门", "complete", 11 * D, "pexels", { duration: "01:02" }),
    mk("基金定投第一课", "complete", 12 * D + 5 * H, "pexels", { duration: "00:55" }),
    mk("手机摄影构图技巧", "complete", 13 * D, "pixabay", { duration: "00:44" }),
    mk("露营装备清单", "draft", 14 * D, "coverr"),
    mk("职场沟通五个习惯", "complete", 15 * D + 3 * H, "pexels", { duration: "01:08" }),
    mk("宋词里的春天", "complete", 16 * D, "pexels", { duration: "00:52" }),
    mk("AI 绘画工具横评", "failed", 17 * D + 6 * H, "loomloom", { error: "AI 来源计费未确认" }),
    mk("一周备餐计划", "complete", 18 * D, "pixabay", { duration: "00:49" }),
    mk("桌面改造灵感", "complete", 19 * D + 2 * H, "coverr", { duration: "00:37" }),
    mk("跑步姿势纠正", "complete", 20 * D, "pexels", { duration: "00:58" }),
    mk("浏览器效率插件", "draft", 21 * D, "pexels"),
    mk("阳台种菜指南", "complete", 22 * D + 4 * H, "pixabay", { duration: "01:03" }),
    mk("睡眠改善实验", "complete", 23 * D, "pexels", { duration: "00:46" }),
    mk("二手相机验机流程", "complete", 24 * D + 7 * H, "coverr", { duration: "01:15" }),
  ];
  state.presets = [
    { id: uid(), builtin: true, name: "竖屏口播 · 默认", desc: "9:16 库存视频 + 晓晓配音 + 底部白字描边字幕",
      params: { aspect: "portrait", videoSource: "pexels", voiceMode: "tts", ttsServer: "edge", voiceName: "zh-CN-XiaoxiaoNeural", videoCount: 1, subtitleEnabled: true, fontSize: 60, fontColor: "#FFFFFF", strokeWidth: 2, position: "bottom", bgmVolume: 0.2 } },
    { id: uid(), builtin: true, name: "横屏知识科普", desc: "16:9 长片段 + 云希男声 + 低音量背景音乐",
      params: { aspect: "landscape", videoSource: "pexels", voiceName: "zh-CN-YunxiNeural", clipDuration: 5, fontSize: 52, bgmVolume: 0.12, paragraphNumber: 4, videoCount: 1 } },
    { id: uid(), builtin: true, name: "英文出海", desc: "English script + Jenny voice + Pixabay footage",
      params: { scriptLang: "en-US", aspect: "landscape", videoSource: "pixabay", voiceName: "en-US-JennyNeural", terms: "ai, lifestyle, technology", fontSize: 56 } },
    { id: uid(), builtin: true, name: "快速草稿", desc: "短文案快渲染，用于预览效果",
      params: { paragraphNumber: 2, clipDuration: 2, materialConcurrency: 5, renderConcurrency: 4, videoCount: 1, fontSize: 64 } },
  ];
  const hm = (subject, platform, result, ago, dur) => ({ id: uid(), subject, platform, result, time: now - ago, duration: dur });
  state.history = [
    hm("三分钟看懂黑洞", "抖音", "success", 4 * H, "3.2s"),
    hm("三分钟看懂黑洞", "视频号", "success", 4 * H + 60000, "4.1s"),
    hm("咖啡拉花入门教程", "小红书", "success", 1 * D, "2.8s"),
    hm("咖啡拉花入门教程", "B站", "failed", 1 * D + 60000, "—"),
    hm("城市夜景延时摄影", "抖音", "success", 3 * D, "3.5s"),
    hm("健康早餐五种做法", "YouTube", "success", 4 * D + 2 * H, "6.9s"),
  ];
  seedShortDrama();
}

/* ============================================================
   Short-drama studio — series / script-plan / wizard data model
   (demo seeds; production schema lives in the solution doc §4)
   ============================================================ */
function sdHash(str) {
  let h = 2166136261; const s = String(str);
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
const KF_PALETTES = [
  ["#0e2a4a", "#123a5e", "#22d3ee", "#f5a524"],
  ["#1c1030", "#3b1d5e", "#d946ef", "#22d3ee"],
  ["#0b2b26", "#0e6b5c", "#00c880", "#f5e663"],
  ["#2b1a0e", "#6b3a0e", "#f5a524", "#ff8a6a"],
  ["#101c3a", "#1c2f6b", "#4c8dff", "#d946ef"],
  ["#26121f", "#5e1d3b", "#f0455a", "#f5a524"],
];
/* procedural keyframe: gradient sky + skyline + figure silhouette, deterministic per seed */
function kfSvg(seedStr, label) {
  const h = sdHash(seedStr || "empty");
  const p = KF_PALETTES[h % KF_PALETTES.length];
  const r = (n) => ((h >>> n) & 255) / 255;
  const gid = "kf" + h;
  let skyline = "";
  for (let i = 0; i < 7; i++) {
    const bw = 14 + Math.floor(r(i * 3) * 14);
    const bh = 18 + Math.floor(r(i * 5 + 1) * 34);
    const bx = i * 23 + Math.floor(r(i * 7 + 2) * 6);
    skyline += `<rect x="${bx}" y="${72 - bh}" width="${bw}" height="${bh}" fill="${p[1]}" opacity="0.9"/>`;
    if (i % 2 === 0) skyline += `<rect x="${bx + 3}" y="${76 - bh}" width="3" height="3" fill="${p[2]}" opacity="0.85"/>`;
  }
  const fx = 30 + Math.floor(r(9) * 100);
  return `<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${esc(label || "keyframe")}">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0.7" y2="1">
      <stop offset="0" stop-color="${p[0]}"/><stop offset="1" stop-color="${p[1]}"/></linearGradient></defs>
    <rect width="160" height="90" fill="url(#${gid})"/>
    <circle cx="${118 + Math.floor(r(4) * 26)}" cy="${14 + Math.floor(r(6) * 12)}" r="${6 + Math.floor(r(8) * 5)}" fill="${p[3]}" opacity="0.8"/>
    ${skyline}
    <rect y="72" width="160" height="18" fill="${p[0]}"/>
    <path d="M${fx - 7} 90 L${fx - 5} 66 Q${fx} 60 ${fx + 5} 66 L${fx + 7} 90 Z" fill="#05080f"/>
    <circle cx="${fx}" cy="59" r="5" fill="#05080f"/>
    <path d="M${fx - 5} 63 Q${fx} 67 ${fx + 5} 63" stroke="${p[2]}" stroke-width="1.2" fill="none" opacity="0.9"/>
    <rect x="0" y="0" width="160" height="90" fill="none" stroke="${p[2]}" stroke-opacity="0.25"/>
    <path d="M0 ${84 - Math.floor(r(11) * 8)} L160 ${80 - Math.floor(r(13) * 10)}" stroke="${p[3]}" stroke-width="0.8" opacity="0.5"/>
  </svg>`;
}
/* procedural character portrait: deterministic head/shoulders with rim light */
function portraitSvg(seedStr, label) {
  const h = sdHash(seedStr || "char");
  const p = KF_PALETTES[(h >>> 3) % KF_PALETTES.length];
  const r = (n) => ((h >>> n) & 255) / 255;
  const gid = "pt" + h;
  const hair = h % 3;
  const hairPath = hair === 0
    ? '<path d="M42 44 Q60 20 78 44 L78 52 Q60 38 42 52 Z" fill="#0a0d14"/>'
    : hair === 1
      ? '<path d="M40 46 Q60 18 80 46 L82 70 Q78 52 60 44 Q42 52 38 70 Z" fill="#0a0d14"/>'
      : '<path d="M43 42 Q60 24 77 42 L76 48 Q60 36 44 48 Z" fill="#0a0d14"/>';
  return `<svg viewBox="0 0 120 120" preserveAspectRatio="xMidYMid slice" role="img" aria-label="${esc(label || "character")}">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${p[0]}"/><stop offset="1" stop-color="${p[1]}"/></linearGradient></defs>
    <rect width="120" height="120" fill="url(#${gid})"/>
    <circle cx="${86 + Math.floor(r(5) * 16)}" cy="${18 + Math.floor(r(7) * 10)}" r="10" fill="${p[3]}" opacity="0.5"/>
    <path d="M28 120 Q30 84 60 82 Q90 84 92 120 Z" fill="#0d1320"/>
    <path d="M28 120 Q30 84 60 82" stroke="${p[2]}" stroke-width="1.6" fill="none" opacity="0.9"/>
    <circle cx="60" cy="56" r="19" fill="#141b2b"/>
    ${hairPath}
    <path d="M45 60 Q48 68 55 70" stroke="${p[2]}" stroke-width="1.4" fill="none" opacity="0.8"/>
    <circle cx="53" cy="56" r="1.6" fill="${p[2]}"/><circle cx="67" cy="56" r="1.6" fill="${p[2]}"/>
    <path d="M55 66 Q60 69 65 66" stroke="${p[3]}" stroke-width="1.2" fill="none" opacity="0.85"/>
  </svg>`;
}

/* genre templates: pre-bind style bible + voice + BGM mood + canned cast */
const GENRES = [
  { id: "urban", hue: 0, voice: "zh-CN-XiaoxiaoNeural",
    style: { tone: "都市冷调·高对比", palette: "青蓝夜色 + 琥珀霓虹", camera: "手持跟拍与低角度仰拍", era: "当代都市" },
    bgm: { mood: "紧张渐强的都市电子", prompt: "dark urban electronic, rising tension, neon night, 90 bpm" },
    chars: [
      { name: "林晚", role: "protagonist", persona: "外柔内刚，被裁员后绝地反击", appearance: "25岁职场女性，齐肩黑发，米色风衣，眼神坚定", voice: "zh-CN-XiaoxiaoNeural" },
      { name: "沈聆", role: "support", persona: "克制理性的投资人，暗中相助", appearance: "30岁男性，深灰西装，银边眼镜，神情克制", voice: "zh-CN-YunxiNeural" },
      { name: "顾湘", role: "support", persona: "狡黠热心的自媒体博主", appearance: "28岁女性，栗色卷发，机车夹克，笑容狡黠", voice: "zh-CN-XiaoyiNeural" },
    ] },
  { id: "period", hue: 3, voice: "zh-CN-XiaoyiNeural",
    style: { tone: "暖金青绿·柔光", palette: "灯会暖金 + 庭院青绿", camera: "缓慢推拉与对称构图", era: "架空古代" },
    bgm: { mood: "轻快国风小调", prompt: "playful chinese folk, guzheng and dizi, lantern festival, 100 bpm" },
    chars: [
      { name: "苏小满", role: "protagonist", persona: "机灵善良的点心铺少女", appearance: "18岁少女，双鬟发髻，藕色襦裙，眉眼弯弯", voice: "zh-CN-XiaoyiNeural" },
      { name: "萧景行", role: "support", persona: "微服私访的冷面世子", appearance: "22岁青年，玄色锦袍，白玉发冠，眉目清冷", voice: "zh-CN-YunxiNeural" },
    ] },
  { id: "suspense", hue: 4, voice: "zh-CN-YunxiNeural",
    style: { tone: "低照度青灰·雨雾", palette: "雨夜青灰 + 警示红", camera: "长焦偷窥视角与缓慢横移", era: "当代都市" },
    bgm: { mood: "心跳低音与弦乐悬疑", prompt: "suspense thriller, heartbeat bass, tense strings, rainy night, 70 bpm" },
    chars: [
      { name: "程野", role: "protagonist", persona: "失眠的刑警，追一桩旧案", appearance: "35岁男性，黑色风衣，胡渣，眼神疲惫锐利", voice: "zh-CN-YunxiNeural" },
      { name: "白荔", role: "support", persona: "知晓真相的心理医生", appearance: "30岁女性，白色高领毛衣，短发，平静微笑", voice: "zh-CN-XiaoxiaoNeural" },
    ] },
  { id: "healing", hue: 2, voice: "zh-CN-XiaoxiaoNeural",
    style: { tone: "奶油暖光·低饱和", palette: "奶油白 + 木质棕 + 植物绿", camera: "固定机位与微距特写", era: "当代小镇" },
    bgm: { mood: "舒缓钢琴与环境声", prompt: "gentle piano, warm ambient, cozy corner shop, 60 bpm" },
    chars: [
      { name: "陈一禾", role: "protagonist", persona: "返乡开深夜食堂的前程序员", appearance: "29岁男性，围裙，短发，笑容温和", voice: "zh-CN-YunxiNeural" },
      { name: "外婆", role: "support", persona: "毒舌心软的老街坊", appearance: "70岁女性，银发盘髻，蓝布围裙，眼神慈祥", voice: "zh-CN-XiaoxiaoNeural" },
    ] },
  { id: "scifi", hue: 1, voice: "zh-CN-YunxiNeural",
    style: { tone: "紫蓝辉光·高反差", palette: "星际紫蓝 + 信号品红", camera: "广角仰拍与轨道环绕", era: "2140 年轨道都市" },
    bgm: { mood: "合成器浪潮与脉冲节拍", prompt: "synthwave, pulsing arpeggio, orbital city, 110 bpm" },
    chars: [
      { name: "凯-7", role: "protagonist", persona: "觉醒情感的货运机器人", appearance: "人形机械体，磨砂银外壳，蓝色光条眼瞳", voice: "zh-CN-YunxiNeural" },
      { name: "蓝茱", role: "support", persona: "地下网络的信号黑客", appearance: "24岁女性，荧光紫短发，光纤夹克", voice: "zh-CN-XiaoyiNeural" },
    ] },
];
function genreById(id) { return GENRES.find((g) => g.id === id) || GENRES[0]; }

/* six-shot narrative arc used by the wizard board generator (bilingual) */
const WIZ_ARC = [
  { rel: "establish", engine: "local_fl2v", dur: 8.5, shared: false,
    zh: { n: "开场：城市还没睡，{c}已经站在命运的路口。", v: "城市夜景大全景，{c}的剪影立于霓虹之下" },
    en: { n: "Opening: the city never sleeps, and {c} stands at a crossroads of fate.", v: "Wide city nightscape, silhouette of {c} under neon" } },
  { rel: "continue", engine: "local_fl2v", dur: 9.5, shared: true,
    zh: { n: "一个意外的发现，把{c}推回了风暴中心。", v: "特写：{c}发现关键线索，瞳孔骤缩" },
    en: { n: "An unexpected discovery pulls {c} back into the storm.", v: "Close-up: {c} finds the key clue, eyes widening" } },
  { rel: "contrast", engine: "stock", dur: 10, shared: false,
    zh: { n: "这座城市从不缺机会，缺的是被看见的入口。", v: "城市夜景延时，车流如河（库存素材）" },
    en: { n: "This city never lacks chances — only doors that let you be seen.", v: "City night timelapse, traffic like a river (stock)" } },
  { rel: "escalate", engine: "local_fl2v", dur: 9.5, shared: false,
    zh: { n: "{c}做了决定：这一次，不再交给别人评审。", v: "雨窗特写，笔记本与钢笔，{c}写下决心" },
    en: { n: "{c} decides: this time, no more waiting for someone else's verdict.", v: "Rainy window close-up, notebook and pen, resolve written down" } },
  { rel: "continue", engine: "local_fl2v", dur: 10, shared: true,
    zh: { n: "天台的风很大。盟友只问了一句：你要多少启动资金？", v: "天台双人对话剪影，城市灯火背景" },
    en: { n: "The rooftop wind is fierce. The ally asks only: how much seed money do you need?", v: "Two-figure rooftop dialogue silhouette against city lights" } },
  { rel: "match_cut", engine: "local_fl2v", dur: 10, shared: true,
    zh: { n: "旧工牌坠入江风。镜头推向{c}的眼睛——好戏才刚开始。", v: "工牌坠落→眼部特写匹配剪辑，霓虹入瞳" },
    en: { n: "The old badge falls into the river wind. Push in on {c}'s eyes — the real show begins.", v: "Falling badge match-cuts to an eye close-up, neon in the iris" } },
];

function mkScene(id, order, o) {
  return Object.assign({
    id, order, locked: false, speaker: "narrator",
    narration: "", est_duration: 8, measured_duration: null,
    visual: "", keywords: [], characters: [], location: "",
    relation_to_prev: order === 1 ? "establish" : "continue", relation_note: "",
    engine: "local_fl2v",
    material: { source: "pexels", candidates: [], selected: null, in: 0, out: 5 },
    keyframe: { first: null, last: null, first_prompt: "", last_prompt: "", shared_with_prev: false },
    transition_to_next: "none", subtitle_cues: null, boundary_health: "unknown",
    cost: { tier: "free", estimate_cny: 0, request_key: null },
  }, o);
}

function seedShortDrama() {
  const g = GENRES[0];
  const chars = g.chars.map((c, i) => Object.assign({ id: "c" + (i + 1), seed: 900001 + i, lora: null, reference_images: ["ref-1", "ref-2", "ref-3"] }, c));
  const series = {
    series_version: 1, id: "sr-denghuo", title: "灯火之上", genre_template: "urban",
    style_bible: Object.assign({}, g.style),
    characters: chars,
    locations: [
      { id: "l1", name: "写字楼大堂", prompt: "深夜写字楼大堂，玻璃幕墙映出霓虹" },
      { id: "l2", name: "城市天台", prompt: "城市天台，远处江面与灯火车流" },
      { id: "l3", name: "雨窗咖啡馆", prompt: "暖光咖啡馆，木质吧台与雨窗" },
    ],
    episodes: [
      { id: "ep1", seq: 1, title: "被裁员的夜晚", logline: "林晚抱着纸箱走出写字楼，却在垃圾桶里捡回了被否决的方案。", hook: "方案扉页上多了一行陌生人的批注", status: "rendered", plan_id: "ep1" },
      { id: "ep2", seq: 2, title: "方案复活", logline: "招标屏幕上滚动的题目，正是她被否决的那份方案。", hook: "沈聆问：你要多少启动资金？", status: "draft", plan_id: "ep2" },
      { id: "ep3", seq: 3, title: "正面交锋", logline: "发布会前夜，对手提前拿到了她的第七版方案。", hook: "监控录像里出现了不该出现的人", status: "outline", plan_id: null },
    ],
  };
  state.seriesList = [series];
  state.activeSeriesId = series.id;
  /* episode 2 storyboard — the working plan (6 scenes, ≈57.5s vs 60s target) */
  const S = (id, order, o) => mkScene(id, order, Object.assign({ characters: ["c1"], location: "l1" }, o));
  const ep2 = {
    plan_version: 1, revision: 3, status: "draft", series_id: series.id, episode_id: "ep2",
    title: "灯火之上 · 第2集 方案复活", logline: series.episodes[1].logline,
    style: Object.assign({ consistency_subject: "林晚：齐肩黑发 + 米色风衣（参考图 c1）" }, g.style),
    target_duration: 60, aspect: "9:16", quality_tier: "draft",
    voice: { name: "zh-CN-XiaoxiaoNeural", rate: 1.0 },
    bgm: { type: "acestep_local", mood: g.bgm.mood, prompt: g.bgm.prompt, volume: 0.2, fade_in: 1.0, fade_out: 3.0 },
    llm: { provider: "ollama", model: "gemma4:26b" }, seed: 20261120,
    scenes: [
      S("s1", 1, { narration: "深夜十一点，林晚抱着纸箱走出写字楼。三个月的心血，换来一句「架构调整」。", est_duration: 8.5,
        visual: "深夜写字楼大堂，林晚抱纸箱走向旋转门，霓虹倒影", keywords: ["night office", "lobby", "neon"],
        relation_to_prev: "establish", relation_note: "开场建立人物与困境", engine: "local_fl2v",
        keyframe: { first: "ep2-s1-f", last: "ep2-s1-l", first_prompt: "深夜大堂全景，抱纸箱女性背影，霓虹倒影", last_prompt: "旋转门前回首，目光落向大堂屏幕", shared_with_prev: false },
        transition_to_next: "fade", boundary_health: "ok", cost: { tier: "free", estimate_cny: 0, request_key: "a3f8c2" } }),
      S("s2", 2, { narration: "电梯门合上的瞬间，她瞥见大堂屏幕上滚动的新项目招标——正是她被否决的那份方案的题目。", est_duration: 9.5,
        visual: "电梯间特写→大堂招标屏，题目字样清晰", keywords: ["elevator", "screen", "bidding"],
        relation_to_prev: "continue", relation_note: "同一空间承接，视线引导发现线索", engine: "local_fl2v",
        keyframe: { first: "ep2-s1-l", last: "ep2-s2-l", first_prompt: "（共享上段尾帧）", last_prompt: "招标屏特写，题目字样与方案同名", shared_with_prev: true },
        transition_to_next: "none", boundary_health: "ok", cost: { tier: "free", estimate_cny: 0, request_key: "b71e09" } }),
      S("s3", 3, { narration: "这座城市从不缺机会，缺的是被看见的入口。林晚在便利店坐了一夜，把方案改到了第七版。", est_duration: 10,
        visual: "城市夜景延时，车流如河；便利店暖窗剪影", keywords: ["city night", "timelapse", "convenience store"],
        relation_to_prev: "contrast", relation_note: "宏大夜景对比个人孤灯，情绪反差", engine: "stock", location: "l1",
        material: { source: "pexels", candidates: [
          { id: "px-8841", label: "city night timelapse", seed: "cand-8841" },
          { id: "px-9032", label: "traffic river aerial", seed: "cand-9032" },
          { id: "px-7710", label: "store window rain", seed: "cand-7710" },
        ], selected: "px-8841", in: 0, out: 10 },
        keyframe: { first: null, last: null, first_prompt: "", last_prompt: "", shared_with_prev: false },
        transition_to_next: "fade", boundary_health: "warn" }),
      S("s4", 4, { narration: "第七版方案的扉页上，她写下一行小字：这一次，不再交给别人评审。", est_duration: 9.5, location: "l3",
        visual: "雨窗咖啡馆特写，笔记本与钢笔，字迹入镜", keywords: ["rain window", "notebook", "cafe"],
        relation_to_prev: "escalate", relation_note: "从旁观到行动，决心递进", engine: "local_fl2v",
        keyframe: { first: "ep2-s4-f", last: "ep2-s4-l", first_prompt: "雨窗暖光，笔记本扉页特写", last_prompt: "钢笔收笔，抬眼望向窗外夜色", shared_with_prev: false },
        transition_to_next: "zoom", boundary_health: "ok", cost: { tier: "free", estimate_cny: 0, request_key: null } }),
      S("s5", 5, { narration: "天台的风很大。沈聆看完方案，只问了一句：「你要多少启动资金？」", est_duration: 10,
        visual: "天台双人对话剪影，城市灯火背景", keywords: ["rooftop", "dialogue", "city lights"], characters: ["c1", "c2"], location: "l2",
        relation_to_prev: "continue", relation_note: "决心落地为盟约，同夜承接", engine: "local_fl2v",
        keyframe: { first: "ep2-s4-l", last: "ep2-s5-l", first_prompt: "（共享上段尾帧）", last_prompt: "沈聆合上方案，目光投向林晚", shared_with_prev: true },
        transition_to_next: "none", boundary_health: "ok", cost: { tier: "free", estimate_cny: 0, request_key: "c9d4e1" } }),
      S("s6", 6, { narration: "林晚把纸箱里的工牌扔进江风里。镜头推向她的眼睛——灯火之上，好戏才刚开始。", est_duration: 10,
        visual: "工牌坠落→眼部特写匹配剪辑，霓虹入瞳", keywords: ["badge falling", "eye closeup", "match cut"], location: "l2",
        relation_to_prev: "match_cut", relation_note: "坠落轨迹匹配瞳孔推进，集尾悬念", engine: "local_fl2v",
        keyframe: { first: "ep2-s5-l", last: "ep2-s6-l", first_prompt: "（共享上段尾帧）", last_prompt: "眼部大特写，霓虹灯火映在瞳孔里", shared_with_prev: true },
        transition_to_next: "none", boundary_health: "ok", cost: { tier: "free", estimate_cny: 0, request_key: null } }),
    ],
  };
  /* episode 1 — already rendered: measured durations backfilled */
  const ep1 = {
    plan_version: 1, revision: 5, status: "confirmed", series_id: series.id, episode_id: "ep1",
    title: "灯火之上 · 第1集 被裁员的夜晚", logline: series.episodes[0].logline,
    style: Object.assign({ consistency_subject: "林晚：齐肩黑发 + 米色风衣（参考图 c1）" }, g.style),
    target_duration: 45, aspect: "9:16", quality_tier: "final",
    voice: { name: "zh-CN-XiaoxiaoNeural", rate: 1.0 },
    bgm: { type: "acestep_local", mood: g.bgm.mood, prompt: g.bgm.prompt, volume: 0.2, fade_in: 1.0, fade_out: 3.0 },
    llm: { provider: "ollama", model: "gemma4:26b" }, seed: 20261119,
    scenes: [
      S("e1s1", 1, { narration: "晚上十一点，人事部的灯还亮着。林晚知道，今晚的谈话不会愉快。", est_duration: 9, measured_duration: 9.4,
        visual: "走廊长镜头，人事部灯光", engine: "local_fl2v", boundary_health: "ok", transition_to_next: "fade",
        keyframe: { first: "ep1-s1-f", last: "ep1-s1-l", first_prompt: "走廊长镜头", last_prompt: "门前停顿", shared_with_prev: false } }),
      S("e1s2", 2, { narration: "「架构调整」四个字，抹掉了她三个月的通宵。", est_duration: 8, measured_duration: 8.2,
        visual: "会议室对切，解约书特写", engine: "local_fl2v", boundary_health: "ok", transition_to_next: "none",
        keyframe: { first: "ep1-s1-l", last: "ep1-s2-l", first_prompt: "（共享）", last_prompt: "解约书特写", shared_with_prev: true } }),
      S("e1s3", 3, { narration: "纸箱很轻，轻得像这三个月从未存在过。", est_duration: 9, measured_duration: 9.1,
        visual: "大堂背影，纸箱与旋转门", engine: "local_fl2v", boundary_health: "ok", transition_to_next: "fade",
        keyframe: { first: "ep1-s3-f", last: "ep1-s3-l", first_prompt: "大堂背影", last_prompt: "垃圾桶旁俯身", shared_with_prev: false } }),
      S("e1s4", 4, { narration: "直到她在垃圾桶里，捡回了那份被否决的方案——扉页上多了一行陌生人的批注。", est_duration: 12, measured_duration: 12.6,
        visual: "方案扉页特写，陌生批注入镜", engine: "local_fl2v", boundary_health: "ok", transition_to_next: "none",
        keyframe: { first: "ep1-s3-l", last: "ep1-s4-l", first_prompt: "（共享）", last_prompt: "批注大特写", shared_with_prev: true } }),
    ],
  };
  state.plans = { ep1, ep2 };
  state.plan = ep2;
  state.selectedScene = "";
}

/* ---------------- short-drama helpers ---------------- */
function activeSeries() { return state.seriesList.find((s) => s.id === state.activeSeriesId) || state.seriesList[0]; }
function planScenes() { return state.plan ? state.plan.scenes : []; }
function sceneById(id) { return planScenes().find((s) => s.id === id); }
function prevScene(sc) { const ss = planScenes(); const i = ss.findIndex((x) => x.id === sc.id); return i > 0 ? ss[i - 1] : null; }
function kfSeed(sc, which) {
  if (which === "first" && sc.keyframe.shared_with_prev) {
    const pv = prevScene(sc);
    if (pv && pv.keyframe.last) return pv.keyframe.last;
  }
  return sc.keyframe[which];
}
function planTotal() { return Math.round(planScenes().reduce((a, s) => a + (s.measured_duration || s.est_duration), 0) * 10) / 10; }
function estFromText(txt) { return Math.max(2, Math.round((String(txt || "").length / 4.2) * 10) / 10); }
function sceneCost(sc) { return sc.engine === "cloud_ai" ? 1.2 : 0; }
function engineOnline(eng) {
  if (eng === "stock" || eng === "cloud_ai") return true;
  return !!state.engines.comfy;
}
function charById(id) { const sr = activeSeries(); return sr ? sr.characters.find((c) => c.id === id) : null; }
function locById(id) { const sr = activeSeries(); return sr ? sr.locations.find((l) => l.id === id) : null; }

/* ---------------- persistence ---------------- */
const LS_KEY = "changofilm-ui-demo-shell";
function saveShell() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      lang: state.lang, theme: state.theme, activePage: state.activePage,
      leftCollapsed: state.leftCollapsed, rightCollapsed: state.rightCollapsed,
      mode: state.mode, wizardStep: state.wizard.step,
    }));
  } catch (e) { /* file:// private mode — ignore */ }
}
function loadShell() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (s.lang === "zh" || s.lang === "en") state.lang = s.lang;
    if (s.theme === "dark" || s.theme === "light") state.theme = s.theme;
    if (typeof s.leftCollapsed === "boolean") state.leftCollapsed = s.leftCollapsed;
    if (typeof s.rightCollapsed === "boolean") state.rightCollapsed = s.rightCollapsed;
    if (s.activePage && PAGES[s.activePage]) state.activePage = s.activePage;
    if (s.mode === "simple" || s.mode === "pro") state.mode = s.mode;
    if (s.wizardStep >= 1 && s.wizardStep <= 5) state.wizard.step = s.wizardStep;
    if (state.mode === "simple" && !SIMPLE_PAGES.includes(state.activePage)) state.activePage = "wizard";
  } catch (e) { /* ignore */ }
}

/* ---------------- navigation registry ---------------- */
const PAGES = {
  wizard: { icon: "wand", group: "create" },
  tasks: { icon: "tasks", group: "create" },
  script: { icon: "script", group: "create" },
  plan: { icon: "board", group: "create" },
  series: { icon: "series", group: "create" },
  audio: { icon: "audio", group: "create" },
  video: { icon: "video", group: "create" },
  subtitle: { icon: "subtitle", group: "create" },
  history: { icon: "history", group: "publish" },
  channels: { icon: "channels", group: "publish" },
  llm: { icon: "llm", group: "config" },
  material: { icon: "material", group: "config" },
  presets: { icon: "presets", group: "config" },
  settings: { icon: "settings", group: "config" },
};
const NAV_ORDER = ["wizard", "tasks", "script", "plan", "series", "audio", "video", "subtitle", "history", "channels", "llm", "material", "presets", "settings"];
const SIMPLE_PAGES = ["wizard", "series", "tasks", "settings"];

function processingCount() {
  return state.tasks.filter((x) => x.state === "processing").length;
}

/* ---------------- shell rendering ---------------- */
function renderNav() {
  const groups = { create: [], publish: [], config: [] };
  const ids = state.mode === "simple" ? NAV_ORDER.filter((id) => SIMPLE_PAGES.includes(id)) : NAV_ORDER;
  ids.forEach((id) => groups[PAGES[id].group].push(id));
  let html = "";
  for (const g of ["create", "publish", "config"]) {
    if (!groups[g].length) continue;
    html += `<div class="nav-group">${esc(t("group." + g))}</div>`;
    for (const id of groups[g]) {
      const active = state.activePage === id ? " active" : "";
      const count = id === "tasks" && processingCount() > 0 ? `<span class="nav-count">${processingCount()}</span>` : "";
      html += `<button class="nav-item${active}" data-action="nav" data-page="${id}" data-tip="${esc(t("nav." + id))}" aria-current="${active ? "page" : "false"}">
        ${icon(PAGES[id].icon)}<span class="nav-label">${esc(t("nav." + id))}</span>${count}</button>`;
    }
  }
  $("#navScroll").innerHTML = html;
  $("#navCollapseIcon").innerHTML = icon("chevLeft", 15);
  $("#navCollapseLabel").textContent = state.leftCollapsed ? t("expand.nav") : t("collapse.nav");
  $("#navCollapse").setAttribute("aria-expanded", String(!state.leftCollapsed));
  $("#navCollapse").setAttribute("aria-label", state.leftCollapsed ? t("expand.nav") : t("collapse.nav"));
}

function renderTopbar() {
  const n = processingCount();
  const badge = $("#runBadge");
  badge.className = "run-badge" + (n > 0 ? " busy" : "");
  badge.innerHTML = `<span class="dot"></span>${n > 0 ? esc(tf("top.running", { n })) : esc(t("top.idle"))}`;
  $("#themeToggle").innerHTML = icon(state.theme === "dark" ? "sun" : "moon");
  $("#themeToggle").setAttribute("aria-label", t("theme.toggle"));
  $("#settingsShortcut").innerHTML = icon("settings");
  $("#settingsShortcut").setAttribute("aria-label", t("nav.settings"));
  $("#genToggleMobile").innerHTML = icon("log");
  $("#genToggleMobile").setAttribute("aria-label", t("gen.title"));
  $("#langSelect").value = state.lang;
  const mt = $("#modeToggle");
  mt.innerHTML = `<span class="mode-opt${state.mode === "simple" ? " active" : ""}">${esc(t("mode.simple"))}</span><span class="mode-opt${state.mode === "pro" ? " active" : ""}">${esc(t("mode.pro"))}</span>`;
  mt.setAttribute("aria-pressed", String(state.mode === "pro"));
  mt.setAttribute("aria-label", t("mode.toggle"));
  mt.title = t("mode.toggle");
  renderProjectChip();
}

/* ============================================================
   Project binding — current project = task record (unique id)
   ============================================================ */
function taskById(id) { return state.tasks.find((x) => x.id === id); }
function currentTask() { return taskById(state.currentProjectId); }
function isLocked() { const x = currentTask(); return !!x && x.state === "complete"; }
function projectName() { return (state.params.subject || "").trim() || t("project.untitled"); }

function renderProjectChip() {
  const chip = $("#projectChip");
  if (!chip) return;
  const locked = isLocked();
  const name = projectName();
  chip.classList.toggle("locked", locked);
  chip.innerHTML = `${icon(locked ? "lock" : "folder", 14)}<span class="project-name">${esc(name)}</span>` +
    (state.dirty ? `<span class="dirty-dot" title="${esc(t("project.dirty"))}"></span>` : "") + icon("chevDown", 13);
  chip.setAttribute("aria-label", t("project.switcher") + ": " + name);
  chip.setAttribute("aria-expanded", String(state.projectMenuOpen));
  const save = $("#projectSave");
  save.hidden = !state.dirty || locked;
  save.innerHTML = icon("check", 13) + `<span class="save-label">${esc(t("project.save"))}</span>`;
  save.title = t("project.dirty");
  if (state.projectMenuOpen) renderProjectMenu();
}
function sortedProjects() {
  return state.tasks.slice().sort((a, b) => (b.updatedAt || b.createdAt) - (a.updatedAt || a.createdAt));
}
function renderProjectMenu() {
  const menu = $("#projectMenu");
  const all = sortedProjects();
  const rows = all.slice(0, state.projectLimit);
  const remaining = all.length - rows.length;
  menu.innerHTML = `
    <button class="pm-new" data-action="projectNew">${icon("plus", 15)}<span>${esc(t("project.new"))}</span></button>
    <div class="pm-list">${rows.map((x) => {
      const cur = x.id === state.currentProjectId;
      const dot = x.state === "complete" ? "var(--green)" : x.state === "failed" ? "var(--red)" : x.state === "processing" ? "var(--cyan)" : "var(--text-faint)";
      return `<button class="pm-row${cur ? " current" : ""}" data-action="projectSelect" data-id="${x.id}">
        <span class="pm-dot" style="background:${dot}"></span>
        <span class="pm-subj">${esc(x.subject || t("project.untitled"))}</span>
        ${x.state === "complete" ? `<span class="pm-lock">${icon("lock", 11)}</span>` : ""}
        <span class="pm-id mono">#${esc(x.id)}</span>
        ${cur ? `<span class="badge green">${esc(t("tasks.current"))}</span>` : ""}
      </button>`;
    }).join("")}</div>
    ${remaining > 0
      ? `<button class="pm-more" data-action="projectMore">${icon("chevDown", 13)}${esc(tf("project.loadMore", { n: remaining }))}</button>`
      : `<div class="pm-all">${esc(tf("project.allLoaded", { n: all.length }))}</div>`}`;
  menu.hidden = false;
}
function openProjectMenu() { state.projectMenuOpen = true; state.projectLimit = 20; renderProjectChip(); }
function closeProjectMenu() {
  if (!state.projectMenuOpen) return;
  state.projectMenuOpen = false;
  $("#projectMenu").hidden = true;
  $("#projectChip").setAttribute("aria-expanded", "false");
}

/* dirty tracking: compare working params against the loaded baseline */
function markDirty() {
  if (isLocked()) return;
  state.dirty = JSON.stringify(state.params) !== state.baseline;
  renderProjectChip();
}
function saveProject(silent) {
  let x = currentTask();
  if (!x) {
    x = { id: uid(), createdAt: Date.now(), videos: 1, duration: "00:42" };
    state.tasks.unshift(x);
    state.currentProjectId = x.id;
  }
  if (x.state === "complete") return;
  x.subject = (state.params.subject || "").trim();
  x.source = state.params.videoSource;
  x.params = JSON.parse(JSON.stringify(state.params));
  x.updatedAt = Date.now();
  state.baseline = JSON.stringify(state.params);
  state.dirty = false;
  renderProjectChip();
  if (state.activePage === "tasks") renderTaskTable();
  if (!silent) toast(t("project.saved") + " · #" + x.id, "success");
}
function loadProject(id, opts) {
  opts = opts || {};
  const x = taskById(id);
  if (!x) return;
  stopVoicePreview();
  if (aiTimer) { clearInterval(aiTimer); aiTimer = null; state.aiScript.busy = false; }
  state.params = Object.assign(defaultParams(), JSON.parse(JSON.stringify(x.params || {})));
  ensureLlmDefaults();
  state.currentProjectId = id;
  state.baseline = JSON.stringify(state.params);
  state.dirty = false;
  state.formError = "";
  state.aiScript.text = state.params.script || "";
  state.aiScript.keywords = (state.params.terms || "").split(/[,，]/).map((s) => s.trim()).filter(Boolean);
  closeDrawer(); closeProjectMenu();
  if (opts.navigate) { go("script"); renderActionBar(); } else { renderPage(); renderActionBar(); }
  renderProjectChip();
  if (state.activePage === "tasks") renderTaskTable();
  const msg = opts.toastKey ? t(opts.toastKey) : t("project.loaded");
  toast(msg + ": " + (x.subject || t("project.untitled")) + " · #" + x.id, x.state === "complete" ? "info" : "success");
  if (x.state === "complete") toast(t("project.lockedHint"), "warn", null, null, 5200);
}
function requestSwitch(fn) {
  if (state.dirty && !isLocked()) {
    openModal(t("project.unsavedTitle"), `<p class="modal-text">${esc(tf("project.unsavedBody", { name: projectName() }))}</p>`, [
      { label: t("project.saveSwitch"), cls: "btn-primary", fn: () => { saveProject(true); fn(); } },
      { label: t("project.discard"), cls: "", fn },
      { label: t("project.cancel"), cls: "btn-ghost", fn: null },
    ]);
  } else fn();
}
function newProject() {
  requestSwitch(() => {
    const id = uid();
    state.tasks.unshift({
      id, subject: "", state: "draft", createdAt: Date.now(), updatedAt: Date.now(),
      source: "pexels", videos: 1, duration: "00:42", params: defaultParams(),
    });
    loadProject(id, { navigate: true, toastKey: "project.created" });
  });
}
function saveAsNew() {
  const src = currentTask();
  const id = uid();
  const params = JSON.parse(JSON.stringify(state.params));
  state.tasks.unshift({
    id, subject: (params.subject || "").trim(), state: "draft", createdAt: Date.now(), updatedAt: Date.now(),
    source: params.videoSource, videos: 1, duration: "00:42", params,
  });
  loadProject(id, { navigate: true, toastKey: "project.savedAsNew" });
}

/* modal (unsaved-changes confirmation) */
let modalActions = [];
function openModal(title, bodyHtml, actions) {
  modalActions = actions;
  $("#modalTitle").innerHTML = icon("alert", 17) + esc(title);
  $("#modalBody").innerHTML = bodyHtml;
  $("#modalActions").innerHTML = actions.map((a, i) =>
    `<button class="btn ${a.cls || ""}" data-modal-idx="${i}">${esc(a.label)}</button>`).join("");
  $("#modalScrim").classList.add("show");
  $("#modal").classList.add("open");
}
function closeModal() {
  $("#modalScrim").classList.remove("show");
  $("#modal").classList.remove("open");
  modalActions = [];
}

/* preset library */
function presetById(id) { return state.presets.find((x) => x.id === id); }
function applyPreset(id) {
  const pr = presetById(id);
  if (!pr) return;
  if (isLocked()) { toast(t("project.lockedHint"), "warn"); return; }
  Object.assign(state.params, JSON.parse(JSON.stringify(pr.params || {})));
  ensureLlmDefaults();
  state.presetMenuOpen = false;
  markDirty(); renderPage(); renderActionBar();
  toast(t("presets.applied") + ": " + pr.name, "success");
}
function stripVolatile(params) {
  const p = JSON.parse(JSON.stringify(params));
  delete p.providerKeys; delete p.uploadedAudio; delete p.uploadedMaterials; delete p.uploadedBgm;
  return p;
}
function presetSaveAs() {
  const name = (state.presetName || "").trim();
  if (!name) { toast(t("presets.nameRequired"), "warn"); return; }
  const p = state.params;
  state.presets.unshift({
    id: uid(), builtin: false, name,
    desc: `${sourceLabel(p.videoSource)} · ${p.aspect === "portrait" ? "9:16" : "16:9"} · ${p.voiceMode === "tts" ? p.voiceName : t("audio." + (p.voiceMode === "upload" ? "upload" : "none"))}`,
    params: stripVolatile(p),
  });
  state.presetName = "";
  renderPage();
  toast(t("presets.saved") + ": " + name, "success");
}
function presetDelete(id) {
  const idx = state.presets.findIndex((x) => x.id === id);
  if (idx < 0 || state.presets[idx].builtin) return;
  const removed = state.presets.splice(idx, 1)[0];
  renderPage();
  toast(t("presets.deleted") + ": " + removed.name, "info", t("tasks.undo"), () => {
    state.presets.splice(Math.min(idx, state.presets.length), 0, removed);
    if (state.activePage === "presets") renderPage();
  });
}
function presetExportOne(id) {
  const pr = presetById(id);
  if (!pr) return;
  downloadJSON("changofilm-preset-" + pr.name.replace(/[\\/:*?"<>|\s]+/g, "_") + ".json", {
    schema: "changofilm.param_preset", version: 1, exportedAt: new Date().toISOString(),
    name: pr.name, desc: pr.desc || "", params: pr.params,
  });
  toast(t("presets.exported") + ": " + pr.name, "success");
}
function presetLibExport() {
  downloadJSON("changofilm-param-presets.json", {
    schema: "changofilm.param_presets", version: 1, exportedAt: new Date().toISOString(),
    presets: state.presets.map((p) => ({ name: p.name, desc: p.desc || "", params: p.params })),
  });
  toast(t("presets.exported") + " · " + state.presets.length, "success");
}
function presetLibImport(file) {
  readJSONFile(file, (obj) => {
    let list = null;
    if (obj && Array.isArray(obj.presets)) list = obj.presets;
    else if (obj && obj.params && typeof obj.params === "object") list = [obj];
    list = (list || []).filter((p) => p && p.params && typeof p.params === "object");
    if (!list.length) { toast(t("presets.bad"), "error"); return; }
    list.forEach((p) => state.presets.push({
      id: uid(), builtin: false, name: String(p.name || t("project.untitled")), desc: String(p.desc || ""),
      params: stripVolatile(Object.assign(defaultParams(), p.params)),
    }));
    if (state.activePage === "presets") renderPage();
    toast(tf("presets.imported", { n: list.length }), "success");
  });
}

function renderTabbar() {
  /* mobile: simple = 4 focused tabs; pro = full nav as a scrollable strip (no page unreachable) */
  const ids = state.mode === "simple" ? ["wizard", "series", "tasks", "settings"] : NAV_ORDER;
  $("#tabbar").innerHTML = ids.map((id) =>
    `<button data-action="nav" data-page="${id}" class="${state.activePage === id ? "active" : ""}">${icon(PAGES[id].icon, 19)}<span>${esc(t("nav." + id))}</span></button>`
  ).join("");
  const act = $("#tabbar").querySelector("button.active");
  if (act && act.scrollIntoView) act.scrollIntoView({ inline: "center", block: "nearest" });
}

function sourceLabel(id) {
  const p = MATERIAL_PROVIDERS.find((x) => x.id === id);
  return p ? p.name : id;
}
function sourceKeyOk(id) {
  if (id === "local") return state.params.uploadedMaterials.length > 0;
  if (id === "codex_image") return true;
  return Boolean((state.params.providerKeys[id] || "").trim());
}
const AI_SOURCES = ["metaso_minimax", "ofox", "loomloom", "volcengine_seedance", "infistar", "jalapeno", "wavespeed", "muapi"];

function renderActionBar() {
  const p = state.params;
  const running = state.run.status === "running";
  const locked = isLocked();
  const srcOk = sourceKeyOk(p.videoSource);
  const voiceTxt = p.voiceMode === "tts" ? (p.voiceName || "—") : p.voiceMode === "upload" ? t("audio.upload") : t("audio.none");
  const chips = `
    <span class="chip ${srcOk ? "" : "warn"}"><span class="chip-dot"></span>${esc(t("ready.source"))} · ${esc(sourceLabel(p.videoSource))}</span>
    <span class="chip"><span class="chip-dot"></span>${esc(t("ready.voice"))} · ${esc(voiceTxt)}</span>
    <span class="chip ${p.subtitleEnabled ? "" : "off"}"><span class="chip-dot"></span>${esc(t("ready.subtitle"))} · ${p.subtitleEnabled ? "ON" : "OFF"}</span>
    <span class="chip"><span class="chip-dot"></span>${esc(t("ready.count"))} · ${p.videoCount}</span>`;
  $("#actionBar").innerHTML = `
    <div class="ready-chips">${chips}</div>
    <button class="btn btn-ghost btn-icon" data-action="presetExport" title="${esc(t("action.export"))}" aria-label="${esc(t("action.export"))}">${icon("download")}</button>
    <button class="btn btn-ghost btn-icon" data-action="presetImport" title="${esc(t("action.import"))}" aria-label="${esc(t("action.import"))}">${icon("upload")}</button>
    ${locked ? `<button class="btn btn-primary" data-action="saveAsNew">${icon("copy", 15)}${esc(t("project.saveAsNew"))}</button>` : ""}
    <button class="btn btn-primary${running ? " running" : ""}" data-action="generate" ${running || locked ? "disabled" : ""}>
      ${running ? '<span class="spinner"></span>' + esc(t("action.generating")) : locked ? icon("lock", 15) + esc(t("project.locked")) : iconFill("play", 15) + esc(t("action.generate"))}
    </button>`;
}

function renderGenStatic() {
  $("#genTitle").innerHTML = icon("log", 15) + esc(t("gen.title"));
  $("#railLabel").textContent = t("gen.rail");
  $("#jumpLatest").textContent = t("gen.jump");
  $("#failToggle").innerHTML = icon("flask", 15);
  $("#failToggle").title = t("gen.fail") + " — " + t("gen.failHint");
  $("#failToggle").style.color = state.run.failMode ? "var(--red)" : "";
  $("#failToggle").setAttribute("aria-pressed", String(state.run.failMode));
  $("#genCollapse").innerHTML = icon("chevRight", 15);
  $("#genCollapse").setAttribute("aria-label", t("collapse.nav"));
  $("#railExpand").innerHTML = icon("chevLeft", 15);
  $("#drawerCloseBtn").innerHTML = icon("x");
}

function applyShellClasses() {
  const body = $("#body");
  body.classList.toggle("nav-collapsed", state.leftCollapsed);
  body.classList.toggle("gen-collapsed", state.rightCollapsed);
  document.documentElement.setAttribute("data-theme", state.theme);
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  updateScrim();
}

function updateScrim() {
  const w = window.innerWidth;
  const genOverlay = w <= 1500 && !state.rightCollapsed;
  const navOverlay = w <= 1100 && !state.leftCollapsed;
  $("#scrim").classList.toggle("show", genOverlay || navOverlay);
}

function go(page) {
  if (!PAGES[page]) return;
  state.activePage = page;
  state.formError = "";
  saveShell();
  renderNav(); renderTabbar(); renderPage();
  $("#pageScroll").scrollTop = 0;
  if (window.innerWidth <= 1100 && !state.leftCollapsed) { state.leftCollapsed = true; applyShellClasses(); renderNav(); saveShell(); }
}

function toggleNav() {
  state.leftCollapsed = !state.leftCollapsed;
  applyShellClasses(); renderNav(); saveShell();
}
function toggleGen() {
  state.rightCollapsed = !state.rightCollapsed;
  applyShellClasses(); saveShell();
  if (!state.rightCollapsed) updateGenUI();
}
function toggleTheme() {
  state.theme = state.theme === "dark" ? "light" : "dark";
  applyShellClasses(); renderTopbar(); saveShell();
  if (state.activePage === "settings") renderPage();
}
function setLang(lang) {
  state.lang = lang; saveShell();
  if ($("#drawer").classList.contains("open")) closeDrawer();
  renderNav(); renderTopbar(); renderTabbar(); renderActionBar(); renderGenStatic(); renderPage(); updateGenUI(true);
}

/* ---------------- toasts ---------------- */
function toast(msg, type, actionLabel, actionFn, ttl) {
  type = type || "success";
  const el = document.createElement("div");
  el.className = "toast " + type;
  const ic = type === "success" ? "check" : type === "error" ? "alert" : type === "warn" ? "alert" : "info";
  el.innerHTML = `${icon(ic, 16)}<span class="toast-msg">${esc(msg)}</span>` +
    (actionLabel ? `<button class="toast-action">${esc(actionLabel)}</button>` : "");
  $("#toasts").appendChild(el);
  let done = false;
  const dismiss = () => {
    if (done) return; done = true;
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 220);
  };
  if (actionLabel && actionFn) {
    el.querySelector(".toast-action").addEventListener("click", () => { actionFn(); dismiss(); });
  }
  setTimeout(dismiss, ttl || (actionLabel ? 5000 : 3200));
}

/* ---------------- drawer ---------------- */
function openDrawer(title, html) {
  $("#drawerTitle").textContent = title;
  $("#drawerBody").innerHTML = html;
  $("#drawer").classList.add("open");
  $("#scrim").classList.add("show");
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  updateScrim();
}/* ---------------- shared domain data ---------------- */
const MATERIAL_PROVIDERS = [
  { id: "pexels", name: "Pexels", group: "stock" },
  { id: "pixabay", name: "Pixabay", group: "stock" },
  { id: "coverr", name: "Coverr", group: "stock" },
  { id: "metaso_minimax", name: "Metaso MiniMax H3", group: "aiVideo" },
  { id: "ofox", name: "OFox AI", group: "aiVideo" },
  { id: "loomloom", name: "LoomLoom", group: "aiVideo" },
  { id: "volcengine_seedance", name: "Seedance", group: "aiVideo" },
  { id: "infistar", name: "Infistar", group: "aiVideo" },
  { id: "jalapeno", name: "Jalapeno Cloud", group: "aiVideo" },
  { id: "wavespeed", name: "WaveSpeed", group: "aiVideo" },
  { id: "muapi", name: "MuAPI", group: "aiVideo" },
  { id: "openai_image", name: "OpenAI Image", group: "aiImage" },
  { id: "codex_image", name: "Codex Image", group: "aiImage" },
  { id: "local", name: "Local", group: "local" },
];
const LLM_PROVIDERS = [
  { id: "openai", name: "OpenAI", color: "#10a37f", models: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"], baseUrl: "https://api.openai.com/v1" },
  { id: "deepseek", name: "DeepSeek", color: "#4c8dff", models: ["deepseek-chat", "deepseek-reasoner"], baseUrl: "https://api.deepseek.com/v1" },
  { id: "moonshot", name: "Moonshot Kimi", color: "#6b5cff", models: ["moonshot-v1-8k", "moonshot-v1-32k"], baseUrl: "https://api.moonshot.cn/v1" },
  { id: "qwen", name: "Qwen", color: "#ff6a00", models: ["qwen-plus", "qwen-max"], baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { id: "gemini", name: "Google Gemini", color: "#22d3ee", models: ["gemini-2.0-flash", "gemini-2.5-pro"], baseUrl: "https://generativelanguage.googleapis.com/v1beta" },
  { id: "ollama", name: "Ollama", color: "#8b98a9", models: ["qwen2.5:7b", "llama3.1:8b"], baseUrl: "http://127.0.0.1:11434/v1" },
];
const TTS_SERVERS = [
  { id: "edge", name: "Edge TTS" }, { id: "azure", name: "Azure TTS" },
  { id: "minimax", name: "MiniMax" }, { id: "elevenlabs", name: "ElevenLabs" },
  { id: "fish", name: "Fish Audio" }, { id: "voxcpm", name: "VoxCPM" },
  { id: "chatterbox", name: "Chatterbox" }, { id: "kokoro", name: "Kokoro" },
];
const VOICES = {
  edge: ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural", "en-US-JennyNeural", "en-US-GuyNeural"],
  azure: ["zh-CN-XiaoxiaoMultilingualNeural", "zh-CN-YunyangNeural"],
  minimax: ["female-shaonv", "male-qn-qingse", "female-yujie"],
  elevenlabs: ["Rachel", "Adam", "Bella"],
  fish: ["fish-speech-1.5", "fish-speech-1.6"],
  voxcpm: ["voxcpm-default"],
  chatterbox: ["default-Female", "default-Male"],
  kokoro: ["kokoro-zf-xiaobei", "kokoro-zm-yunxi"],
};
const FONTS = [
  { id: "MicrosoftYaHeiBold.ttf", name: "Microsoft YaHei Bold" },
  { id: "SimHei.ttf", name: "SimHei" },
  { id: "SourceHanSansCN-Bold.ttf", name: "Source Han Sans CN" },
  { id: "Arial-Bold.ttf", name: "Arial Bold" },
];
const SCRIPT_LANGS = ["", "zh-CN", "zh-HK", "zh-TW", "en-US", "de-DE", "es-ES", "fr-FR", "id-ID", "it-IT", "ru-RU", "vi-VN", "th-TH", "tr-TR", "ca-ES"];
const PLATFORMS = [
  { id: "douyin", name: "抖音", color: "#fe2c55" },
  { id: "wechat", name: "视频号", color: "#07c160" },
  { id: "xiaohongshu", name: "小红书", color: "#ff2442" },
  { id: "bilibili", name: "B站", color: "#00a1d6" },
];
const SOURCE_HELP = {
  pexels: "免费库存视频，需配置 Pexels API Key。",
  pixabay: "免费库存视频与图片，需配置 Pixabay API Key。",
  coverr: "免费高清库存视频，需配置 Coverr API Key。",
  metaso_minimax: "秘塔 MiniMax H3 文生视频，按量计费。",
  ofox: "OFox AI 视频聚合，按量计费。",
  loomloom: "胜算云 AI 视频，先询价确认后扣费。",
  volcengine_seedance: "火山引擎 Seedance 文生视频，按量计费。",
  infistar: "Infistar AI 视频，按量计费。",
  jalapeno: "Jalapeno Cloud AI 视频，按量计费。",
  wavespeed: "WaveSpeed AI 视频，按量计费。",
  muapi: "MuAPI AI 视频聚合，按量计费。",
  openai_image: "OpenAI 兼容文生图 + 缓慢放大动效。",
  codex_image: "使用 ChatGPT Codex 配额生成图片。",
  local: "使用本地上传的视频/图片素材。",
};

/* ---------------- control builders ---------------- */
function pageHead(key) {
  return `<div class="page-head"><h1 class="page-title"><span class="accent-bar"></span>${esc(t("nav." + key))}</h1>
    <p class="page-sub">${esc(t("page." + key + ".sub"))}</p></div>`;
}
function field(label, control, help) {
  return `<div class="field"><div class="field-label">${label}</div>${control}${help ? `<div class="field-help">${help}</div>` : ""}</div>`;
}
function opts(list, current) {
  return list.map((o) => `<option value="${esc(o.v)}"${String(o.v) === String(current) ? " selected" : ""}>${esc(o.l)}</option>`).join("");
}
function selectBind(path, list, rerender, extra) {
  const cur = getPath(state, path);
  return `<select class="select" data-bind="${path}"${rerender ? ' data-rerender="1"' : ""}${extra || ""}>${opts(list, cur)}</select>`;
}
function groupedSelectBind(path, groups, rerender) {
  const cur = getPath(state, path);
  const body = groups.map((g) => `<optgroup label="${esc(g.label)}">${opts(g.items, cur)}</optgroup>`).join("");
  return `<select class="select" data-bind="${path}"${rerender ? ' data-rerender="1"' : ""}>${body}</select>`;
}
function fmtVal(v, fmt) {
  if (fmt === "pct") return Math.round(v * 100) + "%";
  if (fmt === "x") return Number(v).toFixed(1) + "×";
  if (fmt === "s") return v + "s";
  return String(v);
}
function rangeBind(path, min, max, step, fmt) {
  const v = getPath(state, path);
  return `<div class="range-row"><input type="range" min="${min}" max="${max}" step="${step}" value="${v}" data-bind="${path}" data-fmt="${fmt || ""}" aria-label="${esc(path)}">
    <span class="range-val" data-out="${path}" data-fmt="${fmt || ""}">${esc(fmtVal(v, fmt))}</span></div>`;
}
function toggleBind(path, label, rerender) {
  const v = getPath(state, path);
  return `<label class="toggle"><input type="checkbox" data-bind="${path}"${rerender ? ' data-rerender="1"' : ""}${v ? " checked" : ""}><span class="track"></span><span class="toggle-label">${label}</span></label>`;
}
function colorBind(path) {
  const v = getPath(state, path);
  return `<div class="color-field"><input type="color" value="${esc(v)}" data-bind="${path}" aria-label="${esc(path)}"><span class="color-hex" data-out="${path}">${esc(v)}</span></div>`;
}
function expander(id, title, body, open) {
  return `<div class="expander${open ? " open" : ""}" id="${id}">
    <button class="expander-head" data-action="expander" data-allow-locked aria-expanded="${open ? "true" : "false"}">${icon("chevRight", 14)}${title}</button>
    <div class="expander-body">${body}</div></div>`;
}
function hexToRgba(hex, a) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return `rgba(0,0,0,${a})`;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/* ---------------- page: tasks ---------------- */
function stateBadge(st) {
  if (st === "processing") return `<span class="badge cyan pulse"><span class="b-dot"></span>${esc(t("tasks.processing"))}</span>`;
  if (st === "complete") return `<span class="badge green"><span class="b-dot"></span>${esc(t("tasks.complete"))}</span>`;
  if (st === "draft") return `<span class="badge blue"><span class="b-dot"></span>${esc(t("tasks.draft"))}</span>`;
  return `<span class="badge red"><span class="b-dot"></span>${esc(t("tasks.failed"))}</span>`;
}
function filteredTasks() {
  const q = state.taskSearch.trim().toLowerCase();
  return state.tasks.filter((x) =>
    (state.taskFilter === "all" || x.state === state.taskFilter) &&
    (!q || x.subject.toLowerCase().includes(q))
  );
}
function renderTaskTable() {
  const body = $("#taskTableBody");
  if (!body) return;
  const rows = filteredTasks();
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty">${icon("clapper", 40)}<p>${esc(t("tasks.empty"))}</p></div></td></tr>`;
    return;
  }
  body.innerHTML = rows.map((x) => `
    <tr class="${x.id === state.currentProjectId ? "current-row" : ""}">
      <td>${stateBadge(x.state)}</td>
      <td>
        <button class="subj-link" data-action="taskLoad" data-id="${x.id}" title="${esc(t("tasks.load"))}: ${esc(x.subject || t("project.untitled"))}">${esc(x.subject || t("project.untitled"))}</button>
        <div class="id-line"><span class="id-chip mono" title="ID: ${esc(x.id)}">#${esc(x.id)}</span>${x.state === "complete" ? `<span class="id-lock" title="${esc(t("project.locked"))}">${icon("lock", 11)}</span>` : ""}</div>
        ${x.error ? `<div class="field-help" style="color:var(--red)">${esc(x.error)}</div>` : ""}
      </td>
      <td class="mono">${fmtDateTime(x.createdAt)}</td>
      <td class="muted">${esc(sourceLabel(x.source))}</td>
      <td><div class="row-actions">
        ${x.state === "complete" ? `<button class="icon-btn" data-action="taskPlay" data-id="${x.id}" title="${esc(t("tasks.play"))}" aria-label="${esc(t("tasks.play"))}">${iconFill("play", 15)}</button>` : ""}
        <button class="icon-btn" data-action="taskLoad" data-id="${x.id}" title="${esc(t("tasks.load"))}" aria-label="${esc(t("tasks.load"))}">${icon("restore", 15)}</button>
        <button class="icon-btn" data-action="taskFolder" data-id="${x.id}" title="${esc(t("tasks.folder"))}" aria-label="${esc(t("tasks.folder"))}">${icon("folder", 15)}</button>
        <button class="icon-btn danger" data-action="taskDelete" data-id="${x.id}" title="${esc(t("tasks.delete"))}" aria-label="${esc(t("tasks.delete"))}">${icon("trash", 15)}</button>
      </div></td>
    </tr>`).join("");
}
function pageTasks() {
  const counts = { all: state.tasks.length, draft: 0, processing: 0, complete: 0, failed: 0 };
  state.tasks.forEach((x) => counts[x.state]++);
  const tabs = [["all", "tasks.all"], ["draft", "tasks.draft"], ["processing", "tasks.processing"], ["complete", "tasks.complete"], ["failed", "tasks.failed"]]
    .map(([k, lk]) => `<button class="filter-tab${state.taskFilter === k ? " active" : ""}" data-action="taskFilter" data-filter="${k}">${esc(t(lk))}<span class="cnt">${counts[k]}</span></button>`).join("");
  const queue = state.publishQueue.length ? `
    <div class="queue-strip">${icon("send", 16)}<strong>${esc(t("tasks.queue"))}</strong>
      <span class="q-items">${state.publishQueue.map((q) => `<span class="chip">${esc(q.subject)} → ${esc(q.platforms.join(" / "))}</span>`).join("")}</span>
      <span class="badge green" style="margin-left:auto">${esc(t("tasks.queueAuto"))}</span>
    </div>` : "";
  const presetMenu = state.presetMenuOpen ? `
    <div class="preset-menu">${state.presets.map((pr) => `
      <button class="preset-menu-item" data-action="presetApply" data-id="${pr.id}">
        <span class="pm-name">${icon("presets", 13)}${esc(pr.name)}</span>
        <span class="pm-desc">${esc(pr.desc || "")}</span>
      </button>`).join("")}
    </div>` : "";
  return pageHead("tasks") + queue + `
    <div class="toolbar">
      <div class="filter-tabs" style="margin:0">${tabs}</div>
      <div class="search">${icon("search", 15)}<input class="input" data-bind="taskSearch" value="${esc(state.taskSearch)}" placeholder="${esc(t("tasks.search"))}"></div>
      <div class="preset-dropdown">
        <button class="btn btn-sm" data-action="presetMenu" aria-expanded="${state.presetMenuOpen}" aria-haspopup="true">${icon("presets", 14)}${esc(t("presets.menu"))}${icon("chevDown", 12)}</button>
        ${presetMenu}
      </div>
    </div>
    <div class="table-wrap"><table class="table">
      <thead><tr><th>${esc(t("tasks.col.state"))}</th><th>${esc(t("tasks.col.subject"))}</th><th>${esc(t("tasks.col.time"))}</th><th>${esc(t("tasks.col.source"))}</th><th style="text-align:right">${esc(t("tasks.col.actions"))}</th></tr></thead>
      <tbody id="taskTableBody"></tbody>
    </table></div>`;
}

/* ---------------- page: script ---------------- */
function pageScript() {
  const p = state.params;
  const langOpts = SCRIPT_LANGS.map((c) => ({ v: c, l: c === "" ? t("script.autoDetect") : c }));
  const advanced = `
    ${field(esc(t("script.paragraphs")), rangeBind("params.paragraphNumber", 1, 8, 1, "int"))}
    ${field(esc(t("script.requirements")), `<textarea class="textarea" rows="2" data-bind="params.customRequirements" placeholder="${esc(t("script.requirementsPh"))}">${esc(p.customRequirements)}</textarea>`)}
    ${field(esc(t("script.systemPrompt")), `<textarea class="textarea" rows="6" data-bind="params.systemPrompt">${esc(p.systemPrompt)}</textarea>`)}
    <div class="field-row">
      <button class="btn btn-sm" data-action="resetPrompt">${icon("restore", 14)}${esc(t("script.resetPrompt"))}</button>
      <button class="btn btn-sm" data-action="previewPrompt">${icon("eye", 14)}${esc(t("script.promptPreview"))}</button>
    </div>`;
  const previewBody = state.aiScript.text
    ? esc(state.aiScript.text)
    : `<span class="placeholder">${esc(t("script.previewEmpty"))}</span>`;
  const kw = state.aiScript.keywords.length
    ? `<div class="section-label">${esc(t("script.keywords"))}</div><div class="kw-chips">${state.aiScript.keywords.map((k) => `<span class="kw-chip">${esc(k)}</span>`).join("")}</div>`
    : "";
  return pageHead("script") + `
    ${state.formError ? `<div class="alert error">${icon("alert", 16)}<span>${esc(state.formError)}</span></div>` : ""}
    <div class="grid grid-2-1">
      <div class="card">
        <div class="card-title">${icon("script", 16)}${esc(t("script.settings"))}
          <button class="btn btn-ghost btn-sm hint" data-action="nav" data-page="llm" data-allow-locked>${esc(t("script.configureLlm"))} →</button>
        </div>
        ${field(esc(t("script.subject")) + ' <span class="req">*</span>', `<textarea class="textarea" rows="3" data-bind="params.subject" placeholder="${esc(t("script.subjectPh"))}">${esc(p.subject)}</textarea>`)}
        ${field(esc(t("script.script")), `<textarea class="textarea" rows="5" data-bind="params.script" placeholder="${esc(t("script.scriptPh"))}">${esc(p.script)}</textarea>`)}
        ${field(esc(t("script.terms")), `<input class="input" data-bind="params.terms" value="${esc(p.terms)}" placeholder="${esc(t("script.termsPh"))}">`)}
        ${field(esc(t("script.lang")), selectBind("params.scriptLang", langOpts))}
        ${expander("expScriptAdv", esc(t("script.advanced")), advanced, false)}
      </div>
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <div class="card-title">${icon("spark", 16)}${esc(t("script.aiTitle"))}</div>
          <button class="btn btn-primary" style="width:100%" data-action="aiScript" ${state.aiScript.busy ? "disabled" : ""}>
            ${state.aiScript.busy ? '<span class="spinner"></span>' + esc(t("script.generating")) : icon("spark", 15) + esc(t("script.aiBtn"))}
          </button>
          <div class="field-help" style="margin-top:8px">${esc(t("llm.current"))}: ${esc((LLM_PROVIDERS.find((x) => x.id === p.llmProvider) || {}).name || p.llmProvider)} · ${esc(p.llmModel)}</div>
        </div>
        <div class="card" style="flex:1">
          <div class="card-title">${icon("eye", 16)}${esc(t("script.previewTitle"))}</div>
          <div class="script-preview" id="aiScriptPreview">${previewBody}</div>
          ${kw}
        </div>
      </div>
    </div>`;
}

/* ---------------- page: audio ---------------- */
function pageAudio() {
  const p = state.params;
  const seg = [["tts", "audio.tts"], ["upload", "audio.upload"], ["none", "audio.none"]]
    .map(([v, lk]) => `<button data-action="segment" data-path="params.voiceMode" data-value="${v}" class="${p.voiceMode === v ? "active" : ""}">${esc(t(lk))}</button>`).join("");
  let modeBody = "";
  if (p.voiceMode === "tts") {
    const voices = (VOICES[p.ttsServer] || VOICES.edge).map((v) => ({ v, l: v }));
    if (!voices.some((o) => o.v === p.voiceName)) p.voiceName = voices[0].v;
    const keyField = p.ttsServer !== "edge" ? expander("expVoiceKey", esc(t("audio.providerKey")),
      field("API Key", `<input class="input" type="password" data-bind="params.providerKeys.${p.ttsServer}" value="${esc(p.providerKeys[p.ttsServer] || "")}" placeholder="${esc(t("llm.keyPh"))}">`), false) : "";
    modeBody = `
      ${field(esc(t("audio.service")), selectBind("params.ttsServer", TTS_SERVERS.map((s) => ({ v: s.id, l: s.name })), true))}
      ${field(esc(t("audio.voice")), selectBind("params.voiceName", voices))}
      <div class="field">
        <div class="field-label">${esc(t("audio.preview"))}</div>
        <div class="field-row" style="flex:0 0 auto;gap:12px">
          <button class="btn btn-sm" data-action="voicePreview" style="flex:0 0 auto">${iconFill("play", 14)}<span id="voiceBtnLabel">${esc(t("audio.preview"))}</span></button>
          <div class="wave${state.voicePreview.playing ? " playing" : ""}" id="voiceWave" style="flex:1">${"<span></span>".repeat(24)}</div>
          <span class="range-val" id="voiceTime" style="flex:0 0 auto">0:00</span>
        </div>
        <div class="field-help">${esc(t("audio.previewHint"))}</div>
      </div>
      ${field(esc(t("audio.volume")), rangeBind("params.voiceVolume", 0, 2, 0.1, "pct"))}
      ${field(esc(t("audio.rate")), rangeBind("params.voiceRate", 0.5, 2, 0.1, "x"))}
      ${keyField}`;
  } else if (p.voiceMode === "upload") {
    modeBody = `
      <div class="field">
        <input type="file" id="audioUploadFile" data-file="audio" accept="audio/*" hidden>
        <button class="btn" data-action="pickFile" data-target="audioUploadFile">${icon("upload", 15)}${esc(t("audio.uploadBtn"))}</button>
        ${p.uploadedAudio ? `<span class="badge green" style="margin-left:10px">${esc(t("audio.uploaded"))}: ${esc(p.uploadedAudio)}</span>` : ""}
      </div>
      ${field(esc(t("audio.volume")), rangeBind("params.voiceVolume", 0, 2, 0.1, "pct"))}`;
  } else {
    modeBody = `<div class="alert info">${icon("info", 16)}<span>${esc(t("audio.noneHint"))}</span></div>`;
  }
  const bgmTypes = [
    { v: "random", l: t("audio.bgmRandom") }, { v: "none", l: t("audio.bgmNone") },
    { v: "custom", l: t("audio.bgmCustom") }, { v: "sonilo", l: "Sonilo AI" }, { v: "elevenlabs", l: "ElevenLabs Music" },
  ];
  let bgmExtra = "";
  if (p.bgmType === "custom") {
    bgmExtra = `<div class="field"><input type="file" id="bgmUploadFile" data-file="bgm" accept="audio/*" hidden>
      <button class="btn btn-sm" data-action="pickFile" data-target="bgmUploadFile">${icon("upload", 14)}${esc(t("audio.uploadBtn"))}</button>
      ${p.uploadedBgm ? `<span class="badge green" style="margin-left:8px">${esc(p.uploadedBgm)}</span>` : ""}</div>`;
  } else if (p.bgmType === "sonilo" || p.bgmType === "elevenlabs") {
    bgmExtra = field("API Key", `<input class="input" type="password" data-bind="params.providerKeys.${p.bgmType}" value="${esc(p.providerKeys[p.bgmType] || "")}" placeholder="${esc(t("llm.keyPh"))}">`);
  }
  return pageHead("audio") + `
    <div class="grid grid-2">
      <div class="card">
        <div class="card-title">${icon("audio", 16)}${esc(t("audio.settings"))}</div>
        ${field(esc(t("audio.mode")), `<div class="segmented">${seg}</div>`)}
        ${modeBody}
      </div>
      <div class="card">
        <div class="card-title">${icon("audio", 16)}${esc(t("audio.bgm"))}</div>
        ${field(esc(t("audio.bgmType")), selectBind("params.bgmType", bgmTypes, true))}
        ${field(esc(t("audio.bgmVolume")), rangeBind("params.bgmVolume", 0, 1, 0.05, "pct"))}
        ${bgmExtra}
      </div>
    </div>`;
}

/* ---------------- page: video ---------------- */
function pageVideo() {
  const p = state.params;
  const groups = ["stock", "aiVideo", "aiImage", "local"].map((g) => ({
    label: t("video." + g),
    items: MATERIAL_PROVIDERS.filter((x) => x.group === g).map((x) => ({ v: x.id, l: x.name })),
  }));
  const isAi = AI_SOURCES.includes(p.videoSource);
  const billing = isAi ? `
    <div class="alert warn">${icon("alert", 16)}<span>${esc(t("video.billing"))}</span></div>
    <div class="field">${toggleBind("params.chargeConfirmed", esc(t("video.billingConfirm")))}</div>` : "";
  const localUpload = p.videoSource === "local" ? `
    <div class="field">
      <input type="file" id="materialUploadFile" data-file="materials" accept="video/*,image/*" multiple hidden>
      <button class="btn" data-action="pickFile" data-target="materialUploadFile">${icon("upload", 15)}${esc(t("video.upload"))}</button>
      <div class="field-help">${esc(t("video.uploadHint"))}</div>
      ${p.uploadedMaterials.length ? `<div class="kw-chips" style="margin-top:8px">${p.uploadedMaterials.map((f) => `<span class="kw-chip">${esc(f)}</span>`).join("")}</div>` : ""}
    </div>` : "";
  const motion = p.videoSource === "openai_image" || p.videoSource === "codex_image"
    ? field(esc(t("video.motion")), selectBind("params.imageMotion", [{ v: "static", l: t("video.motionStatic") }, { v: "zoom", l: t("video.motionZoom") }]))
    : "";
  const transOpts = [["none", "video.transNone"], ["shuffle", "video.transShuffle"], ["fade_in", "video.transFadeIn"], ["fade_out", "video.transFadeOut"], ["slide_in", "video.transSlideIn"], ["slide_out", "video.transSlideOut"], ["zoom_in", "video.transZoomIn"], ["zoom_out", "video.transZoomOut"]]
    .map(([v, lk]) => ({ v, l: t(lk) }));
  const advanced = `
    ${field(esc(t("video.encoder")), selectBind("params.encoder", [{ v: "libx264", l: t("video.encoderDefault") }, { v: "libx265", l: "libx265 (HEVC)" }, { v: "h264_nvenc", l: "h264_nvenc (NVIDIA)" }, { v: "h264_qsv", l: "h264_qsv (Intel)" }]))}
    ${field(esc(t("video.seed")), `<input class="input" data-bind="params.seed" value="${esc(p.seed)}" placeholder="${esc(t("video.seedPh"))}">`)}
    ${field(esc(t("video.materialConcurrency")), rangeBind("params.materialConcurrency", 1, 8, 1, "int"))}
    ${field(esc(t("video.renderConcurrency")), rangeBind("params.renderConcurrency", 1, 8, 1, "int"))}`;
  return pageHead("video") + `
    <div class="grid grid-2">
      <div class="card">
        <div class="card-title">${icon("material", 16)}${esc(t("video.source"))}
          <button class="btn btn-ghost btn-sm hint" data-action="nav" data-page="material" data-allow-locked>${esc(t("video.configureMaterial"))} →</button>
        </div>
        ${field(esc(t("video.source")), groupedSelectBind("params.videoSource", groups, true))}
        <div class="field-help" style="margin:-6px 0 12px">${esc(SOURCE_HELP[p.videoSource] || "")}</div>
        ${billing}${localUpload}${motion}
      </div>
      <div class="card">
        <div class="card-title">${icon("video", 16)}${esc(t("video.settings"))}</div>
        ${field(esc(t("video.aspect")), `<div class="aspect-picker">
          <button class="aspect-opt${p.aspect === "portrait" ? " active" : ""}" data-action="aspect" data-value="portrait"><span class="aspect-frame portrait"></span><span class="aspect-name">${esc(t("video.portrait"))}</span></button>
          <button class="aspect-opt${p.aspect === "landscape" ? " active" : ""}" data-action="aspect" data-value="landscape"><span class="aspect-frame landscape"></span><span class="aspect-name">${esc(t("video.landscape"))}</span></button>
        </div>`)}
        <div class="grid grid-2" style="gap:12px">
          ${field(esc(t("video.concat")), selectBind("params.concatMode", [{ v: "sequential", l: t("video.sequential") }, { v: "random", l: t("video.random") }], false, p.matchOrder ? " disabled" : ""))}
          ${field(esc(t("video.transition")), selectBind("params.transition", transOpts))}
          ${field(esc(t("video.fit")), selectBind("params.fitMode", [{ v: "cover", l: t("video.fitCover") }, { v: "contain", l: t("video.fitContain") }]))}
          ${field(esc(t("video.count")), `<input class="input" type="number" min="1" max="5" step="1" data-bind="params.videoCount" value="${p.videoCount}">`)}
        </div>
        <div class="field">${toggleBind("params.matchOrder", esc(t("video.matchOrder")), true)}</div>
        ${field(esc(t("video.clipDuration")), rangeBind("params.clipDuration", 1, 10, 1, "s"))}
        ${field(esc(t("video.clipSpeed")), rangeBind("params.clipSpeed", 0.5, 2, 0.1, "x"))}
        ${expander("expVideoAdv", esc(t("video.advanced")), advanced, false)}
      </div>
    </div>`;
}

/* ---------------- page: subtitle ---------------- */
function pageSubtitle() {
  const p = state.params;
  const posOpts = [["top", "subtitle.posTop"], ["center", "subtitle.posCenter"], ["bottom", "subtitle.posBottom"], ["two_thirds_bottom", "subtitle.posTwoThirds"], ["custom", "subtitle.posCustom"]]
    .map(([v, lk]) => ({ v, l: t(lk) }));
  const customPos = p.position === "custom" ? field(esc(t("subtitle.customPos")), rangeBind("params.customPosition", 0, 100, 1, "int")) : "";
  return pageHead("subtitle") + `
    <div class="grid grid-2-1">
      <div class="card">
        <div class="card-title">${icon("subtitle", 16)}${esc(t("subtitle.settings"))}
          <span class="hint"><button class="btn btn-ghost btn-sm" data-action="subtitleReset">${icon("restore", 14)}${esc(t("subtitle.reset"))}</button></span>
        </div>
        <div class="field">${toggleBind("params.subtitleEnabled", esc(t("subtitle.enable")))}</div>
        <div class="grid grid-2" style="gap:12px">
          ${field(esc(t("subtitle.font")), selectBind("params.font", FONTS.map((f) => ({ v: f.id, l: f.name }))))}
          ${field(esc(t("subtitle.position")), selectBind("params.position", posOpts, true))}
          ${field(esc(t("subtitle.display")), selectBind("params.displayMode", [{ v: "sentence", l: t("subtitle.sentence") }, { v: "word_by_word", l: t("subtitle.word") }]))}
          ${field(esc(t("subtitle.animation")), selectBind("params.animation", [{ v: "none", l: t("subtitle.animNone") }, { v: "pop_spring", l: t("subtitle.animPop") }, { v: "fade_in", l: t("subtitle.animFade") }]))}
        </div>
        ${customPos}
        ${field(esc(t("subtitle.fontSize")), rangeBind("params.fontSize", 20, 120, 1, "int"))}
        <div class="grid grid-2" style="gap:12px">
          ${field(esc(t("subtitle.fontColor")), colorBind("params.fontColor"))}
          ${field(esc(t("subtitle.strokeColor")), colorBind("params.strokeColor"))}
        </div>
        ${field(esc(t("subtitle.strokeWidth")), rangeBind("params.strokeWidth", 0, 8, 0.5, "int"))}
        <div class="field">${toggleBind("params.subtitleBgEnabled", esc(t("subtitle.bgEnable")))}</div>
        <div class="grid grid-2" style="gap:12px">
          ${field(esc(t("subtitle.bgColor")), colorBind("params.subtitleBgColor"))}
          <div class="field" style="display:flex;align-items:flex-end;padding-bottom:4px">${toggleBind("params.roundedBg", esc(t("subtitle.rounded")))}</div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">${icon("eye", 16)}${esc(t("subtitle.preview"))}</div>
        <div class="preview-stage">
          <div>
            <div class="phone">
              <div class="phone-scene"></div>
              <div class="phone-sub pos-bottom" id="phoneSub"></div>
            </div>
            <div class="phone-caption">1080 × 1920 · 9:16</div>
          </div>
        </div>
        ${field(esc(t("subtitle.previewText")), `<input class="input" data-bind="previewText" value="${esc(state.previewText)}" placeholder="${esc(t("subtitle.sample"))}">`)}
      </div>
    </div>`;
}
function updateSubtitlePreview(replayAnim) {
  const el = $("#phoneSub");
  if (!el) return;
  const p = state.params;
  let text = state.previewText || p.subject || t("subtitle.sample");
  if (p.displayMode === "word_by_word") {
    const words = text.split(/\s+/);
    text = words.length > 1 ? words[0] : text.slice(0, 2);
  }
  const scale = 0.2;
  const posClass = { top: "pos-top", center: "pos-center", bottom: "pos-bottom", two_thirds_bottom: "pos-two-thirds", custom: "pos-custom" }[p.position] || "pos-bottom";
  el.className = "phone-sub " + posClass;
  el.style.setProperty("--custom-pos", p.customPosition + "%");
  el.style.fontSize = Math.max(8, p.fontSize * scale) + "px";
  el.style.color = p.fontColor;
  el.style.webkitTextStroke = p.strokeWidth > 0 ? (p.strokeWidth * scale).toFixed(1) + "px " + p.strokeColor : "0";
  el.style.opacity = p.subtitleEnabled ? "1" : "0.18";
  const bg = p.subtitleBgEnabled ? hexToRgba(p.subtitleBgColor, 0.55) : "transparent";
  const radius = p.roundedBg ? "6px" : "2px";
  el.innerHTML = `<span class="sub-bg" style="background:${bg};border-radius:${radius}">${esc(text)}</span>`;
  if (replayAnim && p.animation !== "none" && p.subtitleEnabled) {
    el.classList.remove("anim-pop", "anim-fade");
    void el.offsetWidth;
    el.classList.add(p.animation === "pop_spring" ? "anim-pop" : "anim-fade");
  }
}

/* ---------------- page: publish history ---------------- */
function renderHistoryTable() {
  const body = $("#historyTableBody");
  if (!body) return;
  const rows = state.history.filter((x) =>
    (state.historyPlatform === "all" || x.platform === state.historyPlatform) &&
    (state.historyResult === "all" || x.result === state.historyResult)
  );
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty">${icon("history", 40)}<p>${esc(t("tasks.empty"))}</p></div></td></tr>`;
    return;
  }
  body.innerHTML = rows.map((x) => `
    <tr>
      <td><div class="subj">${esc(x.subject)}</div></td>
      <td class="mono">${fmtDateTime(x.time)}</td>
      <td><span class="badge gray">${esc(x.platform)}</span></td>
      <td>${x.result === "success" ? `<span class="badge green"><span class="b-dot"></span>${esc(t("history.success"))}</span>` : `<span class="badge red"><span class="b-dot"></span>${esc(t("history.failed"))}</span>`}</td>
      <td class="mono">${esc(x.duration)}</td>
      <td><div class="row-actions"><button class="btn btn-sm" data-action="republish" data-id="${x.id}">${icon("send", 13)}${esc(t("history.republish"))}</button></div></td>
    </tr>`).join("");
}
function pageHistory() {
  const platforms = ["抖音", "视频号", "小红书", "B站", "YouTube"];
  return pageHead("history") + `
    <div class="toolbar">
      ${selectBind("historyPlatform", [{ v: "all", l: t("history.allPlatforms") }].concat(platforms.map((p) => ({ v: p, l: p }))))}
      ${selectBind("historyResult", [{ v: "all", l: t("history.allResults") }, { v: "success", l: t("history.success") }, { v: "failed", l: t("history.failed") }])}
    </div>
    <div class="table-wrap"><table class="table">
      <thead><tr><th>${esc(t("history.video"))}</th><th>${esc(t("history.time"))}</th><th>${esc(t("history.platform"))}</th><th>${esc(t("history.result"))}</th><th>${esc(t("history.duration"))}</th><th style="text-align:right">${esc(t("tasks.col.actions"))}</th></tr></thead>
      <tbody id="historyTableBody"></tbody>
    </table></div>`;
}/* ---------------- page: LLM providers ---------------- */
function ensureLlmDefaults() {
  const p = state.params;
  if (!p.providerModels) p.providerModels = {};
  if (!p.providerBaseUrls) p.providerBaseUrls = {};
  LLM_PROVIDERS.forEach((pr) => {
    if (!p.providerModels[pr.id]) p.providerModels[pr.id] = pr.id === p.llmProvider && pr.models.includes(p.llmModel) ? p.llmModel : pr.models[0];
    if (p.providerBaseUrls[pr.id] == null) p.providerBaseUrls[pr.id] = "";
  });
}
function keyInput(id, path, value) {
  return `<div class="input-group">
    <input class="input" type="password" id="${id}" data-bind="${path}" value="${esc(value || "")}" placeholder="${esc(t("llm.keyPh"))}" autocomplete="off">
    <button class="btn btn-icon" data-action="eye" data-target="${id}" data-allow-locked aria-label="show/hide">${icon("eye", 14)}</button>
  </div>`;
}
function pageLlm() {
  ensureLlmDefaults();
  const p = state.params;
  const cards = LLM_PROVIDERS.map((pr) => {
    const key = p.providerKeys[pr.id] || "";
    const current = p.llmProvider === pr.id;
    const test = state.llmTest[pr.id];
    const testHtml = test === "testing" ? `<span class="test-result">${esc(t("llm.testing"))}</span>`
      : test === "ok" ? `<span class="test-result ok">${icon("check", 13)}${esc(t("llm.testOk"))}</span>`
      : test === "bad" ? `<span class="test-result bad">${icon("x", 13)}${esc(t("llm.testBad"))}</span>` : "";
    return `<div class="provider-card"${current ? ' style="border-color:var(--border-hue)"' : ""}>
      <div class="provider-head">
        <span class="provider-logo" style="background:${pr.color}">${esc(pr.name[0])}</span>
        <span class="provider-name">${esc(pr.name)}</span>
        ${current ? `<span class="badge green">${esc(t("llm.current"))}</span>` : key ? `<span class="badge gray">${esc(t("llm.configured"))}</span>` : `<span class="badge gray">${esc(t("llm.notConfigured"))}</span>`}
      </div>
      ${field("API Key", keyInput("key_llm_" + pr.id, "params.providerKeys." + pr.id, key))}
      ${field("Base URL", `<input class="input" data-bind="params.providerBaseUrls.${pr.id}" value="${esc(p.providerBaseUrls[pr.id])}" placeholder="${esc(pr.baseUrl)}">`)}
      ${field(esc(t("llm.model")), selectBind("params.providerModels." + pr.id, pr.models.map((m) => ({ v: m, l: m }))))}
      <div class="field-row" style="margin-top:10px">
        <button class="btn btn-sm" data-action="llmTest" data-provider="${pr.id}" ${test === "testing" ? "disabled" : ""}>${test === "testing" ? '<span class="spinner"></span>' : icon("refresh", 13)}${esc(t("llm.test"))}</button>
        <button class="btn btn-primary btn-sm" data-action="llmSaveUse" data-provider="${pr.id}" ${current ? "disabled" : ""}>${esc(t("llm.saveUse"))}</button>
      </div>${testHtml}
    </div>`;
  }).join("");
  return pageHead("llm") + `<div class="grid grid-auto">${cards}</div>`;
}

/* ---------------- page: material sources ---------------- */
function pageMaterial() {
  const p = state.params;
  const groupColor = { stock: "var(--blue)", aiVideo: "var(--magenta)", aiImage: "var(--cyan)" };
  const sections = ["stock", "aiVideo", "aiImage"].map((g) => {
    const cards = MATERIAL_PROVIDERS.filter((x) => x.group === g).map((pr) => {
      const key = p.providerKeys[pr.id] || "";
      const using = p.videoSource === pr.id;
      const noKey = pr.id === "codex_image";
      return `<div class="provider-card"${using ? ' style="border-color:var(--border-hue)"' : ""}>
        <div class="provider-head">
          <span class="provider-logo" style="background:${groupColor[g]}">${esc(pr.name[0])}</span>
          <span class="provider-name">${esc(pr.name)}</span>
          ${using ? `<span class="badge green">${esc(t("llm.current"))}</span>` : noKey || key ? `<span class="badge gray">${esc(t("llm.configured"))}</span>` : `<span class="badge gray">${esc(t("llm.notConfigured"))}</span>`}
        </div>
        <div class="field-help" style="margin-bottom:9px">${esc(SOURCE_HELP[pr.id] || "")}</div>
        ${noKey ? "" : field("API Key", keyInput("key_mat_" + pr.id, "params.providerKeys." + pr.id, key))}
        <div class="field-row" style="margin-top:10px">
          ${noKey ? "" : `<button class="btn btn-sm" data-action="materialSave">${icon("key", 13)}${esc(t("common.save"))}</button>`}
          <button class="btn btn-primary btn-sm" data-action="materialUse" data-source="${pr.id}" ${using ? "disabled" : ""}>${esc(t("material.useSource"))}</button>
        </div>
      </div>`;
    }).join("");
    return `<div class="section-label">${esc(t("video." + g))}</div><div class="grid grid-auto" style="margin-bottom:18px">${cards}</div>`;
  }).join("");
  const localUsing = p.videoSource === "local";
  const localCard = `<div class="section-label">${esc(t("video.local"))}</div>
    <div class="provider-card"${localUsing ? ' style="border-color:var(--border-hue)"' : ""}>
      <div class="provider-head">
        <span class="provider-logo" style="background:var(--amber)">L</span>
        <span class="provider-name">Local</span>
        ${localUsing ? `<span class="badge green">${esc(t("llm.current"))}</span>` : `<span class="badge gray">${esc(tf("video.uploadedFiles", { n: p.uploadedMaterials.length }))}</span>`}
      </div>
      <div class="field-help" style="margin-bottom:9px">${esc(SOURCE_HELP.local)}</div>
      <div class="field-row">
        <button class="btn btn-sm" data-action="nav" data-page="video">${icon("upload", 13)}${esc(t("video.upload"))}</button>
        <button class="btn btn-primary btn-sm" data-action="materialUse" data-source="local" ${localUsing ? "disabled" : ""}>${esc(t("material.useSource"))}</button>
      </div>
    </div>`;
  return pageHead("material") + sections + localCard;
}

/* ---------------- page: publish channels ---------------- */
const channelBusy = {};
function pageChannels() {
  const c = state.channels;
  const cards = PLATFORMS.map((pr) => {
    const logged = c[pr.id];
    const busy = channelBusy[pr.id];
    return `<div class="provider-card">
      <div class="provider-head">
        <span class="provider-logo" style="background:${pr.color};color:#fff">${esc(pr.name[0])}</span>
        <span class="provider-name">${esc(pr.name)}</span>
        ${logged ? `<span class="badge green"><span class="b-dot"></span>${esc(t("channels.loggedIn"))}</span>` : `<span class="badge gray">${esc(t("channels.notLoggedIn"))}</span>`}
      </div>
      <button class="btn btn-sm ${logged ? "btn-danger" : "btn-primary"}" style="width:100%" data-action="${logged ? "channelLogout" : "channelLogin"}" data-platform="${pr.id}" ${busy ? "disabled" : ""}>
        ${busy ? '<span class="spinner"></span>' + esc(t("channels.loggingIn")) : esc(logged ? t("channels.logout") : t("channels.login"))}
      </button>
    </div>`;
  }).join("");
  const overseas = `<div class="provider-card">
    <div class="provider-head">
      <span class="provider-logo" style="background:var(--blue);color:#fff">${icon("globe", 16)}</span>
      <span class="provider-name">${esc(t("channels.uploadPost"))}</span>
      ${c.uploadPostEnabled ? `<span class="badge green">${esc(t("llm.configured"))}</span>` : `<span class="badge gray">${esc(t("llm.notConfigured"))}</span>`}
    </div>
    <div class="field">${toggleBind("channels.uploadPostEnabled", esc(t("channels.enable")), true)}</div>
    ${c.uploadPostEnabled ? `
      ${field("API Key", keyInput("key_uploadpost", "channels.uploadPostKey", c.uploadPostKey))}
      <div class="field">${toggleBind("channels.uploadPostAuto", esc(t("channels.autoPublish")))}</div>` : ""}
  </div>`;
  return pageHead("channels") + `
    <div class="section-label">${esc(t("channels.domestic"))}</div>
    <div class="grid grid-auto" style="margin-bottom:18px">${cards}</div>
    <div class="section-label">${esc(t("channels.overseas"))}</div>
    <div class="grid grid-auto">${overseas}</div>`;
}

/* ---------------- page: settings ---------------- */
function pageSettings() {
  const s = state.settings;
  const pageOpts = NAV_ORDER.map((id) => ({ v: id, l: t("nav." + id) }));
  const cs = state.cacheStats;
  return pageHead("settings") + `
    <div class="grid grid-2">
      <div class="card">
        <div class="card-title">${icon("settings", 16)}${esc(t("settings.general"))}</div>
        <div class="field">${toggleBind("settings.openFolderOnCompletion", esc(t("settings.openFolder")))}</div>
        <div class="field">${toggleBind("settings.hideLog", esc(t("settings.hideLog")))}</div>
      </div>
      <div class="card">
        <div class="card-title">${icon("sun", 16)}${esc(t("settings.interface"))}</div>
        ${field(esc(t("settings.theme")), selectBind("theme", [{ v: "dark", l: t("settings.themeDark") }, { v: "light", l: t("settings.themeLight") }]))}
        ${field(esc(t("settings.language")), selectBind("lang", [{ v: "zh", l: "简体中文" }, { v: "en", l: "English" }]))}
        ${field(esc(t("settings.defaultPage")), selectBind("settings.defaultPage", pageOpts))}
      </div>
      <div class="card">
        <div class="card-title">${icon("key", 16)}${esc(t("settings.keys"))}</div>
        <div class="field-row">
          <button class="btn" data-action="keysExport">${icon("download", 15)}${esc(t("settings.keysExport"))}</button>
          <button class="btn" data-action="keysImport">${icon("upload", 15)}${esc(t("settings.keysImport"))}</button>
        </div>
      </div>
      <div class="card">
        <div class="card-title">${icon("broom", 16)}${esc(t("settings.cache"))}</div>
        <div class="stat-grid" style="margin-bottom:12px">
          <div class="stat"><div class="stat-val">${cs.files}</div><div class="stat-label">${esc(t("settings.cacheFiles"))}</div></div>
          <div class="stat"><div class="stat-val">${(cs.sizeMB / 1024).toFixed(1)}G</div><div class="stat-label">${esc(t("settings.cacheSize"))}</div></div>
          <div class="stat"><div class="stat-val">${cs.oldestDays}d</div><div class="stat-label">${esc(t("settings.cacheOldest"))}</div></div>
        </div>
        <div class="field-row">
          <button class="btn" data-action="cacheRefresh">${icon("refresh", 15)}${esc(t("settings.cacheRefresh"))}</button>
          <button class="btn btn-danger" data-action="cacheClean">${icon("broom", 15)}${esc(t("settings.cacheClean"))}</button>
        </div>
      </div>
    </div>`;
}

/* ---------------- page: parameter presets ---------------- */
function pagePresets() {
  const cards = state.presets.map((pr) => {
    const p = pr.params || {};
    const chips = [
      p.aspect ? `<span class="chip">${p.aspect === "portrait" ? "9:16" : "16:9"}</span>` : "",
      p.videoSource ? `<span class="chip">${esc(sourceLabel(p.videoSource))}</span>` : "",
      p.voiceName ? `<span class="chip">${esc(p.voiceName)}</span>` : "",
      p.videoCount ? `<span class="chip">×${p.videoCount}</span>` : "",
      p.fontSize ? `<span class="chip">${esc(t("subtitle.fontSize"))} ${p.fontSize}</span>` : "",
    ].filter(Boolean).join("");
    return `<div class="provider-card preset-card">
      <div class="provider-head">
        <span class="provider-logo" style="background:var(--grad-primary)">${icon("presets", 15)}</span>
        <span class="provider-name">${esc(pr.name)}</span>
        ${pr.builtin ? `<span class="badge gray">${esc(t("presets.builtin"))}</span>` : ""}
      </div>
      <div class="field-help" style="margin-bottom:9px">${esc(pr.desc || "")}</div>
      <div class="kw-chips" style="margin:0 0 10px">${chips}</div>
      <div class="field-row" style="margin-top:10px">
        <button class="btn btn-primary btn-sm" data-action="presetApply" data-id="${pr.id}">${icon("check", 13)}${esc(t("presets.apply"))}</button>
        <button class="btn btn-sm" data-action="presetExportOne" data-id="${pr.id}" title="${esc(t("presets.export"))}">${icon("download", 13)}${esc(t("presets.export"))}</button>
        ${pr.builtin ? "" : `<button class="btn btn-sm btn-danger" data-action="presetDelete" data-id="${pr.id}" title="${esc(t("presets.delete"))}" aria-label="${esc(t("presets.delete"))}">${icon("trash", 13)}</button>`}
      </div>
    </div>`;
  }).join("");
  return pageHead("presets") + `
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">${icon("presets", 16)}${esc(t("presets.saveAs"))}</div>
      <div class="field-row">
        <input class="input" id="presetNameInput" data-bind="presetName" value="${esc(state.presetName)}" placeholder="${esc(t("presets.namePh"))}" style="flex:2">
        <button class="btn btn-primary" data-action="presetSaveAs">${icon("plus", 14)}${esc(t("common.save"))}</button>
        <button class="btn" data-action="presetLibImport">${icon("upload", 14)}${esc(t("presets.import"))}</button>
        <button class="btn" data-action="presetLibExport">${icon("download", 14)}${esc(t("presets.exportAll"))}</button>
      </div>
      <div class="field-help" style="margin-top:8px">${esc(t("presets.stripHint"))}</div>
    </div>
    <div class="grid grid-auto">${cards}</div>`;
}

/* ============================================================
   page: creator wizard — five steps, beginner-first
   ============================================================ */
function engineStrip() {
  const items = [["comfy", "engines.comfy"], ["acestep", "engines.acestep"], ["ollama", "engines.ollama"]];
  const anyOff = Object.values(state.engines).some((v) => !v);
  return `<div class="engine-strip" role="group" aria-label="${esc(t("engines.title"))}">
    <span class="es-title">${icon("llm", 14)}${esc(t("engines.title"))}</span>
    ${items.map(([k, lk]) => `<button class="engine-dot${state.engines[k] ? " on" : ""}" data-action="engineToggle" data-engine="${k}" data-allow-locked
      title="${esc(t("engines.toggleHint"))}" aria-label="${esc(t(lk))}: ${esc(t(state.engines[k] ? "engines.online" : "engines.offline"))}">
      <span class="ed-light"></span><span class="ed-name">${esc(t(lk))}</span><span class="ed-state">${esc(t(state.engines[k] ? "engines.online" : "engines.offline"))}</span></button>`).join("")}
    <button class="btn btn-sm" data-action="engineAllLocal" data-allow-locked>${icon("spark", 13)}${esc(t("engines.allLocal"))}</button>
    ${anyOff ? `<span class="es-degrade">${icon("alert", 13)}${esc(t("engines.degrade"))}</span>` : `<span class="es-queue">${esc(t("engines.queueHint"))}</span>`}
  </div>`;
}
function stepper(path, min, max, delta) {
  const v = getPath(state, path);
  return `<div class="stepper">
    <button class="btn btn-sm" data-action="wizStepVal" data-path="${path}" data-delta="${-delta}" data-min="${min}" data-max="${max}" ${v <= min ? "disabled" : ""} aria-label="−">−</button>
    <span class="stepper-val mono" data-out="${path}">${v}</span>
    <button class="btn btn-sm" data-action="wizStepVal" data-path="${path}" data-delta="${delta}" data-min="${min}" data-max="${max}" ${v >= max ? "disabled" : ""} aria-label="+">+</button>
  </div>`;
}
function wizStepsBar() {
  const w = state.wizard;
  return `<div class="wizard-steps" role="list">${[1, 2, 3, 4, 5].map((i) =>
    `<button class="wstep${w.step === i ? " active" : ""}${w.step > i ? " done" : ""}" data-action="wizGo" data-step="${i}" ${i > w.step ? "disabled" : ""} role="listitem" aria-current="${w.step === i ? "step" : "false"}">
      <span class="ws-num">${w.step > i ? icon("check", 12) : i}</span><span class="ws-label">${esc(t("wizard.step" + i))}</span></button>`
  ).join('<span class="ws-bar"></span>')}</div>`;
}
function wizStep1() {
  const w = state.wizard;
  const cards = GENRES.map((g) => `
    <button class="genre-card${w.genre === g.id ? " active" : ""}" data-action="wizGenre" data-genre="${g.id}" aria-pressed="${w.genre === g.id}">
      <span class="gc-thumb">${kfSvg("genre-" + g.id, t("wizard.tpl." + g.id))}</span>
      <span class="gc-name">${esc(t("wizard.tpl." + g.id))}</span>
      <span class="gc-desc">${esc(t("wizard.tpl." + g.id + "Desc"))}</span>
      <span class="gc-chips"><span class="chip">${esc(g.style.tone)}</span><span class="chip">${esc(g.voice.replace("zh-CN-", "").replace("Neural", ""))}</span><span class="chip">9:16</span></span>
    </button>`).join("");
  return `
    ${engineStrip()}
    <div class="card">
      <div class="card-title">${icon("wand", 16)}${esc(t("wizard.idea"))}</div>
      <textarea class="textarea" rows="3" data-bind="wizard.idea" placeholder="${esc(t("wizard.ideaPh"))}">${esc(w.idea)}</textarea>
      <div class="field-row" style="margin-top:12px">
        ${field(esc(t("wizard.duration")), stepper("wizard.duration", 30, 180, 15))}
        ${field(esc(t("wizard.episodes")), stepper("wizard.episodes", 1, 12, 1))}
      </div>
    </div>
    <div class="section-label">${esc(t("wizard.genre"))}</div>
    <div class="genre-grid">${cards}</div>`;
}
function wizCharCard(c, i) {
  const voices = VOICES.edge.map((v) => ({ v, l: v }));
  return `<div class="char-card">
    <div class="cc-portrait">${portraitSvg(c.seed + "-" + c.name, c.name)}
      <button class="btn btn-sm cc-regen" data-action="wizCharRegen" data-idx="${i}" title="${esc(t("wizard.charRegen"))}">${icon("refresh", 13)}${esc(t("wizard.charRegen"))}</button>
    </div>
    <div class="cc-body">
      <div class="field-row">
        <input class="input" data-bind="wizard.chars.${i}.name" value="${esc(c.name)}" placeholder="${esc(t("wizard.charName"))}" aria-label="${esc(t("wizard.charName"))}">
        <button class="icon-btn danger" data-action="wizCharDelete" data-idx="${i}" title="${esc(t("wizard.charDelete"))}" aria-label="${esc(t("wizard.charDelete"))}">${icon("trash", 14)}</button>
      </div>
      <input class="input" data-bind="wizard.chars.${i}.persona" value="${esc(c.persona)}" placeholder="${esc(t("wizard.charPersona"))}" aria-label="${esc(t("wizard.charPersona"))}">
      <textarea class="textarea" rows="2" data-bind="wizard.chars.${i}.appearance" placeholder="${esc(t("wizard.charAppearance"))}" aria-label="${esc(t("wizard.charAppearance"))}">${esc(c.appearance)}</textarea>
      <div class="field-row">
        <select class="select" data-bind="wizard.chars.${i}.voice" aria-label="${esc(t("wizard.charVoice"))}">${opts(voices, c.voice)}</select>
        <span class="chip mono">${esc(t("series.charSeed"))} ${c.seed}</span>
      </div>
    </div>
  </div>`;
}
function wizStep2() {
  const w = state.wizard;
  const body = w.charsBusy
    ? `<div class="wiz-busy"><span class="spinner"></span>${esc(t("wizard.charsBusy"))}</div>`
    : w.chars.length
      ? `<div class="char-grid">${w.chars.map((c, i) => wizCharCard(c, i)).join("")}</div>`
      : `<div class="empty">${icon("user", 40)}<p>${esc(t("wizard.charsHint"))}</p></div>`;
  return `
    <div class="card">
      <div class="card-title">${icon("user", 16)}${esc(t("wizard.charsTitle"))}
        <button class="btn btn-primary btn-sm hint" data-action="wizCharsExtract" ${w.charsBusy ? "disabled" : ""}>${w.charsBusy ? '<span class="spinner"></span>' : icon("spark", 13)}${esc(t("wizard.charsExtract"))}</button>
      </div>
      <div class="alert info">${icon("info", 15)}<span>${esc(t("wizard.charsHint"))}</span></div>
      ${body}
      <div class="field-row" style="margin-top:12px">
        <button class="btn" data-action="wizCharAdd">${icon("plus", 14)}${esc(t("wizard.charAdd"))}</button>
      </div>
    </div>`;
}
function wizStep3() {
  const w = state.wizard;
  const rows = w.outline.map((ep, i) => `
    <div class="outline-row" draggable="true" data-drag-ep="${i}">
      <span class="or-grip" aria-hidden="true">${icon("grip", 15)}</span>
      <span class="or-seq mono">${esc(tf("series.ep", { n: i + 1 }))}</span>
      <div class="or-fields">
        <input class="input" data-bind="wizard.outline.${i}.logline" value="${esc(ep.logline)}" placeholder="${esc(t("wizard.epLogline"))}" aria-label="${esc(t("wizard.epLogline"))}">
        <input class="input" data-bind="wizard.outline.${i}.hook" value="${esc(ep.hook)}" placeholder="${esc(t("wizard.epHook"))}" aria-label="${esc(t("wizard.epHook"))}">
      </div>
      <button class="icon-btn danger" data-action="wizEpDelete" data-idx="${i}" title="${esc(t("wizard.epDelete"))}" aria-label="${esc(t("wizard.epDelete"))}">${icon("trash", 14)}</button>
    </div>`).join("");
  return `
    <div class="card">
      <div class="card-title">${icon("series", 16)}${esc(t("wizard.outlineTitle"))}</div>
      <div class="field-help" style="margin-bottom:10px">${esc(t("wizard.outlineHint"))}</div>
      <div class="outline-list">${rows}</div>
      <div class="field-row" style="margin-top:12px">
        <button class="btn" data-action="wizEpAdd">${icon("plus", 14)}${esc(t("wizard.epAdd"))}</button>
      </div>
    </div>`;
}
function wizStep4() {
  const w = state.wizard;
  if (w.boardBusy) return `<div class="card"><div class="wiz-busy"><span class="spinner"></span>${esc(t("wizard.boardBusy"))}</div></div>`;
  if (!w.planReady || !state.plan) {
    return `<div class="card"><div class="empty">${icon("board", 40)}<p>${esc(t("wizard.boardHint"))}</p>
      <button class="btn btn-primary" data-action="wizBoardGen">${icon("spark", 15)}${esc(t("wizard.boardGen"))}</button></div></div>`;
  }
  const rows = planScenes().map((sc) => {
    const seed = kfSeed(sc, "first") || sc.visual;
    const adv = `<div class="field-row">
      ${engineSelect(sc)}
      ${costBadge(sc)}
    </div>`;
    return `<tr>
      <td><div class="cb-visual"><span class="cb-thumb">${kfSvg(seed, sc.visual)}</span><span>${esc(sc.visual)}</span></div></td>
      <td class="cb-line">${esc(sc.narration)}</td>
      <td class="mono">${sc.est_duration}s</td>
      <td><span class="conn-chip">${esc(t("plan.rel." + sc.relation_to_prev))}</span><span class="health-dot ${sc.boundary_health}" title="${esc(t("plan.bh." + sc.boundary_health))}"></span>
        ${expander("expWizAdv" + sc.id, esc(t("wizard.advanced")), adv, false)}</td>
    </tr>`;
  }).join("");
  return `
    <div class="card">
      <div class="card-title">${icon("board", 16)}${esc(t("wizard.boardTitle"))}
        <button class="btn btn-sm hint" data-action="wizardOpenPlan" data-allow-locked>${esc(t("wizard.openPro"))} →</button>
      </div>
      <div class="field-help" style="margin-bottom:10px">${esc(t("wizard.boardHint"))}</div>
      <div class="table-wrap"><table class="table compact-board">
        <thead><tr><th>${esc(t("wizard.colVisual"))}</th><th>${esc(t("wizard.colLine"))}</th><th>${esc(t("wizard.colDur"))}</th><th>${esc(t("wizard.colLink"))}</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </div>`;
}
function costSummaryHtml() {
  const scenes = planScenes();
  const local = scenes.filter((s) => sceneCost(s) === 0).length;
  const paid = scenes.reduce((a, s) => a + sceneCost(s), 0);
  return `<div class="cost-summary">
    <div class="cs-row"><span class="cs-label">${icon("check", 14)}${esc(t("wizard.costLocal"))}</span><span class="badge green">${local} · ${esc(t("plan.cost.free"))}</span></div>
    <div class="cs-row"><span class="cs-label">${icon("alert", 14)}${esc(t("wizard.costCloud"))}</span>${paid > 0 ? `<span class="badge amber">${esc(tf("plan.cost.paid", { n: paid.toFixed(1) }))}</span>` : `<span class="badge green">${esc(t("wizard.costFree"))}</span>`}</div>
  </div>`;
}
function wizStep5() {
  const w = state.wizard;
  const tiers = [["draft", "wizard.tierDraft", "wizard.tierDraftDesc"], ["final", "wizard.tierFinal", "wizard.tierFinalDesc"]];
  return `
    ${engineStrip()}
    <div class="grid grid-2">
      <div class="card">
        <div class="card-title">${icon("flask", 16)}${esc(t("wizard.tier"))}</div>
        <div class="tier-grid">${tiers.map(([v, lk, dk]) => `
          <button class="tier-card${w.tier === v ? " active" : ""}" data-action="wizTier" data-tier="${v}" aria-pressed="${w.tier === v}">
            <span class="tc-name">${esc(t(lk))}</span><span class="tc-desc">${esc(t(dk))}</span>
          </button>`).join("")}</div>
      </div>
      <div class="card">
        <div class="card-title">${icon("presets", 16)}${esc(t("wizard.costTitle"))}</div>
        ${costSummaryHtml()}
        <div class="field-help" style="margin-top:8px">${esc(t("engines.queueHint"))}</div>
      </div>
    </div>
    <button class="btn btn-primary wiz-start" data-action="wizStart" ${state.run.status === "running" ? "disabled" : ""}>
      ${iconFill("play", 16)}${esc(t("wizard.start"))}
    </button>`;
}
function pageWizard() {
  const w = state.wizard;
  const bodies = { 1: wizStep1, 2: wizStep2, 3: wizStep3, 4: wizStep4, 5: wizStep5 };
  return pageHead("wizard") + wizStepsBar() + bodies[w.step]() + `
    <div class="wiz-nav">
      ${w.step > 1 ? `<button class="btn" data-action="wizBack">${icon("chevLeft", 14)}${esc(t("wizard.back"))}</button>` : "<span></span>"}
      ${w.step < 5 ? `<button class="btn btn-primary" data-action="wizNext">${esc(t("wizard.next"))}${icon("chevRight", 14)}</button>` : "<span></span>"}
    </div>`;
}

/* ============================================================
   page: script plan — storyboard pro mode
   ============================================================ */
function engineSelect(sc) {
  const i = planScenes().indexOf(sc);
  const list = ["local_fl2v", "local_i2v", "stock", "cloud_ai"].map((v) => {
    const off = !engineOnline(v);
    return `<option value="${v}"${v === sc.engine ? " selected" : ""}${off ? " disabled" : ""}>${esc(t("plan.engine." + v))}${off ? " · " + esc(t("engines.offline")) : ""}</option>`;
  }).join("");
  return `<select class="select engine-select" data-bind="plan.scenes.${i}.engine" data-rerender="1" aria-label="${esc(t("plan.engine"))}">${list}</select>`;
}
function costBadge(sc) {
  const c = sceneCost(sc);
  return c > 0
    ? `<span class="cost-badge paid">${esc(tf("plan.cost.paid", { n: c.toFixed(1) }))}</span>`
    : `<span class="cost-badge free">${esc(t("plan.cost.free"))}</span>`;
}
function planMeterHtml() {
  const pl = state.plan;
  const total = planTotal(), target = pl.target_duration;
  const hasMeasured = pl.scenes.some((s) => s.measured_duration);
  const over = Math.abs(total - target) > target * 0.1;
  const pct = Math.min(100, Math.round((total / target) * 100));
  return `<div class="meter${over ? " over" : ""}" id="planMeter">
    <div class="meter-nums">
      <span>${esc(t("plan.meter.target"))} <b class="mono">${target}s</b></span>
      <span>${esc(t("plan.meter.planned"))} <b class="mono" data-meter="planned">${total}s</b></span>
      ${hasMeasured ? `<span>${esc(t("plan.meter.measured"))} <b class="mono">${total}s</b></span>` : ""}
    </div>
    <div class="meter-bar"><div class="meter-fill" data-meter="fill" style="width:${pct}%"></div><span class="meter-tick" title="±10%"></span></div>
    <div class="meter-note" data-meter="note">${esc(t(over ? "plan.meter.over" : "plan.meter.ok"))}</div>
  </div>`;
}
function updatePlanMeter() {
  const el = $("#planMeter");
  if (!el || !state.plan) return;
  const total = planTotal(), target = state.plan.target_duration;
  const over = Math.abs(total - target) > target * 0.1;
  el.classList.toggle("over", over);
  el.querySelector('[data-meter="planned"]').textContent = total + "s";
  el.querySelector('[data-meter="fill"]').style.width = Math.min(100, Math.round((total / target) * 100)) + "%";
  el.querySelector('[data-meter="note"]').textContent = t(over ? "plan.meter.over" : "plan.meter.ok");
  planScenes().forEach((sc) => {
    const blk = document.querySelector(`.tl-block[data-id="${sc.id}"]`);
    if (blk) { blk.style.flexGrow = sc.est_duration; const d = blk.querySelector(".tlb-dur"); if (d) d.textContent = sc.est_duration + "s"; }
    const badge = document.querySelector(`[data-dur-badge="${sc.id}"]`);
    if (badge) badge.textContent = sc.est_duration + "s";
  });
}
function planTimelineHtml() {
  const scenes = planScenes();
  const total = planTotal() || 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<span class="tl-tick" style="left:${f * 100}%">${Math.round(total * f)}s</span>`).join("");
  const blocks = scenes.map((sc) => {
    const sel = state.selectedScene === sc.id ? " selected" : "";
    const cues = Math.max(1, Math.ceil(sc.narration.length / 12));
    return `<button class="tl-block eng-${sc.engine}${sel}" data-action="sceneSelect" data-id="${sc.id}" data-drag-scene="${sc.id}" draggable="true"
      style="flex-grow:${sc.est_duration}" aria-label="${esc(t("plan.scene"))} ${sc.order} · ${sc.est_duration}s">
      <span class="tlb-num">${sc.order}</span><span class="tlb-dur mono">${sc.est_duration}s</span>
      <span class="tl-cues" title="${esc(t("plan.cues"))}">${"<i></i>".repeat(cues)}</span>
    </button>`;
  }).join("");
  const pl = state.plan;
  const fi = Math.min(30, (pl.bgm.fade_in / total) * 100), fo = Math.min(30, (pl.bgm.fade_out / total) * 100);
  return `<div class="card timeline-card">
    <div class="card-title">${icon("video", 16)}${esc(t("plan.timeline"))}<span class="tl-hint">${esc(t("plan.timelineHint"))}</span></div>
    <div class="timeline-wrap">
      <div class="tl-ruler">${ticks}</div>
      <div class="tl-track">${blocks}</div>
      <div class="tl-bgm"><span class="tl-bgm-label">${esc(t("plan.bgmTrack"))} · ${esc(pl.bgm.type === "acestep_local" ? t("plan.bgmLocal") : pl.bgm.mood)}</span>
        <div class="tl-bgm-bar" style="background:linear-gradient(90deg, transparent 0%, var(--magenta) ${fi}%, var(--magenta) ${100 - fo}%, transparent 100%)"></div></div>
    </div>
  </div>`;
}
function connectorHtml(sc) {
  const pv = prevScene(sc);
  if (!pv) return "";
  const rel = sc.relation_to_prev;
  const shared = sc.keyframe.shared_with_prev && sc.engine.startsWith("local") && pv.engine.startsWith("local");
  return `<div class="connector" aria-label="${esc(t("plan.relation"))}: ${esc(t("plan.rel." + rel))}">
    <span class="conn-line"></span>
    <div class="conn-row">
      <span class="conn-chip rel-${rel}">${icon(rel === "match_cut" ? "link" : rel === "contrast" ? "flask" : "chevDown", 12)}${esc(t("plan.rel." + rel))}</span>
      ${sc.relation_note ? `<span class="conn-note">${esc(sc.relation_note)}</span>` : ""}
      ${shared ? `<span class="conn-shared" title="${esc(t("plan.kfShared"))}">${icon("link", 11)}${esc(t("plan.sharedFrame"))}</span>` : ""}
      <span class="health-dot ${sc.boundary_health}" title="${esc(t("plan.boundary"))}: ${esc(t("plan.bh." + sc.boundary_health))}" aria-label="${esc(t("plan.boundary"))}: ${esc(t("plan.bh." + sc.boundary_health))}"></span>
    </div>
    <span class="conn-line"></span>
  </div>`;
}
function materialRowHtml(sc) {
  const i = planScenes().indexOf(sc);
  const cands = sc.material.candidates.map((cd) => `
    <button class="cand-thumb${sc.material.selected === cd.id ? " active" : ""}" data-action="scenePickCand" data-id="${sc.id}" data-cand="${cd.id}" title="${esc(cd.label)}" aria-label="${esc(cd.label)}" aria-pressed="${sc.material.selected === cd.id}">${kfSvg(cd.seed, cd.label)}</button>`).join("");
  return `<div class="mat-row">
    <span class="mat-label">${icon("material", 13)}${esc(t("plan.material"))} · ${esc(sourceLabel(sc.material.source))}</span>
    <span class="mat-cands">${cands}</span>
    <label class="mat-io"><span>${esc(t("plan.in"))}</span><input class="input mono" type="number" min="0" step="0.5" data-bind="plan.scenes.${i}.material.in" value="${sc.material.in}" aria-label="${esc(t("plan.in"))}"></label>
    <label class="mat-io"><span>${esc(t("plan.out"))}</span><input class="input mono" type="number" min="0.5" step="0.5" data-bind="plan.scenes.${i}.material.out" value="${sc.material.out}" aria-label="${esc(t("plan.out"))}"></label>
  </div>`;
}
function sceneCardHtml(sc, i) {
  const sel = state.selectedScene === sc.id ? " selected" : "";
  const first = kfSeed(sc, "first"), last = kfSeed(sc, "last");
  const pv = prevScene(sc);
  const shared = sc.keyframe.shared_with_prev && sc.engine.startsWith("local") && pv && pv.engine.startsWith("local");
  const busy = state.kfBusy[sc.id];
  const thumb = sc.engine === "stock"
    ? kfSvg((sc.material.candidates.find((c) => c.id === sc.material.selected) || {}).seed || sc.visual, sc.visual)
    : first ? kfSvg(first, sc.visual) : `<span class="kf-empty">${icon("material", 22)}</span>`;
  const chars = sc.characters.map((id) => {
    const c = charById(id);
    return c ? `<button class="chip chip-link" data-action="seriesCharOpen" data-id="${id}" data-allow-locked>${icon("user", 11)}${esc(c.name)}</button>` : "";
  }).join("");
  const loc = locById(sc.location);
  const offline = !engineOnline(sc.engine);
  return `${connectorHtml(sc)}
  <div class="scene-card${sel}${sc.locked ? " locked" : ""}" data-scene="${sc.id}" data-drag-scene="${sc.id}" draggable="true">
    <div class="scene-head">
      <span class="sc-grip" aria-hidden="true">${icon("grip", 14)}</span>
      <span class="sc-order mono">${sc.order}</span>
      <span class="sc-dur badge blue mono" data-dur-badge="${sc.id}">${sc.est_duration}s</span>
      ${engineSelect(sc)}${costBadge(sc)}
      <span class="sc-head-spacer"></span>
      <button class="icon-btn sc-lock${sc.locked ? " on" : ""}" data-action="sceneLock" data-id="${sc.id}" aria-pressed="${sc.locked}" title="${esc(t(sc.locked ? "plan.unlock" : "plan.lock"))}" aria-label="${esc(t(sc.locked ? "plan.unlock" : "plan.lock"))}">${icon("lock", 14)}</button>
      <button class="icon-btn" data-action="sceneDetails" data-id="${sc.id}" data-allow-locked title="${esc(t("plan.details"))}" aria-label="${esc(t("plan.details"))}">${icon("eye", 14)}</button>
    </div>
    ${offline ? `<div class="alert warn sc-offline">${icon("alert", 14)}<span style="flex:1">${esc(t("plan.engineOffline"))}</span><button class="btn btn-sm" data-action="sceneDegrade" data-id="${sc.id}">${esc(t("plan.degradeStock"))}</button></div>` : ""}
    <div class="scene-main">
      <button class="sc-thumb" data-action="sceneDetails" data-id="${sc.id}" data-allow-locked aria-label="${esc(t("plan.details"))}">
        ${thumb}
        ${last && sc.engine !== "stock" ? `<span class="kf-corner" title="${esc(t("plan.kfLast"))}">${kfSvg(last, t("plan.kfLast"))}</span>` : ""}
        ${shared ? `<span class="kf-shared" title="${esc(t("plan.kfShared"))}">${icon("link", 11)}</span>` : ""}
        ${busy ? `<span class="kf-progress"><span class="spinner"></span>${esc(busy.label)}</span>` : ""}
      </button>
      <div class="sc-fields">
        <textarea class="textarea sc-narration" rows="2" data-bind="plan.scenes.${i}.narration" ${sc.locked ? "disabled" : ""} aria-label="${esc(t("plan.narration"))}">${esc(sc.narration)}</textarea>
        <div class="field-row">
          <input class="input sc-visual" data-bind="plan.scenes.${i}.visual" value="${esc(sc.visual)}" ${sc.locked ? "disabled" : ""} aria-label="${esc(t("plan.visual"))}">
          <label class="sc-dur-edit"><span>${esc(t("plan.estDur"))}</span><input class="input mono" type="number" min="2" max="60" step="0.5" data-bind="plan.scenes.${i}.est_duration" value="${sc.est_duration}" ${sc.locked ? "disabled" : ""} aria-label="${esc(t("plan.estDur"))}"></label>
        </div>
        <div class="kw-chips">${sc.keywords.map((k) => `<span class="kw-chip">${esc(k)}</span>`).join("")}${chars}${loc ? `<span class="chip">${icon("folder", 11)}${esc(loc.name)}</span>` : ""}</div>
        ${sc.engine === "stock" ? materialRowHtml(sc) : ""}
        <div class="field-row sc-foot">
          <label class="sc-trans"><span>${esc(t("plan.transition"))}</span>${selectBind(`plan.scenes.${i}.transition_to_next`, ["none", "fade", "slide", "zoom", "match_cut"].map((v) => ({ v, l: t("plan.trans." + v) })), true)}</label>
          <div class="row-actions">
            <button class="btn btn-sm" data-action="sceneRegen" data-id="${sc.id}" ${sc.locked ? "disabled" : ""}>${icon("refresh", 13)}${esc(t("plan.regen"))}</button>
            ${sc.engine === "stock"
              ? `<button class="btn btn-sm" data-action="sceneSwap" data-id="${sc.id}">${icon("material", 13)}${esc(t("plan.swap"))}</button>`
              : `<button class="btn btn-sm" data-action="kfGen" data-id="${sc.id}" data-which="pair" ${!state.engines.comfy || busy ? "disabled" : ""}>${icon("spark", 13)}${esc(t("plan.kfGen"))}</button>`}
          </div>
        </div>
      </div>
    </div>
  </div>`;
}
function sceneDrawerHtml(sc) {
  const i = planScenes().indexOf(sc);
  const pv = prevScene(sc);
  const prevLast = pv ? kfSeed(pv, "last") : null;
  const thisFirst = kfSeed(sc, "first");
  const diff = prevLast && thisFirst ? (prevLast === thisFirst ? 0 : (sdHash(prevLast + thisFirst) % 40) + 8) : null;
  const busyF = state.kfBusy[sc.id + ":first"], busyL = state.kfBusy[sc.id + ":last"];
  const shared = sc.keyframe.shared_with_prev && !!pv;
  const gallery = sc.engine === "stock" && sc.material.candidates.length ? `
    <div class="section-label">${esc(t("plan.candidates"))}</div>
    <div class="cand-gallery">${sc.material.candidates.map((cd) => `
      <button class="cand-thumb lg${sc.material.selected === cd.id ? " active" : ""}" data-action="scenePickCand" data-id="${sc.id}" data-cand="${cd.id}" aria-pressed="${sc.material.selected === cd.id}">
        ${kfSvg(cd.seed, cd.label)}<span class="cand-label">${esc(cd.label)}</span></button>`).join("")}</div>` : "";
  return `
    ${sc.cost.request_key ? `<div class="alert info">${icon("info", 14)}<span>${esc(t("plan.kfCache"))} · <span class="mono">${esc(sc.cost.request_key)}</span></span></div>` : ""}
    <div class="section-label">${esc(t("plan.kfPair"))}</div>
    <div class="kf-pair">
      <div class="kf-cell"><span class="kf-cap">${esc(t("plan.prevLast"))}</span>${prevLast ? kfSvg(prevLast, t("plan.prevLast")) : `<span class="kf-empty">—</span>`}</div>
      <div class="kf-diff">
        ${diff !== null ? `<span class="badge ${diff === 0 ? "green" : diff < 25 ? "amber" : "red"}">${esc(t("plan.diffScore"))} ${diff}</span>` : ""}
        ${shared && thisFirst === prevLast ? `<span class="conn-shared">${icon("link", 11)}${esc(t("plan.sharedFrame"))}</span>` : ""}
      </div>
      <div class="kf-cell"><span class="kf-cap">${esc(t("plan.thisFirst"))}</span>${thisFirst ? kfSvg(thisFirst, t("plan.thisFirst")) : `<span class="kf-empty">—</span>`}</div>
    </div>
    ${busyF || busyL ? `<div class="wiz-busy"><span class="spinner"></span>${esc((busyF || busyL).label)}</div>` : ""}
    <div class="field-row" style="margin-top:10px">
      <button class="btn btn-sm" data-action="kfGen" data-id="${sc.id}" data-which="first" ${!state.engines.comfy || busyF || shared ? "disabled" : ""} title="${esc(shared ? t("plan.kfShared") : t("plan.kfFirst"))}">${icon("spark", 13)}${esc(t("plan.kfFirst"))}</button>
      <button class="btn btn-sm" data-action="kfGen" data-id="${sc.id}" data-which="last" ${!state.engines.comfy || busyL ? "disabled" : ""}>${icon("spark", 13)}${esc(t("plan.kfLast"))}</button>
    </div>
    ${field(esc(t("plan.firstPrompt")), `<textarea class="textarea" rows="2" data-bind="plan.scenes.${i}.keyframe.first_prompt" ${sc.locked ? "disabled" : ""}>${esc(sc.keyframe.first_prompt)}</textarea>`)}
    ${field(esc(t("plan.lastPrompt")), `<textarea class="textarea" rows="2" data-bind="plan.scenes.${i}.keyframe.last_prompt" ${sc.locked ? "disabled" : ""}>${esc(sc.keyframe.last_prompt)}</textarea>`)}
    ${field(esc(t("plan.narration")), `<textarea class="textarea" rows="3" data-bind="plan.scenes.${i}.narration" ${sc.locked ? "disabled" : ""}>${esc(sc.narration)}</textarea>`)}
    ${field(esc(t("plan.visual")), `<input class="input" data-bind="plan.scenes.${i}.visual" value="${esc(sc.visual)}" ${sc.locked ? "disabled" : ""}>`)}
    <div class="field-row">
      ${field(esc(t("plan.relation")), selectBind(`plan.scenes.${i}.relation_to_prev`, ["establish", "continue", "contrast", "escalate", "match_cut", "unknown"].map((v) => ({ v, l: t("plan.rel." + v) })), true))}
      ${field(esc(t("plan.engine")), engineSelect(sc))}
    </div>
    ${field(esc(t("plan.relNote")), `<input class="input" data-bind="plan.scenes.${i}.relation_note" value="${esc(sc.relation_note)}">`)}
    <div class="kw-chips" style="margin:8px 0">
      <span class="chip">${esc(t("plan.boundary"))}</span><span class="health-dot ${sc.boundary_health}"></span><span class="chip">${esc(t("plan.bh." + sc.boundary_health))}</span>
      ${costBadge(sc)}
    </div>
    ${gallery}`;
}
function pagePlan() {
  const pl = state.plan;
  if (!pl) {
    return pageHead("plan") + `<div class="card"><div class="empty">${icon("board", 44)}
      <p><strong>${esc(t("plan.empty"))}</strong></p><p>${esc(t("plan.emptyHint"))}</p>
      <button class="btn btn-primary" data-action="aiPlan">${icon("spark", 15)}${esc(t("plan.emptyCta"))}</button></div></div>`;
  }
  const busy = state.planBusy.active;
  const castIds = [...new Set(pl.scenes.flatMap((s) => s.characters))];
  const header = `<div class="card plan-head">
    <div class="ph-left">
      <span class="badge ${pl.status === "confirmed" ? "green" : "blue"}" data-plan-status>${esc(t("plan.status." + pl.status))}</span>
      <span class="chip">${pl.scenes.length} ${esc(t("plan.scenes"))}</span>
      <div class="segmented tier-seg">${["draft", "final"].map((v) => `<button data-action="planTier" data-tier="${v}" class="${pl.quality_tier === v ? "active" : ""}">${esc(t(v === "draft" ? "wizard.tierDraft" : "wizard.tierFinal"))}</button>`).join("")}</div>
    </div>
    ${planMeterHtml()}
    <div class="ph-actions">
      <button class="btn" data-action="aiPlan" ${busy ? "disabled" : ""}>${busy ? '<span class="spinner"></span>' + esc(t("plan.aiBusy")) : icon("spark", 14) + esc(t("plan.aiBtn"))}</button>
      <button class="btn btn-ghost btn-icon" data-action="planExport" data-allow-locked title="${esc(t("plan.export"))}" aria-label="${esc(t("plan.export"))}">${icon("download", 15)}</button>
      <button class="btn btn-ghost btn-icon" data-action="planImport" data-allow-locked title="${esc(t("plan.import"))}" aria-label="${esc(t("plan.import"))}">${icon("upload", 15)}</button>
      <button class="btn btn-primary" data-action="planConfirm" data-allow-locked ${state.run.status === "running" ? "disabled" : ""}>${iconFill("play", 14)}${esc(t("plan.confirm"))}</button>
    </div>
  </div>`;
  const settings = `<div class="grid grid-2-1">
    <div class="card">
      <div class="card-title">${icon("clapper", 16)}${esc(t("plan.filmTitle"))}</div>
      ${field(esc(t("plan.filmTitle")), `<input class="input" data-bind="plan.title" value="${esc(pl.title)}">`)}
      ${field(esc(t("plan.logline")), `<input class="input" data-bind="plan.logline" value="${esc(pl.logline)}">`)}
      <div class="section-label">${esc(t("plan.style"))}</div>
      <div class="field-row">
        ${field(esc(t("plan.styleTone")), `<input class="input" data-bind="plan.style.tone" value="${esc(pl.style.tone)}">`)}
        ${field(esc(t("plan.stylePalette")), `<input class="input" data-bind="plan.style.palette" value="${esc(pl.style.palette)}">`)}
        ${field(esc(t("plan.styleCamera")), `<input class="input" data-bind="plan.style.camera" value="${esc(pl.style.camera)}">`)}
      </div>
      ${castIds.length ? `<div class="section-label">${esc(t("plan.cast"))}</div><div class="kw-chips">${castIds.map((id) => {
        const c = charById(id);
        return c ? `<button class="chip chip-link" data-action="seriesCharOpen" data-id="${id}" data-allow-locked>${icon("user", 11)}${esc(c.name)}</button>` : "";
      }).join("")}</div>` : ""}
    </div>
    <div class="card">
      <div class="card-title">${icon("audio", 16)}${esc(t("plan.voice"))} & ${esc(t("plan.bgm"))}</div>
      ${field(esc(t("plan.voice")), selectBind("plan.voice.name", VOICES.edge.map((v) => ({ v, l: v }))))}
      ${field(esc(t("audio.bgmType")), selectBind("plan.bgm.type", [
        { v: "acestep_local", l: t("plan.bgmLocal") }, { v: "random", l: t("audio.bgmRandom") },
        { v: "none", l: t("audio.bgmNone") }, { v: "custom", l: t("audio.bgmCustom") },
      ], true))}
      ${pl.bgm.type === "acestep_local" ? `
        ${field(esc(t("plan.bgmMood")), `<input class="input" data-bind="plan.bgm.mood" value="${esc(pl.bgm.mood)}">`)}
        ${field(esc(t("plan.bgmPrompt")), `<textarea class="textarea" rows="2" data-bind="plan.bgm.prompt">${esc(pl.bgm.prompt)}</textarea>`)}` : ""}
      ${field(esc(t("plan.bgmVolume")), rangeBind("plan.bgm.volume", 0, 1, 0.05, "pct"))}
      <div class="field-row">
        ${field(esc(t("plan.bgmFadeIn")), `<input class="input mono" type="number" min="0" max="10" step="0.5" data-bind="plan.bgm.fade_in" value="${pl.bgm.fade_in}">`)}
        ${field(esc(t("plan.bgmFadeOut")), `<input class="input mono" type="number" min="0" max="10" step="0.5" data-bind="plan.bgm.fade_out" value="${pl.bgm.fade_out}">`)}
      </div>
    </div>
  </div>`;
  const genlog = busy ? `<div class="card plan-genlog"><div class="card-title">${icon("log", 15)}${esc(t("plan.genLog"))}</div>
    ${state.planBusy.logs.map((l) => `<div class="log-line ${l.lv}"><span class="log-msg">${esc(l.msg)}</span></div>`).join("")}</div>` : "";
  const shown = busy ? pl.scenes.slice(0, Math.max(1, busy.revealed)) : pl.scenes;
  const board = shown.map((sc, i) => sceneCardHtml(sc, i)).join("") +
    (busy ? `<div class="wiz-busy"><span class="spinner"></span>${esc(t("plan.aiBusy"))}</div>` : "");
  return pageHead("plan") + header + engineStrip() + genlog + settings + planTimelineHtml() +
    `<div class="section-label">${esc(t("plan.storyboard"))}</div><div class="storyboard">${board}</div>`;
}

/* ============================================================
   page: series studio — episodes / character bible / style bible
   ============================================================ */
function epStatusBadge(st) {
  const cls = st === "rendered" ? "green" : st === "confirmed" ? "cyan" : st === "draft" ? "blue" : "gray";
  return `<span class="badge ${cls}"><span class="b-dot"></span>${esc(t("series.epStatus." + st))}</span>`;
}
function seriesLibraryHtml() {
  const cards = state.seriesList.map((sr) => {
    const rendered = sr.episodes.filter((e) => e.status === "rendered").length;
    const covers = sr.episodes.slice(0, 3).map((e, i) => `<span class="sc-cover-cell">${kfSvg(sr.id + "-" + e.id, e.title)}</span>`).join("");
    return `<button class="series-card" data-action="seriesOpen" data-id="${sr.id}">
      <span class="series-cover">${covers}</span>
      <span class="series-meta">
        <span class="series-title">${esc(sr.title)}</span>
        <span class="kw-chips"><span class="chip">${esc(t("wizard.tpl." + (sr.genre_template === "custom" ? "urban" : sr.genre_template)))}</span>
          <span class="chip">${esc(tf("series.coverEps", { n: sr.episodes.length }))}</span>
          <span class="badge green">${rendered}/${sr.episodes.length} ${esc(t("series.epStatus.rendered"))}</span></span>
      </span>
    </button>`;
  }).join("");
  return `<div class="section-label">${esc(t("series.library"))}</div>
    <div class="series-grid">${cards}
      <button class="series-card new" data-action="seriesNew">
        <span class="series-new-inner">${icon("plus", 26)}<span>${esc(t("series.new"))}</span><span class="field-help">${esc(t("series.newHint"))}</span></span>
      </button>
    </div>`;
}
function seriesEpisodesHtml(sr) {
  const rows = sr.episodes.map((ep) => {
    const pl = ep.plan_id ? state.plans[ep.plan_id] : null;
    const health = pl ? (pl.scenes.some((s) => s.boundary_health === "warn") ? "warn" : pl.scenes.every((s) => s.boundary_health === "ok") ? "ok" : "unknown") : "unknown";
    return `<div class="ep-row">
      <span class="or-seq mono">${esc(tf("series.ep", { n: ep.seq }))}</span>
      <div class="ep-fields">
        <div class="ep-title-line"><strong>${esc(ep.title)}</strong>${epStatusBadge(ep.status)}<span class="health-dot ${health}" title="${esc(t("plan.boundary"))}: ${esc(t("plan.bh." + health))}"></span></div>
        <div class="field-help">${esc(ep.logline)}</div>
        <div class="ep-hook">${icon("alert", 12)}${esc(t("series.hook"))}: ${esc(ep.hook)}</div>
      </div>
      <div class="row-actions">
        ${ep.plan_id ? `<button class="btn btn-sm" data-action="epOpen" data-id="${ep.id}" data-allow-locked>${icon("board", 13)}${esc(t("series.epOpen"))}</button>` : ""}
        ${ep.status === "outline" ? `<button class="btn btn-sm btn-primary" data-action="epNext" data-id="${ep.id}">${icon("spark", 13)}${esc(t("series.epNext"))}</button>` : ""}
      </div>
    </div>`;
  }).join("");
  return `<div class="ep-list">${rows}</div>`;
}
function seriesCharactersHtml(sr) {
  const cards = sr.characters.map((c, i) => {
    const voices = VOICES.edge.map((v) => ({ v, l: v }));
    return `<div class="char-card bible">
      <div class="cc-portrait lg">${portraitSvg(c.seed + "-" + c.name, c.name)}</div>
      <div class="cc-body">
        <div class="ep-title-line"><strong>${esc(c.name)}</strong><span class="chip">${esc(c.role)}</span><span class="chip mono">${esc(t("series.charSeed"))} ${c.seed}</span></div>
        <div class="field-help">${esc(c.persona)}</div>
        ${field(esc(t("wizard.charAppearance")), `<textarea class="textarea" rows="2" data-bind="seriesList.${state.seriesList.indexOf(sr)}.characters.${i}.appearance">${esc(c.appearance)}</textarea>`)}
        <div class="field-row">
          <select class="select" data-bind="seriesList.${state.seriesList.indexOf(sr)}.characters.${i}.voice" aria-label="${esc(t("wizard.charVoice"))}">${opts(voices, c.voice)}</select>
          <button class="btn btn-sm" data-action="charListen" data-id="${c.id}">${iconFill("play", 13)}${esc(t("series.charListen"))}</button>
        </div>
        <div class="section-label">${esc(t("series.charRefs"))}</div>
        <div class="cand-gallery">${c.reference_images.map((r, ri) => `<span class="cand-thumb lg static">${portraitSvg(c.seed + "-" + c.name + "-" + r, c.name + " " + r)}<span class="cand-label mono">${esc(r)}</span></span>`).join("")}</div>
      </div>
    </div>`;
  }).join("");
  return `<div class="alert info">${icon("info", 15)}<span>${esc(t("series.charConsistency"))}</span></div>
    <div class="char-grid bible">${cards}</div>`;
}
function seriesStyleHtml(sr) {
  const idx = state.seriesList.indexOf(sr);
  const swatches = (sr.style_bible.palette.match(/#[0-9a-f]{6}/gi) || []);
  return `<div class="card">
    <div class="card-title">${icon("presets", 16)}${esc(t("series.style"))}</div>
    <div class="alert info">${icon("info", 15)}<span>${esc(t("series.styleHint"))}</span></div>
    <div class="grid grid-2">
      ${field(esc(t("plan.styleTone")), `<input class="input" data-bind="seriesList.${idx}.style_bible.tone" value="${esc(sr.style_bible.tone)}">`)}
      ${field(esc(t("plan.stylePalette")), `<input class="input" data-bind="seriesList.${idx}.style_bible.palette" value="${esc(sr.style_bible.palette)}">`)}
      ${field(esc(t("plan.styleCamera")), `<input class="input" data-bind="seriesList.${idx}.style_bible.camera" value="${esc(sr.style_bible.camera)}">`)}
      ${field(esc(t("series.styleEra")), `<input class="input" data-bind="seriesList.${idx}.style_bible.era" value="${esc(sr.style_bible.era)}">`)}
    </div>
    <div class="section-label">${esc(t("plan.kfPair"))}</div>
    <div class="style-strip">${[0, 1, 2, 3].map((i) => `<span class="style-cell">${kfSvg(sr.id + "-style-" + i + "-" + sr.style_bible.palette, sr.style_bible.tone)}</span>`).join("")}</div>
  </div>`;
}
function pageSeries() {
  if (state.seriesView === "library" || !activeSeries()) return pageHead("series") + seriesLibraryHtml();
  const sr = activeSeries();
  const tabs = [["episodes", "series.episodes", "series"], ["characters", "series.characters", "user"], ["style", "series.style", "presets"]]
    .map(([k, lk, ic]) => `<button class="filter-tab${state.seriesTab === k ? " active" : ""}" data-action="seriesTab" data-tab="${k}">${icon(ic, 14)}${esc(t(lk))}</button>`).join("");
  const body = state.seriesTab === "episodes" ? seriesEpisodesHtml(sr)
    : state.seriesTab === "characters" ? seriesCharactersHtml(sr)
    : seriesStyleHtml(sr);
  return pageHead("series") + `
    <div class="series-head">
      <button class="btn btn-sm" data-action="seriesBack">${icon("chevLeft", 13)}${esc(t("series.back"))}</button>
      <span class="series-title lg">${esc(sr.title)}</span>
      <span class="chip">${esc(t("wizard.tpl." + (sr.genre_template === "custom" ? "urban" : sr.genre_template)))}</span>
      <span class="chip">${esc(tf("series.coverEps", { n: sr.episodes.length }))}</span>
    </div>
    <div class="filter-tabs">${tabs}</div>
    ${body}`;
}

/* ---------------- page dispatcher ---------------- */
const PAGE_RENDERERS = {
  wizard: pageWizard, plan: pagePlan, series: pageSeries,
  tasks: pageTasks, script: pageScript, audio: pageAudio, video: pageVideo, subtitle: pageSubtitle,
  history: pageHistory, llm: pageLlm, material: pageMaterial, channels: pageChannels, presets: pagePresets, settings: pageSettings,
};
const LOCK_PAGES = ["script", "plan", "audio", "video", "subtitle"];
function renderPage() {
  const root = $("#pageRoot");
  root.classList.remove("locked-page");
  root.innerHTML = PAGE_RENDERERS[state.activePage]();
  if (isLocked() && LOCK_PAGES.includes(state.activePage)) {
    root.classList.add("locked-page");
    root.insertAdjacentHTML("afterbegin", `
      <div class="alert warn lock-banner">${icon("lock", 16)}
        <span style="flex:1">${esc(t("project.lockedHint"))}</span>
        <button class="btn btn-sm btn-primary" data-action="saveAsNew" data-allow-locked>${icon("copy", 13)}${esc(t("project.saveAsNew"))}</button>
      </div>`);
    root.querySelectorAll("input, select, textarea, button").forEach((el) => {
      if (!el.hasAttribute("data-allow-locked")) el.disabled = true;
    });
  }
  if (state.activePage === "tasks") renderTaskTable();
  if (state.activePage === "history") renderHistoryTable();
  if (state.activePage === "subtitle") updateSubtitlePreview(false);
}

/* ============================================================
   Simulated generation engine — real phase sequence from
   Main.py _render_generation_activity (L2351)
   ============================================================ */
function buildSteps(fail) {
  const p = state.params;
  const id = state.run.taskId;
  const llm = (LLM_PROVIDERS.find((x) => x.id === p.llmProvider) || {}).name || p.llmProvider;
  const S = [];
  const add = (ph, lv, z, e, pg) => S.push({ ph, lv, zh: z, en: e, pg });
  add("queued", "phase", t("phase.queued"), t("phase.queued"), 0);
  add(null, "info", `任务已加入队列 task_id=${id}`, `Task queued task_id=${id}`, 2);
  add("preparing", "phase", t("phase.preparing"), t("phase.preparing"), 4);
  add(null, "info", "检查配置与依赖…", "Checking configuration & dependencies…", 6);
  add(null, "info", `创建任务目录 storage/tasks/${id}`, `Created task dir storage/tasks/${id}`, 8);
  add(null, "ok", "配置校验通过", "Configuration validated", 10);
  add("script", "phase", t("phase.script"), t("phase.script"), 12);
  add(null, "info", `调用大模型 ${llm} · ${p.llmModel}`, `Calling LLM ${llm} · ${p.llmModel}`, 16);
  add(null, "info", "生成文案第 1 段…", "Writing script paragraph 1…", 20);
  add(null, "info", `生成文案第 2/${p.paragraphNumber} 段…`, `Writing paragraph 2/${p.paragraphNumber}…`, 24);
  add(null, "ok", "文案生成完成（286 字）", "Script generated (286 chars)", 28);
  add("terms", "phase", t("phase.terms"), t("phase.terms"), 30);
  add(null, "info", "正在提取视频关键词…", "Extracting video keywords…", 33);
  add(null, "ok", `关键词: ${(p.terms || "ai, lifestyle, technology").split(/[,，]/).slice(0, 4).join(", ")}`, `Keywords: ${(p.terms || "ai, lifestyle, technology").split(/[,，]/).slice(0, 4).join(", ")}`, 36);
  add("audio", "phase", t("phase.audio"), t("phase.audio"), 38);
  if (p.voiceMode === "tts") {
    add(null, "info", `TTS ${p.ttsServer} · ${p.voiceName}`, `TTS ${p.ttsServer} · ${p.voiceName}`, 42);
    add(null, "info", "合成语音片段 1/3…", "Synthesizing audio clip 1/3…", 46);
    add(null, "info", "合成语音片段 2/3…", "Synthesizing audio clip 2/3…", 50);
    add(null, "info", "合成语音片段 3/3…", "Synthesizing audio clip 3/3…", 54);
    add(null, "ok", "配音完成，时长 00:42", "Narration done, duration 00:42", 58);
  } else if (p.voiceMode === "upload") {
    add(null, "info", `使用上传音频 ${p.uploadedAudio}`, `Using uploaded audio ${p.uploadedAudio}`, 50);
    add(null, "ok", "音频预处理完成", "Audio preprocessed", 58);
  } else {
    add(null, "info", "无配音模式，跳过 TTS", "No voiceover, skipping TTS", 58);
  }
  add(null, "info", `背景音乐混音（音量 ${Math.round(p.bgmVolume * 100)}%）`, `Mixing BGM (volume ${Math.round(p.bgmVolume * 100)}%)`, 60);
  add("subtitle", "phase", t("phase.subtitle"), t("phase.subtitle"), 62);
  if (p.subtitleEnabled) {
    add(null, "info", "语音对齐，生成逐词时间戳…", "Aligning speech, word timestamps…", 66);
    add(null, "info", "写出 subtitle.srt", "Writing subtitle.srt", 70);
    add(null, "ok", "字幕生成完成（12 条）", "Subtitles generated (12 cues)", 72);
  } else {
    add(null, "info", "字幕已关闭，跳过", "Subtitles disabled, skipping", 72);
  }
  add("materials", "phase", t("phase.materials"), t("phase.materials"), 74);
  add(null, "info", `素材来源 ${sourceLabel(p.videoSource)}，检索匹配画面…`, `Source ${sourceLabel(p.videoSource)}, searching footage…`, 78);
  add(null, "info", "下载素材片段 1/4…", "Downloading clip 1/4…", 82);
  if (fail) {
    add(null, "error", "素材下载失败：API 返回 401（Key 无效）", "Material download failed: API 401 (invalid key)", 84);
    add(null, "error", "任务终止，请检查素材来源配置", "Task aborted, check material source config", 84);
    S.push({ fail: true });
    return S;
  }
  add(null, "info", "下载素材片段 2/4…", "Downloading clip 2/4…", 84);
  add(null, "info", "下载素材片段 3/4…", "Downloading clip 3/4…", 86);
  add(null, "info", "下载素材片段 4/4…", "Downloading clip 4/4…", 88);
  add(null, "ok", "素材准备完成（4 个片段）", "Materials ready (4 clips)", 90);
  add("rendering", "phase", t("phase.rendering"), t("phase.rendering"), 92);
  add(null, "info", `ffmpeg 合成 ${p.aspect === "portrait" ? "1080×1920" : "1920×1080"} · ${p.encoder}`, `ffmpeg composing ${p.aspect === "portrait" ? "1080×1920" : "1920×1080"} · ${p.encoder}`, 94);
  add(null, "info", "渲染片段 1/2…", "Rendering segment 1/2…", 96);
  add(null, "info", "渲染片段 2/2…", "Rendering segment 2/2…", 97);
  add(null, "info", "混流封装 final-1.mp4", "Muxing final-1.mp4", 98);
  add(null, "warn", "成片审查警告：第 2 段素材与文案相关性较低", "Review warning: clip 2 has low relevance to script", 99);
  add(null, "ok", "成片审查完成（1 条警告）", "Review finished (1 warning)", 99);
  S.push({ done: true, pg: 100 });
  return S;
}

let logPinned = true;
function logMsg(l) { return l.key ? t(l.key) : state.lang === "zh" ? l.zh : l.en; }
function logLineHtml(l) {
  return `<span class="log-time">${esc(l.time)}</span><span class="log-msg">${esc(logMsg(l))}</span>`;
}
function pushLog(lv, zh, en, key) {
  const entry = { time: clock(), lv, zh, en, key };
  state.run.logs.push(entry);
  const box = $("#logLines");
  if (box) {
    const div = document.createElement("div");
    div.className = "log-line " + lv;
    div.innerHTML = logLineHtml(entry);
    box.appendChild(div);
    const well = $("#logWell");
    if (logPinned) well.scrollTop = well.scrollHeight;
    else $("#jumpLatest").classList.add("show");
  }
}
function renderAllLogs() {
  const box = $("#logLines");
  if (!box) return;
  box.innerHTML = state.run.logs.map((l) => `<div class="log-line ${l.lv}">${logLineHtml(l)}</div>`).join("");
  const well = $("#logWell");
  if (logPinned) well.scrollTop = well.scrollHeight;
}

function startRun() {
  if (state.run.status === "running") return;
  const p = state.params;
  const block = (key, page) => {
    state.formError = t(key);
    toast(t(key), "error");
    if (page && state.activePage !== page) go(page); else renderPage();
  };
  if (!p.subject.trim() && !p.script.trim()) return block("toast.genBlocked.empty", "script");
  if (p.videoSource === "local" && !p.uploadedMaterials.length) return block("toast.genBlocked.local", "video");
  if (!sourceKeyOk(p.videoSource)) return block("toast.genBlocked.key", "material");
  if (AI_SOURCES.includes(p.videoSource) && !p.chargeConfirmed) return block("toast.genBlocked.billing", "video");
  if (p.voiceMode === "upload" && !p.uploadedAudio) return block("toast.genBlocked.audio", "audio");
  if (isLocked()) { toast(t("project.lockedHint"), "warn"); return; }
  state.formError = "";
  if (engineTimer) { clearInterval(engineTimer); engineTimer = null; }
  /* bind the run to the current project: reuse its unique id, auto-save params */
  let proj = currentTask();
  if (!proj) {
    proj = { id: uid(), createdAt: Date.now(), videos: 1, duration: "00:42" };
    state.tasks.unshift(proj);
    state.currentProjectId = proj.id;
  }
  const subject = p.subject.trim() || p.script.trim().slice(0, 24);
  proj.subject = subject; proj.state = "processing"; proj.source = p.videoSource;
  proj.params = JSON.parse(JSON.stringify(p)); proj.updatedAt = Date.now(); delete proj.error;
  state.baseline = JSON.stringify(p); state.dirty = false;
  state.run = Object.assign(state.run, {
    status: "running", phase: "queued", progress: 0, logs: [], startedAt: Date.now(), endedAt: 0,
    taskId: proj.id, subject, stepIndex: 0, result: null,
  });
  state.run.steps = state.run.planMode ? buildPlanSteps(state.run.failMode) : buildSteps(state.run.failMode);
  logPinned = true;
  $("#jumpLatest").classList.remove("show");
  renderAllLogs();
  if (state.rightCollapsed) { state.rightCollapsed = false; applyShellClasses(); saveShell(); }
  engineTimer = setInterval(engineTick, 400);
  toast(t("toast.genStarted"), "info");
  renderActionBar(); renderTopbar(); renderNav(); updateGenUI(true);
  if (state.activePage === "script" || state.activePage === "tasks") renderPage();
}
function engineTick() {
  const run = state.run;
  const step = run.steps[run.stepIndex++];
  if (!step) return;
  if (step.fail) return failRun();
  if (step.done) return finishRun();
  if (step.ph) run.phase = step.ph;
  if (typeof step.pg === "number") run.progress = step.pg;
  if (step.lv === "phase") pushLog(step.lv, null, null, "phase." + step.ph);
  else pushLog(step.lv, step.zh, step.en);
  updateGenUI(false);
}
function finishRun() {
  clearInterval(engineTimer); engineTimer = null;
  const run = state.run;
  run.status = "done"; run.phase = "complete"; run.progress = 100; run.endedAt = Date.now();
  run.result = { subject: run.subject, duration: "00:42", count: state.params.videoCount };
  pushLog("ok", `视频生成完成 · final-1.mp4 · ${fmtElapsed(run.endedAt - run.startedAt)}`, `Video generation completed · final-1.mp4 · ${fmtElapsed(run.endedAt - run.startedAt)}`);
  const proj = taskById(run.taskId);
  if (proj) {
    proj.state = "complete"; proj.subject = run.subject; proj.source = state.params.videoSource;
    proj.duration = "00:42"; proj.videos = state.params.videoCount;
    proj.params = JSON.parse(JSON.stringify(state.params)); proj.updatedAt = Date.now(); delete proj.error;
  } else {
    state.tasks.unshift({
      id: run.taskId, subject: run.subject, state: "complete", createdAt: Date.now(), updatedAt: Date.now(),
      source: state.params.videoSource, duration: "00:42", videos: state.params.videoCount,
      params: JSON.parse(JSON.stringify(state.params)),
    });
  }
  if (state.currentProjectId === run.taskId) { state.baseline = JSON.stringify(state.params); state.dirty = false; }
  if (run.planMode) finishPlanRun();
  toast(t("toast.genDone"), "success");
  renderActionBar(); renderTopbar(); renderNav(); updateGenUI(false);
  if (state.activePage === "tasks" || LOCK_PAGES.includes(state.activePage)) renderPage();
}
function failRun() {
  clearInterval(engineTimer); engineTimer = null;
  const run = state.run;
  run.status = "failed"; run.phase = "failed"; run.endedAt = Date.now();
  const errMsg = state.lang === "zh" ? "素材下载失败：API 返回 401（Key 无效）" : "Material download failed: API 401 (invalid key)";
  pushLog("error", null, null, "phase.failed");
  const proj = taskById(run.taskId);
  if (proj) {
    proj.state = "failed"; proj.subject = run.subject; proj.source = state.params.videoSource;
    proj.error = errMsg; proj.params = JSON.parse(JSON.stringify(state.params)); proj.updatedAt = Date.now();
  } else {
    state.tasks.unshift({
      id: run.taskId, subject: run.subject, state: "failed", createdAt: Date.now(), updatedAt: Date.now(),
      source: state.params.videoSource, error: errMsg,
      params: JSON.parse(JSON.stringify(state.params)),
    });
  }
  toast(t("toast.genFailed"), "error");
  renderActionBar(); renderTopbar(); renderNav(); updateGenUI(false);
  if (state.activePage === "tasks") renderPage();
}

function updateGenUI(fullLogs) {
  const run = state.run;
  const status = $("#genStatus");
  const well = $("#logWell");
  const result = $("#genResult");
  well.style.display = state.settings.hideLog || run.status === "idle" ? "none" : "";
  if (run.status === "idle") {
    status.innerHTML = `<div class="gen-empty">${icon("clapper", 34)}<p><strong>${esc(t("gen.empty"))}</strong></p><p style="margin-top:6px">${esc(t("gen.emptyHint"))}</p></div>`;
    result.innerHTML = "";
  } else {
    const running = run.status === "running";
    const chipColor = run.status === "failed" ? "var(--red)" : run.status === "done" ? "var(--green)" : "var(--cyan)";
    const chipBg = run.status === "failed" ? "var(--red-soft)" : run.status === "done" ? "var(--green-soft)" : "var(--cyan-soft)";
    const elapsed = fmtElapsed((run.endedAt || Date.now()) - run.startedAt);
    status.innerHTML = `
      <div class="status-top">
        <span class="phase-chip" style="color:${chipColor};background:${chipBg}">${running ? '<span class="b-dot"></span>' : icon(run.status === "done" ? "check" : "alert", 12)}${esc(t("phase." + run.phase))}</span>
        <span class="elapsed">${esc(t("gen.elapsed"))} ${elapsed}</span>
      </div>
      <div class="progress"><div class="progress-fill${running ? " running" : ""}" style="width:${run.progress}%"></div></div>
      <div class="progress-meta"><span>${esc(t("gen.progress"))} ${Math.round(run.progress)}%</span><span class="mono">#${esc(run.taskId)}</span></div>
      ${state.settings.hideLog ? `<div class="field-help" style="margin-top:8px">${esc(t("gen.logHidden"))}</div>` : ""}`;
    if (run.status === "done" && run.result) {
      const warnMsg = state.lang === "zh" ? "第 2 段素材与文案相关性较低，建议人工复核后再发布。" : "Clip 2 has low relevance to the script; review before publishing.";
      result.innerHTML = `<div class="result-card">
        <div class="result-poster">
          <span class="res-tag">${state.params.aspect === "portrait" ? "1080×1920" : "1920×1080"} · MP4</span>
          <button class="play-big" data-action="downloadResult" aria-label="${esc(t("gen.download"))}">${iconFill("play", 20)}</button>
        </div>
        <div class="result-meta">
          <span class="res-subj" title="${esc(run.result.subject)}">${esc(run.result.subject)}</span>
          <button class="btn btn-primary btn-sm" data-action="downloadResult">${icon("download", 13)}${esc(t("gen.download"))}</button>
          <button class="btn btn-ghost btn-sm" data-action="viewTask">${esc(t("gen.viewTask"))}</button>
        </div>
      </div>
      ${expander("expReviewWarn", esc(t("gen.reviewWarn")), `<div class="alert warn" style="margin:8px 0 0">${icon("alert", 15)}<span>${esc(warnMsg)}</span></div>`, false)}`;
    } else if (run.status === "failed") {
      const lastErr = run.logs.filter((l) => l.lv === "error" && !l.key).slice(-1)[0];
      result.innerHTML = `<div class="alert error" style="margin:0">${icon("alert", 16)}<span>${esc(lastErr ? logMsg(lastErr) : t("gen.failed"))}</span></div>`;
    } else {
      result.innerHTML = "";
    }
  }
  const dot = $("#railDot");
  dot.className = "rail-dot" + (run.status === "running" ? " running" : run.status === "done" ? " done" : run.status === "failed" ? " failed" : "");
  const badge = $("#railBadge");
  badge.hidden = run.status !== "running";
  badge.textContent = Math.round(run.progress) + "%";
  if (fullLogs) renderAllLogs();
}

/* ============================================================
   AI script generation (typewriter) & voice preview
   ============================================================ */
function composeAiScript(subject) {
  const n = state.params.paragraphNumber;
  const zh = state.lang === "zh";
  const paras = zh ? [
    `你知道吗？${subject}，正在悄悄改变我们每个人的生活。先别划走，这条视频用一分钟讲清楚。`,
    `先说结论：${subject}并不是遥不可及的概念，它已经出现在你每天的衣食住行里。从推荐算法到智能助手，变化比想象中更快。`,
    `举个例子：过去需要几个小时完成的事情，现在几分钟就能搞定。效率提升的背后，是工具与方法的彻底革新。`,
    `当然，任何新事物都有两面性。理解它的边界，才能更好地利用它，而不是被它牵着走。`,
    `未来已来，只是分布不均。掌握${subject}的关键信息，你就比大多数人领先了一步。`,
    `如果这条视频对你有帮助，点个赞收藏一下，评论区聊聊你的看法，我们下期见！`,
  ] : [
    `Did you know? ${subject} is quietly changing all of our lives. Stay with me — one minute is all it takes.`,
    `Here's the takeaway: ${subject} is not a distant concept. It's already in your daily routine, moving faster than you think.`,
    `For example, tasks that used to take hours now take minutes. Behind that leap is a complete rethink of tools and methods.`,
    `Of course, every new thing has two sides. Understanding its limits helps you use it — not the other way around.`,
    `The future is here, just unevenly distributed. Grasp the essentials of ${subject} and you're ahead of the curve.`,
    `If this helped, like and save. Tell me your take in the comments — see you next time!`,
  ];
  const body = paras.slice(0, Math.max(2, Math.min(n + 1, paras.length))).join("\n\n");
  const keywords = zh ? ["人工智能", "生活方式", "效率工具", "科技趋势", "未来"] : ["ai", "lifestyle", "productivity", "technology", "future"];
  return { text: body, keywords: keywords.slice(0, 5) };
}
function aiScriptGenerate() {
  if (state.aiScript.busy) return;
  const p = state.params;
  if (!p.subject.trim()) { toast(t("script.needSubject"), "warn"); return; }
  if (!(p.providerKeys[p.llmProvider] || "").trim()) { toast(t("toast.genBlocked.key"), "error"); go("llm"); return; }
  const { text, keywords } = composeAiScript(p.subject.trim());
  state.aiScript.busy = true;
  state.aiScript.text = "";
  state.aiScript.keywords = [];
  renderPage();
  if (aiTimer) clearInterval(aiTimer);
  let i = 0;
  aiTimer = setInterval(() => {
    const box = $("#aiScriptPreview");
    if (!box) { clearInterval(aiTimer); aiTimer = null; state.aiScript.busy = false; return; }
    i = Math.min(text.length, i + 4);
    box.textContent = text.slice(0, i);
    if (i >= text.length) {
      clearInterval(aiTimer); aiTimer = null;
      state.aiScript.busy = false;
      state.aiScript.text = text;
      state.aiScript.keywords = keywords;
      p.script = text;
      p.terms = keywords.join(", ");
      markDirty();
      renderPage();
      toast(t("script.done"), "success");
    }
  }, 30);
}
let voiceSecs = 0;
function voicePreviewToggle() {
  const wave = $("#voiceWave");
  if (!wave) return;
  if (state.voicePreview.playing) return stopVoicePreview();
  state.voicePreview.playing = true;
  voiceSecs = 0;
  wave.classList.add("playing");
  const lbl = $("#voiceBtnLabel");
  if (lbl) lbl.textContent = t("common.close");
  if (voiceTimer) clearInterval(voiceTimer);
  voiceTimer = setInterval(() => {
    voiceSecs += 0.5;
    const timeEl = $("#voiceTime");
    if (!timeEl || voiceSecs >= 8) return stopVoicePreview();
    timeEl.textContent = `0:${pad(Math.floor(voiceSecs))}`;
  }, 500);
}
function stopVoicePreview() {
  state.voicePreview.playing = false;
  if (voiceTimer) { clearInterval(voiceTimer); voiceTimer = null; }
  const wave = $("#voiceWave");
  if (wave) wave.classList.remove("playing");
  const lbl = $("#voiceBtnLabel");
  if (lbl) lbl.textContent = t("audio.preview");
  const timeEl = $("#voiceTime");
  if (timeEl) timeEl.textContent = "0:00";
}

/* ============================================================
   Presets, key backup, task actions
   ============================================================ */
function presetExport() {
  downloadJSON("changofilm-settings-preset.json", {
    schema: "changofilm.settings_preset", version: 1, exportedAt: new Date().toISOString(),
    params: JSON.parse(JSON.stringify(state.params)),
  });
  toast(t("toast.presetExported"), "success");
}
function readJSONFile(file, cb) {
  const reader = new FileReader();
  reader.onload = () => { try { cb(JSON.parse(String(reader.result))); } catch (e) { cb(null); } };
  reader.onerror = () => cb(null);
  reader.readAsText(file, "utf-8");
}
function presetImport(file) {
  readJSONFile(file, (obj) => {
    if (!obj || typeof obj.params !== "object" || obj.params == null || typeof obj.params.subject !== "string") {
      toast(t("toast.presetBad"), "error"); return;
    }
    Object.assign(state.params, obj.params);
    ensureLlmDefaults();
    markDirty();
    renderPage(); renderActionBar();
    toast(t("toast.presetImported"), "success");
  });
}
function keysExport() {
  downloadJSON("changofilm-api-keys.json", { schema: "changofilm.api_keys", version: 1, providerKeys: state.params.providerKeys });
  toast(t("settings.keysExported"), "success");
}
function keysImport(file) {
  readJSONFile(file, (obj) => {
    if (!obj || typeof obj.providerKeys !== "object" || obj.providerKeys == null) { toast(t("toast.presetBad"), "error"); return; }
    Object.assign(state.params.providerKeys, obj.providerKeys);
    renderPage(); renderActionBar();
    toast(t("settings.keysImported"), "success");
  });
}
function taskPlay(id) {
  const x = taskById(id);
  if (!x) return;
  openDrawer(t("tasks.preview"), `
    <div class="result-card" style="margin-bottom:14px">
      <div class="result-poster">
        <span class="res-tag">${x.params && x.params.aspect === "landscape" ? "1920×1080" : "1080×1920"} · MP4</span>
        <button class="play-big" data-action="downloadResult" aria-label="${esc(t("tasks.play"))}">${iconFill("play", 20)}</button>
      </div>
      <div class="result-meta"><span class="res-subj">${esc(x.subject)}</span><span class="mono" style="font-size:11px;color:var(--text-dim)">${esc(x.duration || "00:42")}</span></div>
    </div>
    <div class="progress" style="margin-bottom:14px"><div class="progress-fill" style="width:35%"></div></div>
    <div class="kw-chips">
      <span class="chip">${esc(t("ready.source"))} · ${esc(sourceLabel(x.source))}</span>
      <span class="chip">${esc(t("tasks.col.time"))} · ${fmtDateTime(x.createdAt)}</span>
      <span class="chip">${esc(t("ready.count"))} · ${x.videos || 1}</span>
    </div>
    <div class="field-row" style="margin-top:16px">
      <button class="btn btn-primary" data-action="downloadResult">${icon("download", 15)}${esc(t("gen.download"))}</button>
      <button class="btn" data-action="taskLoad" data-id="${x.id}">${icon("restore", 15)}${esc(t("tasks.load"))}</button>
    </div>`);
}
function taskLoad(id) {
  requestSwitch(() => loadProject(id, { navigate: true, toastKey: "tasks.loaded" }));
}
function taskDelete(id) {
  const idx = state.tasks.findIndex((x) => x.id === id);
  if (idx < 0) return;
  const removed = state.tasks.splice(idx, 1)[0];
  if (state.activePage === "tasks") renderPage(); else renderTaskTable();
  toast(t("tasks.deleted") + ": " + removed.subject, "info", t("tasks.undo"), () => {
    state.tasks.splice(Math.min(idx, state.tasks.length), 0, removed);
    if (state.activePage === "tasks") renderPage(); else renderTaskTable();
    renderNav();
  });
}
function republish(id, btn) {
  const x = state.history.find((h) => h.id === id);
  if (!x || btn.disabled) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>' + esc(t("history.republish"));
  setTimeout(() => {
    x.result = "success"; x.time = Date.now(); x.duration = (2 + Math.random() * 4).toFixed(1) + "s";
    renderHistoryTable();
    toast(t("history.republished") + ": " + x.subject + " → " + x.platform, "success");
  }, 1200);
}
function llmTest(provider, btn) {
  if (state.llmTest[provider] === "testing") return;
  state.llmTest[provider] = "testing";
  renderPage();
  setTimeout(() => {
    const key = state.params.providerKeys[provider] || "";
    state.llmTest[provider] = key.trim().length >= 8 ? "ok" : "bad";
    if (state.activePage === "llm") renderPage();
  }, 900);
}
function llmSaveUse(provider) {
  ensureLlmDefaults();
  const pr = LLM_PROVIDERS.find((x) => x.id === provider);
  if (!pr) return;
  state.params.llmProvider = provider;
  state.params.llmModel = state.params.providerModels[provider] || pr.models[0];
  state.params.llmBaseUrl = state.params.providerBaseUrls[provider] || "";
  markDirty();
  renderPage();
  toast(t("llm.saved"), "success");
}
function channelLogin(platform) {
  if (channelBusy[platform]) return;
  channelBusy[platform] = true;
  renderPage();
  setTimeout(() => {
    channelBusy[platform] = false;
    state.channels[platform] = true;
    if (state.activePage === "channels") renderPage();
    toast(t("channels.loginOk"), "success");
  }, 1500);
}

/* ============================================================
   Short-drama actions — mode / engines / wizard / series
   ============================================================ */
let wizTimer = null, planTimer = null;
const kfTimers = {};
function setMode(m) {
  state.mode = m;
  saveShell();
  toast(t(m === "simple" ? "mode.simpleOn" : "mode.proOn"), "info");
  if (m === "simple" && !SIMPLE_PAGES.includes(state.activePage)) go("wizard");
  else { renderNav(); renderTabbar(); renderPage(); }
  renderTopbar();
}
function ensureOutline() {
  const w = state.wizard;
  if (w.outline.length) return;
  const zh = state.lang === "zh";
  const hooksZh = ["她在垃圾桶里捡回了那份被否决的方案", "监控录像里出现了不该出现的人", "账户余额突然多出一笔匿名转账", "对手的发布会邀请函寄到了她手上", "真相只差最后一块拼图"];
  const hooksEn = ["She retrieves the rejected proposal from the trash", "Someone impossible appears on the CCTV footage", "An anonymous transfer lands in her account", "The rival's launch invitation arrives at her door", "The truth is one puzzle piece away"];
  w.outline = Array.from({ length: w.episodes }, (_, i) => ({
    id: "ep" + (i + 1),
    logline: zh
      ? (i === 0 ? `起点：${w.idea}。主角被逼到墙角，第一次显露锋芒。` : i === w.episodes - 1 ? "终局：所有伏线收拢，主角完成最后一击。" : `冲突升级：盟友与背叛同时出现，第${i + 1}次交锋。`)
      : (i === 0 ? `Setup: ${w.idea}. Cornered, the lead shows an edge for the first time.` : i === w.episodes - 1 ? "Finale: every thread converges for the final strike." : `Escalation ${i + 1}: allies and betrayal arrive together.`),
    hook: (zh ? hooksZh : hooksEn)[i % 5],
  }));
}
function wizNext() {
  const w = state.wizard;
  if (w.step === 1) {
    if (!w.idea.trim()) { toast(t("wizard.needIdea"), "warn"); return; }
    if (!w.genre) w.genre = "urban";
  }
  if (w.step === 2) {
    if (!w.chars.length) { toast(t("wizard.needChars"), "warn"); return; }
    ensureOutline();
  }
  if (w.step === 4 && !w.planReady) { toast(t("wizard.needPlan"), "warn"); return; }
  w.step = Math.min(5, w.step + 1);
  saveShell(); renderPage();
  $("#pageScroll").scrollTop = 0;
}
function wizCharsExtract() {
  const w = state.wizard;
  if (w.charsBusy) return;
  w.charsBusy = true; renderPage();
  const g = genreById(w.genre);
  if (wizTimer) clearTimeout(wizTimer);
  wizTimer = setTimeout(() => {
    w.chars = g.chars.map((c, i) => Object.assign({ id: "c" + (i + 1), seed: 900001 + i * 7, reference_images: ["ref-1", "ref-2", "ref-3"], lora: null }, c));
    w.charsBusy = false;
    if (state.activePage === "wizard") renderPage();
    toast(t("wizard.charsDone"), "success");
  }, 1200);
}
/* six-shot arc → ScriptPlan for a series episode (shared by wizard & next-episode) */
function arcPlanFor(sr, ep, target, tier) {
  const g = genreById(sr.genre_template);
  const lang = state.lang === "en" ? "en" : "zh";
  const lead = sr.characters[0] ? sr.characters[0].name : (lang === "zh" ? "主角" : "the lead");
  const fill = (s) => s.split("{c}").join(lead);
  const scale = (target || 60) / 57.5;
  let prevLast = null;
  const scenes = WIZ_ARC.map((a, i) => {
    const L = a[lang] || a.zh;
    const local = a.engine.startsWith("local");
    const first = local ? (a.shared && prevLast ? prevLast : "wiz-" + ep.id + "-s" + (i + 1) + "-f") : null;
    const last = local ? "wiz-" + ep.id + "-s" + (i + 1) + "-l" : null;
    if (local) prevLast = last;
    return mkScene("w" + (i + 1), i + 1, {
      narration: fill(L.n), visual: fill(L.v), est_duration: Math.round(a.dur * scale * 10) / 10,
      engine: a.engine, relation_to_prev: a.rel,
      characters: sr.characters[0] ? [sr.characters[0].id] : [], location: sr.locations[0] ? sr.locations[0].id : "",
      keywords: [g.id, a.rel === "contrast" ? "timelapse" : "cinematic"],
      keyframe: { first, last, first_prompt: fill(L.v), last_prompt: "", shared_with_prev: !!(a.shared && local) },
      transition_to_next: a.rel === "contrast" ? "fade" : i % 2 ? "none" : "fade",
      boundary_health: a.engine === "stock" ? "warn" : "ok",
      material: a.engine === "stock" ? {
        source: "pexels", candidates: [
          { id: "px-5501", label: "city night timelapse", seed: "wiz-cand-1" },
          { id: "px-5502", label: "traffic river aerial", seed: "wiz-cand-2" },
        ], selected: "px-5501", in: 0, out: Math.round(a.dur * scale * 10) / 10,
      } : { source: "pexels", candidates: [], selected: null, in: 0, out: 5 },
    });
  });
  return {
    plan_version: 1, revision: 1, status: "draft", series_id: sr.id, episode_id: ep.id,
    title: sr.title + " · " + tf("series.ep", { n: ep.seq }), logline: ep.logline,
    style: Object.assign({ consistency_subject: lead }, sr.style_bible),
    target_duration: target || 60, aspect: "9:16", quality_tier: tier || "draft",
    voice: { name: sr.characters[0] ? sr.characters[0].voice : g.voice, rate: 1.0 },
    bgm: { type: "acestep_local", mood: g.bgm.mood, prompt: g.bgm.prompt, volume: 0.2, fade_in: 1.0, fade_out: 3.0 },
    llm: { provider: "ollama", model: "gemma4:26b" }, seed: sdHash(sr.id + ep.id) % 100000,
    scenes,
  };
}
function buildWizardPlan() {
  const w = state.wizard;
  const g = genreById(w.genre);
  const sr = {
    series_version: 1, id: "sr-" + uid(), title: w.idea.trim().slice(0, 18) || t("project.untitled"),
    genre_template: g.id, style_bible: Object.assign({}, g.style),
    characters: w.chars.map((c, i) => Object.assign({}, c, { id: "c" + (i + 1) })),
    locations: [],
    episodes: w.outline.map((ep, i) => ({
      id: "ep" + (i + 1), seq: i + 1, title: tf("series.ep", { n: i + 1 }),
      logline: ep.logline, hook: ep.hook, status: i === 0 ? "draft" : "outline", plan_id: i === 0 ? "wiz-" + i : null,
    })),
  };
  const pl = arcPlanFor(sr, sr.episodes[0], w.duration, w.tier);
  state.seriesList.unshift(sr);
  state.activeSeriesId = sr.id;
  state.plans["wiz-0"] = pl;
  state.plan = pl;
  state.selectedScene = "";
}

function handleSdAction(el, ev) {
  const a = el.dataset.action;
  switch (a) {
    case "modeToggle": setMode(state.mode === "simple" ? "pro" : "simple"); return true;
    case "engineToggle": {
      const k = el.dataset.engine;
      state.engines[k] = !state.engines[k];
      renderPage();
      toast(t("engines." + k) + " · " + t(state.engines[k] ? "engines.online" : "engines.offline"), state.engines[k] ? "success" : "warn");
      return true;
    }
    case "engineAllLocal": {
      state.engines = { comfy: true, acestep: true, ollama: true };
      if (state.plan) {
        state.plan.bgm.type = "acestep_local";
        state.plan.llm = { provider: "ollama", model: "gemma4:26b" };
        state.plan.scenes.forEach((s) => { if (s.engine === "cloud_ai") { s.engine = "local_fl2v"; s.cost = { tier: "free", estimate_cny: 0, request_key: null }; } });
      }
      state.params.llmProvider = "ollama"; state.params.llmModel = "gemma4:26b";
      renderPage(); renderActionBar();
      toast(t("engines.allLocalDone"), "success");
      return true;
    }
    case "wizGo": { const s = +el.dataset.step; if (s <= state.wizard.step) { state.wizard.step = s; saveShell(); renderPage(); } return true; }
    case "wizBack": state.wizard.step = Math.max(1, state.wizard.step - 1); saveShell(); renderPage(); return true;
    case "wizNext": wizNext(); return true;
    case "wizGenre": state.wizard.genre = el.dataset.genre; renderPage(); return true;
    case "wizStepVal": {
      const p = el.dataset.path;
      const v = Math.max(+el.dataset.min, Math.min(+el.dataset.max, getPath(state, p) + (+el.dataset.delta)));
      setPath(state, p, v);
      if (p === "wizard.episodes") state.wizard.outline = [];
      renderPage();
      return true;
    }
    case "wizCharsExtract": wizCharsExtract(); return true;
    case "wizCharAdd": {
      const w = state.wizard;
      w.chars.push({ id: "c" + (w.chars.length + 1), name: state.lang === "zh" ? "新角色" : "New role", role: "support", persona: "", appearance: "", voice: "zh-CN-YunxiNeural", seed: 900000 + Math.floor(Math.random() * 9999), reference_images: ["ref-1"], lora: null });
      renderPage();
      return true;
    }
    case "wizCharDelete": { const rm = state.wizard.chars.splice(+el.dataset.idx, 1)[0]; renderPage(); toast(t("wizard.charDeleted") + ": " + rm.name, "info"); return true; }
    case "wizCharRegen": { const c = state.wizard.chars[+el.dataset.idx]; if (c) { c.seed = 900000 + Math.floor(Math.random() * 9999); renderPage(); toast(t("wizard.charRegenDone"), "success"); } return true; }
    case "wizEpAdd": { const w = state.wizard; w.outline.push({ id: "ep" + (w.outline.length + 1), logline: "", hook: "" }); w.episodes = w.outline.length; renderPage(); return true; }
    case "wizEpDelete": { const w = state.wizard; w.outline.splice(+el.dataset.idx, 1); w.episodes = w.outline.length; renderPage(); return true; }
    case "wizBoardGen": {
      const w = state.wizard;
      if (w.boardBusy) return true;
      w.boardBusy = true; renderPage();
      if (wizTimer) clearTimeout(wizTimer);
      wizTimer = setTimeout(() => {
        buildWizardPlan();
        w.planReady = true; w.boardBusy = false;
        if (state.activePage === "wizard") renderPage();
        toast(t("wizard.boardDone"), "success");
      }, 1400);
      return true;
    }
    case "wizTier": state.wizard.tier = el.dataset.tier; if (state.plan && state.wizard.planReady) state.plan.quality_tier = el.dataset.tier; renderPage(); return true;
    case "wizStart": {
      if (!state.wizard.planReady) { toast(t("wizard.needPlan"), "warn"); return true; }
      state.plan.quality_tier = state.wizard.tier;
      startPlanRun();
      return true;
    }
    case "wizardOpenPlan": state.mode = "pro"; saveShell(); renderTopbar(); go("plan"); return true;
    case "seriesOpen": state.activeSeriesId = el.dataset.id; state.seriesView = "detail"; state.seriesTab = "episodes"; renderPage(); return true;
    case "seriesBack": state.seriesView = "library"; renderPage(); return true;
    case "seriesNew": state.wizard.step = 1; state.wizard.planReady = false; go("wizard"); return true;
    case "seriesTab": state.seriesTab = el.dataset.tab; renderPage(); return true;
    case "seriesCharOpen": state.seriesView = "detail"; state.seriesTab = "characters"; go("series"); return true;
    case "charListen": toast(t("audio.previewHint") + " · " + el.dataset.id, "info"); return true;
    case "epOpen": {
      const sr = activeSeries();
      const ep = sr && sr.episodes.find((e) => e.id === el.dataset.id);
      if (ep && ep.plan_id && state.plans[ep.plan_id]) {
        state.plan = state.plans[ep.plan_id];
        state.selectedScene = "";
        go("plan");
        toast(t("series.epOpened") + ": " + ep.title, "success");
      }
      return true;
    }
    case "epNext": {
      const sr = activeSeries();
      const ep = sr && sr.episodes.find((e) => e.id === el.dataset.id);
      if (!ep || ep.plan_id) return true;
      toast(t("series.epNextBusy"), "info");
      setTimeout(() => {
        const pl = arcPlanFor(sr, ep, 60, "draft");
        state.plans[ep.id] = pl;
        ep.plan_id = ep.id; ep.status = "draft";
        state.plan = pl; state.selectedScene = "";
        go("plan");
        toast(t("series.epNextDone") + ": " + ep.title, "success");
      }, 1200);
      return true;
    }
    default: return handleSdPlanAction(el, ev);
  }
}

/* ============================================================
   Short-drama plan actions — storyboard editing & local engine sims
   ============================================================ */
function refreshSceneDrawer() {
  if (!$("#drawer").classList.contains("open")) return;
  if (!$("#drawerTitle").textContent.startsWith(t("plan.drawerTitle"))) return;
  const sc = sceneById(state.drawerScene);
  if (!sc) { closeDrawer(); return; }
  $("#drawerTitle").textContent = t("plan.drawerTitle") + " · " + sc.order;
  $("#drawerBody").innerHTML = sceneDrawerHtml(sc);
}
function openSceneDrawer(id) {
  const sc = sceneById(id);
  if (!sc) return;
  state.drawerScene = id;
  openDrawer(t("plan.drawerTitle") + " · " + sc.order, sceneDrawerHtml(sc));
}
function ensureCandidates(sc) {
  if (!sc.material.candidates.length) {
    sc.material.candidates = [1, 2, 3].map((n) => ({
      id: "px-" + (5000 + (sdHash(sc.id + n) % 4000)),
      label: (sc.keywords[0] || "footage") + " " + n,
      seed: sc.id + "-cand-" + n,
    }));
  }
  if (!sc.material.selected) sc.material.selected = sc.material.candidates[0].id;
  sc.material.source = "pexels";
  sc.material.in = 0;
  sc.material.out = sc.est_duration;
}
function handleSdPlanAction(el, ev) {
  const a = el.dataset.action;
  const id = el.dataset.id;
  const sc = id ? sceneById(id) : null;
  switch (a) {
    case "planTier": state.plan.quality_tier = el.dataset.tier; renderPage(); return true;
    case "aiPlan": aiPlanGenerate(); return true;
    case "planExport":
      downloadJSON("script-plan.json", { schema: "changofilm.script_plan", version: 1, exported_at: new Date().toISOString(), plan: state.plan });
      toast(t("plan.exported"), "success");
      return true;
    case "planImport": $("#planImportFile").click(); return true;
    case "planConfirm": startPlanRun(); return true;
    case "sceneSelect": state.selectedScene = id; renderPage(); return true;
    case "sceneDetails": state.selectedScene = id; renderPage(); openSceneDrawer(id); return true;
    case "sceneLock":
      if (!sc) return true;
      sc.locked = !sc.locked;
      toast(t(sc.locked ? "plan.locked" : "plan.unlocked"), sc.locked ? "info" : "success");
      renderPage(); refreshSceneDrawer();
      return true;
    case "sceneRegen":
      if (!sc) return true;
      if (sc.locked) { toast(t("plan.regenLocked"), "warn"); return true; }
      regenScene(sc, false);
      toast(t("plan.regenDone"), "success");
      renderPage(); refreshSceneDrawer();
      return true;
    case "sceneSwap": {
      if (!sc || !sc.material.candidates.length) return true;
      const cs = sc.material.candidates;
      const i = cs.findIndex((c) => c.id === sc.material.selected);
      sc.material.selected = cs[(i + 1) % cs.length].id;
      sc.boundary_health = "unknown";
      toast(t("plan.swapped"), "success");
      renderPage(); refreshSceneDrawer();
      return true;
    }
    case "scenePickCand":
      if (!sc) return true;
      sc.material.selected = el.dataset.cand;
      sc.boundary_health = "unknown";
      renderPage(); refreshSceneDrawer();
      return true;
    case "sceneDegrade":
      if (!sc) return true;
      sc.engine = "stock";
      sc.keyframe.shared_with_prev = false;
      ensureCandidates(sc);
      if (sc.transition_to_next === "none") sc.transition_to_next = "fade";
      sc.boundary_health = "unknown";
      sc.cost = { tier: "free", estimate_cny: 0, request_key: null };
      toast(t("plan.degraded"), "info");
      renderPage(); refreshSceneDrawer();
      return true;
    case "kfGen": kfGenerate(id, el.dataset.which || "pair"); return true;
    default: return false;
  }
}
function handleSdBind(el, path, value) {
  if (path.startsWith("seriesList.")) { if (el.dataset.rerender) renderPage(); return; }
  if (!path.startsWith("plan.")) return; /* wizard / series / engines: plain state edits */
  const m = path.match(/^plan\.scenes\.(\d+)\.(.+)$/);
  if (m) {
    const sc = planScenes()[+m[1]];
    if (!sc) return;
    const f = m[2];
    if (f === "narration") {
      sc.est_duration = estFromText(value);
      const i = planScenes().indexOf(sc);
      document.querySelectorAll(`[data-bind="plan.scenes.${i}.est_duration"]`).forEach((inp) => { if (inp !== document.activeElement) inp.value = sc.est_duration; });
      document.querySelectorAll(`[data-bind="${path}"]`).forEach((x) => { if (x !== el) x.value = value; });
      updatePlanMeter();
      return;
    }
    if (f === "est_duration") {
      sc.est_duration = Math.max(2, Math.min(60, value || 2));
      updatePlanMeter();
      return;
    }
    if (f === "engine") {
      sc.cost = { tier: sceneCost(sc) > 0 ? "paid" : "free", estimate_cny: sceneCost(sc), request_key: null };
      if (sc.engine === "stock") { sc.keyframe.shared_with_prev = false; ensureCandidates(sc); }
      sc.boundary_health = sc.engine === "stock" ? "unknown" : sc.keyframe.shared_with_prev ? "ok" : "unknown";
      renderPage(); refreshSceneDrawer();
      return;
    }
    if (f === "transition_to_next" || f === "relation_to_prev") { renderPage(); refreshSceneDrawer(); return; }
    if (f === "material.in" || f === "material.out") { sc.boundary_health = "unknown"; return; }
    if (f === "visual") {
      document.querySelectorAll(`[data-bind="${path}"]`).forEach((x) => { if (x !== el) x.value = value; });
      return;
    }
    if (f.startsWith("keyframe.")) { refreshSceneDrawer(); return; }
    return;
  }
  if (["plan.bgm.type", "plan.bgm.fade_in", "plan.bgm.fade_out", "plan.voice.name"].includes(path)) renderPage();
}

/* regeneration variant pools — bilingual, relation-aware, id-preserving */
const REGEN_VARIANTS = {
  establish: [
    { zh: { n: "夜色压城，{c}站在故事的起点，身后是没有退路的灯火。", v: "城市夜景大全景，{c}背影立于霓虹街头" },
      en: { n: "Night presses on the city. {c} stands at the story's start, lights behind offering no retreat.", v: "Wide city nightscape, back view of {c} under neon" } },
    { zh: { n: "凌晨的末班车进站，{c}数着口袋里最后的硬币，故事从这里开始。", v: "地铁站台冷光，{c}侧脸与进站列车" },
      en: { n: "The last train pulls in. {c} counts the final coins in a pocket — the story starts here.", v: "Cold subway platform light, profile of {c} and arriving train" } },
  ],
  continue: [
    { zh: { n: "顺着上一幕的视线，{c}推开了那扇本不该打开的门。", v: "承接上段尾帧构图，{c}推门手部特写" },
      en: { n: "Following the last shot's eyeline, {c} pushes open a door that should have stayed shut.", v: "Matching prev last-frame composition, close-up of {c}'s hand on the door" } },
    { zh: { n: "同一盏灯下，{c}把线索摊开在桌面，答案近得让人心慌。", v: "同场景桌面俯拍，线索纸张与台灯光斑" },
      en: { n: "Under the same lamp, {c} spreads the clues on the desk — the answer is unnervingly close.", v: "Same-location top-down desk shot, clue papers in lamplight" } },
  ],
  contrast: [
    { zh: { n: "城市依旧车水马龙，没有人知道{c}的这一夜有多漫长。", v: "城市车流延时大全景，与人物孤灯形成反差" },
      en: { n: "The city flows on, traffic unchanged — no one knows how long {c}'s night has been.", v: "City traffic timelapse wide shot, contrasting the lone lamp" } },
    { zh: { n: "橱窗里是别人的庆功宴，橱窗外是{c}没吃完的冷便当。", v: "暖色橱窗与冷色街道的对切构图" },
      en: { n: "Inside the window, someone else's celebration; outside, {c}'s cold unfinished bento.", v: "Warm shop window cross-cut against the cold street" } },
  ],
  escalate: [
    { zh: { n: "{c}把犹豫折好放进口袋：这一次，筹码押自己。", v: "雨窗特写，{c}落笔签名，笔尖压出折痕" },
      en: { n: "{c} folds the hesitation into a pocket: this time, the bet is on herself.", v: "Rainy window close-up, {c} signing, pen tip pressing a crease" } },
    { zh: { n: "倒计时只剩七十二小时，{c}拨通了那个最不想拨的号码。", v: "手机屏幕倒计时特写，{c}拇指悬在拨号键上" },
      en: { n: "Seventy-two hours left. {c} dials the number she least wanted to call.", v: "Phone countdown close-up, thumb of {c} hovering over the call key" } },
  ],
  match_cut: [
    { zh: { n: "坠落的工牌翻转成霓虹里的瞳孔——{c}的故事，才刚刚开场。", v: "工牌坠落轨迹匹配眼部推进，霓虹入瞳" },
      en: { n: "The falling badge flips into an iris full of neon — {c}'s story has only just begun.", v: "Falling badge match-cuts to a push-in on the eye, neon in the iris" } },
    { zh: { n: "合上的方案与亮起的招标屏叠成同一帧，{c}笑了。", v: "方案合页动作匹配屏幕亮起，同构图叠化" },
      en: { n: "The closing proposal and the lighting bid screen fold into one frame — {c} smiles.", v: "Proposal closing match-cuts to the screen lighting up, same composition" } },
  ],
  unknown: [
    { zh: { n: "{c}停下脚步，这一段的关联还待复核——先留下一个悬念。", v: "{c}驻足回望，构图留白待导演确认" },
      en: { n: "{c} stops — this link is pending review, so leave a cliffhanger here.", v: "{c} pauses and looks back, negative space awaiting the director" } },
  ],
};
function regenScene(sc, silent) {
  const pool = REGEN_VARIANTS[sc.relation_to_prev] || REGEN_VARIANTS.continue;
  const v = pool[(sdHash(sc.id + ":" + state.plan.revision) + (silent ? 0 : 1)) % pool.length];
  const L = v[state.lang === "en" ? "en" : "zh"] || v.zh;
  const c = charById(sc.characters[0]);
  const lead = c ? c.name : (state.lang === "zh" ? "主角" : "the lead");
  const fill = (s) => s.split("{c}").join(lead);
  sc.narration = fill(L.n);
  sc.visual = fill(L.v);
  sc.est_duration = estFromText(sc.narration);
  sc.measured_duration = null;
  if (sc.engine !== "stock") {
    const tag = sc.id + "-r" + state.plan.revision;
    if (!sc.keyframe.shared_with_prev) sc.keyframe.first = tag + "-f";
    sc.keyframe.last = tag + "-l";
    sc.keyframe.first_prompt = sc.keyframe.shared_with_prev ? (state.lang === "zh" ? "（共享上段尾帧）" : "(shared prev last frame)") : fill(L.v);
    sc.keyframe.last_prompt = fill(L.v);
    sc.boundary_health = sc.keyframe.shared_with_prev ? "ok" : "unknown";
    sc.cost.request_key = null;
  } else {
    sc.boundary_health = "unknown";
  }
  if (!silent) { state.plan.revision++; state.plan.status = "draft"; }
}
function aiPlanGenerate() {
  if (state.planBusy.active) return;
  if (!state.plan) {
    const sr = activeSeries();
    const ep = sr.episodes.find((e) => !e.plan_id) || sr.episodes[0];
    const pl = arcPlanFor(sr, ep, 60, "draft");
    state.plans[ep.id] = pl;
    ep.plan_id = ep.id;
    state.plan = pl;
    state.selectedScene = "";
  }
  const busy = state.planBusy;
  busy.active = true; busy.revealed = 0; busy.logs = [];
  const scenes = planScenes();
  const log = (lv, msg) => { busy.logs.push({ lv, msg }); };
  if (state.engines.ollama) log("info", t("plan.genOllama"));
  else log("warn", t("plan.genFallback"));
  log("info", t("plan.genOutline"));
  renderPage();
  let i = 0;
  if (planTimer) clearInterval(planTimer);
  planTimer = setInterval(() => {
    const sc = scenes[i];
    if (sc.locked) log("warn", tf("plan.genLockedSkip", { a: sc.order }));
    else { log("info", tf("plan.genScene", { a: i + 1, b: scenes.length })); regenScene(sc, true); }
    busy.revealed = i + 1;
    i++;
    if (i >= scenes.length) {
      clearInterval(planTimer); planTimer = null;
      busy.active = false;
      state.plan.revision++;
      state.plan.status = "draft";
      log("ok", t("plan.genDone"));
      renderPage();
      toast(t("plan.genDone"), "success");
    } else renderPage();
  }, 650);
}
function kfGenerate(id, which) {
  const sc = sceneById(id);
  if (!sc) return;
  if (!state.engines.comfy) { toast(t("plan.kfOffline"), "warn"); return; }
  const keys = which === "pair" ? [id + ":first", id + ":last"] : [id + ":" + which];
  if (state.kfBusy[id] || keys.some((k) => state.kfBusy[k])) return;
  const steps = state.plan.quality_tier === "final" ? 8 : 4;
  const setBusy = (label) => {
    keys.forEach((k) => { state.kfBusy[k] = { label }; });
    if (which === "pair") state.kfBusy[id] = { label };
    renderPage(); refreshSceneDrawer();
  };
  const clearBusy = () => { keys.forEach((k) => { delete state.kfBusy[k]; }); delete state.kfBusy[id]; };
  const cached = which !== "pair" && sc.cost.request_key && sc.keyframe[which];
  if (cached) {
    setBusy(t("plan.kfCache"));
    kfTimers[id] = setTimeout(() => { clearBusy(); renderPage(); refreshSceneDrawer(); toast(t("plan.kfCache"), "success"); }, 500);
    return;
  }
  setBusy(tf("plan.kfQueue", { n: 1 + (sdHash(id) % 3) }));
  let step = 0;
  const tick = () => {
    step++;
    if (step <= steps) {
      setBusy(tf("plan.kfStep", { a: step, b: steps }));
      kfTimers[id] = setTimeout(tick, 260);
      return;
    }
    const tag = id + "-k" + Date.now().toString(16).slice(-5);
    if ((which === "pair" || which === "first") && !sc.keyframe.shared_with_prev) sc.keyframe.first = tag + "-f";
    if (which === "pair" || which === "last") sc.keyframe.last = tag + "-l";
    sc.cost.request_key = sdHash(tag).toString(16).slice(0, 6);
    sc.boundary_health = sc.keyframe.shared_with_prev ? "ok" : "unknown";
    clearBusy();
    renderPage(); refreshSceneDrawer();
    toast(t("plan.kfDone"), "success");
  };
  kfTimers[id] = setTimeout(tick, 600);
}
function reorderScenes(fromId, toId) {
  const ss = planScenes();
  const fi = ss.findIndex((s) => s.id === fromId), ti = ss.findIndex((s) => s.id === toId);
  if (fi < 0 || ti < 0 || fi === ti) return;
  const [moved] = ss.splice(fi, 1);
  ss.splice(ti, 0, moved);
  ss.forEach((s, i) => { s.order = i + 1; });
  const lo = Math.min(fi, ti), hi = Math.max(fi, ti);
  for (let i = Math.max(1, lo); i <= Math.min(ss.length - 1, hi + 1); i++) {
    ss[i].relation_to_prev = "unknown";
    ss[i].relation_note = "";
    ss[i].boundary_health = "unknown";
  }
  ss[0].relation_to_prev = "establish";
  ss.forEach((s, i) => {
    if (!s.keyframe.shared_with_prev) return;
    const pv = i > 0 ? ss[i - 1] : null;
    if (!pv || !pv.engine.startsWith("local") || !s.engine.startsWith("local")) s.keyframe.shared_with_prev = false;
  });
  state.plan.revision++;
  state.plan.status = "draft";
  toast(t("plan.reordered"), "info");
  renderPage(); refreshSceneDrawer();
}

/* drag reorder + plan import (short-drama specific listeners) */
function bindSdEvents() {
  const imp = $("#planImportFile");
  if (imp) imp.addEventListener("change", () => {
    const f = imp.files && imp.files[0];
    imp.value = "";
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const raw = JSON.parse(String(reader.result));
        const pl = raw && raw.schema === "changofilm.script_plan" ? raw.plan : raw;
        if (!pl || pl.plan_version !== 1 || !Array.isArray(pl.scenes) || !pl.scenes.length) throw new Error("bad plan");
        pl.scenes = pl.scenes.map((s, i) => mkScene(s.id || "s" + (i + 1), i + 1, s));
        pl.revision = (pl.revision || 0) + 1;
        pl.status = "draft";
        state.plan = pl;
        if (pl.episode_id) state.plans[pl.episode_id] = pl;
        state.selectedScene = "";
        renderPage();
        toast(t("plan.imported"), "success");
      } catch (e) { toast(t("plan.importBad"), "error"); }
    };
    reader.readAsText(f);
  });
  let dragScene = null, dragEp = null;
  const clearDrag = () => {
    dragScene = null; dragEp = null;
    document.querySelectorAll(".dragging").forEach((x) => x.classList.remove("dragging"));
  };
  document.addEventListener("dragstart", (ev) => {
    const el = ev.target;
    if (!el || !el.closest) return;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT") { ev.preventDefault(); return; }
    const sc = el.closest("[data-drag-scene]");
    const ep = el.closest("[data-drag-ep]");
    if (sc && state.activePage === "plan") {
      dragScene = sc.dataset.dragScene;
      ev.dataTransfer.effectAllowed = "move";
      try { ev.dataTransfer.setData("text/plain", dragScene); } catch (e) { /* headless */ }
      sc.classList.add("dragging");
    } else if (ep) {
      dragEp = +ep.dataset.dragEp;
      ev.dataTransfer.effectAllowed = "move";
      try { ev.dataTransfer.setData("text/plain", String(dragEp)); } catch (e) { /* headless */ }
      ep.classList.add("dragging");
    }
  });
  document.addEventListener("dragover", (ev) => {
    if (dragScene === null && dragEp === null) return;
    const el = ev.target;
    if (!el || !el.closest) return;
    if ((dragScene !== null && el.closest("[data-drag-scene]")) || (dragEp !== null && el.closest("[data-drag-ep]"))) {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "move";
    }
  });
  document.addEventListener("drop", (ev) => {
    const el = ev.target;
    if (dragScene !== null) {
      ev.preventDefault();
      const from = dragScene;
      const target = el && el.closest ? el.closest("[data-drag-scene]") : null;
      clearDrag();
      if (target && target.dataset.dragScene !== from) reorderScenes(from, target.dataset.dragScene);
    } else if (dragEp !== null) {
      ev.preventDefault();
      const from = dragEp;
      const target = el && el.closest ? el.closest("[data-drag-ep]") : null;
      clearDrag();
      if (target && +target.dataset.dragEp !== from) {
        const arr = state.wizard.outline;
        const [m] = arr.splice(from, 1);
        arr.splice(+target.dataset.dragEp, 0, m);
        renderPage();
      }
    }
  });
  document.addEventListener("dragend", clearDrag);
}

/* ---------------- plan-driven generation ---------------- */
function startPlanRun() {
  const pl = state.plan;
  if (!pl) { toast(t("plan.confirmNeed"), "warn"); return; }
  if (state.run.status === "running") return;
  const empty = pl.scenes.find((s) => !String(s.narration || "").trim());
  if (empty) {
    toast(tf("plan.needNarration", { a: empty.order }), "warn");
    state.selectedScene = empty.id;
    go("plan");
    return;
  }
  const offline = pl.scenes.find((s) => s.engine.startsWith("local") && !engineOnline(s.engine));
  if (offline) {
    toast(t("plan.localOffline"), "warn");
    state.selectedScene = offline.id;
    go("plan");
    return;
  }
  const launch = () => {
    /* a completed project is locked — a confirmed plan always starts a fresh draft */
    if (isLocked()) {
      const nid = uid();
      state.tasks.unshift({ id: nid, subject: "", state: "draft", createdAt: Date.now(), updatedAt: Date.now(), source: "pexels", videos: 1, duration: "00:42", params: defaultParams() });
      state.currentProjectId = nid;
      state.params = defaultParams();
      state.baseline = JSON.stringify(state.params);
      state.dirty = false;
    }
    pl.status = "confirmed";
    pl.revision++;
    const sr = state.seriesList.find((x) => x.id === pl.series_id);
    const ep = sr && sr.episodes.find((e) => e.id === pl.episode_id);
    if (ep) ep.status = "confirmed";
    /* sync legacy params so shell chips / action bar reflect the plan */
    const p = state.params;
    p.subject = pl.title;
    p.script = pl.scenes.map((s) => s.narration).join("\n");
    p.voiceMode = "tts"; p.voiceName = pl.voice.name; p.ttsServer = "edge";
    p.aspect = pl.aspect === "9:16" ? "portrait" : "landscape";
    p.bgmType = pl.bgm.type === "none" ? "none" : pl.bgm.type === "custom" ? "custom" : "random";
    p.bgmVolume = pl.bgm.volume;
    p.videoSource = "pexels"; p.chargeConfirmed = true; p.subtitleEnabled = true;
    p.llmProvider = "ollama"; p.llmModel = pl.llm.model;
    state.run.planMode = true;
    toast(t("plan.confirmed"), "success");
    startRun();
    if (state.activePage === "plan") renderPage();
  };
  const paid = pl.scenes.filter((s) => sceneCost(s) > 0);
  if (paid.length) {
    const cost = paid.reduce((a, s) => a + sceneCost(s), 0);
    openModal(t("plan.paidTitle"), `<p>${esc(tf("plan.paidBody", { n: paid.length, c: cost.toFixed(1) }))}</p>`, [
      { label: t("plan.paidGo"), cls: "btn-primary", fn: launch },
      { label: t("project.cancel"), cls: "btn-ghost", fn: null },
    ]);
    return;
  }
  launch();
}
function buildPlanSteps(fail) {
  const pl = state.plan;
  const scenes = pl.scenes;
  const S = [];
  const add = (ph, lv, z, e, pg) => S.push({ ph, lv, zh: z, en: e, pg });
  const id = state.run.taskId;
  const tierRes = pl.quality_tier === "final" ? "1080×1920" : "768×1360 turbo";
  add("queued", "phase", t("phase.queued"), t("phase.queued"), 0);
  add(null, "info", `任务已加入队列 task_id=${id} · plan rev${pl.revision}`, `Task queued task_id=${id} · plan rev${pl.revision}`, 2);
  add("preparing", "phase", t("phase.preparing"), t("phase.preparing"), 4);
  add(null, "info", `加载已确认方案 script-plan.json（${scenes.length} 场景 · ${tierRes}）`, `Loading confirmed script-plan.json (${scenes.length} scenes · ${tierRes})`, 7);
  add(null, "ok", "方案校验通过：order 连续 / locked 段保护 / 时长容差 ±10%", "Plan validated: contiguous order / locked scenes / ±10% duration tolerance", 10);
  add("script", "phase", t("phase.script"), t("phase.script"), 12);
  add(null, "info", "方案已确认，按分镜执行（跳过自由文案生成）", "Plan confirmed — executing the storyboard (free-form script generation skipped)", 14);
  add(null, "info", `风格圣经注入每个 prompt：${pl.style.tone} · ${pl.style.palette}`, `Style bible injected into every prompt: ${pl.style.tone} · ${pl.style.palette}`, 16);
  add("audio", "phase", t("phase.audio"), t("phase.audio"), 18);
  if (pl.bgm.type === "acestep_local") {
    if (state.engines.acestep) {
      add(null, "info", "ACE-Step 本地作曲：模型预热（首次 ~300s，演示加速）", "ACE-Step local composition: model warmup (~300s first run, accelerated in demo)", 20);
      add(null, "info", `作曲中 · ${pl.bgm.prompt}`, `Composing · ${pl.bgm.prompt}`, 22);
      add(null, "ok", `BGM 完成 ${pl.target_duration}s · 淡入 ${pl.bgm.fade_in}s / 淡出 ${pl.bgm.fade_out}s`, `BGM done ${pl.target_duration}s · fade in ${pl.bgm.fade_in}s / out ${pl.bgm.fade_out}s`, 24);
    } else {
      add(null, "warn", "ACE-Step 离线：BGM 降级为随机曲库", "ACE-Step offline: BGM degraded to the random library", 24);
    }
  }
  add(null, "info", `整篇旁白一次 TTS · ${pl.voice.name}（保留 pause 契约）`, `Full narration in one TTS pass · ${pl.voice.name} (pause contract kept)`, 26);
  add(null, "info", "sub_maker cues 按场景旁白边界切分时间窗…", "Windowing sub_maker cues by scene narration boundaries…", 28);
  scenes.forEach((sc, i) => {
    add(null, "info", `场景 ${sc.order}/${scenes.length} 时间窗回填 · ${sc.est_duration}s`, `Scene ${sc.order}/${scenes.length} time window backfilled · ${sc.est_duration}s`, 28 + Math.round(((i + 1) / scenes.length) * 4));
  });
  add(null, "ok", "配音完成，实测总时长回填方案", "Narration done, measured total backfilled into the plan", 34);
  add("subtitle", "phase", t("phase.subtitle"), t("phase.subtitle"), 36);
  add(null, "info", "语音对齐，生成逐词时间戳…", "Aligning speech, word timestamps…", 38);
  const cueN = scenes.reduce((a, s) => a + Math.max(1, Math.ceil(s.narration.length / 12)), 0);
  add(null, "ok", `字幕回填 ${cueN} 条 cue → 各场景 subtitle_cues`, `Backfilled ${cueN} cues → per-scene subtitle_cues`, 40);
  add("materials", "phase", t("phase.materials"), t("phase.materials"), 42);
  const span = 46 / scenes.length;
  let failed = false;
  scenes.forEach((sc, i) => {
    if (failed) return;
    const base = 42 + span * i;
    const pg = (f) => Math.min(88, Math.round(base + span * f));
    add(null, "info", `场景 ${sc.order}/${scenes.length} · ${t("plan.engine." + sc.engine)} · ${sc.est_duration}s`, `Scene ${sc.order}/${scenes.length} · ${t("plan.engine." + sc.engine)} · ${sc.est_duration}s`, pg(0.1));
    if (sc.engine === "stock") {
      add(null, "info", `库存检索 [${sc.keywords.join(", ")}] → 绑定 ${sc.material.selected || "候选 1"} · in ${sc.material.in}s / out ${sc.material.out}s`, `Stock search [${sc.keywords.join(", ")}] → bound ${sc.material.selected || "candidate 1"} · in ${sc.material.in}s / out ${sc.material.out}s`, pg(0.5));
      if (fail && i === 1) {
        failed = true;
        add(null, "error", "素材下载失败：API 返回 401（Key 无效）", "Material download failed: API 401 (invalid key)", pg(0.6));
        add(null, "error", "任务终止，请检查素材来源配置", "Task aborted, check material source config", pg(0.6));
        S.push({ fail: true });
        return;
      }
      add(null, "ok", "素材下载完成，切点标记待审查", "Clip downloaded, boundary flagged for review", pg(0.9));
    } else if (sc.engine === "cloud_ai") {
      add(null, "info", `云端付费生成 ≈¥${sceneCost(sc).toFixed(1)}（已确认）`, `Cloud paid generation ≈¥${sceneCost(sc).toFixed(1)} (confirmed)`, pg(0.4));
      add(null, "ok", "云端片段回执 OK", "Cloud clip receipt OK", pg(0.9));
    } else {
      if (sc.cost.request_key) {
        add(null, "ok", `requestKey ${sc.cost.request_key} 命中缓存，直接复用`, `requestKey ${sc.cost.request_key} cache hit — reusing`, pg(0.3));
      } else {
        add(null, "info", `ComfyUI 排队：前方 ${1 + (sdHash(sc.id) % 3)} 个任务（单显卡串行）`, `ComfyUI queue: ${1 + (sdHash(sc.id) % 3)} ahead (single-GPU serial)`, pg(0.2));
        if (sc.keyframe.shared_with_prev) add(null, "info", "共享边界帧：上段尾帧 → 本段首帧条件化（FL2V）", "Shared boundary frame: prev last → this first conditioning (FL2V)", pg(0.35));
        add(null, "info", `IPAdapter 注入角色参考图 + 固定种子 · ${pl.style.consistency_subject}`, `IPAdapter character refs + fixed seed · ${pl.style.consistency_subject}`, pg(0.45));
        const steps = pl.quality_tier === "final" ? 8 : 4;
        add(null, "info", `KSampler ${Math.ceil(steps / 2)}/${steps} 步…`, `KSampler ${Math.ceil(steps / 2)}/${steps} steps…`, pg(0.6));
        add(null, "info", `KSampler ${steps}/${steps} 步 · 视频解码`, `KSampler ${steps}/${steps} steps · video decode`, pg(0.8));
      }
      add(null, "ok", `场景 ${sc.order} 片段就绪 · 边界帧差检测 ok`, `Scene ${sc.order} clip ready · boundary frame-diff ok`, pg(0.95));
    }
  });
  if (failed) return S;
  if (fail) {
    add(null, "error", "素材下载失败：API 返回 401（Key 无效）", "Material download failed: API 401 (invalid key)", 60);
    S.push({ fail: true });
    return S;
  }
  add(null, "ok", `素材准备完成（${scenes.length} 段全部按方案绑定）`, `Materials ready (${scenes.length} clips bound per plan)`, 90);
  add("rendering", "phase", t("phase.rendering"), t("phase.rendering"), 92);
  add(null, "info", `按方案时间线拼接（${pl.aspect} · ${tierRes}）`, `Concatenating per plan timeline (${pl.aspect} · ${tierRes})`, 94);
  scenes.forEach((sc, i) => {
    if (sc.transition_to_next !== "none" && i < scenes.length - 1) {
      add(null, "info", `转场 ${sc.order}→${sc.order + 1} · ${t("plan.trans." + sc.transition_to_next)}`, `Transition ${sc.order}→${sc.order + 1} · ${t("plan.trans." + sc.transition_to_next)}`, 95);
    }
  });
  add(null, "info", "混流封装 final-1.mp4", "Muxing final-1.mp4", 97);
  const warnScenes = scenes.filter((s) => s.engine === "stock");
  if (warnScenes.length) {
    add(null, "warn", `切点审查 scene_boundary_jump：场景 ${warnScenes.map((s) => s.order).join("/")} 库存素材边界突变风险，已用转场遮蔽`, `Boundary review scene_boundary_jump: scene ${warnScenes.map((s) => s.order).join("/")} stock boundary jump risk, masked by transitions`, 98);
  }
  add(null, "ok", "成片审查完成（逐场景回执已写入方案）", "Review finished (per-scene receipts written into the plan)", 99);
  S.push({ done: true, pg: 100 });
  return S;
}
function finishPlanRun() {
  const run = state.run;
  run.planMode = false;
  const pl = state.plan;
  if (!pl) return;
  pl.scenes.forEach((sc) => {
    const jitter = ((sdHash(sc.id + ":" + pl.revision) % 17) - 8) / 10;
    sc.measured_duration = Math.max(2, Math.round((sc.est_duration + jitter) * 10) / 10);
    sc.subtitle_cues = Math.max(1, Math.ceil(sc.narration.length / 12));
    sc.boundary_health = sc.engine === "stock" ? "warn" : "ok";
    if (sc.engine === "stock") sc.material.out = sc.measured_duration;
  });
  const total = planTotal();
  const dur = `${pad(Math.floor(total / 60))}:${pad(Math.floor(total % 60))}`;
  if (run.result) run.result.duration = dur;
  const proj = taskById(run.taskId);
  if (proj) proj.duration = dur;
  const sr = state.seriesList.find((x) => x.id === pl.series_id);
  const ep = sr && sr.episodes.find((e) => e.id === pl.episode_id);
  if (ep) ep.status = "rendered";
  pushLog("ok", `实测时长回填：${total}s（目标 ${pl.target_duration}s）· 剧集状态 → 已渲染`, `Measured durations backfilled: ${total}s (target ${pl.target_duration}s) · episode → rendered`);
}

/* ============================================================
   Event wiring
   ============================================================ */
function handleAction(el, ev) {
  const a = el.dataset.action;
  if (handleSdAction(el, ev)) return;
  switch (a) {
    case "nav": go(el.dataset.page); break;
    case "navCollapse": toggleNav(); break;
    case "genCollapse": case "genToggleMobile": toggleGen(); break;
    case "themeToggle": toggleTheme(); break;
    case "scrimClose": closeOverlays(); break;
    case "drawerClose": closeDrawer(); break;
    case "jumpLatest": {
      const well = $("#logWell");
      well.scrollTop = well.scrollHeight;
      logPinned = true;
      $("#jumpLatest").classList.remove("show");
      break;
    }
    case "failToggle":
      state.run.failMode = !state.run.failMode;
      renderGenStatic();
      toast(t("gen.fail") + (state.run.failMode ? " · ON" : " · OFF"), state.run.failMode ? "warn" : "info");
      break;
    case "generate": state.run.planMode = false; startRun(); break;
    case "projectMenu": state.projectMenuOpen ? closeProjectMenu() : openProjectMenu(); break;
    case "projectSave": saveProject(); break;
    case "projectSelect": {
      const id = el.dataset.id;
      closeProjectMenu();
      if (id !== state.currentProjectId) requestSwitch(() => loadProject(id, {}));
      break;
    }
    case "projectNew": closeProjectMenu(); newProject(); break;
    case "projectMore": state.projectLimit += 20; renderProjectMenu(); break;
    case "modalCancel": closeModal(); break;
    case "saveAsNew": saveAsNew(); break;
    case "presetMenu": state.presetMenuOpen = !state.presetMenuOpen; renderPage(); break;
    case "presetApply": applyPreset(el.dataset.id); break;
    case "presetSaveAs": presetSaveAs(); break;
    case "presetDelete": presetDelete(el.dataset.id); break;
    case "presetExportOne": presetExportOne(el.dataset.id); break;
    case "presetLibExport": presetLibExport(); break;
    case "presetLibImport": $("#presetLibImportFile").click(); break;
    case "presetExport": presetExport(); break;
    case "presetImport": $("#presetImportFile").click(); break;
    case "aiScript": aiScriptGenerate(); break;
    case "resetPrompt":
      state.params.systemPrompt = DEFAULT_SYSTEM_PROMPT;
      markDirty();
      renderPage(); toast(t("script.promptReset"), "success");
      break;
    case "previewPrompt": {
      const p = state.params;
      const finalPrompt = p.systemPrompt + "\n\n" + (p.customRequirements ? p.customRequirements + "\n\n" : "") +
        (state.lang === "zh" ? `主题：${p.subject || "（未填写）"}\n段落数：${p.paragraphNumber}\n语言：${p.scriptLang || "自动检测"}` : `Subject: ${p.subject || "(empty)"}\nParagraphs: ${p.paragraphNumber}\nLanguage: ${p.scriptLang || "auto"}`);
      openDrawer(t("script.promptPreview"), `<div class="script-preview">${esc(finalPrompt)}</div>`);
      break;
    }
    case "voicePreview": voicePreviewToggle(); break;
    case "pickFile": { const inp = document.getElementById(el.dataset.target); if (inp) inp.click(); break; }
    case "segment": setPath(state, el.dataset.path, el.dataset.value); markDirty(); renderPage(); renderActionBar(); break;
    case "aspect": state.params.aspect = el.dataset.value; markDirty(); renderPage(); break;
    case "expander": {
      const exp = el.closest(".expander");
      const open = exp.classList.toggle("open");
      el.setAttribute("aria-expanded", String(open));
      break;
    }
    case "taskFilter": state.taskFilter = el.dataset.filter; renderPage(); break;
    case "taskPlay": taskPlay(el.dataset.id); break;
    case "taskLoad": taskLoad(el.dataset.id); break;
    case "taskFolder": toast(t("tasks.folderOpened"), "info"); break;
    case "taskDelete": taskDelete(el.dataset.id); break;
    case "republish": republish(el.dataset.id, el); break;
    case "subtitleReset":
      Object.assign(state.params, SUBTITLE_DEFAULTS);
      markDirty();
      renderPage(); renderActionBar(); toast(t("subtitle.resetDone"), "success");
      break;
    case "llmTest": llmTest(el.dataset.provider, el); break;
    case "llmSaveUse": llmSaveUse(el.dataset.provider); break;
    case "eye": {
      const inp = document.getElementById(el.dataset.target);
      if (inp) {
        const show = inp.type === "password";
        inp.type = show ? "text" : "password";
        el.innerHTML = icon(show ? "eyeOff" : "eye", 14);
      }
      break;
    }
    case "materialSave": toast(t("material.keySet"), "success"); break;
    case "materialUse":
      state.params.videoSource = el.dataset.source;
      state.params.chargeConfirmed = false;
      markDirty();
      renderPage(); renderActionBar(); toast(t("material.using") + ": " + sourceLabel(el.dataset.source), "success");
      break;
    case "channelLogin": channelLogin(el.dataset.platform); break;
    case "channelLogout":
      state.channels[el.dataset.platform] = false;
      renderPage(); toast(t("channels.notLoggedIn"), "info");
      break;
    case "cacheRefresh":
      state.cacheStats = { files: 100 + Math.floor(Math.random() * 60), sizeMB: 900 + Math.floor(Math.random() * 600), oldestDays: 5 + Math.floor(Math.random() * 15) };
      renderPage(); toast(t("settings.cacheRefreshed"), "info");
      break;
    case "cacheClean":
      state.cacheStats = { files: 0, sizeMB: 0, oldestDays: 0 };
      renderPage(); toast(t("settings.cacheCleaned"), "success");
      break;
    case "keysExport": keysExport(); break;
    case "keysImport": $("#keyImportFile").click(); break;
    case "downloadResult": toast(t("toast.downloaded"), "success"); break;
    case "viewTask": go("tasks"); break;
  }
}
function closeOverlays() {
  closeDrawer();
  let changed = false;
  if (window.innerWidth <= 1100 && !state.leftCollapsed) { state.leftCollapsed = true; changed = true; }
  if (window.innerWidth <= 1500 && !state.rightCollapsed) { state.rightCollapsed = true; changed = true; }
  if (changed) { applyShellClasses(); renderNav(); saveShell(); }
  updateScrim();
}

function handleBind(el) {
  const path = el.dataset.bind;
  if (!path) return;
  if (isLocked() && path.startsWith("params.")) return;
  let value;
  if (el.type === "checkbox") value = el.checked;
  else if (el.type === "range" || el.type === "number") value = parseFloat(el.value) || 0;
  else value = el.value;
  if (path === "params.videoCount") value = Math.max(1, Math.min(5, Math.round(value)));
  setPath(state, path, value);
  document.querySelectorAll(`[data-out="${path}"]`).forEach((out) => {
    out.textContent = fmtVal(value, out.dataset.fmt || el.dataset.fmt || "");
  });
  if (path.startsWith("wizard.") || path.startsWith("plan.") || path.startsWith("series.") || path.startsWith("seriesList.") || path.startsWith("engines.")) { handleSdBind(el, path, value); return; }
  const subKey = path.startsWith("params.") ? path.slice(7) : "";
  if (path === "previewText" || (subKey in SUBTITLE_DEFAULTS)) updateSubtitlePreview(path === "params.animation");
  if (["params.videoSource", "params.voiceMode", "params.voiceName", "params.subtitleEnabled", "params.videoCount"].includes(path)) renderActionBar();
  if (path === "taskSearch") renderTaskTable();
  if (path === "historyPlatform" || path === "historyResult") renderHistoryTable();
  if (path === "settings.hideLog") updateGenUI(false);
  if (path === "theme") { applyShellClasses(); renderTopbar(); saveShell(); }
  if (path === "lang") { setLang(value); return; }
  if (path.startsWith("params.")) markDirty();
  if (el.dataset.rerender) renderPage();
}

function handleFileInput(input) {
  const kind = input.dataset.file;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  if (kind === "audio") state.params.uploadedAudio = files[0].name;
  else if (kind === "bgm") state.params.uploadedBgm = files[0].name;
  else if (kind === "materials") state.params.uploadedMaterials = files.map((f) => f.name);
  input.value = "";
  markDirty();
  renderPage(); renderActionBar();
}

function bindEvents() {
  document.addEventListener("click", (ev) => {
    const mi = ev.target.closest("[data-modal-idx]");
    if (mi) {
      const a = modalActions[+mi.dataset.modalIdx];
      closeModal();
      if (a && a.fn) a.fn();
      return;
    }
    if (state.projectMenuOpen && !ev.target.closest(".project-switcher")) closeProjectMenu();
    if (state.presetMenuOpen && !ev.target.closest(".preset-dropdown")) {
      state.presetMenuOpen = false;
      if (state.activePage === "tasks") renderPage();
    }
    const el = ev.target.closest("[data-action]");
    if (el && !el.disabled) handleAction(el, ev);
  });
  document.addEventListener("input", (ev) => {
    const el = ev.target;
    if (!el.dataset || !el.dataset.bind) return;
    if (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "file") return;
    handleBind(el);
  });
  document.addEventListener("change", (ev) => {
    const el = ev.target;
    if (el.id === "langSelect") { setLang(el.value); return; }
    if (el.id === "presetImportFile") { if (el.files[0]) presetImport(el.files[0]); el.value = ""; return; }
    if (el.id === "presetLibImportFile") { if (el.files[0]) presetLibImport(el.files[0]); el.value = ""; return; }
    if (el.id === "keyImportFile") { if (el.files[0]) keysImport(el.files[0]); el.value = ""; return; }
    if (el.dataset && el.dataset.file) { handleFileInput(el); return; }
    if (!el.dataset || !el.dataset.bind) return;
    if (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "number") handleBind(el);
  });
  $("#logWell").addEventListener("scroll", () => {
    const well = $("#logWell");
    logPinned = well.scrollTop + well.clientHeight >= well.scrollHeight - 30;
    $("#jumpLatest").classList.toggle("show", !logPinned && state.run.logs.length > 0);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.ctrlKey && !ev.shiftKey && !ev.altKey && (ev.key === "b" || ev.key === "B")) { ev.preventDefault(); toggleNav(); }
    else if (ev.ctrlKey && !ev.shiftKey && !ev.altKey && (ev.key === "j" || ev.key === "J")) { ev.preventDefault(); toggleGen(); }
    else if (ev.key === "Escape") {
      if ($("#modal").classList.contains("open")) closeModal();
      else if (state.projectMenuOpen) closeProjectMenu();
      else if (state.presetMenuOpen) { state.presetMenuOpen = false; if (state.activePage === "tasks") renderPage(); }
      else if ($("#drawer").classList.contains("open")) closeDrawer();
      else closeOverlays();
    }
  });
  const mqGen = window.matchMedia("(max-width: 1500px)");
  const mqNav = window.matchMedia("(max-width: 1100px)");
  const onMq = () => {
    let changed = false;
    if (mqGen.matches && !state.rightCollapsed) { state.rightCollapsed = true; changed = true; }
    if (mqNav.matches && !state.leftCollapsed) { state.leftCollapsed = true; changed = true; }
    if (changed) { applyShellClasses(); renderNav(); saveShell(); }
    updateScrim();
  };
  if (mqGen.addEventListener) { mqGen.addEventListener("change", onMq); mqNav.addEventListener("change", onMq); }
  else { mqGen.addListener(onMq); mqNav.addListener(onMq); }
  window.addEventListener("resize", updateScrim);
}

/* ---------------- init ---------------- */
function init() {
  seed();
  loadShell();
  if (!PAGES[state.activePage]) state.activePage = state.settings.defaultPage || "script";
  if (window.innerWidth <= 1500) state.rightCollapsed = true;
  if (window.innerWidth <= 1100) state.leftCollapsed = true;
  /* start on a fresh blank draft project — params are bound to it from the first edit */
  const pid = uid();
  state.tasks.unshift({
    id: pid, subject: "", state: "draft", createdAt: Date.now(), updatedAt: Date.now(),
    source: "pexels", videos: 1, duration: "00:42", params: defaultParams(),
  });
  state.currentProjectId = pid;
  state.params = defaultParams();
  ensureLlmDefaults();
  state.baseline = JSON.stringify(state.params);
  applyShellClasses();
  renderNav(); renderTopbar(); renderTabbar(); renderActionBar(); renderGenStatic();
  renderPage();
  updateGenUI(true);
  bindEvents();
  bindSdEvents();
}
init();
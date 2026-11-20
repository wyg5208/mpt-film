/* ============================================================
   MoneyPrinterTurbo · Three-Column Studio Console — demo app
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
}

/* ---------------- persistence ---------------- */
const LS_KEY = "mpt-ui-demo-shell";
function saveShell() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      lang: state.lang, theme: state.theme, activePage: state.activePage,
      leftCollapsed: state.leftCollapsed, rightCollapsed: state.rightCollapsed,
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
  } catch (e) { /* ignore */ }
}

/* ---------------- navigation registry ---------------- */
const PAGES = {
  tasks: { icon: "tasks", group: "create" },
  script: { icon: "script", group: "create" },
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
const NAV_ORDER = ["tasks", "script", "audio", "video", "subtitle", "history", "channels", "llm", "material", "presets", "settings"];

function processingCount() {
  return state.tasks.filter((x) => x.state === "processing").length;
}

/* ---------------- shell rendering ---------------- */
function renderNav() {
  const groups = { create: [], publish: [], config: [] };
  NAV_ORDER.forEach((id) => groups[PAGES[id].group].push(id));
  let html = "";
  for (const g of ["create", "publish", "config"]) {
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
  downloadJSON("mpt-preset-" + pr.name.replace(/[\\/:*?"<>|\s]+/g, "_") + ".json", {
    schema: "mpt.param_preset", version: 1, exportedAt: new Date().toISOString(),
    name: pr.name, desc: pr.desc || "", params: pr.params,
  });
  toast(t("presets.exported") + ": " + pr.name, "success");
}
function presetLibExport() {
  downloadJSON("mpt-param-presets.json", {
    schema: "mpt.param_presets", version: 1, exportedAt: new Date().toISOString(),
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
  const ids = ["tasks", "script", "audio", "video", "subtitle"];
  $("#tabbar").innerHTML = ids.map((id) =>
    `<button data-action="nav" data-page="${id}" class="${state.activePage === id ? "active" : ""}">${icon(PAGES[id].icon, 19)}<span>${esc(t("nav." + id))}</span></button>`
  ).join("");
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

/* ---------------- page dispatcher ---------------- */
const PAGE_RENDERERS = {
  tasks: pageTasks, script: pageScript, audio: pageAudio, video: pageVideo, subtitle: pageSubtitle,
  history: pageHistory, llm: pageLlm, material: pageMaterial, channels: pageChannels, presets: pagePresets, settings: pageSettings,
};
const LOCK_PAGES = ["script", "audio", "video", "subtitle"];
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
  state.run.steps = buildSteps(state.run.failMode);
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
  downloadJSON("mpt-settings-preset.json", {
    schema: "mpt.settings_preset", version: 1, exportedAt: new Date().toISOString(),
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
  downloadJSON("mpt-api-keys.json", { schema: "mpt.api_keys", version: 1, providerKeys: state.params.providerKeys });
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
   Event wiring
   ============================================================ */
function handleAction(el, ev) {
  const a = el.dataset.action;
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
    case "generate": startRun(); break;
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
}
init();
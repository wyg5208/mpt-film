"""服务能力目录：平台、能力标签与真实接线映射。

这里集中保存跨 WebUI 服务商配置页、任务预检和备用源转移共用的稳定元数据：
每个平台覆盖哪些具体服务（LLM Provider、素材来源、配音、音乐），以及该平台
真实接线的能力。能力只声明当前代码已经接线的部分，不虚标未实现的能力；
"怎么调用"仍由服务层适配器负责。

分组顺序遵循产品口径：国内厂商 → 本地与免费引擎 → 国际主流 → 聚合/推广平台。
"""

from dataclasses import dataclass

# 能力常量（真实接线的能力集合）。
CAP_TEXT = "text"              # 文字生成（脚本/关键词/分镜方案）
CAP_IMAGE_GEN = "image_gen"    # 图片生成（文生图，含订阅引擎）
CAP_T2V = "t2v"                # 文生视频
CAP_I2V = "i2v"                # 图生视频（首帧驱动）
CAP_TTS = "tts"                # 配音（文本转语音）
CAP_MUSIC = "music"            # 背景音乐
CAP_STOCK_VIDEO = "stock_video"  # 库存视频
CAP_STOCK_IMAGE = "stock_image"  # 库存图片

# 能力 → i18n key（WebUI 展示用）。
CAPABILITY_LABEL_KEYS = {
    CAP_TEXT: "Capability Text",
    CAP_IMAGE_GEN: "Capability Image Gen",
    CAP_T2V: "Capability Text To Video",
    CAP_I2V: "Capability Image To Video",
    CAP_TTS: "Capability TTS",
    CAP_MUSIC: "Capability Music",
    CAP_STOCK_VIDEO: "Capability Stock Video",
    CAP_STOCK_IMAGE: "Capability Stock Image",
}

# 平台分组（展示顺序即元组顺序）。
GROUP_DOMESTIC = "domestic"          # 国内厂商
GROUP_LOCAL = "local"                # 本地与免费引擎
GROUP_INTERNATIONAL = "international"  # 国际主流
GROUP_AGGREGATOR = "aggregator"      # 聚合/推广平台

GROUP_LABEL_KEYS = {
    GROUP_DOMESTIC: "Platform Group Domestic",
    GROUP_LOCAL: "Platform Group Local",
    GROUP_INTERNATIONAL: "Platform Group International",
    GROUP_AGGREGATOR: "Platform Group Aggregator",
}
PLATFORM_GROUP_ORDER = (
    GROUP_DOMESTIC,
    GROUP_LOCAL,
    GROUP_INTERNATIONAL,
    GROUP_AGGREGATOR,
)


@dataclass(frozen=True, slots=True)
class ServicePlatform:
    """一个对外可见的服务平台及其在本产品中的真实接线。"""

    platform_id: str
    default_label: str
    group: str
    capabilities: tuple[str, ...] = ()
    llm_ids: tuple[str, ...] = ()
    material_ids: tuple[str, ...] = ()
    tts_ids: tuple[str, ...] = ()
    music_ids: tuple[str, ...] = ()

    @property
    def label_key(self) -> str:
        return f"platform_label.{self.platform_id}"

    @property
    def service_ids(self) -> tuple[str, ...]:
        return self.llm_ids + self.material_ids + self.tts_ids + self.music_ids


SERVICE_PLATFORMS = (
    # 国内厂商
    ServicePlatform(
        "metaso", "Metaso MiniMax", GROUP_DOMESTIC,
        capabilities=(CAP_T2V,),
        material_ids=("metaso_minimax",),
    ),
    ServicePlatform(
        "volcengine", "ByteDance VolcEngine", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT, CAP_T2V, CAP_I2V),
        llm_ids=("volcengine",),
        material_ids=("volcengine_seedance",),
    ),
    ServicePlatform(
        "minimax", "MiniMax", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT, CAP_T2V, CAP_TTS),
        llm_ids=("minimax",),
        tts_ids=("minimax-tts",),
    ),
    ServicePlatform(
        "qwen", "Alibaba Cloud Qwen", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT,),
        llm_ids=("qwen",),
    ),
    ServicePlatform(
        "kimi", "Kimi / Moonshot AI", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT,),
        llm_ids=("moonshot", "kimi_code"),
    ),
    ServicePlatform(
        "deepseek", "DeepSeek", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT,),
        llm_ids=("deepseek",),
    ),
    ServicePlatform(
        "xiaomi", "Xiaomi MiMo", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT, CAP_TTS),
        llm_ids=("mimo",),
        tts_ids=("mimo-tts",),
    ),
    ServicePlatform(
        "siliconflow", "SiliconFlow", GROUP_DOMESTIC,
        capabilities=(CAP_TTS,),
        tts_ids=("siliconflow",),
    ),
    ServicePlatform(
        "iflytek", "iFlytek Spark (Astron MaaS)", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT,),
        llm_ids=("iflytek",),
    ),
    ServicePlatform(
        "modelscope", "Alibaba ModelScope", GROUP_DOMESTIC,
        capabilities=(CAP_TEXT,),
        llm_ids=("modelscope",),
    ),
    ServicePlatform(
        "voxcpm", "VoxCPM (ModelBest)", GROUP_DOMESTIC,
        capabilities=(CAP_TTS,),
        tts_ids=("voxcpm",),
    ),
    # 本地与免费引擎
    ServicePlatform(
        "edge", "Edge TTS (Free)", GROUP_LOCAL,
        capabilities=(CAP_TTS,),
        tts_ids=("azure-tts-v1",),
    ),
    ServicePlatform(
        "ollama", "Ollama", GROUP_LOCAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("ollama",),
    ),
    ServicePlatform(
        "llamacpp", "llama.cpp (llama-server)", GROUP_LOCAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("llamacpp",),
    ),
    ServicePlatform(
        "comfyui", "ComfyUI (Local)", GROUP_LOCAL,
        capabilities=(CAP_IMAGE_GEN, CAP_T2V, CAP_I2V),
        material_ids=("local",),
    ),
    ServicePlatform(
        "chatterbox", "Chatterbox TTS (Self-hosted)", GROUP_LOCAL,
        capabilities=(CAP_TTS,),
        tts_ids=("chatterbox",),
    ),
    ServicePlatform(
        "kokoro", "Kokoro TTS (Self-hosted)", GROUP_LOCAL,
        capabilities=(CAP_TTS,),
        tts_ids=("kokoro",),
    ),
    # 国际主流
    ServicePlatform(
        "openai", "OpenAI / ChatGPT / Codex", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT, CAP_IMAGE_GEN),
        llm_ids=("openai", "openai_codex", "openai_chatgpt"),
        material_ids=("openai_image", "codex_image"),
    ),
    ServicePlatform(
        "anthropic", "Anthropic Claude", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("anthropic", "claude_code"),
    ),
    ServicePlatform(
        "google", "Google Gemini", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT, CAP_TTS),
        llm_ids=("gemini",),
        tts_ids=("gemini-tts",),
    ),
    ServicePlatform(
        "azure", "Microsoft Azure", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT, CAP_TTS),
        llm_ids=("azure",),
        tts_ids=("azure-tts-v2",),
    ),
    ServicePlatform(
        "xai", "xAI Grok", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("grok",),
    ),
    ServicePlatform(
        "groq", "Groq", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("groq",),
    ),
    ServicePlatform(
        "elevenlabs", "ElevenLabs", GROUP_INTERNATIONAL,
        capabilities=(CAP_TTS, CAP_MUSIC),
        tts_ids=("elevenlabs",),
        music_ids=("elevenlabs_music",),
    ),
    ServicePlatform(
        "sonilo", "Sonilo", GROUP_INTERNATIONAL,
        capabilities=(CAP_MUSIC,),
        music_ids=("sonilo",),
    ),
    ServicePlatform(
        "fishaudio", "Fish Audio", GROUP_INTERNATIONAL,
        capabilities=(CAP_TTS,),
        tts_ids=("fish_audio",),
    ),
    ServicePlatform(
        "pexels", "Pexels", GROUP_INTERNATIONAL,
        capabilities=(CAP_STOCK_VIDEO, CAP_STOCK_IMAGE),
        material_ids=("pexels", "pexels_image"),
    ),
    ServicePlatform(
        "pixabay", "Pixabay", GROUP_INTERNATIONAL,
        capabilities=(CAP_STOCK_VIDEO, CAP_STOCK_IMAGE),
        material_ids=("pixabay", "pixabay_image"),
    ),
    ServicePlatform(
        "coverr", "Coverr", GROUP_INTERNATIONAL,
        capabilities=(CAP_STOCK_VIDEO,),
        material_ids=("coverr",),
    ),
    ServicePlatform(
        "cloudflare", "Cloudflare AI Gateway", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("cloudflare",),
    ),
    ServicePlatform(
        "litellm", "LiteLLM / OneAPI", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("litellm", "oneapi"),
    ),
    ServicePlatform(
        "pollinations", "Pollinations AI", GROUP_INTERNATIONAL,
        capabilities=(CAP_TEXT,),
        llm_ids=("pollinations",),
    ),
    # 聚合/推广平台
    ServicePlatform(
        "shengsuanyun", "Shengsuan Cloud", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT, CAP_T2V),
        llm_ids=("shengsuanyun",),
        material_ids=("loomloom",),
    ),
    ServicePlatform(
        "ofox", "OFox AI", GROUP_AGGREGATOR,
        capabilities=(CAP_T2V,),
        material_ids=("ofox",),
    ),
    ServicePlatform(
        "infistar", "Infistar", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT, CAP_T2V),
        llm_ids=("infistar",),
        material_ids=("infistar",),
    ),
    ServicePlatform(
        "jalapeno", "Jalapeno Cloud", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT, CAP_T2V),
        llm_ids=("jalapeno",),
        material_ids=("jalapeno",),
    ),
    ServicePlatform(
        "wavespeed", "WaveSpeed AI", GROUP_AGGREGATOR,
        capabilities=(CAP_T2V,),
        material_ids=("wavespeed",),
    ),
    ServicePlatform(
        "muapi", "MuAPI", GROUP_AGGREGATOR,
        capabilities=(CAP_T2V,),
        material_ids=("muapi",),
    ),
    ServicePlatform(
        "muse_spark", "Muse Spark", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("muse_spark",),
    ),
    ServicePlatform(
        "apimart", "APIMart", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("apimart",),
    ),
    ServicePlatform(
        "aihubmix", "AIHubMix", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("aihubmix",),
    ),
    ServicePlatform(
        "aimlapi", "AIML API", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("aimlapi",),
    ),
    ServicePlatform(
        "evolink", "EvoLink", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("evolink",),
    ),
    ServicePlatform(
        "openrouter", "OpenRouter", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("openrouter",),
    ),
    ServicePlatform(
        "api_route", "API Route", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("api_route",),
    ),
    ServicePlatform(
        "fluxionai", "Fluxion AI", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("fluxionai",),
    ),
    ServicePlatform(
        "cheaperinference", "Cheaper Inference", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("cheaperinference",),
    ),
    ServicePlatform(
        "requesty", "Requesty", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("requesty",),
    ),
    ServicePlatform(
        "futureinfra", "FutureInfra", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("futureinfra",),
    ),
    ServicePlatform(
        "yapi", "Y-API", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("yapi",),
    ),
    ServicePlatform(
        "opper", "Opper", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("opper",),
    ),
    ServicePlatform(
        "onomeo", "onomeo", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("onomeo",),
    ),
    ServicePlatform(
        "empiriolabs", "EmpirioLabs AI", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("empiriolabs",),
    ),
    ServicePlatform(
        "runcrate", "Runcrate", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("runcrate",),
    ),
    ServicePlatform(
        "cloudgpu", "CloudGPU", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("cloudgpu",),
    ),
    ServicePlatform(
        "cheapaimodel", "cheapaimodel", GROUP_AGGREGATOR,
        capabilities=(CAP_TEXT,),
        llm_ids=("cheapaimodel",),
    ),
)

SERVICE_PLATFORMS_BY_ID = {platform.platform_id: platform for platform in SERVICE_PLATFORMS}

if len(SERVICE_PLATFORMS_BY_ID) != len(SERVICE_PLATFORMS):
    raise RuntimeError("duplicate service platform id in catalog")

# 素材能力分组：与 WebUI 的 VIDEO_SOURCE_GROUPS 业务顺序一致（不含 local）。
MATERIAL_CAPABILITY_GROUPS = {
    "ai_video": (
        "metaso_minimax", "ofox", "loomloom", "volcengine_seedance",
        "infistar", "jalapeno", "wavespeed", "muapi",
    ),
    "ai_image": ("openai_image", "codex_image"),
    "stock_video": ("pexels", "pixabay", "coverr"),
    "stock_image": ("pexels_image", "pixabay_image"),
}

# 每个 LLM Provider 的展示能力：当前全部真实接线为文字生成（见 capabilities_for_service）。

# 服务 ID 分属四个独立命名空间（LLM Provider / 素材来源 / 配音 / 音乐），
# 聚合平台的 LLM id 与素材 id 可能同名（如 infistar），因此按 (kind, id) 索引。
_PLATFORM_BY_SERVICE = {}
for _platform in SERVICE_PLATFORMS:
    for _kind, _ids in (
        ("llm", _platform.llm_ids),
        ("material", _platform.material_ids),
        ("tts", _platform.tts_ids),
        ("music", _platform.music_ids),
    ):
        for _service_id in _ids:
            _key = (_kind, _service_id)
            if _key in _PLATFORM_BY_SERVICE:
                raise RuntimeError(f"duplicate service id in catalog: {_key}")
            _PLATFORM_BY_SERVICE[_key] = _platform

# local（本地文件）不属于任何在线平台；comfyui 平台承载本地关键帧引擎。
_PLATFORM_BY_SERVICE[("material", "local")] = SERVICE_PLATFORMS_BY_ID["comfyui"]


def platform_for_service(service_id: str, kind: str = "material") -> ServicePlatform | None:
    """按具体服务 ID 与命名空间定位所属平台。"""
    return _PLATFORM_BY_SERVICE.get((kind, service_id))


def capabilities_for_service(service_id: str, kind: str = "material") -> tuple[str, ...]:
    """返回服务 ID 在本产品中的真实能力集合。"""
    platform = platform_for_service(service_id, kind)
    if platform is None:
        return ()
    if kind == "llm":
        return (CAP_TEXT,)
    if kind == "material":
        return tuple(
            capability
            for capability in platform.capabilities
            if capability in (CAP_IMAGE_GEN, CAP_T2V, CAP_I2V, CAP_STOCK_VIDEO, CAP_STOCK_IMAGE)
        )
    if kind == "tts":
        return (CAP_TTS,)
    if kind == "music":
        return (CAP_MUSIC,)
    return platform.capabilities


def material_capability_of_source(source_id: str) -> str | None:
    """素材来源所属的能力分组（ai_video/ai_image/stock_video/stock_image）。"""
    for group, sources in MATERIAL_CAPABILITY_GROUPS.items():
        if source_id in sources:
            return group
    return None

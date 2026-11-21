import hashlib
import html
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import requests
import contextlib
import streamlit as st
import streamlit.components.v1 as components
from loguru import logger
from pydantic import ValidationError
from streamlit_tour import Tour

# WebUI 作为独立入口运行时，需要让项目根目录优先于第三方依赖，
# 避免依赖中的同名 app 包遮蔽 ChangoFilm 自己的 app 包。
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir in sys.path:
    sys.path.remove(root_dir)
sys.path.insert(0, root_dir)

from app.config import config
from app.models import const
from app.models import service_catalog
from app.models.llm_provider import (
    DEFAULT_LLM_PROVIDER_ID,
    LLM_PROVIDER_REGISTRY,
    get_llm_provider,
    normalize_provider_override,
)
from app.models.schema import (
    ImageMotion,
    MaterialInfo,
    ScriptPlan,
    ScriptScene,
    Series,
    SeriesCharacter,
    SeriesEpisode,
    VideoAspect,
    VideoConcatMode,
    VideoFitMode,
    VideoParams,
    VideoTransitionMode,
    estimate_scene_duration,
)
from app.services import bgm as bgm_service
from app.services import material_upload as material_upload_service
from app.services import (
    cache_manager,
    comfy_local,
    llm,
    loomloom,
    material,
    metaso_minimax,
    muapi,
    infistar_video,
    jalapeno_video,
    ofox,
    plan_store,
    series_store,
    social_auto_upload,
    source_failover,
    subtitle,
    upload_post,
    video,
    volcengine_seedance,
    voice,
    webui_task,
)
from app.services import elevenlabs_music as elevenlabs_music_service
from app.services import sonilo as sonilo_service
from app.services import state as sm
from app.services import task as tm
from app.services import publish_history
from app.services import version_checker
from app.utils.logging_utils import (
    LOG_LEVELS,
    configure_terminal_logger,
    get_logging_options,
)
from app.utils import utils
from app.utils.request_logging import trace_http_call
from webui import brand_theme

st.set_page_config(
    page_title="ChangoFilm",
    page_icon=str(brand_theme.ICON_FILE),
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "About": "# ChangoFilm\nA local-first studio for professional series short "
        "dramas. Provide a topic or script and ChangoFilm produces the copy, "
        "visuals, voiceover, subtitles and music, then composes a finished "
        "episode on your own machine.",
    },
)


# Streamlit 1.59 会在页面右上角默认展示 Deploy、skills nudge 等平台入口。
# ChangoFilm 是面向终端用户的本地工具，这些入口会造成顶部大块空白，
# 也会让新用户误以为需要安装额外组件。这里统一隐藏 Streamlit 平台工具栏，
# 并压缩主容器顶部留白，只保留项目自己的标题、语言选择和业务设置区域。
style_file = Path(__file__).with_name("styles.css")
streamlit_style = f"<style>{style_file.read_text(encoding='utf-8')}</style>"
st.markdown(streamlit_style, unsafe_allow_html=True)
# 品牌主题层在站内样式之后注入：变量 + 结构覆盖，随会话主题控件即时生效。
brand_theme.inject()
# 定义资源目录
font_dir = utils.font_dir()
song_dir = utils.song_dir()
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml")
# 语言列表必须在会话状态初始化前可用，首次访问时才能把浏览器 locale 映射到
# 项目真正支持的语言；自动识别结果只进入当前会话，不修改全局配置。
locales = utils.load_locales(i18n_dir)
DEFAULT_CHATTERBOX_BASE_URL = "http://127.0.0.1:4123/v1"
DEFAULT_CHATTERBOX_MODEL = "chatterbox"
DEFAULT_CHATTERBOX_VOICES = ["default-Female"]
DEFAULT_KOKORO_BASE_URL = "http://127.0.0.1:8880/v1"
DEFAULT_KOKORO_MODEL = "kokoro"
# empty = ask the server for its voice list (GET {base_url}/audio/voices)
DEFAULT_KOKORO_VOICES: list[str] = []
DEFAULT_VOXCPM_BASE_URL = voice.VOXCPM_DEFAULT_BASE_URL
DEFAULT_VOXCPM_VOICE = voice.VOXCPM_DEFAULT_VOICE
VOXCPM_REFERENCE_AUDIO_SESSION_KEY = "voxcpm_reference_audio"
VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY = "voxcpm_reference_audio_error"
VOXCPM_PROMPT_AUDIO_SESSION_KEY = "voxcpm_prompt_audio"
VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY = "voxcpm_prompt_audio_error"
VOXCPM_PROMPT_TEXT_SESSION_KEY = "voxcpm_prompt_text_input"
VOXCPM_HIGH_FIDELITY_SESSION_KEY = "voxcpm_high_fidelity_enabled"
VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY = "voxcpm_separate_prompt_audio_enabled"
VOXCPM_PROMPT_EXAMPLE_MODE_SESSION_KEY = "voxcpm_prompt_example_mode"
ONBOARDING_TOUR_KEY = "changofilm-onboarding-v1"
CUSTOM_LLM_ENDPOINT_ID = "custom"
VOICE_MODE_TTS = "tts"
VOICE_MODE_UPLOAD = "upload"
VOICE_MODE_NONE = "none"
LOOMLOOM_MAX_POLL_FAILURES = 5
# WebUI 按素材能力分组展示视频来源，但底层仍保存原有 video_source 值。
# AI 视频组与设置页共用同一业务顺序：合作服务商优先，并按秘塔、OFox、胜算云、
# 火山引擎、无限星河排列；其余服务随后展示。这样两个入口的顺序一致，同时
# 不改变 config.toml、历史任务和 API 请求中的字段语义，旧用户无需迁移配置。
VIDEO_SOURCE_GROUPS = {
    "stock_video": ("pexels", "pixabay", "coverr"),
    "stock_image": ("pexels_image", "pixabay_image"),
    "ai_video": (
        "metaso_minimax",
        "ofox",
        "loomloom",
        "volcengine_seedance",
        "infistar",
        "jalapeno",
        "wavespeed",
        "muapi",
    ),
    "ai_image": ("openai_image", "codex_image"),
    "local": ("local",),
}
# Upload-Post 的 API Key 与发布用户分别在两个页面管理，并且发布用户名称
# 不等于登录邮箱。集中维护入口可以避免多语言文案各自硬编码 URL 后发生偏差，
# 也方便用户从 WebUI 直接完成首次配置和后续账号维护。
UPLOAD_POST_API_KEYS_URL = "https://app.upload-post.com/api-keys"
UPLOAD_POST_MANAGE_USERS_URL = "https://app.upload-post.com/manage-users"
# 国内发布通道（social-auto-upload）的平台展示名。品牌名保持原文，
# 不随界面语言翻译；任务卡发布徽标与设置页多选框共用同一份映射。
SOCIAL_PUBLISH_PLATFORM_LABELS = {
    "douyin": "抖音",
    "tencent": "视频号",
    "xiaohongshu": "小红书",
    "bilibili": "B站",
    "kuaishou": "快手",
    "weibo": "微博",
    "baijiahao": "百家号",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "youtube": "YouTube",
}
SAU_REPO_URL = "https://github.com/dreammis/social-auto-upload"
# 素材设置与视频来源说明共用推广入口，避免两个位置的链接参数不一致。
OFOX_REFERRAL_URL = (
    "https://ofox.ai/?utm_source=github"
    "&utm_medium=sponsorship&utm_content=moneyprinterturbo"
)
# “默认”是 WebUI 专用哨兵，不会写入 config.toml，也不会传给 FFmpeg。
# 后端在 video_codec 未配置时继续采用稳定的 libx264；单独保留该哨兵可以区分
# “跟随项目默认策略”和“用户明确固定 libx264”，便于未来安全调整默认策略。
DEFAULT_VIDEO_CODEC_OPTION = "__default__"
# LoomLoom 的能力接口只返回模型 ID 和展示名，不提供价格。这里仅维护用户确认过
# 的参考价，用于帮助选择模型；最终费用按实际模型调用结算。别名同时覆盖
# 当前展示名和常见模型 ID，未收录的新模型会自然返回空价格，不影响选择或报价。
LOOMLOOM_VIDEO_MODEL_PRICES = (
    (("veo31fast", "googleveo31fastpreview"), "￥0.700/秒", "￥0.700/秒"),
    (
        (
            "通义万相22图生视频fastlora",
            "通义万相22文生视频fastlora",
            "tongyiwanxiang22i2vfastlora",
            "tongyiwanxiang22t2vfastlora",
            "wanx22i2vfastlora",
            "wanx22t2vfastlora",
        ),
        "￥0.350–0.770/条",
        "￥0.350/条（480P）；￥0.770/条（720P）",
    ),
    (("即梦30文生视频720p", "jimeng30t2v720p"), "￥0.230/秒", "￥0.230/秒"),
    (("即梦30pro视频", "jimeng30pro视频", "jimeng30provideo"), "￥1.000/秒", "￥1.000/秒"),
    (("veo3", "googleveo3"), "￥1.400/秒", "￥1.400/秒"),
    (("veo31", "googleveo31"), "￥1.400/秒", "￥1.400/秒"),
    (
        ("klingv2", "可灵v2"),
        "￥10.00–20.00/条",
        "￥10.00/条（5 秒）；￥20.00/条（10 秒）",
    ),
    (
        ("klingv21master", "可灵v21master"),
        "￥10.00–20.00/条",
        "￥10.00/条（5 秒）；￥20.00/条（10 秒）",
    ),
    (
        ("viduq3pro",),
        "￥0.440–1.000/秒",
        "￥0.440/秒（540P）；￥0.940/秒（720P）；￥1.000/秒（1080P）",
    ),
)
DEFAULT_SUBTITLE_SETTINGS = {
    "subtitle_enabled": True,
    "font_name": "MicrosoftYaHeiBold.ttc",
    "subtitle_position": "bottom",
    "subtitle_display_mode": "sentence",
    "subtitle_animation": "none",
    "custom_position": 70.0,
    "text_fore_color": "#FFFFFF",
    "font_size": 60,
    "stroke_color": "#000000",
    "stroke_width": 1.5,
    "subtitle_background_enabled": False,
    "subtitle_background_color": "#000000",
    "rounded_subtitle_background": False,
}
LOCAL_MATERIAL_EXTENSIONS = set(material_upload_service.SUPPORTED_MATERIAL_EXTENSIONS)
CUSTOM_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
_FINAL_VIDEO_PATTERN = re.compile(
    r"^final-(?P<index>\d+)\.(?P<extension>mp4|mov|mkv|webm)$",
    re.IGNORECASE,
)
# 与 app/services/bgm.py、app/services/material_upload.py 的上传文件名规则共用
# 同一份清单：除路径分隔符与 Win32 非法字符外，还要移除所有控制符和会改变显示
# 形态的字符。此前只拦截 ord < 32（C0 控制符），漏掉了同一类问题的另一半：
# * C1 控制符 U+007F-U+009F：会原样进入下载文件名、日志和界面。
# * 双向文本控制符 U+200E/U+200F/U+202A-U+202E/U+2066-U+2069：U+202E 之后的
#   字符会被反向渲染，``holiday<U+202E>4pm`` 看起来像另一个扩展名。
# * U+2028/U+2029（Unicode 行/段分隔符）能在一行日志里制造视觉换行。
# 视频主题是用户自由输入的文本，可以直接粘贴这些字符，因此必须在这里过滤。
# 字符串不使用 r'' 前缀：``\\`` 表示要排除的反斜杠本身，``\x``/``\u`` 转义由
# Python 解析，避免把转义文本写进字符集。
_DOWNLOAD_FILENAME_INVALID_PATTERN = re.compile(
    "[<>:\"/\\\\|?*\\x00-\\x1f\\x7f-\\x9f"
    "\\u200e\\u200f\\u2028\\u2029\\u202a-\\u202e\\u2066-\\u2069]"
)
_WINDOWS_RESERVED_FILENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {
        f"{prefix}{number}"
        for prefix in ("COM", "LPT")
        for number in range(1, 10)
    }
    # Win32 还会把 Latin-1 上标数字 ¹、²、³ 识别为设备编号。虽然这类主题
    # 很少见，但仍会导致 Windows 下载失败，因此与普通数字保留名统一处理。
    | {
        f"{prefix}{number}"
        for prefix in ("COM", "LPT")
        for number in ("¹", "²", "³")
    }
)
_RUNTIME_CONFIG_SECTIONS = {
    "app": config.app,
    "azure": config.azure,
    "chatterbox": config.chatterbox,
    "kokoro": config.kokoro,
    "elevenlabs": config.elevenlabs,
    "minimax_tts": config.minimax_tts,
    "siliconflow": config.siliconflow,
    "fish_audio": config.fish_audio,
    "voxcpm": config.voxcpm,
    "ui": config.ui,
}
# 设置预设与密钥备份使用各自的文件标识。导入时先校验 schema 和版本，
# 避免把任务记录、config.toml 或其它 JSON 误当成本功能的导出文件。
SETTINGS_PRESET_SCHEMA = "changofilm.settings-preset"
SETTINGS_PRESET_VERSION = 1
SETTINGS_PRESET_FILE_NAME = "changofilm-settings.json"
KEY_BACKUP_SCHEMA = "changofilm.key-backup"
KEY_BACKUP_VERSION = 1
KEY_BACKUP_FILE_NAME = "changofilm-keys.json"
# Export files contain only settings or credentials, not media. Reject oversized
# uploads before decoding and parsing them in the Streamlit process.
MAX_SETTINGS_TRANSFER_BYTES = 2 * 1024 * 1024
# 预设只描述生成参数。素材、配音和配乐都是本机文件路径，预设通常要在另一台
# 机器或另一个容器里导入，带上这些路径只会指向不存在的文件。
PRESET_EXCLUDED_PARAM_KEYS = frozenset(
    {
        "video_materials",
        "custom_audio_file",
        "bgm_file",
    }
)
# 项目绑定：每个任务目录一份 params.json 生成参数快照。只有 params.json
# 而没有 script.json 的目录是“草稿”（保存过但尚未提交生成）。
PROJECT_PARAMS_SCHEMA = "changofilm.project-params"
PROJECT_PARAMS_VERSION = 1
PROJECT_PARAMS_FILE_NAME = "params.json"
# 品牌升级（MoneyPrinterTurbo → ChangoFilm）前导出的文件仍带旧 schema：
# 导入/读取时兼容旧标识，新导出一律写新标识，用户无需手工转换。
LEGACY_SETTINGS_PRESET_SCHEMA = "moneyprinterturbo.settings-preset"
LEGACY_KEY_BACKUP_SCHEMA = "moneyprinterturbo.key-backup"
LEGACY_PROJECT_PARAMS_SCHEMA = "moneyprinterturbo.project-params"
_LEGACY_SCHEMA_ALIASES = {
    SETTINGS_PRESET_SCHEMA: LEGACY_SETTINGS_PRESET_SCHEMA,
    KEY_BACKUP_SCHEMA: LEGACY_KEY_BACKUP_SCHEMA,
    PROJECT_PARAMS_SCHEMA: LEGACY_PROJECT_PARAMS_SCHEMA,
}
# 预设库：storage/presets 下的具名预设，复用设置预设的 schema，导出文件
# 可以直接在其它机器导入。内置预设是代码常量，不落盘、不可删除。
PRESET_LIBRARY_DIR_NAME = "presets"
BUILTIN_PRESETS = (
    (
        "builtin-knowledge",
        "Builtin Preset Knowledge",
        {
            "video_aspect": "9:16",
            "video_clip_duration": 5,
            "image_motion": "zoom",
            "subtitle_enabled": True,
            "bgm_type": "random",
            "bgm_volume": 0.2,
        },
    ),
    (
        "builtin-cinema",
        "Builtin Preset Cinema",
        {
            "video_aspect": "16:9",
            "video_clip_duration": 8,
            "video_transition_mode": "FadeIn",
            "image_motion": "zoom",
            "subtitle_enabled": False,
            "bgm_type": "random",
            "bgm_volume": 0.35,
        },
    ),
    (
        "builtin-vlog",
        "Builtin Preset Vlog",
        {
            "video_aspect": "9:16",
            "video_clip_duration": 6,
            "video_transition_mode": "Shuffle",
            "image_motion": "static",
            "subtitle_enabled": True,
            "bgm_type": "random",
            "bgm_volume": 0.25,
        },
    ),
    (
        "builtin-ambient",
        "Builtin Preset Ambient",
        {
            "video_aspect": "16:9",
            "video_clip_duration": 10,
            "video_transition_mode": "FadeOut",
            "image_motion": "zoom",
            "subtitle_enabled": False,
            "voice_name": "no-voice",
            "bgm_type": "random",
            "bgm_volume": 0.4,
        },
    ),
)
# 密钥按配置项名称后缀识别。新增 Provider 只要沿用现有命名，就会自动进入
# 备份，不需要再维护第二份密钥清单。
CREDENTIAL_KEY_SUFFIXES = (
    "api_key",
    "api_keys",
    "api_token",
    "access_key",
    "secret_key",
    "speech_key",
)
# 只恢复密钥而不恢复配套配置项时，凭据仍然不可用。这些配套项与密钥一起备份。
CREDENTIAL_COMPANION_KEYS = {
    # Azure 语音必须同时知道区域。
    "azure": ("speech_region",),
    # Provider 的额外字段由 Registry 声明，例如 Cloudflare AI Gateway 的
    # Account ID 和 Gateway ID。只恢复 API Key 而丢掉这些字段时，换到另一台
    # 机器后该 Provider 仍然无法调用。从 Registry 读取可以让以后新增的
    # Provider 自动进入备份，不需要在这里维护第二份字段清单。
    "app": tuple(
        provider.config_key(field.config_suffix)
        for provider in LLM_PROVIDER_REGISTRY
        for field in provider.extra_fields
    ),
}

NON_LLM_COMPANION_KEYS = {
    "app": ("upload_post_username",)
}
# 同一个密钥在不同面板可能使用各自的控件 key：音频面板直接编辑 Gemini 和
# MiMo 的 LLM 密钥。恢复备份时必须清除每一个别名，否则遗留的旧值
# 会在下一次 rerun 覆盖刚刚恢复的密钥。
CREDENTIAL_WIDGET_STATE_ALIASES = {
    ("app", "gemini_api_key"): ("gemini_tts_api_key_input",),
    ("app", "mimo_api_key"): ("mimo_tts_api_key_input",),
}
# ui 分区只保存界面偏好，不含任何凭据，备份时整体跳过。
KEY_BACKUP_EXCLUDED_SECTIONS = frozenset({"ui"})


# -----------------------------------------------------------------------------
# 启动配置、会话状态与本地化
# -----------------------------------------------------------------------------


def _set_runtime_config(section_name, key, value):
    """
    更新 WebUI 配置，但不等待正在生成视频的后台任务。

    后台任务结束前，配置层只保留同一配置项的最新值；任务释放配置锁时会自动
    应用并保存。页面控件值仍由 Streamlit session_state 维护，因此暂存期间的
    rerun 不会把用户刚输入的内容重置为旧配置。
    """
    config_section = _RUNTIME_CONFIG_SECTIONS[section_name]
    updated = config.update_config_nonblocking(config_section, key, value)
    if not updated:
        logger.debug(f"deferred WebUI config update: section={section_name}, key={key}")
    return updated


def _delete_runtime_config(section_name, key):
    """删除 WebUI 配置项；后台任务占用配置时延后执行。"""
    config_section = _RUNTIME_CONFIG_SECTIONS[section_name]
    deleted = config.delete_config_nonblocking(config_section, key)
    if not deleted:
        logger.debug(f"deferred WebUI config delete: section={section_name}, key={key}")
    return deleted


def _save_runtime_config():
    """请求保存 WebUI 配置；后台任务占用配置时立即返回。"""
    saved = config.try_save_config()
    if not saved:
        logger.debug("deferred WebUI config save until active task completes")
    return saved


def _saved_ui_choice(key, options, default, section=None):
    """读取一个持久化选择，并把旧配置或手工编辑的非法值降级为默认值。"""
    options = list(options)
    section = config.ui if section is None else section
    saved = section.get(key, default)
    numeric_default = isinstance(default, (int, float)) and not isinstance(
        default, bool
    )
    # bool 是 int 的子类，``True == 1``。手工把数值选项写成 TOML
    # 布尔值时必须拒绝，不能让它伪装成第一个数值 option。
    if numeric_default and isinstance(saved, bool):
        return default
    for option in options:
        if saved == option:
            # 返回 options 中的真实值，顺便把 TOML 1.0 等价归一化为
            # 整数选项 1，避免下游参数类型随配置写法漂移。
            return option

    # TOML 中的数值通常保留原类型；仍兼容用户手工写成字符串的情况。
    if numeric_default and isinstance(saved, str):
        try:
            converted = type(default)(saved)
        except (TypeError, ValueError):
            converted = None
        for option in options:
            if converted == option:
                return option
    return default


def _saved_ui_number(key, default, minimum, maximum, number_type=float):
    """读取并限幅持久化数值，避免非法配置破坏 Streamlit slider。"""
    try:
        saved = config.ui.get(key, default)
        if isinstance(saved, bool):
            raise ValueError("boolean is not a numeric setting")
        value = number_type(saved)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite value")
    except (TypeError, ValueError, OverflowError):
        value = default
    return min(maximum, max(minimum, value))


def _saved_ui_bool(key, default):
    """兼容 TOML 布尔值和常见手工字符串，拒绝含义不明的旧值。"""
    value = config.ui.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _saved_ui_color(key, default):
    """只把标准六位十六进制颜色传给 Streamlit color picker。"""
    value = str(config.ui.get(key, default) or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return default


def _saved_ui_text(key, default="", max_length=None):
    """读取持久化文本并遵守对应 WebUI 控件的长度上限。"""
    value = str(config.ui.get(key, default) or default)
    if max_length is not None:
        value = value[:max_length]
    return value


def _run_llm_read_operation(operation_name, operation):
    """
    使用稳定的当前 LLM 配置执行只读请求，并避免等待视频生成任务。

    能立即取得配置锁时继续沿用原来的互斥保护；锁已被后台视频任务持有时，
    全局配置在任务结束前不会发生变化，因此可以安全复制当前配置，并叠加页面
    尚未落盘的 Provider、模型和密钥。这样新文案使用界面中的最新选择，同时
    不会改变正在生成的视频任务。
    """
    with config.try_runtime_config_lock() as lock_acquired:
        # 配置层在复制全局值和叠加待更新值期间持有队列锁，因此快照只能看到
        # 更新前或更新后的完整状态，不会混用两组 Provider 参数。
        app_config_snapshot = config.snapshot_config_with_pending(config.app)
        if lock_acquired:
            return operation(app_config_snapshot)

    logger.info(
        f"run read-only LLM operation with active task configuration: "
        f"operation={operation_name}"
    )
    return operation(app_config_snapshot)


def _parse_chatterbox_voices(voices):
    # Chatterbox 是自托管服务，音色列表由用户在 WebUI 中手动输入。
    # 这里统一兼容 TOML 数组和输入框里的逗号分隔字符串，避免下拉框、
    # 试听按钮和后续生成流程使用不同格式导致状态不一致。
    if isinstance(voices, str):
        return [v.strip() for v in voices.split(",") if v.strip()]
    return [str(v).strip() for v in voices or [] if str(v).strip()]


def _sync_chatterbox_config_from_session_state():
    # Streamlit 的按钮会触发整页 rerun，而 Chatterbox 配置输入框位于
    # “试听语音合成”按钮之后。如果试听时只读取 config.chatterbox，可能拿不到
    # 用户刚在输入框里填入的 base_url/model/voices。先从 session_state 同步一次，
    # 可以保证按钮逻辑和输入框显示逻辑使用同一份最新配置。
    _set_runtime_config(
        "chatterbox",
        "base_url",
        (
            st.session_state.get(
                "chatterbox_base_url_input",
                config.chatterbox.get("base_url") or DEFAULT_CHATTERBOX_BASE_URL,
            )
            or ""
        ).strip(),
    )
    _set_runtime_config(
        "chatterbox",
        "api_key",
        st.session_state.get(
            "chatterbox_api_key_input", config.chatterbox.get("api_key", "")
        ),
    )
    _set_runtime_config(
        "chatterbox",
        "model_id",
        (
            st.session_state.get(
                "chatterbox_model_input",
                config.chatterbox.get("model_id") or DEFAULT_CHATTERBOX_MODEL,
            )
            or DEFAULT_CHATTERBOX_MODEL
        ).strip(),
    )
    _set_runtime_config(
        "chatterbox",
        "voices",
        _parse_chatterbox_voices(
            st.session_state.get(
                "chatterbox_voices_input",
                config.chatterbox.get("voices") or DEFAULT_CHATTERBOX_VOICES,
            )
        ),
    )


def _sync_kokoro_config_from_session_state():
    # 音色目录先于设置输入框渲染，先同步浏览器状态，确保本次 rerun 就使用
    # 新端点和手工音色配置，不必再操作一次控件。
    _set_runtime_config(
        "kokoro",
        "base_url",
        (
            st.session_state.get(
                "kokoro_base_url_input",
                config.kokoro.get("base_url") or DEFAULT_KOKORO_BASE_URL,
            )
            or ""
        ).strip(),
    )
    _set_runtime_config(
        "kokoro",
        "api_key",
        st.session_state.get(
            "kokoro_api_key_input", config.kokoro.get("api_key", "")
        ),
    )
    _set_runtime_config(
        "kokoro",
        "model_id",
        (
            st.session_state.get(
                "kokoro_model_input",
                config.kokoro.get("model_id") or DEFAULT_KOKORO_MODEL,
            )
            or DEFAULT_KOKORO_MODEL
        ).strip(),
    )
    _set_runtime_config(
        "kokoro",
        "voices",
        _parse_chatterbox_voices(
            st.session_state.get(
                "kokoro_voices_input",
                config.kokoro.get("voices") or DEFAULT_KOKORO_VOICES,
            )
        ),
    )


def _get_kokoro_voice_options(saved_voice_name: str) -> list[str]:
    """会话内短缓存远端目录，断线时保留上次选择，不把故障当成用户改音色。"""
    if config.kokoro.get("voices"):
        return voice.get_kokoro_voices()

    # 仅保留当前服务的一条缓存。更换端点/凭据立即重查，缓存不保存明文 Key；
    # 30 秒内的其他 UI 操作不重复阻塞 5 秒等待一个已知离线的服务。
    signature = (
        (config.kokoro.get("base_url") or "").strip().rstrip("/"),
        _credential_signature(config.kokoro.get("api_key", "")),
    )
    catalog = st.session_state.get("kokoro_voice_catalog", {})
    if catalog.get("signature") != signature:
        catalog = {"signature": signature, "voices": [], "checked_at": None}
    now = time.monotonic()
    if catalog["checked_at"] is None or now - catalog["checked_at"] >= 30:
        fetched = voice.get_kokoro_voices(fallback=False)
        catalog.update(checked_at=now, available=bool(fetched))
        if fetched:
            catalog["voices"] = fetched
        st.session_state["kokoro_voice_catalog"] = catalog

    options = list(catalog["voices"])
    if not catalog["available"]:
        st.warning(tr("Kokoro Voices Unavailable"))
        # 首次打开时可能没有缓存，仍保留配置文件中的真实选择；恢复连接后
        # 只有成功返回的新目录才能判定某个旧音色确实已被服务器删除。
        if voice.is_kokoro_voice(saved_voice_name) and saved_voice_name not in options:
            options.insert(0, saved_voice_name)
    return options or [f"kokoro:{voice.KOKORO_DEFAULT_VOICE}"]


def _detect_audio_mime(audio_file: str, audio_bytes: bytes) -> str:
    # 有些 OpenAI-compatible TTS 服务，例如 travisvn/chatterbox-tts-api，
    # 即使请求 response_format=mp3，也会返回 WAV 内容。WebUI 试听如果固定
    # 使用 audio/mp3，浏览器可能无法播放，因此这里按文件头识别真实格式。
    header = audio_bytes[:12]
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav"
    if header.startswith(b"ID3") or header[:2] in (
        b"\xff\xfb",
        b"\xff\xf3",
        b"\xff\xf2",
    ):
        return "audio/mp3"
    if header.startswith(b"OggS"):
        return "audio/ogg"
    ext = os.path.splitext(audio_file)[1].lower()
    return {
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mp3")


def _build_uploaded_file_path(uploaded_file, target_dir, allowed_extensions, prefix):
    """为浏览器上传文件生成受控的服务端保存路径。"""
    original_name = os.path.basename(str(uploaded_file.name or ""))
    extension = os.path.splitext(original_name)[1].lower()
    if extension not in allowed_extensions:
        logger.warning(
            f"reject unsupported uploaded file extension: {original_name or '<empty>'}"
        )
        raise ValueError("unsupported uploaded file type")

    normalized_target_dir = os.path.realpath(target_dir)
    os.makedirs(normalized_target_dir, exist_ok=True)
    # 不复用浏览器传入的文件名，避免路径分隔符、控制字符或同名覆盖。UUID 只用于
    # 服务端落盘，不改变用户在上传控件中看到的原始名称。
    file_path = os.path.realpath(
        os.path.join(normalized_target_dir, f"{prefix}-{uuid4().hex}{extension}")
    )
    if os.path.commonpath([normalized_target_dir, file_path]) != normalized_target_dir:
        logger.warning(f"invalid uploaded file path: {file_path}")
        raise ValueError("invalid uploaded file path")
    return file_path


def _save_uploaded_local_materials(uploaded_files):
    """Validate a WebUI material batch and undo earlier files on failure."""
    local_videos_dir = utils.storage_dir("local_videos", create=True)
    materials = []
    persisted = []
    saved_paths = []
    try:
        for uploaded_file in uploaded_files:
            stored_name = material_upload_service.save_material_upload(
                uploaded_file.name, uploaded_file
            )
            file_path = os.path.join(local_videos_dir, stored_name)
            saved_paths.append(file_path)
            material_info = MaterialInfo()
            material_info.provider = "local"
            material_info.url = file_path
            materials.append(material_info)
            persisted.append(
                {
                    "provider": material_info.provider,
                    "url": material_info.url,
                    "duration": material_info.duration,
                }
            )
    except Exception:
        for file_path in saved_paths:
            try:
                os.remove(file_path)
            except OSError as exc:
                logger.warning(
                    f"failed to remove local material after batch error: "
                    f"path={file_path}, error={exc}"
                )
        raise
    return materials, persisted


def _initialize_session_state():
    """集中初始化跨 rerun 保留的页面状态。"""
    if not st.session_state.get("cross_post_recovery_checked"):
        # WebUI 可以不经过 FastAPI 独立运行，因此也需要在首次会话初始化时处理
        # 进程重启留下的发布状态。恢复失败时不写标记，后续 rerun 会再次尝试。
        recovered = tm.recover_interrupted_cross_posts()
        if recovered is not None:
            st.session_state["cross_post_recovery_checked"] = True

    saved_ui_language = config.ui.get("language", "")
    browser_locale = st.context.locale
    initial_ui_language = utils.resolve_ui_language(
        saved_language=saved_ui_language,
        browser_locale=browser_locale,
        supported_languages=locales.keys(),
    )

    defaults = {
        "video_subject": "",
        "video_script": "",
        "video_terms": "",
        "paragraph_number_input": _saved_ui_number(
            "paragraph_number",
            1,
            llm.MIN_SCRIPT_PARAGRAPH_NUMBER,
            llm.MAX_SCRIPT_PARAGRAPH_NUMBER,
            int,
        ),
        "video_script_prompt": _saved_ui_text(
            "video_script_prompt",
            max_length=llm.MAX_SCRIPT_PROMPT_LENGTH,
        ),
        "custom_system_prompt": _saved_ui_text(
            "custom_system_prompt",
            llm.DEFAULT_SCRIPT_SYSTEM_PROMPT,
            llm.MAX_SCRIPT_SYSTEM_PROMPT_LENGTH,
        ),
        "match_materials_to_script": bool(
            config.app.get("match_materials_to_script", False)
        ),
        "custom_bgm_file_input": _saved_ui_text("custom_bgm_file"),
        "sonilo_bgm_prompt_input": _saved_ui_text(
            "sonilo_bgm_prompt",
            max_length=sonilo_service.MAX_PROMPT_LENGTH,
        ),
        "elevenlabs_music_prompt_input": _saved_ui_text(
            "elevenlabs_music_prompt",
            max_length=elevenlabs_music_service.MAX_PROMPT_LENGTH,
        ),
        "subtitle_enabled_checkbox": _saved_ui_bool("subtitle_enabled", True),
        "stroke_color_picker": _saved_ui_color("stroke_color", "#000000"),
        "stroke_width_slider": _saved_ui_number(
            "stroke_width", 1.5, 0.0, 10.0
        ),
        "loomloom_candidate_count": _saved_ui_number(
            "loomloom_candidate_count",
            3,
            1,
            loomloom.MAX_SCRIPT_CANDIDATES,
            int,
        ),
        "loomloom_script_duration_seconds": _saved_ui_number(
            "loomloom_script_duration_seconds", 60, 10, 600, int
        ),
        "ui_language": initial_ui_language,
        # 已落盘的本地素材允许用户只修改文案后继续复用。
        "local_video_materials": [],
        # 生成按钮回调先登记任务，使顶部入口能立即显示运行中数量。
        "active_generation_tasks": {},
        # 最近一次从当前页面提交的任务。生成改为后台执行后，页面 Fragment
        # 通过这个 ID 查询状态；刷新时不再依赖正在执行的旧页面脚本。
        "current_generation_task_id": "",
        # LoomLoom 询价与执行必须跨 Streamlit rerun 保留完全相同的输入和
        # clientRequestId，避免网络重试产生重复付费任务。
        "loomloom_script_batch": None,
        "loomloom_script_quote": None,
        "loomloom_script_input_signature": "",
        "loomloom_client_request_id": "",
        "loomloom_run_id": "",
        "loomloom_run_status": "",
        "loomloom_run_error": "",
        "loomloom_poll_failure_count": 0,
        "loomloom_poll_retry_after": 0.0,
        "loomloom_poll_paused": False,
        "loomloom_script_candidates": (),
        "loomloom_candidate_errors": (),
        "loomloom_selected_candidate": 0,
        "loomloom_video_batch": None,
        "loomloom_video_quote": None,
        "loomloom_video_input_signature": "",
        "loomloom_video_client_request_id": "",
        "loomloom_video_confirm_charge": False,
        "loomloom_video_quote_error_signature": "",
        "loomloom_video_quote_error": "",
        "loomloom_video_capability": None,
        "loomloom_video_capability_fingerprint": "",
        "loomloom_video_capability_load_attempt": "",
        "loomloom_video_capability_error": "",
        "loomloom_video_model_id": "",
        # 文案或完整配音刚生成时，在视频数量控件创建前消费这个摘要并自动
        # 填入推荐素材数；消费后即清空，避免覆盖用户后续手动调整。
        "loomloom_video_scene_autofill_digest": "",
        "wavespeed_confirm_charge": False,
        "volcengine_seedance_confirm_charge": False,
        "infistar_confirm_charge": False,
        "jalapeno_confirm_charge": False,
        "ofox_confirm_charge": False,
        "metaso_minimax_confirm_charge": False,
        "muapi_confirm_charge": False,
        # AI 视频按素材段计费，默认只生成一段，用户确认效果后再主动增加数量。
        "loomloom_video_scene_count": _saved_ui_number(
            "loomloom_video_scene_count",
            1,
            1,
            loomloom.MAX_VIDEO_SCENES,
            int,
        ),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


_initialize_session_state()


def tr(key):
    # AppTest 序列化控件时会在裸线程重调 format_func，此时会话态是全局
    # mock（无 ui_language）；用 .get 回退英文而不是 KeyError，保证
    # 已翻译 options 的 selectbox 在测试壳下也能正常序列化。
    loc = locales.get(st.session_state.get("ui_language", "en"), {})
    value = loc.get("Translation", {}).get(key)
    if value is not None:
        return value
    # 新功能优先维护中英文。其它语言缺少单项翻译时统一回退英文，避免在多个
    # locale 中复制相同英文后长期失去同步；英文也没有该键时才显示原始 key。
    return locales.get("en", {}).get("Translation", {}).get(key, key)


# -----------------------------------------------------------------------------
# 任务管理：历史扫描、运行状态、参数恢复与列表交互
# -----------------------------------------------------------------------------


def _format_task_time(timestamp):
    if not timestamp:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _format_task_subject(subject, max_length=30):
    subject = str(subject or "").replace("\n", " ").strip()
    if len(subject) <= max_length:
        return subject or "-"
    return f"{subject[:max_length]}..."


def _safe_load_task_script(task_path):
    script_file = os.path.join(task_path, "script.json")
    if not os.path.isfile(script_file):
        return {}

    try:
        with open(script_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            logger.warning(f"task script data is not an object: {script_file}")
            return {}
        return payload
    except Exception as e:
        logger.warning(f"failed to read task script data: {script_file}, {e}")
        return {}


def _find_final_task_video(task_path: str) -> str:
    """
    返回任务目录中序号最小的最终成片。

    合成流程还会产生 combined、temp-clip 和 MoviePy 临时文件，这些文件不能
    表示任务已成功完成，因此这里只接受 ``final-<序号>.<扩展名>``。
    """
    try:
        files = os.listdir(task_path)
    except OSError:
        return ""

    candidates = []
    for file_name in files:
        match = _FINAL_VIDEO_PATTERN.fullmatch(file_name)
        if match and os.path.isfile(os.path.join(task_path, file_name)):
            candidates.append((int(match.group("index")), file_name))

    if not candidates:
        return ""

    _, file_name = min(candidates, key=lambda item: item[0])
    return os.path.join(task_path, file_name)


def _build_restore_upload_requirements(params: Mapping) -> dict:
    """
    记录历史任务中无法由 Streamlit 自动恢复的上传文件依赖。

    浏览器不允许程序重新填充 file_uploader，因此恢复任务时需要单独记录本地
    素材和自定义音频依赖，并在用户重新生成前检查是否已经主动补充或替换。
    """
    return {
        "local_materials": params.get("video_source") == "local",
        "custom_audio": bool(params.get("custom_audio_file")),
        "original_voice_name": params.get("voice_name") or "",
    }


def _get_unmet_restore_upload_requirements(
    requirements: Mapping | None,
    *,
    video_source: str,
    voice_name: str,
    has_local_materials: bool,
    has_custom_audio: bool,
    voice_mode: str | None = None,
) -> set[str]:
    """返回当前表单仍未满足的历史上传文件依赖。"""
    requirements = requirements or {}
    unmet = set()

    if (
        requirements.get("local_materials")
        and video_source == "local"
        and not has_local_materials
    ):
        unmet.add("local_materials")

    if requirements.get("custom_audio") and not has_custom_audio:
        if voice_mode is not None:
            # 新版 WebUI 使用显式配音方式。用户切换到自动配音或无配音，表示
            # 已主动替换历史上传音频；只有继续选择上传模式时才要求重新上传。
            if voice_mode == VOICE_MODE_UPLOAD:
                unmet.add("custom_audio")
        elif voice_name == requirements.get("original_voice_name", ""):
            # 保留旧调用方按音色判断的兼容行为，避免影响 API 和已有测试工具。
            unmet.add("custom_audio")

    return unmet


def _queue_task_restore(task_id):
    # 任务列表运行在 fragment 中，不能直接修改已经创建的主表单控件状态。
    # 这里只记录候选任务并触发整页 rerun，确认和参数恢复由主页面统一处理。
    st.session_state["task_restore_candidate_id"] = task_id
    st.session_state["task_manager_popover_nonce"] = (
        st.session_state.get("task_manager_popover_nonce", 0) + 1
    )
    st.rerun(scope="app")


def _normalize_task_state(state):
    if state in (
        const.TASK_STATE_COMPLETE,
        const.TASK_STATE_FAILED,
        const.TASK_STATE_PROCESSING,
    ):
        return state
    try:
        return int(state)
    except (TypeError, ValueError):
        return state


def _active_generation_tasks():
    tasks = st.session_state.setdefault("active_generation_tasks", {})
    if not isinstance(tasks, dict):
        tasks = {}
        st.session_state["active_generation_tasks"] = tasks
    return tasks


def _add_active_generation_task(task_id, subject=None):
    tasks = _active_generation_tasks()
    task = tasks.setdefault(task_id, {})
    task["subject"] = subject or task.get("subject") or task_id
    task["mtime"] = task.get("mtime") or datetime.now().timestamp()


def _remove_active_generation_task(task_id):
    tasks = _active_generation_tasks()
    if task_id in tasks:
        del tasks[task_id]
    if st.session_state.get("pending_generation_task_id") == task_id:
        del st.session_state["pending_generation_task_id"]


def _prepare_generation_task():
    # st.button 的 on_click 会在页面脚本重新执行前触发。这里提前生成任务 ID，
    # 顶部任务管理入口就能在同一次 rerun 中显示“生成中”数量。
    current_id = _current_generation_task_id()
    if current_id and webui_task.is_generation_active(current_id):
        st.session_state["pending_generation_task_id"] = current_id
        return
    task_id = str(uuid4())
    st.session_state["pending_generation_task_id"] = task_id
    subject = st.session_state.get("video_subject") or st.session_state.get(
        "video_script"
    )
    _add_active_generation_task(task_id, subject=subject)


def _task_state_label(state, has_video):
    normalized_state = _normalize_task_state(state)
    if normalized_state == "draft":
        return tr("Task Status Draft")
    if normalized_state == const.TASK_STATE_COMPLETE:
        return tr("Task Status Complete")
    if normalized_state == const.TASK_STATE_FAILED:
        return tr("Task Status Failed")
    if normalized_state == const.TASK_STATE_PROCESSING:
        return tr("Task Status Processing")
    if has_video:
        return tr("Task Status Complete")
    return tr("Task Status History")


def _task_state_filter_key(task):
    normalized_state = _normalize_task_state(task.get("state"))
    if normalized_state == "draft":
        return "draft"
    if normalized_state == const.TASK_STATE_PROCESSING:
        return "processing"
    if normalized_state == const.TASK_STATE_FAILED:
        return "failed"
    if normalized_state == const.TASK_STATE_COMPLETE or task["video_file"]:
        return "complete"
    return "history"


def _cross_post_status_caption(task):
    """任务卡的发布状态徽标；未启用发布时返回 None，不影响旧渲染。"""
    state = task.get("cross_post_state")
    if not state:
        return None
    labels = {
        "pending": tr("Publish Pending"),
        "processing": tr("Publish Processing"),
        "complete": tr("Publish Complete"),
        "failed": tr("Publish Failed"),
    }
    text = labels.get(state, state)
    if state == "processing":
        # 进行中展示百分比与当前阶段，与生成进度一样可直观跟踪。
        progress = task.get("cross_post_progress")
        if isinstance(progress, (int, float)):
            text += f" {int(progress)}%"
        stage_labels = {
            "queued": tr("Publish Stage Queued"),
            "metadata": tr("Publish Stage Metadata"),
            "uploading": tr("Publish Stage Uploading"),
        }
        details = []
        platform = task.get("cross_post_platform")
        if platform:
            details.append(SOCIAL_PUBLISH_PLATFORM_LABELS.get(platform, platform))
        stage = stage_labels.get(task.get("cross_post_stage"))
        if stage:
            details.append(stage)
        if details:
            text += " · " + " · ".join(details)
    marks = []
    for entry in task.get("cross_post_results") or []:
        if not isinstance(entry, dict):
            continue
        platform = entry.get("platform")
        if not platform:
            continue
        label = SOCIAL_PUBLISH_PLATFORM_LABELS.get(platform, platform)
        marks.append(f"{label}{'✅' if entry.get('success') else '❌'}")
    if marks:
        text += " · " + " ".join(marks)
    if state == "failed":
        # 失败原因直接上任务卡：取错误尾部的最后一行（通常是异常消息），
        # 避免用户只能去翻控制台才能知道为什么失败。
        error = str(task.get("cross_post_error") or "").strip()
        if error:
            last_line = error.splitlines()[-1].strip()
            if len(last_line) > 120:
                last_line = last_line[:120] + "…"
            text += f" · {last_line}"
    return text


def _publish_channel_configured():
    """任一发布通道可用即允许手动触发；不要求 auto_upload 开关。"""
    return (
        social_auto_upload.social_auto_upload_service.is_configured()
        or upload_post.upload_post_service.is_configured()
    )


def _scan_history_tasks(limit=30):
    tasks_root = utils.task_dir()
    if not os.path.isdir(tasks_root):
        return []

    # 任务管理 fragment 每两秒刷新一次。先只读取低成本的目录元数据并截取最近
    # 的任务，再解析 script.json 和视频列表，避免历史任务很多时反复扫描全部内容。
    task_entries = []
    try:
        with os.scandir(tasks_root) as entries:
            for entry in entries:
                try:
                    if entry.name.startswith(".") or not entry.is_dir(
                        follow_symlinks=False
                    ):
                        continue
                    task_entries.append(
                        (
                            entry.stat(follow_symlinks=False).st_mtime,
                            entry.name,
                            entry.path,
                        )
                    )
                except OSError as e:
                    # 单个任务目录可能正在被删除，不应因此让整个任务面板失效。
                    logger.debug(f"skip unavailable task directory: {entry.path}, {e}")
    except OSError as e:
        logger.warning(f"failed to scan task directory: {tasks_root}, {e}")
        return []

    task_entries.sort(key=lambda item: item[0], reverse=True)
    tasks = []
    for mtime, name, task_path in task_entries[:limit]:
        script_data = _safe_load_task_script(task_path)
        params_data = script_data.get("params", {})
        if not isinstance(params_data, dict):
            params_data = {}
        script_text = script_data.get("script", "")
        if not isinstance(script_text, str):
            script_text = ""
        video_file = _find_final_task_video(task_path)
        # 草稿目录没有 script.json；只在确认为草稿时才读 params.json，
        # 避免给普通历史任务增加额外 IO。
        is_draft = not script_data and os.path.isfile(
            os.path.join(task_path, PROJECT_PARAMS_FILE_NAME)
        )
        subject = (
            params_data.get("video_subject")
            or script_text[:40]
            or name
        )
        if is_draft:
            draft_params = _read_project_params(name) or {}
            subject = draft_params.get("video_subject") or subject
        tasks.append(
            {
                "task_id": name,
                "subject": subject,
                "state": (
                    const.TASK_STATE_COMPLETE
                    if video_file
                    else ("draft" if is_draft else None)
                ),
                "progress": 100 if video_file else 0,
                "mtime": mtime,
                "task_path": task_path,
                "video_file": video_file,
                "source": "history",
            }
        )

    return tasks


def _collect_task_summaries(limit=20):
    history_tasks = {task["task_id"]: task for task in _scan_history_tasks(limit=50)}
    active_tasks = _active_generation_tasks()

    try:
        runtime_tasks, _ = sm.state.get_all_tasks(1, 50)
    except Exception as e:
        logger.warning(f"failed to load runtime tasks: {e}")
        runtime_tasks = []

    # The paginated state view can omit this session's newer tasks after 50
    # older records. Read those active IDs directly so a completed or failed
    # task cannot remain labelled as processing forever.
    runtime_ids = {task.get("task_id") for task in runtime_tasks}
    for task_id in active_tasks:
        if task_id in runtime_ids:
            continue
        try:
            task = sm.state.get_task(task_id)
        except Exception as e:
            logger.warning(f"failed to load active task {task_id}: {e}")
            continue
        if task:
            runtime_tasks.append(task)

    for task in runtime_tasks:
        task_id = task.get("task_id", "")
        if not task_id:
            continue

        task_path = os.path.join(utils.task_dir(), task_id)
        history_task = history_tasks.get(task_id, {})
        video_files = task.get("videos") or []
        video_file = (
            video_files[0] if video_files else history_task.get("video_file", "")
        )
        subject = (
            task.get("video_subject")
            or history_task.get("subject")
            or (task.get("script", "")[:40] if task.get("script") else "")
            or task_id
        )
        task_mtime = active_tasks.get(task_id, {}).get("mtime") or history_task.get(
            "mtime", 0
        )
        if os.path.isdir(task_path):
            try:
                task_mtime = os.path.getmtime(task_path)
            except OSError:
                # Another session can delete this directory between isdir and
                # getmtime. Keep rendering the persisted task state.
                pass

        history_tasks[task_id] = {
            "task_id": task_id,
            "subject": subject,
            "state": task.get("state"),
            "cross_post_state": task.get("cross_post_state"),
            "cross_post_results": task.get("cross_post_results"),
            "cross_post_error": task.get("cross_post_error"),
            "cross_post_progress": task.get("cross_post_progress"),
            "cross_post_stage": task.get("cross_post_stage"),
            "cross_post_platform": task.get("cross_post_platform"),
            "cross_post_platforms": task.get("cross_post_platforms"),
            "cross_post_log": task.get("cross_post_log"),
            "progress": int(task.get("progress", 0) or 0),
            "mtime": task_mtime,
            "task_path": task_path,
            "video_file": video_file,
            "source": "runtime",
        }

    for task_id, active_task in active_tasks.items():
        history_task = history_tasks.get(task_id, {})
        if history_task and _task_state_filter_key(history_task) in {
            "complete",
            "failed",
        }:
            # 会话中的 active 标记只负责覆盖任务刚提交到状态存储前的极短窗口。
            # 后台任务结束后必须以真实终态为准，不能把失败任务重新显示为生成中。
            continue

        task_path = os.path.join(utils.task_dir(), task_id)
        history_tasks[task_id] = {
            "task_id": task_id,
            "subject": active_task.get("subject")
            or history_task.get("subject")
            or task_id,
            "state": const.TASK_STATE_PROCESSING,
            "progress": history_task.get("progress", 0),
            "mtime": active_task.get("mtime")
            or history_task.get("mtime", datetime.now().timestamp()),
            "task_path": task_path,
            "video_file": history_task.get("video_file", ""),
            "source": "active",
        }

    tasks = list(history_tasks.values())
    return sorted(tasks, key=lambda item: item["mtime"], reverse=True)[:limit]


def _is_headless_server():
    # Docker 或无桌面的服务器部署中，WebUI 进程接触不到用户的桌面环境：
    # xdg-open / webbrowser 只会在容器内静默失败。此时应改为浏览器内预览
    # 视频、以路径提示代替打开目录。macOS/Windows 桌面部署不受影响。
    if sys.platform == "darwin" or sys.platform.startswith("win"):
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _open_task_path(task_path):
    tasks_root = os.path.abspath(utils.task_dir())
    normalized_path = os.path.abspath(task_path)
    if not normalized_path.startswith(tasks_root + os.sep):
        logger.warning(f"invalid task folder path: {normalized_path}")
        return
    if not os.path.isdir(normalized_path):
        return
    if _is_headless_server():
        # storage 目录通常以卷挂载映射回宿主机，提示相对路径即可定位文件。
        rel_path = os.path.relpath(normalized_path, os.path.dirname(tasks_root))
        st.toast(f"{tr('Open Task Folder')}: ./storage/{rel_path}", icon="📂")
        return
    webbrowser.open(f"file://{normalized_path}")


def _open_task_video(video_file):
    tasks_root = os.path.abspath(utils.task_dir())
    normalized_file = os.path.abspath(video_file)

    # 视频路径来自任务目录扫描或运行期状态。这里仍然限制只能打开任务目录
    # 内的文件，避免 UI 操作被异常路径扩展成任意本地文件打开能力。
    if not normalized_file.startswith(tasks_root + os.sep):
        logger.warning(f"invalid task video path: {normalized_file}")
        return
    if not os.path.isfile(normalized_file):
        logger.warning(f"task video does not exist: {normalized_file}")
        return

    if _is_headless_server():
        # 无桌面环境时在任务面板内嵌播放器预览，代替调用系统播放器。
        st.session_state["task_preview_video_file"] = normalized_file
        return

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", normalized_file])
        elif sys.platform.startswith("win"):
            os.startfile(normalized_file)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", normalized_file])
    except Exception as e:
        logger.error(f"failed to open task video: {normalized_file}, {e}")


def _delete_task(task_id, task_path, task_state=None):
    # 页面展示的状态可能落后于后台任务。删除前同时检查传入状态、当前会话的
    # 活跃任务和最新状态，避免任务刚开始或已产出中间视频时被误删。
    current_task = None
    try:
        current_task = sm.state.get_task(task_id)
    except Exception as e:
        logger.exception(f"failed to verify task state before deletion: {task_id}, {e}")
        return False

    task_snapshot = dict(current_task or {})
    task_snapshot.setdefault("state", task_state)
    if task_id in _active_generation_tasks():
        task_snapshot["state"] = const.TASK_STATE_PROCESSING

    if tm.is_task_busy(task_snapshot):
        logger.warning(f"refused to delete running task: {task_id}")
        return False

    tasks_root = os.path.abspath(utils.task_dir())
    normalized_path = os.path.abspath(task_path)

    # 删除任务会移除任务状态和本地生成文件。这里必须限定在 storage/tasks
    # 下，避免异常 task_path 造成误删其它本地目录。
    if not normalized_path.startswith(tasks_root + os.sep):
        logger.warning(f"invalid task folder path for deletion: {normalized_path}")
        return False

    try:
        if os.path.isdir(normalized_path):
            shutil.rmtree(normalized_path)
        # Keep the persisted task available for retry when file removal fails
        # (for example, a video is still locked by another process on Windows).
        if hasattr(sm.state, "delete_task"):
            sm.state.delete_task(task_id)
        logger.info(f"deleted task: {task_id}")
        return True
    except Exception as e:
        logger.exception(f"failed to delete task: {task_id}, {e}")
        return False


def _count_processing_tasks(tasks):
    # 顶部任务管理入口只需要展示“生成中”任务数量。
    # 这里复用内部状态 key 判断，避免依赖多语言展示文案导致不同语言下统计不一致。
    processing_task_ids = {
        task["task_id"]
        for task in tasks
        if _task_state_filter_key(task) == "processing"
    }
    return len(processing_task_ids)


def _task_manager_label(processing_count):
    label = tr("Task Manager")
    if processing_count <= 0:
        return label
    return f"{label} · {processing_count}"


def _build_video_download_name(subject, index, total):
    """根据视频主题生成跨平台安全的下载文件名。"""
    safe_subject = _DOWNLOAD_FILENAME_INVALID_PATTERN.sub(" ", str(subject or ""))
    safe_subject = re.sub(r"\s+", " ", safe_subject).strip(" .")[:80].rstrip(" .")
    if not safe_subject:
        safe_subject = "video"
    # Win32 在识别设备名时会忽略扩展名前的尾随空格和句点。与背景音乐上传
    # 的现有规则保持一致，避免 ``CON .topic`` 绕过保留名保护。
    windows_basename = safe_subject.split(".", 1)[0].rstrip(" .").upper()
    if windows_basename in _WINDOWS_RESERVED_FILENAMES:
        safe_subject = f"_{safe_subject}"

    suffix = f"-{index}" if total > 1 else ""
    return f"{safe_subject}{suffix}.mp4"


def _render_task_table(filtered_tasks, key_prefix):
    with st.container(key=f"task_table_header_{key_prefix}"):
        header_cols = st.columns([1.1, 1.7, 3.0, 0.8, 1.6], vertical_alignment="center")
        header_cols[0].caption(tr("Task Status"))
        header_cols[1].caption(tr("Task Updated At"))
        header_cols[2].caption(tr("Task Subject"))
        header_cols[3].caption(tr("Task Progress"))
        header_cols[4].caption(tr("Task Actions"))

    if not filtered_tasks:
        st.info(tr("No Tasks Match Filter"))
        return

    visible_tasks = filtered_tasks[:12]
    publish_configured = _publish_channel_configured()
    list_height = min(390, max(96, len(visible_tasks) * 58))
    with st.container(height=list_height, border=False):
        for task in visible_tasks:
            task_id = task["task_id"]
            has_video = bool(task["video_file"] and os.path.isfile(task["video_file"]))
            is_processing = _task_state_filter_key(task) == "processing"
            is_busy = is_processing or tm.is_task_busy(task)
            has_restore_data = os.path.isfile(
                os.path.join(task["task_path"], "script.json")
            ) or os.path.isfile(
                os.path.join(task["task_path"], PROJECT_PARAMS_FILE_NAME)
            )
            safe_task_key = "".join(ch if ch.isalnum() else "_" for ch in task_id)[:40]

            # 使用 Streamlit 原生 bordered container + columns 保留每行操作。
            # 相比自定义 HTML/CSS 表格，这种方式对 Streamlit 版本变更更稳；
            # 相比 dataframe，又能保留播放、打开目录、删除等行内动作。
            with st.container(
                key=f"task_row_{key_prefix}_{safe_task_key}", border=True
            ):
                row_cols = st.columns(
                    [1.1, 1.7, 3.0, 0.8, 1.6],
                    vertical_alignment="center",
                )
                row_cols[0].write(_task_state_label(task["state"], has_video))
                publish_caption = _cross_post_status_caption(task)
                if publish_caption:
                    row_cols[0].caption(publish_caption)
                row_cols[1].write(_format_task_time(task["mtime"]))
                row_cols[2].write(_format_task_subject(task["subject"]))
                row_cols[3].write(f"{task['progress']}%")

                action_cols = row_cols[4].columns(
                    5,
                    vertical_alignment="center",
                    gap="small",
                )
                with action_cols[0]:
                    play_label = tr("Play")
                    if st.button(
                        play_label,
                        key=f"play_task_{key_prefix}_{task_id}",
                        use_container_width=True,
                        icon=":material/play_arrow:",
                        help=play_label,
                        disabled=not has_video,
                    ):
                        _open_task_video(task["video_file"])

                with action_cols[1]:
                    open_label = tr("Open Task Folder")
                    if st.button(
                        open_label,
                        key=f"open_task_{key_prefix}_{task_id}",
                        use_container_width=True,
                        icon=":material/folder_open:",
                        help=open_label,
                    ):
                        _open_task_path(task["task_path"])

                with action_cols[2]:
                    publish_label = tr("Publish Now")
                    publish_state = task.get("cross_post_state")
                    publish_busy = publish_state in (
                        const.CROSS_POST_STATE_PENDING,
                        const.CROSS_POST_STATE_PROCESSING,
                    )
                    can_publish = (
                        has_video
                        and not is_busy
                        and not publish_busy
                        and publish_configured
                        and _task_state_filter_key(task) == "complete"
                    )
                    if not publish_configured:
                        publish_help = tr("Publish Not Configured Help")
                    elif publish_busy:
                        publish_help = tr("Publish Already Queued")
                    else:
                        publish_help = tr("Publish Now Help")
                    if st.button(
                        publish_label,
                        key=f"publish_task_{key_prefix}_{task_id}",
                        use_container_width=True,
                        icon=":material/send:",
                        help=publish_help,
                        disabled=not can_publish,
                    ):
                        publish_error = tm.publish_task_now(task_id)
                        if publish_error is None:
                            st.toast(tr("Publish Queued Toast"), icon="🚀")
                            st.rerun()
                        else:
                            st.toast(
                                f"{tr('Publish Trigger Failed')}: {publish_error}",
                                icon="⚠️",
                            )

                with action_cols[3]:
                    restore_label = tr("Regenerate Task")
                    if st.button(
                        restore_label,
                        key=f"restore_task_{key_prefix}_{task_id}",
                        use_container_width=True,
                        icon=":material/replay:",
                        help=restore_label,
                        disabled=is_processing or not has_restore_data,
                    ):
                        _queue_task_restore(task_id)

                with action_cols[4]:
                    delete_label = tr("Delete Task")
                    delete_help = (
                        f"{delete_label} ({tr('Task Status Processing')})"
                        if is_busy
                        else delete_label
                    )
                    if st.button(
                        delete_label,
                        key=f"delete_task_{key_prefix}_{task_id}",
                        use_container_width=True,
                        icon=":material/delete:",
                        help=delete_help,
                        disabled=is_busy,
                    ):
                        if _delete_task(task_id, task["task_path"], task["state"]):
                            st.toast(tr("Task Deleted"))
                            st.rerun()
                        else:
                            st.error(tr("Task Delete Failed"))


def _render_publish_queue(tasks):
    """发布队列面板：排队中/进行中的发布任务，随 fragment 每 2 秒刷新。

    发布线程池串行消化队列：触发时若有发布在跑，新任务自动排队，
    这里按“进行中在前、排队在后”展示，并给出进度条与实时日志尾。
    """
    active = [
        task
        for task in tasks
        if task.get("cross_post_state") in ("pending", "processing")
    ]
    if not active:
        return
    active.sort(
        key=lambda task: (
            0 if task.get("cross_post_state") == "processing" else 1,
            -(task.get("mtime") or 0),
        )
    )
    stage_labels = {
        "queued": tr("Publish Stage Queued"),
        "metadata": tr("Publish Stage Metadata"),
        "uploading": tr("Publish Stage Uploading"),
    }
    with st.expander(f"{tr('Publish Queue')} ({len(active)})", expanded=True):
        queue_position = 0
        for task in active:
            running = task.get("cross_post_state") == "processing"
            if not running:
                queue_position += 1
            with st.container(border=True):
                head_cols = st.columns([3, 2], vertical_alignment="center")
                head_cols[0].write(_format_task_subject(task["subject"]))
                platforms = task.get("cross_post_platforms") or []
                platform_text = " ".join(
                    SOCIAL_PUBLISH_PLATFORM_LABELS.get(p, p) for p in platforms
                )
                if running:
                    badge = tr("Publish Processing")
                else:
                    badge = (
                        f"{tr('Publish Pending')} · "
                        f"{tr('Publish Queue Position')} #{queue_position}"
                    )
                head_cols[1].caption(
                    f"{badge}{' · ' + platform_text if platform_text else ''}"
                )
                if running:
                    progress = int(task.get("cross_post_progress") or 0)
                    stage = stage_labels.get(task.get("cross_post_stage"), "")
                    current = task.get("cross_post_platform")
                    current_label = (
                        SOCIAL_PUBLISH_PLATFORM_LABELS.get(current, current)
                        if current
                        else ""
                    )
                    progress_text = " · ".join(
                        part for part in (current_label, stage) if part
                    )
                    st.progress(
                        min(max(progress, 0), 100) / 100,
                        text=f"{progress}%{' · ' + progress_text if progress_text else ''}",
                    )
                log_lines = task.get("cross_post_log") or []
                if log_lines:
                    with st.expander(tr("Publish Log")):
                        st.code("\n".join(log_lines[-15:]), language="text")


def _render_publish_history(entries):
    """发布历史 TAB：自动/手动发布记录，含平台结果、耗时与重新发布。"""
    if not entries:
        st.info(tr("Publish History Empty"))
        return
    for entry in entries:
        task_id = str(entry.get("task_id") or "")
        finished = entry.get("finished_at") or entry.get("recorded_at")
        with st.container(border=True):
            cols = st.columns([3, 2, 1.6, 3, 1.2, 1.4], vertical_alignment="center")
            subject = entry.get("video_subject") or task_id[:8]
            cols[0].markdown(f"**{_format_task_subject(subject)}**")
            videos = entry.get("videos") or []
            video_text = "、".join(os.path.basename(str(v)) for v in videos[:3])
            if video_text:
                cols[0].caption(video_text)
            cols[1].caption(
                datetime.fromtimestamp(finished).strftime("%Y-%m-%d %H:%M:%S")
                if finished
                else "-"
            )
            cols[2].caption(
                tr("Publish Trigger Manual")
                if entry.get("trigger") == "manual"
                else tr("Publish Trigger Auto")
            )
            results = entry.get("results") or []
            marks = " ".join(
                f"{SOCIAL_PUBLISH_PLATFORM_LABELS.get(r.get('platform'), r.get('platform'))}"
                f"{'✅' if r.get('success') else '❌'}"
                for r in results
            )
            state = entry.get("state")
            badge = "✅" if state == "complete" else "❌"
            cols[3].caption(f"{badge} {marks}".strip())
            duration = entry.get("duration_seconds")
            if duration is not None:
                minutes, seconds = divmod(int(duration), 60)
                cols[4].caption(f"{minutes}m{seconds:02d}s" if minutes else f"{seconds}s")
            else:
                cols[4].caption("-")
            try:
                live = sm.state.get_task(task_id) or {}
            except Exception:
                live = {}
            busy = live.get("cross_post_state") in ("pending", "processing")
            if cols[5].button(
                tr("Republish"),
                key=f"republish_history_{task_id}_{int(finished or 0)}",
                use_container_width=True,
                disabled=busy or not task_id,
                icon=":material/send:",
            ):
                publish_error = tm.publish_task_now(task_id)
                if publish_error is None:
                    st.toast(tr("Publish Queued Toast"), icon="🚀")
                    st.rerun()
                else:
                    st.toast(
                        f"{tr('Publish Trigger Failed')}: {publish_error}",
                        icon="⚠️",
                    )
            error = str(entry.get("error") or "").strip()
            if state != "complete" and error:
                st.caption(error.splitlines()[-1][:160])


def _render_task_manager_panel(tasks=None, include_publish_history=True):
    tasks = tasks if tasks is not None else _collect_task_summaries()
    # 发布历史提升为一级页后，任务页不再重复拉取和渲染历史记录。
    history_entries = (
        publish_history.list_publish_history(limit=100)
        if include_publish_history
        else []
    )
    if not tasks and not history_entries:
        st.info(tr("No Tasks Yet"))
        return

    _render_publish_queue(tasks)

    # Streamlit 1.59 支持有状态 Tabs 的惰性渲染。切换时只重新构建当前列表，
    # 避免定时 Fragment 每两秒重复创建四套任务行和操作按钮。
    status_tabs = [
        ("all", tr("All Tasks")),
        ("processing", tr("Task Status Processing")),
        ("complete", tr("Task Status Complete")),
        ("failed", tr("Task Status Failed")),
    ]
    if include_publish_history:
        status_tabs.append(("publish_history", tr("Publish History Tab")))
    tabs = st.tabs(
        [label for _, label in status_tabs],
        key="task_manager_status_tabs",
        on_change="rerun",
    )
    for (status_key, _), tab in zip(status_tabs, tabs):
        if not tab.open:
            continue
        with tab:
            if status_key == "publish_history":
                _render_publish_history(history_entries)
                continue
            filtered_tasks = [
                task
                for task in tasks
                if status_key == "all" or _task_state_filter_key(task) == status_key
            ]
            _render_task_table(filtered_tasks, status_key)

    _render_task_video_preview()


def _render_task_video_preview():
    # 无桌面部署下“播放”按钮的浏览器内回退：在任务面板底部渲染播放器。
    preview_file = st.session_state.get("task_preview_video_file")
    if not preview_file:
        return

    tasks_root = os.path.abspath(utils.task_dir())
    if not (
        preview_file.startswith(tasks_root + os.sep) and os.path.isfile(preview_file)
    ):
        st.session_state.pop("task_preview_video_file", None)
        return

    st.divider()
    preview_cols = st.columns([5, 1], vertical_alignment="center")
    task_name = os.path.basename(os.path.dirname(preview_file))
    preview_cols[0].caption(f"{os.path.basename(preview_file)} · {task_name}")
    closed = preview_cols[1].button(
        "✕",
        key="close_task_video_preview",
        use_container_width=True,
        help=tr("Close"),
    )
    if closed:
        st.session_state.pop("task_preview_video_file", None)
        return
    st.video(preview_file)


def _load_task_restore_payload(task_id):
    tasks_root = os.path.realpath(utils.task_dir())
    task_path = os.path.realpath(os.path.join(tasks_root, str(task_id)))
    try:
        if os.path.commonpath([tasks_root, task_path]) != tasks_root:
            raise ValueError("task path is outside the task directory")
    except ValueError as e:
        logger.warning(f"invalid task restore path: {task_id}, {e}")
        return None

    # 项目快照优先：草稿没有 script.json，且快照比脚本文件更完整。
    project_params = _read_project_params(task_id)
    if project_params is not None:
        return {
            "task_id": str(task_id),
            "subject": project_params.get("video_subject") or str(task_id),
            "params": project_params,
        }

    script_data = _safe_load_task_script(task_path)
    raw_params = script_data.get("params")
    if not isinstance(raw_params, dict):
        logger.warning(f"task has no restorable parameters: {task_id}")
        return None

    params_input = dict(raw_params)
    if script_data.get("script"):
        params_input["video_script"] = script_data["script"]
    if script_data.get("search_terms"):
        params_input["video_terms"] = script_data["search_terms"]

    try:
        params = VideoParams.model_validate(params_input).model_dump(mode="json")
    except Exception as e:
        logger.warning(f"failed to validate task restore parameters: {task_id}, {e}")
        return None

    return {
        "task_id": str(task_id),
        "subject": params.get("video_subject") or script_data.get("script") or task_id,
        "params": params,
    }


def _project_params_path(task_id):
    """任务目录内的 params.json 路径；非法或越界 ID 返回 None。"""
    try:
        normalized_task_id = str(UUID(str(task_id)))
    except (ValueError, TypeError, AttributeError):
        return None
    tasks_root = os.path.realpath(utils.task_dir())
    task_path = os.path.realpath(os.path.join(tasks_root, normalized_task_id))
    try:
        if os.path.commonpath([tasks_root, task_path]) != tasks_root:
            return None
    except ValueError:
        return None
    return os.path.join(task_path, PROJECT_PARAMS_FILE_NAME)


def _write_project_params(task_id, params_dict):
    """原子写入生成参数快照；失败只告警，不阻断生成或保存流程。"""
    params_file = _project_params_path(task_id)
    if not params_file:
        return False
    payload = {
        "schema": PROJECT_PARAMS_SCHEMA,
        "version": PROJECT_PARAMS_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "params": params_dict,
    }
    try:
        os.makedirs(os.path.dirname(params_file), exist_ok=True)
        tmp_file = params_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, params_file)
        return True
    except OSError as e:
        logger.warning(f"failed to write project params: {task_id}, {e}")
        return False


def _read_project_params(task_id):
    """读取并校验项目快照；缺失、损坏或 schema 不符时返回 None。"""
    params_file = _project_params_path(task_id)
    if not params_file or not os.path.isfile(params_file):
        return None
    try:
        with open(params_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        if payload.get("schema") not in (
            PROJECT_PARAMS_SCHEMA,
            LEGACY_PROJECT_PARAMS_SCHEMA,
        ):
            return None
        raw_params = payload.get("params")
        if not isinstance(raw_params, dict):
            return None
        return VideoParams.model_validate(raw_params).model_dump(mode="json")
    except Exception as e:
        logger.warning(f"failed to read project params: {task_id}, {e}")
        return None


def _params_snapshot(params_dict):
    """脏检测用的归一化快照：排除本机媒体路径、统一关键词形态、键排序。"""
    filtered = {
        key: value
        for key, value in params_dict.items()
        if key not in PRESET_EXCLUDED_PARAM_KEYS
    }
    terms = filtered.get("video_terms")
    if isinstance(terms, list):
        filtered["video_terms"] = ", ".join(str(term) for term in terms)
    return json.dumps(filtered, ensure_ascii=False, sort_keys=True)


def _bind_current_project(task_id, params_dict):
    """把会话绑定到某个项目，并以当前参数作为干净基线。"""
    st.session_state["current_project_id"] = str(task_id)
    st.session_state["current_project_subject"] = str(
        params_dict.get("video_subject") or ""
    )
    st.session_state["project_params_baseline"] = _params_snapshot(params_dict)


def _current_project_id():
    return st.session_state.get("current_project_id") or ""


def _project_is_dirty():
    """上一次整页 run 结束时的参数与基线不一致即为脏。"""
    baseline = st.session_state.get("project_params_baseline")
    last = st.session_state.get("project_params_last")
    if not baseline or last is None:
        return False
    return last != baseline


def _project_dirty_display():
    """顶栏展示用的脏标记：本 run 已请求保存或正在回填时，结果必然干净，
    不等下一 run 才消点，避免“已保存却仍带●”的一 run 滞后。"""
    if st.session_state.get("project_save_requested"):
        return False
    if st.session_state.get("project_baseline_pending"):
        return False
    return _project_is_dirty()


def _request_project_save():
    """保存按钮回调：真正的写盘在 run 末尾参数组装完成后执行。"""
    st.session_state["project_save_requested"] = True


def _project_is_locked():
    """绑定项目已出成片时锁定创作参数：已交付任务的快照不允许静默改写。"""
    params_path = _project_params_path(_current_project_id())
    if not params_path:
        return False
    return bool(_find_final_task_video(os.path.dirname(params_path)))


def _finalize_project_binding(params):
    """run 末尾记录参数快照，并处理保存请求与加载后的基线重置。

    基线取“控件渲染完成后”的快照而不是加载 payload 本身：恢复回填会对
    越界值限幅、把关键词列表转成字符串，用 payload 做基线会产生假脏。
    """
    params_dict = params.model_dump(mode="json")
    snapshot = _params_snapshot(params_dict)
    st.session_state["project_params_last"] = snapshot
    # 切换确认选“保存”时回调拿不到组装后的参数，用上一 run 末尾的完整
    # dump 写盘：控件自那以后未变，内容就是用户看到的当前状态。
    st.session_state["project_params_last_full"] = params_dict
    saved_now = False
    if st.session_state.pop("project_save_requested", False):
        task_id = _current_project_id()
        if not task_id:
            task_id = str(uuid4())
            st.session_state["current_project_id"] = task_id
            st.session_state["current_project_subject"] = str(
                params_dict.get("video_subject") or ""
            )
        if _write_project_params(task_id, params_dict):
            st.session_state["project_params_baseline"] = snapshot
            # toast 必须在写盘的同一 run 发出：消息若留到下一 run 开头，
            # 没有后续交互时就永远不显示。
            st.toast(tr("Project Saved"), icon="✅")
            saved_now = True
    if st.session_state.pop("project_baseline_pending", False):
        st.session_state["project_params_baseline"] = snapshot
    elif "project_params_baseline" not in st.session_state:
        # 未绑定会话也以首 run 的默认参数为基线：用户输入后同样算脏，
        # 切换/新建前才会触发三选确认，不会静默丢编辑。
        st.session_state["project_params_baseline"] = snapshot
    if saved_now:
        # 切换器列表在本 run 开头渲染，早于此处写盘；popover 开合不触发
        # rerun，不补一次刷新的话新草稿要等下次无关交互才出现在列表里。
        st.rerun(scope="app")


def _project_switcher_entries(limit):
    """顶栏切换器列表：只保留可恢复参数的任务/草稿，按最近更新排序。"""
    entries = []
    for task in _scan_history_tasks(limit=limit):
        task_path = task["task_path"]
        if os.path.isfile(
            os.path.join(task_path, PROJECT_PARAMS_FILE_NAME)
        ) or os.path.isfile(os.path.join(task_path, "script.json")):
            entries.append(task)
    return entries


def _load_more_projects():
    st.session_state["project_switcher_limit"] = (
        int(st.session_state.get("project_switcher_limit", 20)) + 20
    )
    st.rerun(scope="app")


def _request_project_switch(target_id):
    """切换器条目回调：脏时先弹三选确认，干净时直接加载。"""
    target_id = str(target_id)
    if target_id == _current_project_id():
        return
    if _project_is_dirty():
        st.session_state["project_switch_candidate"] = target_id
        _invalidate_project_switcher_popover()
    else:
        payload = _load_task_restore_payload(target_id)
        if payload:
            st.session_state["task_restore_payload"] = payload
        else:
            st.session_state["project_switch_failed"] = True
    st.rerun(scope="app")


def _request_new_project():
    if _project_is_dirty():
        st.session_state["project_switch_candidate"] = "__new__"
        _invalidate_project_switcher_popover()
    else:
        st.session_state["project_new_blank_requested"] = True
    st.rerun(scope="app")


def _invalidate_project_switcher_popover():
    """三选弹窗出现前让 popover 换 key 重挂载（新实例默认关闭）。

    Streamlit popover 点内部按钮后不会自动关闭，且其浮层 portal 在
    rerun 后重新 append，会盖住后开的 st.dialog 拦截点击。"""
    st.session_state["project_switcher_epoch"] = (
        int(st.session_state.get("project_switcher_epoch", 0)) + 1
    )


def _request_save_as_new():
    """锁定横幅的“另存为新任务”：克隆当前参数到新草稿并改绑解锁。"""
    params_dict = dict(st.session_state.get("project_params_last_full") or {})
    task_id = str(uuid4())
    if _write_project_params(task_id, params_dict):
        _bind_current_project(task_id, params_dict)
        st.session_state["project_baseline_pending"] = True
        st.session_state["project_save_as_new_done"] = True
    else:
        st.session_state["project_save_as_new_failed"] = True
    st.rerun(scope="app")


def _apply_pending_project_switch():
    """在渲染任何控件前执行切换决议：保存/放弃当前修改后加载目标。"""
    action = st.session_state.pop("project_switch_action", None)
    candidate = st.session_state.get("project_switch_candidate")
    if st.session_state.pop("project_new_blank_requested", False):
        action, candidate = "discard", "__new__"
    if action is None:
        # 候选保留：本 run 还要渲染三选确认弹窗。
        return
    st.session_state.pop("project_switch_candidate", None)
    if action == "cancel":
        return
    if action == "save":
        last_full = st.session_state.get("project_params_last_full")
        if last_full:
            task_id = _current_project_id() or str(uuid4())
            _write_project_params(task_id, last_full)
    if candidate == "__new__":
        st.session_state.pop("current_project_id", None)
        st.session_state.pop("current_project_subject", None)
        st.session_state.pop("project_params_baseline", None)
        _apply_restored_params(VideoParams(video_subject="").model_dump(mode="json"))
        st.session_state["project_baseline_pending"] = True
        st.session_state["project_new_blank_done"] = True
    elif candidate:
        payload = _load_task_restore_payload(candidate)
        if payload:
            st.session_state["task_restore_payload"] = payload
        else:
            st.session_state["project_switch_failed"] = True


def _dismiss_project_switch_dialog():
    st.session_state.pop("project_switch_candidate", None)
    st.session_state.pop("project_switch_action", None)


@st.dialog(
    tr("Project Switch Title"),
    width="small",
    on_dismiss=_dismiss_project_switch_dialog,
)
def _render_project_switch_dialog(candidate):
    st.warning(tr("Project Switch Dirty Warning"))
    if candidate == "__new__":
        st.caption(tr("New Blank Project"))
    else:
        payload = _load_task_restore_payload(candidate)
        st.caption(
            _format_task_subject(
                (payload or {}).get("subject") or candidate, max_length=60
            )
        )
    save_col, discard_col, cancel_col = st.columns(3)
    if save_col.button(
        tr("Save And Switch"),
        key="project_switch_save",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["project_switch_action"] = "save"
        st.rerun(scope="app")
    if discard_col.button(
        tr("Discard And Switch"),
        key="project_switch_discard",
        use_container_width=True,
    ):
        st.session_state["project_switch_action"] = "discard"
        st.rerun(scope="app")
    if cancel_col.button(
        tr("Cancel Switch"),
        key="project_switch_cancel",
        use_container_width=True,
    ):
        st.session_state["project_switch_action"] = "cancel"
        st.rerun(scope="app")


def _render_project_lock_banner():
    """已完成项目的锁定横幅：说明原因并给出唯一的解锁出口。"""
    with st.container(key="project_lock_banner"):
        st.warning(tr("Project Locked Banner"), icon=":material/lock:")
        st.button(
            tr("Save As New Task"),
            key="project_save_as_new_button",
            icon=":material/content_copy:",
            type="primary",
            width="stretch",
            on_click=_request_save_as_new,
        )


def _render_project_switcher():
    """顶栏项目切换器：当前项目名 + 脏标记 + 分批项目列表。"""
    current_id = _current_project_id()
    dirty = _project_dirty_display()
    if current_id:
        subject = st.session_state.get("current_project_subject") or ""
    else:
        # 未绑定时展示即将被保存的文案主题；绑定后改用存盘时的主题。
        subject = str(st.session_state.get("video_subject") or "")
    label = _format_task_subject(subject, max_length=18) if subject else tr("Unsaved Project")
    if dirty:
        label += " ●"
    pop_key = "project_switcher"
    if st.session_state.get("project_switch_candidate"):
        # 弹窗打开期间用一次性 key，popover 重挂载为关闭态，
        # 避免残留浮层盖住三选确认弹窗。
        pop_key = f"project_switcher_{st.session_state.get('project_switcher_epoch', 0)}"
    with st.popover(
        label,
        icon=":material/lock:" if _project_is_locked() else ":material/folder_open:",
        key=pop_key,
        help=tr("Project Dirty Help") if dirty else tr("Project Switcher Help"),
    ):
        st.caption(tr("Project Switcher Help"))
        st.button(
            tr("Save Current Project"),
            key="project_save_button",
            icon=":material/save:",
            width="stretch",
            on_click=_request_project_save,
        )
        st.button(
            tr("New Blank Project"),
            key="project_new_button",
            icon=":material/add:",
            width="stretch",
            on_click=_request_new_project,
        )
        st.divider()
        limit = int(st.session_state.get("project_switcher_limit", 20))
        entries = _project_switcher_entries(limit)
        if not entries:
            st.caption(tr("No Saved Projects"))
        for task in entries:
            is_current = task["task_id"] == current_id
            state_label = _task_state_label(task["state"], bool(task["video_file"]))
            st.button(
                _format_task_subject(task["subject"], max_length=24),
                key=f"project_switch_{task['task_id']}",
                icon=":material/check:" if is_current else ":material/description:",
                width="stretch",
                help=f"{state_label} · {_format_task_time(task['mtime'])}",
                on_click=_request_project_switch,
                args=(task["task_id"],),
                disabled=is_current,
            )
        if len(entries) >= limit:
            st.button(
                tr("Load More Projects"),
                key="project_switcher_more",
                icon=":material/expand_more:",
                width="stretch",
                on_click=_load_more_projects,
            )


def _infer_tts_server_from_voice(voice_name):
    if voice.is_no_voice(voice_name):
        return voice.NO_VOICE_NAME
    if voice.is_siliconflow_voice(voice_name):
        return "siliconflow"
    if voice.is_gemini_voice(voice_name):
        return "gemini-tts"
    if voice.is_mimo_voice(voice_name):
        return "mimo-tts"
    if voice.is_minimax_voice(voice_name):
        return "minimax-tts"
    if voice.is_elevenlabs_voice(voice_name):
        return "elevenlabs"
    if voice.is_chatterbox_voice(voice_name):
        return "chatterbox"
    if voice.is_kokoro_voice(voice_name):
        return "kokoro"
    if voice.is_fish_audio_voice(voice_name):
        return "fish_audio"
    if voice.is_voxcpm_voice(voice_name):
        return "voxcpm"
    if voice.is_azure_v2_voice(voice_name):
        return "azure-tts-v2"
    return "azure-tts-v1"


def _set_stable_widget_value(key, value):
    if value is not None:
        st.session_state[localized_widget_key(key)] = value


def _apply_pending_task_restore():
    payload = st.session_state.pop("task_restore_payload", None)
    if not payload:
        return False

    _apply_restored_params(payload["params"])
    # 恢复历史任务即把会话绑定到该项目；基线在 run 末尾按回填后的控件值重置。
    _bind_current_project(payload["task_id"], payload["params"])
    st.session_state["project_baseline_pending"] = True
    st.session_state["task_restore_succeeded"] = True
    logger.info(f"restored task configuration: {payload['task_id']}")
    return True


def _apply_restored_params(params):
    """
    把一份完整的生成参数写回页面控件状态。

    历史任务恢复和设置预设导入使用同一份参数模型，因此共用同一个实现，避免
    新增字段时只更新其中一条路径。调用方必须在渲染任何控件之前执行，否则
    Streamlit 会拒绝修改已经实例化的控件状态。
    """
    video_terms = params.get("video_terms") or ""
    if isinstance(video_terms, list):
        video_terms = ", ".join(str(term) for term in video_terms)

    # 文案与高级脚本设置。
    st.session_state["video_subject"] = params.get("video_subject") or ""
    st.session_state["video_script"] = params.get("video_script") or ""
    st.session_state["video_terms"] = str(video_terms)
    _set_stable_widget_value(
        "script_language_select", params.get("video_language") or ""
    )
    st.session_state["paragraph_number_input"] = params.get("paragraph_number", 1)
    st.session_state["video_script_prompt"] = params.get("video_script_prompt") or ""
    st.session_state["custom_system_prompt"] = (
        params.get("custom_system_prompt") or llm.DEFAULT_SCRIPT_SYSTEM_PROMPT
    )

    # 视频设置。素材上传控件不能由服务端写入，因此本地素材需要用户重新选择。
    video_source = params.get("video_source") or "pexels"
    _set_stable_widget_value("video_source_select", video_source)
    _set_stable_widget_value(
        "video_concat_mode_select", params.get("video_concat_mode") or "random"
    )
    _set_stable_widget_value(
        "video_transition_mode_select",
        params.get("video_transition_mode") or VideoTransitionMode.none.value,
    )
    _set_stable_widget_value(
        f"video_aspect_for_{video_source}",
        params.get("video_aspect") or VideoAspect.portrait.value,
    )
    _set_stable_widget_value(
        "video_fit_mode_select",
        params.get("video_fit_mode") or VideoFitMode.cover.value,
    )
    _set_stable_widget_value(
        "image_motion_select", params.get("image_motion") or ImageMotion.zoom.value
    )
    _set_stable_widget_value(
        "video_clip_duration_select", params.get("video_clip_duration", 3)
    )
    _set_stable_widget_value(
        "video_clip_speed_slider",
        # API 可以写入超过 WebUI 范围的速度，任务生成阶段会安全归一化，但
        # 历史记录仍可能保留原值。恢复任务前再次归一化，避免给 Streamlit
        # slider 注入越界值、NaN 或无穷值导致控件状态异常。
        utils.normalize_clip_speed(params.get("video_clip_speed", 1.0)),
    )
    _set_stable_widget_value("video_count_select", params.get("video_count", 1))
    # video_seed_input 是不带语言后缀的纯 key，不能走 _set_stable_widget_value
    # （它会给 key 追加语言后缀）；恢复历史任务时直接写 session_state。
    try:
        restored_seed_text = ""
        if params.get("video_seed") is not None:
            restored_seed_text = str(int(params["video_seed"]))
    except (TypeError, ValueError):
        restored_seed_text = ""
    st.session_state["video_seed_input"] = restored_seed_text
    st.session_state["match_materials_to_script"] = bool(
        params.get("match_materials_to_script", False)
    )

    # 音频设置。TTS server 未写入旧任务，根据历史 voice_name 推断。
    voice_name = params.get("voice_name") or voice.NO_VOICE_NAME
    tts_server = _infer_tts_server_from_voice(voice_name)
    if params.get("custom_audio_file"):
        voice_mode = VOICE_MODE_UPLOAD
    elif voice.is_no_voice(voice_name):
        voice_mode = VOICE_MODE_NONE
    else:
        voice_mode = VOICE_MODE_TTS
    _set_stable_widget_value("voice_mode_control", voice_mode)
    if tts_server != voice.NO_VOICE_NAME:
        _set_stable_widget_value("tts_server_select", tts_server)
        _set_stable_widget_value(f"speech_synthesis_select_{tts_server}", voice_name)
    _set_stable_widget_value("voice_volume_select", params.get("voice_volume", 1.0))
    _set_stable_widget_value("voice_rate_select", params.get("voice_rate", 1.0))
    bgm_type = params.get("bgm_type") or ""
    _set_stable_widget_value("bgm_type_select", bgm_type)
    _set_stable_widget_value("bgm_volume_select", params.get("bgm_volume", 0.2))
    if bgm_type == "preset" and params.get("bgm_file"):
        # 预设歌曲控件使用文件名作为稳定业务值。历史任务可能保存绝对路径或
        # 相对路径，统一取 basename 后即可匹配当前安全枚举出的歌曲列表。
        _set_stable_widget_value(
            "preset_song_select", os.path.basename(str(params["bgm_file"]))
        )
    st.session_state["custom_bgm_file_input"] = params.get("bgm_file") or ""
    st.session_state["sonilo_bgm_prompt_input"] = (
        params.get("video_music_prompt") or params.get("sonilo_bgm_prompt") or ""
    )
    st.session_state["elevenlabs_music_prompt_input"] = (
        params.get("video_music_prompt") or ""
    )

    # 字幕设置。对旧任务中的越界数值做最小限幅，避免 Slider 无法初始化。
    st.session_state["subtitle_enabled_checkbox"] = bool(
        params.get("subtitle_enabled", True)
    )
    _set_stable_widget_value("font_name_select", params.get("font_name") or "")
    _set_stable_widget_value(
        "subtitle_position_select", params.get("subtitle_position") or "bottom"
    )
    _set_stable_widget_value(
        "subtitle_display_mode_select", params.get("subtitle_display_mode") or "sentence"
    )
    _set_stable_widget_value(
        "subtitle_animation_select", params.get("subtitle_animation") or "none"
    )
    custom_position = min(100.0, max(0.0, float(params.get("custom_position", 70.0))))
    st.session_state["custom_position_input"] = str(custom_position)
    st.session_state["font_color_picker"] = params.get("text_fore_color") or "#FFFFFF"
    st.session_state["font_size_slider"] = min(
        100, max(30, int(params.get("font_size", 60)))
    )
    st.session_state["stroke_color_picker"] = params.get("stroke_color") or "#000000"
    st.session_state["stroke_width_slider"] = min(
        10.0, max(0.0, float(params.get("stroke_width", 1.5)))
    )
    background_color = params.get("text_background_color")
    background_enabled = bool(background_color)
    st.session_state["subtitle_background_enabled_checkbox"] = background_enabled
    if isinstance(background_color, str):
        st.session_state["subtitle_background_color_picker"] = background_color
    st.session_state["rounded_subtitle_background_checkbox"] = bool(
        params.get("rounded_subtitle_background", False) and background_enabled
    )

    st.session_state.pop("local_video_materials_uploader", None)
    # 历史任务只保存素材路径，不能保证这些文件在当前环境仍然存在。
    # 同时清空当前页面已缓存的上传素材，避免恢复后误用另一个任务的文件。
    st.session_state["local_video_materials"] = []
    st.session_state.pop("custom_audio_file_uploader", None)
    st.session_state.pop("voxcpm_reference_audio_uploader", None)
    st.session_state.pop(VOXCPM_REFERENCE_AUDIO_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY, None)
    st.session_state.pop("voxcpm_prompt_audio_uploader", None)
    st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_PROMPT_TEXT_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_HIGH_FIDELITY_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_PROMPT_EXAMPLE_MODE_SESSION_KEY, None)
    st.session_state.pop("custom_bgm_uploader", None)
    st.session_state.pop("custom_bgm_validation", None)
    st.session_state["task_restore_upload_requirements"] = (
        _build_restore_upload_requirements(params)
    )

    return True


def _dismiss_task_restore_dialog():
    st.session_state.pop("task_restore_candidate_id", None)


@st.dialog(
    tr("Regenerate Task"),
    width="small",
    on_dismiss=_dismiss_task_restore_dialog,
)
def _render_task_restore_dialog(task_id):
    payload = _load_task_restore_payload(task_id)
    if payload is None:
        st.error(tr("Task Restore Failed"))
        if st.button(tr("Cancel"), key="cancel_invalid_task_restore"):
            st.session_state.pop("task_restore_candidate_id", None)
            st.rerun(scope="app")
        return

    st.write(tr("Regenerate Task Confirmation"))
    st.caption(_format_task_subject(payload["subject"], max_length=80))
    cancel_col, load_col = st.columns(2)
    if cancel_col.button(
        tr("Cancel"),
        key="cancel_task_restore",
        use_container_width=True,
    ):
        st.session_state.pop("task_restore_candidate_id", None)
        st.rerun(scope="app")
    if load_col.button(
        tr("Load Task Configuration"),
        key="confirm_task_restore",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["task_restore_payload"] = payload
        st.session_state.pop("task_restore_candidate_id", None)
        st.rerun(scope="app")


def _dismiss_settings_dialog():
    """关闭设置弹窗，并确保下一次整页 rerun 不会再次自动打开。"""
    st.session_state["settings_dialog_open"] = False


def _open_settings_dialog(target_tab=None):
    """打开设置弹窗，并可直接定位到指定业务标签页。"""
    st.session_state["settings_dialog_open"] = True
    if not target_tab:
        target_tab = "general"
    if target_tab:
        # 这里只保存稳定的业务 ID，不保存翻译文本；真正创建 tabs 前再根据
        # 当前界面语言解析 label，避免用户切换语言后旧文案成为非法选项。
        st.session_state["settings_dialog_target_tab"] = target_tab


def _open_material_settings_dialog():
    """供视频来源组件回调使用：直接打开素材服务设置。"""
    _open_settings_dialog("material")


def _render_brand(available_update: str | None = None):
    """渲染项目名称、当前版本和可选的更新入口。"""
    update_link = ""
    if available_update:
        update_label = html.escape(
            tr("Update Available").format(version=available_update)
        )
        # Streamlit 会继续用 Markdown 解析传入的 HTML。这里保持链接为单行，
        # 避免多行字符串的缩进被识别成代码块，导致页面直接显示 HTML 源码。
        update_link = (
            '<a class="changofilm-brand__update" '
            f'href="{version_checker.LATEST_RELEASE_PAGE_URL}" '
            'target="_blank" rel="noopener noreferrer" '
            f'aria-label="{update_label}" title="{update_label}">'
            f"{update_label}</a>"
        )
    mark_html = ""
    if brand_theme.theme()["logo"]:
        mark_html = (
            f'<span class="changofilm-brand__mark">{brand_theme.mark_svg()}</span>'
        )
    # 单行 HTML：多行缩进写法在占位符为空时会留下纯空白行，
    # Markdown 会在那里截断 HTML 块，把剩余 span 渲染成代码块。
    st.markdown(
        '<h1 class="changofilm-brand">'
        f"{mark_html}"
        '<span class="changofilm-brand__name">ChangoFilm</span>'
        f'<span class="changofilm-brand__version" title="ChangoFilm version">'
        f"v{html.escape(str(config.project_version))}</span>"
        f"{update_link}"
        "</h1>",
        unsafe_allow_html=True,
    )


@st.fragment(run_every="1s")
def _render_pending_version_check():
    """检查未完成时只刷新品牌区域，避免阻塞或反复执行整页表单。"""
    snapshot = version_checker.poll_available_update(config.project_version)
    if snapshot.complete:
        # 完成后只在本 fragment 内更新品牌区，不主动整页 rerun：
        # 那会在启动后 1–3 秒无请求地重渲整页，抢走刚开始交互的
        # 用户的焦点/滚动位置（“页面漂移”感来源之一）。下一次自然
        # 交互的整页 rerun 会看到 complete 改走静态渲染停止轮询；
        # 在此之前本 fragment 每秒重绘同一份品牌内容（缓存快照，
        # 无视觉差异）。
        _render_brand(snapshot.available_version)
        return
    _render_brand()


def _render_top_bar():
    """渲染品牌、任务管理、设置和语言切换组成的页面顶部栏。"""
    # 顶部栏分为品牌区和操作区两个独立区域。窄屏下由 Streamlit
    # 将两个区域整体换行，操作区内部再根据剩余宽度自动换行。
    with st.container(key="top_bar"):
        brand_col, actions_col = st.columns(
            [3.5, 2.0],
            vertical_alignment="center",
            gap="small",
        )

    with brand_col:
        update_snapshot = version_checker.poll_available_update(config.project_version)
        if update_snapshot.complete:
            _render_brand(update_snapshot.available_version)
        else:
            _render_pending_version_check()

    with actions_col:
        with st.container(
            key="top_bar_actions",
            horizontal=True,
            horizontal_alignment="right",
            vertical_alignment="center",
            gap="small",
            width="stretch",
        ):
            _render_project_switcher()
            st.button(
                tr("Settings"),
                key="open_settings_dialog_button",
                type="secondary",
                icon=":material/settings:",
                width="content",
                on_click=_open_settings_dialog,
            )

            language_codes = list(locales.keys())
            selected_index = 0
            for i, code in enumerate(language_codes):
                if code == st.session_state.get("ui_language", ""):
                    selected_index = i

            selected_language_code = st.selectbox(
                "Language / 语言",
                options=language_codes,
                index=selected_index,
                format_func=lambda code: locales[code].get("Language", code),
                key="top_language_code_selector",
                label_visibility="collapsed",
                width=180,
            )
            if selected_language_code:
                previous_language = st.session_state.get("ui_language", "")
                if selected_language_code != previous_language:
                    logger.info(
                        "UI language changed by user: "
                        f"previous_language={previous_language or '<empty>'}, "
                        f"selected_language={selected_language_code}"
                    )
                    st.session_state["ui_language"] = selected_language_code
                    # 浏览器自动识别只影响当前会话；只有用户主动切换下拉框时才
                    # 写入 config.toml，后续新会话将优先使用该明确选择。
                    _set_runtime_config("ui", "language", selected_language_code)
                    _save_runtime_config()
                    # 切换语言会先重跑顶部栏，正文控件尚未渲染就触发 rerun。
                    # 显式保留本次创作内容，防止 Streamlit 清理旧控件状态后，
                    # 新语言页面把已经输入的主题、文案和关键词重置为空。
                    for content_key in ("video_subject", "video_script", "video_terms"):
                        if content_key in st.session_state:
                            st.session_state[content_key] = st.session_state[content_key]
                    # 切换语言后强制刷新，避免 selectbox 继续展示旧语言文案。
                    st.rerun()


support_locales = [
    "ca-ES",
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US",
    "es-ES",
    "fr-FR",
    "id-ID",
    "it-IT",
    "ru-RU",
    "vi-VN",
    "th-TH",
    "tr-TR",
]


# -----------------------------------------------------------------------------
# 通用 UI 组件、资源缓存与日志
# -----------------------------------------------------------------------------


@st.cache_data(ttl=30, show_spinner=False)
def get_all_fonts():
    # 字体目录很少变化，但 Streamlit 每次控件交互都会 rerun 页面。短周期缓存
    # 可以避免连续重复 os.walk，同时保证新增字体后最多 30 秒即可被发现。
    fonts = []
    for root, dirs, files in os.walk(font_dir):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".ttc"):
                # Keep each option tied to its file, including nested fonts.
                relative_path = os.path.relpath(os.path.join(root, file), font_dir)
                fonts.append(relative_path.replace(os.sep, "/"))
    fonts.sort()
    return fonts


@st.cache_data(ttl=30, show_spinner=False)
def get_all_songs():
    # 背景音乐与字体使用相同的短周期策略，不做永久缓存，兼顾 rerun 性能和
    # 用户运行期间手动添加音乐文件的场景。
    songs = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3"):
                songs.append(file)
    return songs


def open_task_folder(task_id):
    try:
        # task_id 应始终是服务端生成的 UUID。这里先做格式校验，避免异常值
        # 通过路径拼接访问任务目录之外的位置，也避免后续打开目录时触发
        # 平台 shell 对特殊字符的解释。
        normalized_task_id = str(UUID(str(task_id)))
        tasks_root = os.path.abspath(utils.task_dir())
        path = os.path.abspath(os.path.join(tasks_root, normalized_task_id))

        # 即使 UUID 校验通过，也再次确认最终路径仍在任务根目录内，避免
        # 未来调用方调整 task_id 来源时引入路径穿越风险。
        if not path.startswith(tasks_root + os.sep):
            logger.warning(f"invalid task folder path: {path}")
            return

        if os.path.isdir(path):
            webbrowser.open(f"file://{path}")
    except Exception as e:
        logger.exception(f"failed to open task folder: task_id={task_id}, error={e}")


@st.cache_resource
def init_log():
    # 基础日志 Handler 属于进程级资源，而不是页面会话状态。Streamlit 每次组件
    # 交互都会 rerun 页面脚本，代码热重载也可能让缓存失效。日志初始化只能
    # 精确替换终端 Handler，不能清空正在生成任务使用的 WebUI 临时 Handler。
    _lvl = get_logging_options()[0]

    return configure_terminal_logger(
        sys.stdout,
        level=_lvl,
        colorize=True,
    )


init_log()


def tr_optional(key, fallback_language=""):
    loc = locales.get(st.session_state["ui_language"], {})
    value = loc.get("Translation", {}).get(key, "")
    if not value and fallback_language:
        fallback_loc = locales.get(fallback_language, {})
        value = fallback_loc.get("Translation", {}).get(key, "")
    return value if value else ""


def render_onboarding_tour():
    # 引导只覆盖三个稳定入口，不尝试控制 Dialog、Tabs 或业务表单。这样既能让
    # 新用户理解完整流程，也不会把引导状态与 Streamlit 的动态组件生命周期耦合。
    steps = [
        Tour.bind(
            "open_settings_dialog_button",
            title=tr("Onboarding Model Settings Title"),
            desc=tr("Onboarding Model Settings Description"),
            side="bottom",
            align="end",
        ),
        Tour.bind(
            "main_settings_grid",
            title=tr("Onboarding Creation Settings Title"),
            desc=tr("Onboarding Creation Settings Description"),
            side="top",
            align="center",
        ),
        Tour.bind(
            "generate_video_button",
            title=tr("Onboarding Generate Video Title"),
            desc=tr("Onboarding Generate Video Description"),
            side="top",
            align="center",
        ),
    ]

    # streamlit-tour 1.1.0 没有在 Python 构造参数中暴露导航文案，但底层
    # Driver.js 支持在每一步的 popover 配置中覆盖按钮文本。这里统一注入本地化
    # 文案，并对内容做 HTML 转义，因为组件会通过 innerHTML 渲染这些字段。
    previous_text = html.escape(tr("Onboarding Previous"))
    next_text = html.escape(tr("Onboarding Next"))
    done_text = html.escape(tr("Onboarding Done"))
    for index, step in enumerate(steps):
        step.popover["prevBtnText"] = f"&larr; {previous_text}"
        # Driver.js 会在合并单步配置时覆盖已经替换过变量的进度模板，因此直接
        # 写入当前步骤和总步骤数，避免页面显示未解析的 {{current}} 占位符。
        step.popover["progressText"] = f"{index + 1} / {len(steps)}"
        if index == len(steps) - 1:
            step.popover["doneBtnText"] = done_text
        else:
            step.popover["nextBtnText"] = f"{next_text} &rarr;"

    tour = Tour(
        steps=steps,
        key=ONBOARDING_TOUR_KEY,
        show_progress=True,
        animate=True,
        overlay_opacity=0.55,
        one_time_tour=True,
    )

    # 每个 Streamlit 会话只主动启动一次。是否已经完成则由组件通过浏览器
    # localStorage 判断，避免页面 rerun 或普通控件交互反复弹出引导。
    auto_start_key = f"{ONBOARDING_TOUR_KEY}-auto-started"
    if not st.session_state.get(auto_start_key, False):
        st.session_state[auto_start_key] = True
        tour.start()


def _render_generation_logs(task_id):
    """渲染后台任务日志快照，不从工作线程访问 Streamlit 会话状态。"""
    if config.ui.get("hide_log", False):
        return

    log_records = webui_task.get_task_logs(task_id)
    if not log_records:
        return

    st.code("\n".join(log_records))


def _current_generation_task_id():
    """URL 只保存本地任务 ID，让刷新/重连恢复原任务，不保存配置或凭据。"""
    task_id = st.session_state.get("current_generation_task_id", "")
    if not task_id:
        try:
            task_id = str(UUID(st.query_params.get("generation_task", "")))
        except (ValueError, TypeError, AttributeError):
            return ""
        st.session_state["current_generation_task_id"] = task_id
    return task_id


def _generation_is_busy(task_id):
    if not task_id:
        return False
    if webui_task.is_generation_active(task_id):
        return True
    try:
        task = sm.state.get_task(task_id)
    except Exception:
        # 查询异常时不能把“状态未知”当作已完成而放开重复提交。
        return True
    return _normalize_task_state((task or {}).get("state")) == const.TASK_STATE_PROCESSING


def _render_generation_activity(task):
    activity = task.get("generation_activity") or {}
    phase = activity.get("phase", "")
    labels = {
        "queued": "Generation Waiting In Queue",
        "preparing": "Generation Preparing",
        "script": "Generation Writing Script",
        "terms": "Generation Preparing Terms",
        "audio": "Generation Preparing Audio",
        "subtitle": "Generation Preparing Subtitles",
        "materials": "Generation Preparing Materials",
        "submitting": "Generation Submitting",
        "checking": "Generation Checking",
        "remote_queued": "Generation Remote Queued",
        "generating": "Generation Remote Running",
        "generated": "Generation Remote Completed",
        "downloading": "Generation Downloading",
        "verifying": "Generation Verifying",
        "rendering": "Generation Rendering",
    }
    st.info(tr(labels.get(phase, "Generating Video")))
    now = time.time()
    started = (task.get("generation_submitted_at") or task.get("generation_started_at")
               or activity.get("started_at") or now)
    elapsed = max(0, int(now - float(started)))
    st.caption(tr("Generation Elapsed").format(time=f"{elapsed // 60:02d}:{elapsed % 60:02d}"))
    if phase in {"submitting", "remote_queued", "generating", "checking"}:
        st.caption(tr("Generation Long Wait Hint"))
        if activity.get("retrying"):
            st.warning(tr("Generation Poll Retry Hint"))
        if activity.get("confirmed_at"):
            age = max(0, int(now - float(activity["confirmed_at"])))
            st.caption(tr("Generation Last Checked").format(seconds=age))
    if phase == "downloading" and activity.get("downloaded_bytes"):
        downloaded = activity["downloaded_bytes"] / (1024 * 1024)
        st.caption(tr("Generation Downloaded").format(size=f"{downloaded:.1f}"))
    if activity.get("remote_id"):
        st.caption(tr("Generation Remote Task").format(task_id=activity["remote_id"]))


def _format_review_finding(warning):
    """把一条成片审查 finding 压成单行文本：序号 + 检测项 + 时间窗 + 明细。"""
    code = str(warning.get("code") or "review_unknown").removeprefix("review_")
    parts = []
    video_index = warning.get("video_index")
    if video_index is not None:
        parts.append(f"#{video_index}")
    parts.append(code)
    start = float(warning.get("start") or 0.0)
    end = float(warning.get("end") or 0.0)
    if end > 0:
        parts.append(f"{start:.2f}s-{end:.2f}s")
    detail = str(warning.get("detail") or "").strip()
    if detail:
        parts.append(detail)
    return " · ".join(parts)


def _render_review_findings(findings):
    """按 severity 分层展示成片审查 findings：error 显性、warn 折叠、info 只进日志。"""
    errors = [f for f in findings if f.get("severity") == "error"]
    warns = [f for f in findings if f.get("severity") == "warn"]
    infos = [f for f in findings if f.get("severity") not in {"error", "warn"}]
    for finding in errors:
        st.error(_format_review_finding(finding))
    if warns:
        with st.expander(tr("Review Findings (Warnings)"), expanded=False):
            for finding in warns:
                st.markdown(f"- {_format_review_finding(finding)}")
    for finding in infos:
        # info 级（例如 review_unavailable）不进入页面正文，只留在生成日志里。
        logger.info(f"review finding (info): {_format_review_finding(finding)}")


def _render_generation_task_snapshot(task_id, task):
    """根据状态存储中的快照渲染进度、失败原因或最终成片。"""
    if not task:
        st.info(tr("Generating Video"))
        _render_generation_logs(task_id)
        return

    state = _normalize_task_state(task.get("state"))
    progress = max(0, min(100, int(task.get("progress", 0) or 0)))
    if state == const.TASK_STATE_PROCESSING:
        _render_generation_activity(task)
        st.progress(
            progress,
            text=f"{tr('Task Progress')}: {progress}%",
        )
        _render_generation_logs(task_id)
        return

    video_files = task.get("videos") or []
    if state == const.TASK_STATE_FAILED:
        error = str(task.get("error") or "").strip()
        error_key = task.get("error_key")
        error_params = task.get("error_params") or {}
        if (
            isinstance(error_key, str)
            and error_key.startswith("codex.")
            and isinstance(error_params, Mapping)
        ):
            error = tr(error_key).format(**error_params)
        message = tr("Video Generation Failed")
        st.error(f"{message}: {error}" if error else message)
        activity = task.get("generation_activity") or {}
        if activity.get("remote_id"):
            st.warning(tr("Generation Existing Task Hint").format(task_id=activity["remote_id"]))
        if not video_files:
            _render_generation_logs(task_id)
            return
    elif state != const.TASK_STATE_COMPLETE or not video_files:
        st.error(tr("Video Generation Failed"))
        _render_generation_logs(task_id)
        return

    if state == const.TASK_STATE_COMPLETE:
        st.success(tr("Video Generation Completed"))
    # 成片审查 findings 与降级警告共用同一条 warnings 通路，但展示按 severity
    # 分层：error 显性提示，warn 折叠进单个 expander，info 只进生成日志。
    review_findings = []
    plain_warnings = []
    for warning in task.get("warnings") or []:
        if (
            isinstance(warning, Mapping)
            and str(warning.get("code", "")).startswith("review_")
        ):
            review_findings.append(warning)
        else:
            plain_warnings.append(warning)
    for warning in plain_warnings:
        if isinstance(warning, Mapping) and warning.get("code") == "batch_materials_reused":
            st.warning(
                tr("Batch Material Reuse Warning").format(
                    index=warning.get("video_index", ""), count=warning.get("count", 0)
                )
            )
        elif isinstance(warning, Mapping) and warning.get("code") == "sonilo_bgm_failed":
            st.warning(
                tr("Sonilo BGM Fallback Warning").format(
                    index=warning.get("video_index", "")
                )
            )
        elif (
            isinstance(warning, Mapping)
            and warning.get("code") == "elevenlabs_bgm_failed"
        ):
            st.warning(
                tr("ElevenLabs BGM Fallback Warning").format(
                    index=warning.get("video_index", "")
                )
            )
        else:
            st.warning(str(warning))
    _render_review_findings(review_findings)

    available_videos = [
        (index, url)
        for index, url in enumerate(video_files)
        if os.path.isfile(url)
    ]
    for index, url in enumerate(video_files):
        if os.path.isfile(url):
            continue
        logger.warning(
            f"generated video is unavailable: "
            f"task_id={task_id}, video_file={url}"
        )

    try:
        if not available_videos:
            st.warning(tr("Generated Video Files Unavailable"))
        else:
            player_cols = st.columns(len(available_videos) * 2 + 1)
            for player_index, (video_index, url) in enumerate(available_videos):
                with player_cols[player_index * 2 + 1]:
                    st.video(url)
                    download_label = tr("Download Video")
                    if len(video_files) > 1:
                        download_label = f"{download_label} {video_index + 1}"
                    download_name = _build_video_download_name(
                        task.get("video_subject"),
                        video_index + 1,
                        len(video_files),
                    )
                    with open(url, "rb") as video_file:
                        st.download_button(
                            download_label,
                            data=video_file,
                            file_name=download_name,
                            mime=mimetypes.guess_type(url)[0] or "video/mp4",
                            key=f"download_generated_video_{task_id}_{video_index}",
                            icon=":material/download:",
                            on_click="ignore",
                            use_container_width=True,
                        )
    except Exception as exc:
        logger.exception(
            f"failed to render generated video preview: task_id={task_id}, "
            f"video_files={video_files}, error={exc}"
        )

    _render_generation_logs(task_id)
    if (
        state == const.TASK_STATE_COMPLETE
        and st.session_state.get("handled_generation_task_id") != task_id
    ):
        # Fragment 可能重复渲染同一个完成任务。无论是否开启自动打开目录，
        # 每个任务都只处理一次完成事件，避免重复弹出资源管理器或重复写入日志。
        st.session_state["handled_generation_task_id"] = task_id
        if config.ui.get("open_task_folder_on_completion", True):
            open_task_folder(task_id)
        logger.info(f"{tr('Video Generation Completed')}: task_id={task_id}")


@st.fragment(run_every=webui_task.TASK_LOG_REFRESH_INTERVAL_SECONDS)
def _render_running_generation_task(task_id):
    """只在任务运行期间轮询；结束后切回静态结果，停止不必要的定时刷新。"""
    try:
        task = sm.state.get_task(task_id)
    except Exception as exc:
        logger.exception(
            f"failed to query WebUI generation task: task_id={task_id}, error={exc}"
        )
        st.warning(tr("Generation Status Unavailable"))
        return

    if not task and not webui_task.is_generation_active(task_id):
        st.warning(tr("Generation Task Unavailable"))
        return
    state = _normalize_task_state((task or {}).get("state"))
    if state in {const.TASK_STATE_COMPLETE, const.TASK_STATE_FAILED}:
        _remove_active_generation_task(task_id)
        # 完整页面脚本现在没有耗时生成逻辑，可以安全 rerun 并把结果改为静态
        # 渲染。这样任务结束后不会让浏览器永久保留一个两秒轮询的 Fragment。
        st.rerun(scope="app")

    _render_generation_task_snapshot(task_id, task)
    if not webui_task.is_generation_active(task_id):
        # 持久状态可能属于重启前或另一服务进程，不能断言远端任务已停止。
        # 只允许解除当前页面的跟踪，不取消任务、不改写其真实状态。
        st.warning(tr("Generation Untracked Worker Hint"))
        if st.button(tr("Stop Tracking Generation"), key=f"stop_tracking_generation_{task_id}"):
            _remove_active_generation_task(task_id)
            st.session_state["current_generation_task_id"] = ""
            st.query_params.pop("generation_task", None)
            st.rerun(scope="app")


def _render_current_generation_task():
    """在生成按钮下方恢复当前页面最近提交任务的可查询 UI。"""
    task_id = _current_generation_task_id()
    if not task_id:
        return

    try:
        task = sm.state.get_task(task_id)
    except Exception as exc:
        logger.exception(
            f"failed to query current WebUI task: task_id={task_id}, error={exc}"
        )
        # 即使首次读取失败，也要注册 Fragment，让状态后端恢复后自动继续。
        _render_running_generation_task(task_id)
        return

    if not task and not webui_task.is_generation_active(task_id):
        st.warning(tr("Generation Task Unavailable"))
        return
    state = _normalize_task_state((task or {}).get("state"))
    if state in {const.TASK_STATE_COMPLETE, const.TASK_STATE_FAILED}:
        _remove_active_generation_task(task_id)
        _render_generation_task_snapshot(task_id, task)
        return

    _render_running_generation_task(task_id)


def get_llm_provider_tips(provider_id, **kwargs):
    # LLM provider 说明文案统一使用 `llm_provider_tips.<provider_id>` 规则。
    # 这样新增 provider 时只需要在 locale 中补文案；没有文案时不展示提示块，
    # 避免 Main.py 里继续堆叠大量中英文硬编码说明。
    provider = get_llm_provider(provider_id)
    if provider is None:
        return ""

    # Provider 配置说明目前统一维护中文和英文两套规范模板；其它界面语言
    # 统一使用英文，避免在 locale 中复制英文后长期不同步。后续某个语种完成
    # 全量翻译后，再将它加入这里的独立维护范围。
    ui_language = st.session_state.get("ui_language", "en")
    tips_language = ui_language if ui_language in {"zh", "en"} else "en"
    tips = (
        locales.get(tips_language, {}).get("Translation", {}).get(provider.tips_key, "")
    )
    if not tips:
        return tips

    service_endpoint = provider.preferred_service_endpoint(
        prefer_international=tips_language == "en"
    )
    api_key_url = (
        service_endpoint.api_key_url
        if service_endpoint
        else provider.effective_api_key_url()
    )
    format_context = {
        "api_key_url": api_key_url,
        "default_model": provider.default_model,
        "default_base_url": (
            service_endpoint.base_url
            if service_endpoint
            else provider.effective_default_base_url
        ),
        "model_docs_url": (
            service_endpoint.model_docs_url
            if service_endpoint and service_endpoint.model_docs_url
            else provider.effective_model_docs_url(
                prefer_international=tips_language == "en"
            )
        ),
        **{
            f"default_{field.config_suffix}": field.default_value
            for field in provider.extra_fields
        },
        **kwargs,
    }
    try:
        return tips.format(**format_context)
    except Exception as e:
        logger.warning(f"format llm provider tips failed: {provider_id}, {e}")
        return tips


def format_llm_connection_error(provider_id, base_url, error):
    """为可明确定位的鉴权错误补充配置检查建议，同时保留原始响应。"""
    error_text = str(error or "").strip()
    if provider_id in {"openai_codex", "openai_chatgpt"}:
        if provider_id == "openai_chatgpt":
            from app.services.chatgpt_oauth import ERROR_MESSAGES
            message_prefix = "chatgpt.oauth"
        else:
            from app.services.codex_oauth import ERROR_MESSAGES
            message_prefix = "codex.oauth"

        for key, message in ERROR_MESSAGES.items():
            if error_text == message:
                return tr(f"{message_prefix}.{key}")
        status_match = re.fullmatch(
            r"OpenAI - (?:Codex|ChatGPT \(Native OAuth\)) returned HTTP (\d+)\. Check the selected model and your account access\.",
            error_text,
        )
        if status_match:
            return tr(f"{message_prefix}.http_error").format(status=status_match[1])
    normalized_error = error_text.lower()
    authentication_markers = (
        "401",
        "authentication",
        "invalid api key",
        "invalid_api_key",
        "unauthorized",
    )
    provider = get_llm_provider(provider_id)
    if provider is None or not provider.service_endpoints or not any(
        marker in normalized_error for marker in authentication_markers
    ):
        return error_text

    message = tr_optional(
        provider.authentication_error_key,
        fallback_language="en",
    )
    if not message:
        return error_text
    return message.format(base_url=base_url or "-", error=error_text)


def get_llm_provider_label(provider):
    return tr_optional(provider.label_key) or provider.default_label


def get_tts_provider_tips(provider_id):
    # TTS 配置说明与 LLM Provider 采用相同维护策略：只维护中英文，
    # 其它界面语言统一回退英文，避免复制后长期不同步。
    ui_language = st.session_state.get("ui_language", "en")
    tips_language = ui_language if ui_language in {"zh", "en"} else "en"
    return (
        locales.get(tips_language, {})
        .get("Translation", {})
        .get(f"tts_provider_tips.{provider_id}", "")
    )


def localized_widget_key(name, *parts):
    # 部分 Streamlit selectbox 使用稳定 key 记住选择状态，但展示文本来自 locale。
    # 语言切换时把语言也放进 key，可以强制重建控件，避免选中项仍显示旧语言。
    language = st.session_state.get("ui_language", config.ui.get("language", ""))
    suffix_parts = [name, language, *[str(part) for part in parts if part]]
    return "_".join(suffix_parts)


def stable_selectbox(label, options, default_value, key, format_func=None, **kwargs):
    # Streamlit 1.59 对 selectbox 的状态复用更敏感：如果控件没有固定 key，
    # 或者真实选项只是一组临时下标，页面 rerun 后容易被重新计算的 index 覆盖，
    # 表现为用户第一次选择不生效、需要再选一次。这个 helper 统一用稳定业务值
    # 作为真实选项，并在 session_state 里保存该值；展示文案只通过 format_func
    # 转换，避免翻译文案、选项顺序或上游配置变化影响选择状态。
    options = list(options)
    if not options:
        raise ValueError(f"selectbox options cannot be empty: {key}")

    if default_value not in options:
        default_value = options[0]

    widget_key = localized_widget_key(key)
    selected_value = st.session_state.get(widget_key)
    accepts_custom_value = bool(kwargs.get("accept_new_options"))
    has_valid_custom_value = (
        accepts_custom_value
        and isinstance(selected_value, str)
        and bool(selected_value.strip())
    )
    if selected_value not in options and not has_valid_custom_value:
        # 如果上游选项发生变化（例如切换 TTS provider 后声音列表变了），
        # 旧值已经不合法。控件创建前直接初始化 session_state，之后只让 key
        # 管理状态，不再同时传入 index。这样可以避免 Streamlit 在 rerun 时
        # 用重新计算的 index 覆盖用户刚选择的值，导致第一次选择不生效。
        st.session_state[widget_key] = default_value

    if format_func is None:
        format_func = str

    return st.selectbox(
        label,
        options=options,
        format_func=format_func,
        key=widget_key,
        **kwargs,
    )


# Streamlit 原生 selectbox 暂不支持 HTML optgroup。这里使用 1.59 自带的
# Components v2 封装原生 <select>/<optgroup>，无需引入前端依赖，同时保留浏览器
# 原生的键盘导航、无障碍语义和移动端选择体验。组件只传递固定业务值和翻译文本，
# 不接收任意 HTML，从边界上避免配置内容进入 innerHTML。
_GROUPED_SELECT_COMPONENT = st.components.v2.component(
    "changofilm_grouped_select",
    html="""
        <div class="changofilm-grouped-select">
            <div class="changofilm-grouped-select__label-row">
                <label class="changofilm-grouped-select__label"></label>
                <button class="changofilm-grouped-select__settings" type="button"></button>
            </div>
            <div class="changofilm-grouped-select__control">
                <select></select>
            </div>
        </div>
    """,
    css="""
        .changofilm-grouped-select {
            width: 100%;
            color: var(--st-text-color);
            font-family: var(--st-font);
        }

        .changofilm-grouped-select__label-row {
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 0.45rem;
            margin-bottom: 0.35rem;
        }

        .changofilm-grouped-select__label {
            font-size: 0.875rem;
            line-height: 1.25rem;
        }

        .changofilm-grouped-select__settings {
            padding: 0;
            border: 0;
            background: transparent;
            color: var(--st-link-color);
            font: inherit;
            font-size: 0.8rem;
            line-height: 1.25rem;
            cursor: pointer;
        }

        .changofilm-grouped-select__settings:hover {
            text-decoration: underline;
            text-underline-offset: 0.15rem;
        }

        .changofilm-grouped-select__settings:focus-visible {
            border-radius: 0.2rem;
            outline: 2px solid var(--st-primary-color);
            outline-offset: 2px;
        }

        .changofilm-grouped-select__control {
            position: relative;
        }

        .changofilm-grouped-select__control::after {
            position: absolute;
            top: 50%;
            right: 1rem;
            width: 0.55rem;
            height: 0.55rem;
            border-right: 2px solid currentColor;
            border-bottom: 2px solid currentColor;
            content: "";
            pointer-events: none;
            transform: translateY(-70%) rotate(45deg);
        }

        .changofilm-grouped-select select {
            width: 100%;
            min-height: 2.5rem;
            padding: 0.45rem 2.75rem 0.45rem 0.75rem;
            border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
            border-radius: 0.5rem;
            outline: none;
            appearance: none;
            background: var(--st-secondary-background-color);
            color: inherit;
            font: inherit;
            cursor: pointer;
        }

        .changofilm-grouped-select select:hover {
            border-color: color-mix(in srgb, currentColor 36%, transparent);
        }

        .changofilm-grouped-select select:focus-visible {
            border-color: var(--st-primary-color);
            box-shadow: 0 0 0 1px var(--st-primary-color);
        }
    """,
    js="""
        export default function(component) {
            const { data, parentElement, setTriggerValue } = component;
            const label = parentElement.querySelector("label");
            const settings = parentElement.querySelector(".changofilm-grouped-select__settings");
            const select = parentElement.querySelector("select");

            label.textContent = data.label;
            settings.textContent = data.settingsLabel;
            settings.hidden = !data.settingsLabel;
            select.id = data.controlId;
            label.htmlFor = data.controlId;
            select.setAttribute("aria-label", data.label);
            select.replaceChildren();

            for (const groupData of data.groups) {
                const group = document.createElement("optgroup");
                group.label = groupData.label;
                for (const optionData of groupData.options) {
                    const option = document.createElement("option");
                    option.value = optionData.value;
                    option.textContent = optionData.label;
                    group.appendChild(option);
                }
                select.appendChild(group);
            }

            select.value = data.value;
            const handleChange = () => {
                setTriggerValue("selected", select.value);
            };
            const handleSettings = () => {
                setTriggerValue("settings", true);
            };
            select.addEventListener("change", handleChange);
            settings.addEventListener("click", handleSettings);

            return () => {
                select.removeEventListener("change", handleChange);
                settings.removeEventListener("click", handleSettings);
            };
        }
    """,
)


def grouped_selectbox(
    label,
    groups,
    default_value,
    key,
    format_func=None,
    settings_label="",
    on_settings=None,
):
    """渲染带不可选分组标题的单个下拉框，并返回稳定业务值。"""
    if format_func is None:
        format_func = str

    normalized_groups = []
    valid_values = []
    for group_label, options in groups:
        normalized_options = []
        for option in options:
            valid_values.append(option)
            normalized_options.append(
                {"value": option, "label": str(format_func(option))}
            )
        if normalized_options:
            normalized_groups.append(
                {"label": str(group_label), "options": normalized_options}
            )

    if not valid_values:
        raise ValueError(f"grouped selectbox options cannot be empty: {key}")
    if len(set(valid_values)) != len(valid_values):
        raise ValueError(f"grouped selectbox options must be unique: {key}")
    if default_value not in valid_values:
        default_value = valid_values[0]

    # 业务选择保存在与旧 selectbox 相同的 session key 中，设置预设恢复和
    # 语言切换逻辑无需分叉；组件自身使用独立 key，避免与业务状态冲突。
    widget_key = localized_widget_key(key)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = default_value
    selected_value = st.session_state[widget_key]
    if selected_value not in valid_values:
        selected_value = default_value
        st.session_state[widget_key] = selected_value

    result = _GROUPED_SELECT_COMPONENT(
        key=f"{widget_key}_component",
        data={
            "label": label,
            "settingsLabel": settings_label,
            # 显式关联可见 label 与原生 select。组件 key 由固定业务名称和
            # 语言代码组成，在页面内唯一，既方便鼠标点击标签聚焦控件，
            # 也不会引入随机 ID 导致每次 rerun 都重建前端状态。
            "controlId": f"{widget_key}_control",
            "value": selected_value,
            "groups": normalized_groups,
        },
        on_selected_change=lambda: None,
        on_settings_change=on_settings or (lambda: None),
    )
    changed_value = getattr(result, "selected", None)
    if changed_value in valid_values and changed_value != selected_value:
        st.session_state[widget_key] = changed_value
        # Components v2 在当前脚本轮次返回事件时，本轮传给前端的 data 仍是
        # 事件发生前的旧值。立即自动 rerun，让组件和依赖 video_source 的控件
        # 同时收到新值；否则下拉框会被旧 data 短暂覆盖，用户只能再选一次。
        st.rerun()

    return selected_value


def sync_script_order_concat_mode():
    """在文案顺序匹配开启时固定使用顺序拼接，并在关闭后恢复原选择。"""
    widget_key = localized_widget_key("video_concat_mode_select")
    previous_key = "video_concat_mode_before_script_order_match"
    match_script_order = bool(st.session_state.get("match_materials_to_script", False))

    if match_script_order:
        current_mode = st.session_state.get(widget_key, VideoConcatMode.random.value)
        if current_mode != VideoConcatMode.sequential.value:
            st.session_state[previous_key] = current_mode
        st.session_state[widget_key] = VideoConcatMode.sequential.value
        return

    previous_mode = st.session_state.pop(previous_key, None)
    if previous_mode in {
        VideoConcatMode.sequential.value,
        VideoConcatMode.random.value,
    }:
        st.session_state[widget_key] = previous_mode


def reset_script_system_prompt():
    """将高级脚本设置中的系统提示词恢复为当前版本的默认内容。"""
    st.session_state["custom_system_prompt"] = llm.DEFAULT_SCRIPT_SYSTEM_PROMPT


def reset_subtitle_settings():
    """恢复 WebUI 字幕控件和持久化配置中的默认值。"""
    defaults = DEFAULT_SUBTITLE_SETTINGS
    st.session_state["subtitle_enabled_checkbox"] = defaults["subtitle_enabled"]
    _set_stable_widget_value("font_name_select", defaults["font_name"])
    _set_stable_widget_value("subtitle_position_select", defaults["subtitle_position"])
    _set_stable_widget_value(
        "subtitle_display_mode_select", defaults["subtitle_display_mode"]
    )
    _set_stable_widget_value(
        "subtitle_animation_select", defaults["subtitle_animation"]
    )
    st.session_state["custom_position_input"] = str(defaults["custom_position"])
    st.session_state["font_color_picker"] = defaults["text_fore_color"]
    st.session_state["font_size_slider"] = defaults["font_size"]
    st.session_state["stroke_color_picker"] = defaults["stroke_color"]
    st.session_state["stroke_width_slider"] = defaults["stroke_width"]
    st.session_state["subtitle_background_enabled_checkbox"] = defaults[
        "subtitle_background_enabled"
    ]
    st.session_state["subtitle_background_color_picker"] = defaults[
        "subtitle_background_color"
    ]
    st.session_state["rounded_subtitle_background_checkbox"] = defaults[
        "rounded_subtitle_background"
    ]

    # 同步会持久化的 UI 选项，确保恢复后刷新页面仍保持默认设置。
    for key in (
        "subtitle_enabled",
        "font_name",
        "subtitle_position",
        "subtitle_display_mode",
        "subtitle_animation",
        "custom_position",
        "text_fore_color",
        "font_size",
        "stroke_color",
        "stroke_width",
        "subtitle_background_enabled",
        "subtitle_background_color",
        "rounded_subtitle_background",
    ):
        if key in defaults:
            _set_runtime_config("ui", key, defaults[key])


@st.dialog(tr("Final Prompt Preview"), width="large")
def render_script_prompt_preview(prompt):
    """展示将要发送给大模型的完整脚本生成提示词。"""
    st.code(prompt, language="markdown", wrap_lines=True)


def stable_segmented_control(
    label, options, default_value, key, format_func=None, **kwargs
):
    """使用稳定业务值创建单选分段控件，避免语言切换后状态被展示文案覆盖。"""
    options = list(options)
    if not options:
        raise ValueError(f"segmented control options cannot be empty: {key}")

    if default_value not in options:
        default_value = options[0]

    widget_key = localized_widget_key(key)
    if st.session_state.get(widget_key) not in options:
        st.session_state[widget_key] = default_value

    return st.segmented_control(
        label,
        options=options,
        selection_mode="single",
        required=True,
        format_func=format_func or str,
        key=widget_key,
        **kwargs,
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_groq_model_ids(api_key: str, base_url: str) -> list[str]:
    if not api_key:
        return []

    normalized_base_url = (
        (base_url or "https://api.groq.com/openai/v1").strip().rstrip("/")
    )
    models_url = f"{normalized_base_url}/models"

    try:
        response = trace_http_call(
            "GET", requests.get,
            models_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])

        model_ids = []
        for item in data:
            if isinstance(item, dict):
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    model_ids.append(model_id.strip())

        return sorted(set(model_ids))
    except Exception as e:
        logger.warning(f"failed to fetch groq models: {e}")
        return []


def _get_material_api_keys(config_key):
    """将配置中的素材 API Key 统一转换为 WebUI 可编辑字符串。"""
    api_keys = config.snapshot_config_with_pending(config.app).get(config_key, [])
    if isinstance(api_keys, str):
        api_keys = [api_keys]
    return ", ".join(api_keys)


def _save_material_api_keys(config_key, value):
    """保存逗号分隔的素材 API Key，并允许用户显式清空旧配置。"""
    normalized_value = value.replace(" ", "")
    _set_runtime_config(
        "app",
        config_key,
        normalized_value.split(",") if normalized_value else [],
    )


def _format_file_size(size_bytes):
    """将字节数格式化为适合设置页展示的紧凑容量文本。"""
    size = float(max(0, size_bytes))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


@st.cache_data(ttl=30, show_spinner=False)
def _get_video_cache_stats_data(max_age_days=None):
    """
    短周期缓存目录统计，避免设置弹窗内普通控件交互反复扫描大量文件。

    缓存键包含清理天数，因此切换范围只会为每个范围扫描一次；主动刷新或清理
    完成后会显式清空，最多 30 秒的缓存不会影响实际删除时的二次扫描。

    这里只缓存纯 dict，而不是 VideoCacheStats 实例：st.cache_data 需要用 pickle
    序列化返回值，而 pickle 保存自定义类时按「模块名 + 类名」引用，并校验解析
    出来的类与实例的类是同一个对象。Streamlit 源码监视器在本地源码文件发生变化
    时（包含 Windows 上防病毒或索引器引起的偶发事件）会清空 sys.modules 中的
    被监视模块并重新导入；此时仍打开的设置弹窗（Dialog 继承 fragment 行为，
    内部交互不会重建 Main.py 顶层引用）持有的还是旧模块里的类，pickle 会抛
    PicklingError: it's not the same object as ...，并被 Streamlit 包装成
    UnserializableReturnValueError（对应 Streamlit 官方 issue #14593 的已知缺陷）。
    纯 dict 按值序列化、不含类引用，因此不受模块重新导入影响。
    """
    stats = cache_manager.get_video_cache_stats(max_age_days=max_age_days)
    # 字段名与 VideoCacheStats 完全一致，供下方 _get_video_cache_stats 直接展开
    # 还原；今后若 VideoCacheStats 增删字段，需要同步维护这里的字段映射。
    return {
        "file_count": stats.file_count,
        "total_size": stats.total_size,
        "oldest_mtime": stats.oldest_mtime,
        "newest_mtime": stats.newest_mtime,
    }


def _get_video_cache_stats(max_age_days=None) -> cache_manager.VideoCacheStats:
    """在缓存边界之外把纯数据还原为 VideoCacheStats，调用方属性访问方式不变。"""

    # 还原时使用当前生效的 cache_manager 模块；即使模块被重新导入，也只是重建
    # 一个轻量 dataclass，不会再触发 pickle 的「类引用身份」校验。
    return cache_manager.VideoCacheStats(
        **_get_video_cache_stats_data(max_age_days=max_age_days)
    )


def _render_cache_management_settings(panel):
    """渲染默认在线视频素材缓存的统计、预览和安全清理操作。"""
    with panel:
        cleanup_message = st.session_state.pop("video_cache_cleanup_message", None)
        if cleanup_message:
            message_type, message = cleanup_message
            if message_type == "success":
                st.success(message)
            else:
                st.warning(message)

        st.caption(tr("Video Cache Directory"))
        st.code(cache_manager.video_cache_dir(), language="text")

        total_stats = _get_video_cache_stats()
        metric_count, metric_size, metric_oldest = st.columns(3)
        metric_count.metric(tr("Cache File Count"), total_stats.file_count)
        metric_size.metric(
            tr("Cache Total Size"), _format_file_size(total_stats.total_size)
        )
        oldest_text = (
            datetime.fromtimestamp(total_stats.oldest_mtime).strftime("%Y-%m-%d")
            if total_stats.oldest_mtime is not None
            else "-"
        )
        metric_oldest.metric(tr("Oldest Cache Date"), oldest_text)

        st.caption(tr("Video Cache Management Help"))
        cleanup_options = (30, 7, 90, None)
        cleanup_labels = {
            30: tr("Cache Older Than 30 Days"),
            7: tr("Cache Older Than 7 Days"),
            90: tr("Cache Older Than 90 Days"),
            None: tr("All Video Cache"),
        }
        max_age_days = st.selectbox(
            tr("Cache Cleanup Range"),
            options=cleanup_options,
            format_func=lambda value: cleanup_labels[value],
            key="video_cache_cleanup_range",
        )
        cleanup_preview = _get_video_cache_stats(max_age_days=max_age_days)
        st.info(
            tr("Cache Cleanup Preview").format(
                count=cleanup_preview.file_count,
                size=_format_file_size(cleanup_preview.total_size),
            )
        )

        confirm_nonce = st.session_state.get("video_cache_cleanup_confirm_nonce", 0)
        confirmed = st.checkbox(
            tr("Confirm Cache Cleanup"),
            key=f"video_cache_cleanup_confirm_{confirm_nonce}",
        )
        refresh_col, open_col, cleanup_col = st.columns(3)
        if refresh_col.button(
            tr("Refresh Cache Stats"),
            key="refresh_video_cache_stats",
            use_container_width=True,
            icon=":material/refresh:",
        ):
            _get_video_cache_stats_data.clear()
            st.rerun(scope="fragment")

        if open_col.button(
            tr("Open Cache Directory"),
            key="open_video_cache_directory",
            use_container_width=True,
            icon=":material/folder_open:",
        ):
            webbrowser.open(Path(cache_manager.video_cache_dir()).as_uri())

        cleanup_disabled = not confirmed or cleanup_preview.file_count == 0
        if cleanup_col.button(
            tr("Clean Cache Now"),
            key="clean_video_cache_now",
            type="primary",
            disabled=cleanup_disabled,
            use_container_width=True,
            icon=":material/delete_sweep:",
        ):
            result = cache_manager.clean_video_cache(max_age_days=max_age_days)
            message_key = (
                "Cache Cleanup Completed With Failures"
                if result.failed_count
                else "Cache Cleanup Completed"
            )
            st.session_state["video_cache_cleanup_message"] = (
                "warning" if result.failed_count else "success",
                tr(message_key).format(
                    count=result.deleted_count,
                    size=_format_file_size(result.deleted_size),
                    failed=result.failed_count,
                ),
            )
            # Streamlit 不允许在控件实例化后修改同名 session_state。通过递增
            # nonce 让下一次 fragment rerun 创建未勾选的新控件，避免清理完成后
            # 危险确认状态被继续保留。
            st.session_state["video_cache_cleanup_confirm_nonce"] = confirm_nonce + 1
            _get_video_cache_stats_data.clear()
            st.rerun(scope="fragment")


# -----------------------------------------------------------------------------
# 设置预设导出导入与密钥备份
# -----------------------------------------------------------------------------


def _is_credential_config_key(key):
    """判断一个配置项名称是否表示凭据。"""
    return str(key).endswith(CREDENTIAL_KEY_SUFFIXES)


def _is_backup_config_key(section_name, key):
    """凭据本身及其配套配置项都属于密钥备份范围。"""
    if _is_credential_config_key(key):
        return True
    if key in CREDENTIAL_COMPANION_KEYS.get(section_name, ()):
        return True
    return key in NON_LLM_COMPANION_KEYS.get(section_name, ())


def _credential_widget_state_keys(section_name, key):
    """
    返回某个凭据配置项对应的全部 Streamlit 控件 key。

    密码输入框都带 key，Streamlit 中 session_state 的值优先于控件的 value
    参数。恢复备份后必须清除这些残留控件状态，否则页面会继续显示旧密钥，
    并在下一次 rerun 把旧值重新写回配置，让恢复看起来没有生效。多个面板
    共用同一个密钥时会各自持有控件状态，因此返回默认 key 和全部别名。
    """
    if section_name == "app":
        default_widget_key = f"{key}_input"
    else:
        default_widget_key = f"{section_name}_{key}_input"
    return (
        default_widget_key,
        *CREDENTIAL_WIDGET_STATE_ALIASES.get((section_name, key), ()),
    )


def _normalize_backup_value(value):
    """归一化备份值，丢弃空字符串和空列表，避免恢复时覆盖成空配置。"""
    if isinstance(value, list):
        items = [
            str(item).strip()
            for item in value
            if isinstance(item, (str, int, float)) and str(item).strip()
        ]
        return items or None
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        text = str(value).strip()
        return text or None
    return None


def _collect_key_backup(config_sections):
    """从运行期配置分区中收集所有已填写的密钥及其配套配置项。"""
    backup = {}
    for section_name, section in config_sections.items():
        if section_name in KEY_BACKUP_EXCLUDED_SECTIONS:
            continue
        entries = {}
        for key, value in section.items():
            if not _is_backup_config_key(section_name, key):
                continue
            normalized_value = _normalize_backup_value(value)
            if normalized_value is not None:
                entries[key] = normalized_value
        if entries:
            backup[section_name] = entries
    return backup


def _count_backup_keys(backup):
    """统计备份中的配置项数量，用于界面提示和禁用空导出。"""
    return sum(len(entries) for entries in backup.values())


def _build_key_backup_payload(config_sections, app_version):
    """构造密钥备份文件内容。"""
    return {
        "schema": KEY_BACKUP_SCHEMA,
        "version": KEY_BACKUP_VERSION,
        "app_version": str(app_version),
        "keys": _collect_key_backup(config_sections),
    }


def _load_transfer_payload(raw_bytes, schema, version):
    """
    解析导出文件，并校验它确实来自本功能的同一版本。

    用户可能上传任意 JSON。这里只接受声明了正确 schema 和版本的文件，让错误
    提示停留在导入入口，而不是把无法识别的内容写进配置或控件状态。
    Windows 编辑器可能保存带 BOM 的 JSON，因此按 utf-8-sig 解码。
    """
    if len(raw_bytes) > MAX_SETTINGS_TRANSFER_BYTES:
        raise ValueError("settings import exceeds the 2 MB limit")
    payload = json.loads(raw_bytes.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("exported file must contain a JSON object")
    if payload.get("schema") not in (schema, _LEGACY_SCHEMA_ALIASES.get(schema)):
        raise ValueError(f"unexpected schema: {payload.get('schema')!r}")
    if payload.get("version") != version:
        raise ValueError(f"unsupported version: {payload.get('version')!r}")
    return payload


def _parse_key_backup(raw_bytes, config_sections):
    """
    解析密钥备份文件，只保留当前版本认识的分区和配置项。

    备份文件可以手工编辑，也可能来自更新的版本。未知分区或非密钥配置项一律
    忽略，避免通过导入功能改写与凭据无关的配置。
    """
    payload = _load_transfer_payload(raw_bytes, KEY_BACKUP_SCHEMA, KEY_BACKUP_VERSION)
    keys = payload.get("keys")
    if not isinstance(keys, dict):
        raise ValueError("key backup file has no keys object")

    restored = {}
    for section_name, entries in keys.items():
        if section_name not in config_sections:
            continue
        if section_name in KEY_BACKUP_EXCLUDED_SECTIONS:
            continue
        if not isinstance(entries, dict):
            continue
        section_entries = {}
        for key, value in entries.items():
            if not _is_backup_config_key(section_name, key):
                continue
            normalized_value = _normalize_backup_value(value)
            if normalized_value is not None:
                section_entries[key] = normalized_value
        if section_entries:
            restored[section_name] = section_entries

    if not restored:
        raise ValueError("key backup file contains no restorable keys")
    return restored


def _build_settings_preset_payload(params, app_version):
    """构造生成参数预设文件内容。"""
    preset_params = {
        key: value
        for key, value in params.items()
        if key not in PRESET_EXCLUDED_PARAM_KEYS
    }
    if params.get("bgm_type") == "preset" and params.get("bgm_file"):
        try:
            builtin_bgm_path = bgm_service.resolve_builtin_bgm_file(
                str(params["bgm_file"])
            )
        except ValueError:
            # 自定义文件属于本机资源，不能进入可移植的设置预设。异常场景下保持
            # 既有排除行为，避免导出文件包含绝对路径或另一台设备不存在的 UUID。
            pass
        else:
            preset_params["bgm_file"] = Path(builtin_bgm_path).name
    return {
        "schema": SETTINGS_PRESET_SCHEMA,
        "version": SETTINGS_PRESET_VERSION,
        "app_version": str(app_version),
        "params": preset_params,
    }


def _parse_settings_preset(raw_bytes):
    """
    解析预设文件并交给 VideoParams 校验。

    预设可以在其它机器上生成，也可能被手工编辑。统一走模型校验可以复用既有
    的取值范围约束，非法预设在导入时就被拒绝，而不是在生成任务时才失败。
    """
    payload = _load_transfer_payload(
        raw_bytes, SETTINGS_PRESET_SCHEMA, SETTINGS_PRESET_VERSION
    )
    preset_params = payload.get("params")
    if not isinstance(preset_params, dict):
        raise ValueError("settings preset file has no params object")

    params_input = {
        key: value
        for key, value in preset_params.items()
        if key not in PRESET_EXCLUDED_PARAM_KEYS
    }
    if preset_params.get("bgm_type") == "preset" and preset_params.get("bgm_file"):
        # 设置预设只能恢复当前版本真实存在的内置歌曲。服务层同时拒绝目录分隔符
        # 和用户上传文件，防止导入文件借试听功能读取任意本机路径。
        builtin_bgm_path = bgm_service.resolve_builtin_bgm_file(
            str(preset_params["bgm_file"])
        )
        params_input["bgm_file"] = Path(builtin_bgm_path).name
    # video_subject 是 VideoParams 的必填字段，但预设允许只保存风格设置。
    params_input.setdefault("video_subject", "")
    return VideoParams.model_validate(params_input).model_dump(mode="json")


def _apply_key_backup(restored_keys):
    """把解析后的密钥写回运行期配置，并清除对应控件的残留状态。"""
    restored_count = 0
    for section_name, entries in restored_keys.items():
        for key, value in entries.items():
            _set_runtime_config(section_name, key, value)
            for widget_key in _credential_widget_state_keys(section_name, key):
                st.session_state.pop(widget_key, None)
            restored_count += 1
    # ElevenLabs 音色列表按密钥缓存，换用另一份备份后必须重新拉取。
    for cache_key in list(st.session_state.keys()):
        if str(cache_key).startswith("elevenlabs_voices_"):
            del st.session_state[cache_key]
    return restored_count


def _apply_pending_settings_preset():
    """在渲染任何控件之前应用已导入的预设。"""
    preset_params = st.session_state.pop("settings_preset_payload", None)
    if not preset_params:
        return False
    if _project_is_locked():
        # 锁定项目的参数不允许被预设静默覆盖；提示后丢弃本次导入。
        st.toast(tr("Project Locked Preset Refused"), icon="🔒")
        return False

    _apply_restored_params(preset_params)
    logger.info("applied imported settings preset")
    return True


def _render_settings_transfer(params):
    """渲染生成参数预设的导出与导入入口。"""
    with st.expander(tr("Settings Preset"), expanded=False):
        st.caption(tr("Settings Preset Help"))
        preset_payload = _build_settings_preset_payload(
            params.model_dump(mode="json"), config.project_version
        )
        st.download_button(
            tr("Export Settings"),
            data=json.dumps(preset_payload, ensure_ascii=False, indent=2).encode(
                "utf-8"
            ),
            file_name=SETTINGS_PRESET_FILE_NAME,
            mime="application/json",
            use_container_width=True,
            key="export_settings_preset_button",
            icon=":material/download:",
        )
        uploaded_preset = st.file_uploader(
            tr("Import Settings"),
            type=["json"],
            key="settings_preset_uploader",
        )
        if uploaded_preset is None:
            return
        # 上传的文件在之后每次 rerun 都会重新出现。记录已处理的文件标识，
        # 避免用户改完控件后被同一个预设反复覆盖。
        if st.session_state.get("settings_preset_file_id") == uploaded_preset.file_id:
            return

        st.session_state["settings_preset_file_id"] = uploaded_preset.file_id
        try:
            preset_params = _parse_settings_preset(uploaded_preset.getvalue())
        except Exception as e:
            logger.warning(f"failed to import settings preset: {e}")
            st.error(tr("Settings Preset Import Failed"))
            return

        st.session_state["settings_preset_payload"] = preset_params
        st.rerun()


def _preset_library_dir():
    return os.path.join(utils.storage_dir(), PRESET_LIBRARY_DIR_NAME)


def _preset_library_path(preset_id):
    """预设库文件路径；非法或越界 ID 返回 None（与项目快照同一防线）。"""
    try:
        normalized_id = str(UUID(str(preset_id)))
    except (ValueError, TypeError, AttributeError):
        return None
    library_root = os.path.realpath(_preset_library_dir())
    preset_path = os.path.realpath(
        os.path.join(library_root, f"{normalized_id}.json")
    )
    try:
        if os.path.commonpath([library_root, preset_path]) != library_root:
            return None
    except ValueError:
        return None
    return preset_path


def _write_library_preset(preset_id, name, params_dict):
    """原子写入具名预设；文件体复用设置预设 schema，额外携带名称与时间。"""
    preset_file = _preset_library_path(preset_id)
    if not preset_file:
        return False
    payload = _build_settings_preset_payload(params_dict, config.project_version)
    payload["name"] = str(name)
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        os.makedirs(os.path.dirname(preset_file), exist_ok=True)
        tmp_file = preset_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, preset_file)
        return True
    except OSError as e:
        logger.warning(f"failed to write library preset: {preset_id}, {e}")
        return False


def _read_library_preset(preset_id):
    """读取并校验库预设；损坏或 schema 不符的条目跳过，不拖垮整页。"""
    preset_file = _preset_library_path(preset_id)
    if not preset_file or not os.path.isfile(preset_file):
        return None
    try:
        with open(preset_file, "rb") as f:
            raw_bytes = f.read()
        meta = _load_transfer_payload(
            raw_bytes, SETTINGS_PRESET_SCHEMA, SETTINGS_PRESET_VERSION
        )
        params_dict = _parse_settings_preset(raw_bytes)
    except Exception as e:
        logger.warning(f"skip unreadable library preset: {preset_id}, {e}")
        return None
    return {
        "preset_id": str(preset_id),
        "name": str(meta.get("name") or preset_id),
        "saved_at": str(meta.get("saved_at") or ""),
        "params": params_dict,
        "builtin": False,
    }


def _scan_library_presets():
    """按最近保存排序扫描用户预设库。"""
    library_root = _preset_library_dir()
    if not os.path.isdir(library_root):
        return []
    entries = []
    try:
        with os.scandir(library_root) as files:
            for entry in files:
                if not entry.name.endswith(".json") or not entry.is_file(
                    follow_symlinks=False
                ):
                    continue
                preset = _read_library_preset(entry.name[:-5])
                if preset:
                    entries.append(
                        (entry.stat(follow_symlinks=False).st_mtime, preset)
                    )
    except OSError as e:
        logger.warning(f"failed to scan preset library: {library_root}, {e}")
        return []
    entries.sort(key=lambda item: item[0], reverse=True)
    return [preset for _, preset in entries]


def _builtin_preset_entries():
    """内置预设同样走 VideoParams 校验，保证与控件回填链路一致。"""
    entries = []
    for preset_id, name_key, overrides in BUILTIN_PRESETS:
        params_dict = VideoParams(video_subject="", **overrides).model_dump(
            mode="json"
        )
        entries.append(
            {
                "preset_id": preset_id,
                "name": tr(name_key),
                "saved_at": "",
                "params": params_dict,
                "builtin": True,
            }
        )
    return entries


def _find_preset_entry(preset_id):
    preset_id = str(preset_id)
    if preset_id.startswith("builtin-"):
        for entry in _builtin_preset_entries():
            if entry["preset_id"] == preset_id:
                return entry
        return None
    return _read_library_preset(preset_id)


def _save_current_as_preset():
    """把当前创作参数存为具名预设；不改变项目绑定与脏状态。"""
    name = str(st.session_state.get("preset_name_input") or "").strip()
    if not name:
        st.session_state["preset_name_missing"] = True
        return
    params_dict = dict(st.session_state.get("project_params_last_full") or {})
    if not params_dict:
        params_dict = VideoParams(video_subject="").model_dump(mode="json")
    if _write_library_preset(str(uuid4()), name[:60], params_dict):
        st.session_state["preset_saved_name"] = name[:60]
        st.session_state["preset_name_input"] = ""
    else:
        st.session_state["preset_save_failed"] = True


def _request_apply_preset(preset_id):
    """一键应用：锁定时拒绝，脏时先弹三选确认，干净时直接回填。"""
    if _project_is_locked():
        st.session_state["preset_apply_refused"] = True
        return
    if _project_is_dirty():
        st.session_state["preset_apply_candidate"] = str(preset_id)
        return
    entry = _find_preset_entry(preset_id)
    if entry:
        st.session_state["settings_preset_payload"] = entry["params"]
        st.session_state["preset_applied_name"] = entry["name"]
    else:
        st.session_state["preset_apply_failed"] = True


def _apply_pending_preset_apply():
    """在渲染任何控件前执行预设应用决议：保存/放弃当前修改后回填。"""
    action = st.session_state.pop("preset_apply_action", None)
    candidate = st.session_state.get("preset_apply_candidate")
    if action is None:
        # 候选保留：本 run 还要渲染三选确认弹窗。
        return
    st.session_state.pop("preset_apply_candidate", None)
    if action == "cancel":
        return
    if action == "save":
        last_full = st.session_state.get("project_params_last_full")
        if last_full:
            task_id = _current_project_id() or str(uuid4())
            _write_project_params(task_id, last_full)
    entry = _find_preset_entry(candidate)
    if entry:
        st.session_state["settings_preset_payload"] = entry["params"]
        st.session_state["preset_applied_name"] = entry["name"]
    else:
        st.session_state["preset_apply_failed"] = True


def _dismiss_preset_apply_dialog():
    st.session_state.pop("preset_apply_candidate", None)
    st.session_state.pop("preset_apply_action", None)


@st.dialog(
    tr("Preset Apply Title"),
    width="small",
    on_dismiss=_dismiss_preset_apply_dialog,
)
def _render_preset_apply_dialog(candidate):
    st.warning(tr("Preset Apply Dirty Warning"))
    entry = _find_preset_entry(candidate)
    st.caption((entry or {}).get("name") or candidate)
    save_col, discard_col, cancel_col = st.columns(3)
    if save_col.button(
        tr("Save And Apply"),
        key="preset_apply_save",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["preset_apply_action"] = "save"
        st.rerun(scope="app")
    if discard_col.button(
        tr("Discard And Apply"),
        key="preset_apply_discard",
        use_container_width=True,
    ):
        st.session_state["preset_apply_action"] = "discard"
        st.rerun(scope="app")
    if cancel_col.button(
        tr("Cancel Switch"),
        key="preset_apply_cancel",
        use_container_width=True,
    ):
        st.session_state["preset_apply_action"] = "cancel"
        st.rerun(scope="app")


def _request_delete_preset(preset_id):
    st.session_state["preset_delete_candidate"] = str(preset_id)


def _dismiss_preset_delete_dialog():
    st.session_state.pop("preset_delete_candidate", None)


@st.dialog(
    tr("Preset Delete Title"),
    width="small",
    on_dismiss=_dismiss_preset_delete_dialog,
)
def _render_preset_delete_dialog(candidate):
    entry = _read_library_preset(candidate)
    name = (entry or {}).get("name") or candidate
    st.warning(tr("Preset Delete Warning").format(name=name))
    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button(
        tr("Confirm Delete"),
        key="preset_delete_confirm",
        type="primary",
        icon=":material/delete:",
        use_container_width=True,
    ):
        preset_file = _preset_library_path(candidate)
        try:
            if not preset_file:
                raise OSError("invalid preset id")
            os.remove(preset_file)
        except OSError as e:
            logger.warning(f"failed to delete library preset: {candidate}, {e}")
            st.session_state["preset_delete_failed"] = True
        else:
            st.session_state["preset_deleted_name"] = name
        st.session_state.pop("preset_delete_candidate", None)
        st.rerun(scope="app")
    if cancel_col.button(
        tr("Cancel Switch"),
        key="preset_delete_cancel",
        use_container_width=True,
    ):
        st.session_state.pop("preset_delete_candidate", None)
        st.rerun(scope="app")


def _render_presets_page():
    """预设库一级页：存当前参数、导入导出、一键应用与删除。"""
    st.caption(tr("Preset Library Help"))
    with st.container(
        key="preset_save_bar", horizontal=True, vertical_alignment="center"
    ):
        st.text_input(
            tr("Preset Name Input"),
            key="preset_name_input",
            placeholder=tr("Preset Name Placeholder"),
            label_visibility="collapsed",
            max_chars=60,
        )
        st.button(
            tr("Save Current As Preset"),
            key="preset_save_current_button",
            icon=":material/save:",
            type="primary",
            on_click=_save_current_as_preset,
            help=tr("Save Current As Preset"),
        )
    if st.session_state.pop("preset_name_missing", False):
        st.warning(tr("Preset Name Missing"))
    saved_name = st.session_state.pop("preset_saved_name", None)
    if saved_name:
        st.success(tr("Preset Saved").format(name=saved_name))
    if st.session_state.pop("preset_save_failed", False):
        st.error(tr("Preset Save Failed"))
    imported_name = st.session_state.pop("preset_imported_name", None)
    if imported_name:
        st.success(tr("Preset Import Saved").format(name=imported_name))
    if st.session_state.pop("preset_import_failed", False):
        st.error(tr("Settings Preset Import Failed"))

    uploaded_preset = st.file_uploader(
        tr("Import Preset To Library"),
        type=["json"],
        key="preset_library_uploader",
    )
    if uploaded_preset is not None:
        # 与设置导入同样的文件标识去重：避免后续 rerun 反复入库。
        if st.session_state.get("preset_library_file_id") != uploaded_preset.file_id:
            st.session_state["preset_library_file_id"] = uploaded_preset.file_id
            try:
                raw_bytes = uploaded_preset.getvalue()
                meta = _load_transfer_payload(
                    raw_bytes, SETTINGS_PRESET_SCHEMA, SETTINGS_PRESET_VERSION
                )
                params_dict = _parse_settings_preset(raw_bytes)
            except Exception as e:
                logger.warning(f"failed to import library preset: {e}")
                st.session_state["preset_import_failed"] = True
            else:
                name = str(
                    meta.get("name") or Path(uploaded_preset.name).stem or ""
                ).strip()[:60] or tr("Preset Library")
                if _write_library_preset(str(uuid4()), name, params_dict):
                    st.session_state["preset_imported_name"] = name
                else:
                    st.session_state["preset_import_failed"] = True
            st.rerun(scope="app")

    st.divider()
    library_entries = _scan_library_presets()
    for entry in _builtin_preset_entries() + library_entries:
        preset_id = entry["preset_id"]
        with st.container(key=f"preset_row_{preset_id}", border=True):
            st.markdown(f"**{_format_task_subject(entry['name'], max_length=60)}**")
            caption_bits = []
            subject = str(entry["params"].get("video_subject") or "")
            if subject:
                caption_bits.append(_format_task_subject(subject, max_length=30))
            if entry["saved_at"]:
                caption_bits.append(entry["saved_at"].replace("T", " "))
            if entry["builtin"]:
                caption_bits.append(tr("Builtin Preset Tag"))
            if caption_bits:
                st.caption(" · ".join(caption_bits))
            with st.container(
                key=f"preset_actions_{preset_id}", horizontal=True, gap="small"
            ):
                st.button(
                    tr("Apply Preset"),
                    key=f"preset_apply_{preset_id}",
                    icon=":material/bolt:",
                    type="primary",
                    on_click=_request_apply_preset,
                    args=(preset_id,),
                    width="stretch",
                    help=tr("Apply Preset"),
                )
                export_payload = _build_settings_preset_payload(
                    entry["params"], config.project_version
                )
                export_payload["name"] = entry["name"]
                st.download_button(
                    tr("Export Preset"),
                    data=json.dumps(
                        export_payload, ensure_ascii=False, indent=2
                    ).encode("utf-8"),
                    file_name=f"changofilm-preset-{preset_id}.json",
                    mime="application/json",
                    key=f"preset_export_{preset_id}",
                    icon=":material/download:",
                    use_container_width=True,
                    help=tr("Export Preset"),
                )
                if not entry["builtin"]:
                    st.button(
                        tr("Delete Preset"),
                        key=f"preset_delete_{preset_id}",
                        icon=":material/delete:",
                        on_click=_request_delete_preset,
                        args=(preset_id,),
                        width="stretch",
                        help=tr("Delete Preset"),
                    )
    if not library_entries:
        st.caption(tr("Preset Empty"))


def _render_key_backup_settings(panel):
    """渲染密钥备份的导出与恢复入口。"""
    with panel:
        backup_message = st.session_state.pop("key_backup_message", None)
        if backup_message:
            message_type, message = backup_message
            if message_type == "success":
                st.success(message)
            else:
                st.error(message)

        st.caption(tr("Key Backup Help"))
        st.warning(tr("Key Backup Warning"))

        backup_payload = _build_key_backup_payload(
            _RUNTIME_CONFIG_SECTIONS, config.project_version
        )
        backup_key_count = _count_backup_keys(backup_payload["keys"])
        st.caption(tr("Key Backup Summary").format(count=backup_key_count))
        st.download_button(
            tr("Export Keys"),
            data=json.dumps(backup_payload, ensure_ascii=False, indent=2).encode(
                "utf-8"
            ),
            file_name=KEY_BACKUP_FILE_NAME,
            mime="application/json",
            disabled=backup_key_count == 0,
            use_container_width=True,
            key="export_key_backup_button",
            icon=":material/download:",
        )

        uploaded_backup = st.file_uploader(
            tr("Import Keys"),
            type=["json"],
            key="key_backup_uploader",
        )
        if uploaded_backup is None:
            return
        if st.session_state.get("key_backup_file_id") == uploaded_backup.file_id:
            return

        st.session_state["key_backup_file_id"] = uploaded_backup.file_id
        try:
            restored_keys = _parse_key_backup(
                uploaded_backup.getvalue(), _RUNTIME_CONFIG_SECTIONS
            )
        except Exception as e:
            logger.warning(f"failed to import key backup: {e}")
            st.session_state["key_backup_message"] = (
                "error",
                tr("Key Restore Failed"),
            )
        else:
            restored_count = _apply_key_backup(restored_keys)
            _save_runtime_config()
            logger.info(f"restored keys from backup file: count={restored_count}")
            st.session_state["key_backup_message"] = (
                "success",
                tr("Keys Restored").format(count=restored_count),
            )
        # 主页面上的 TTS 密钥输入框也需要读取恢复后的配置，因此整页刷新。
        # 设置弹窗的打开状态保存在 session_state 中，刷新后会重新展开。
        st.rerun(scope="app")


# -----------------------------------------------------------------------------
# 设置与提示词弹窗
# -----------------------------------------------------------------------------


def _render_logging_settings():
    level, log_requests = get_logging_options()
    with st.expander(tr("Diagnostic Logging")):
        st.caption(tr("Diagnostic Logging Help"))
        with st.form("diagnostic_logging_form"):
            selected_level = st.selectbox(
                tr("Log Level"),
                LOG_LEVELS,
                index=LOG_LEVELS.index(level),
                key="diagnostic_log_level",
            )
            selected_trace = st.checkbox(
                tr("Trace API Requests"),
                value=log_requests,
                key="diagnostic_log_requests",
                help=tr("Trace API Requests Help"),
            )
            apply = st.form_submit_button(tr("Apply Logging Settings"))
        if apply:
            # 诊断不改变生成参数，直接生效；持久化仍走非阻塞配置队列。
            config.update_logging_options(selected_level, selected_trace)
            _save_runtime_config()
            st.success(tr("Logging Settings Applied"))


# 设置属于低频操作，使用中等尺寸 Dialog 避免长期占用主页面纵向空间，
# 同时控制阅读行宽，避免弹窗在宽屏设备上显得过于松散。
# Dialog 继承 fragment 行为，内部控件交互只重绘弹窗；函数末尾单独保存配置，
# 关闭时通过回调触发整页同步，确保生成流程读取最新 Provider 和界面设置。
def _remember_settings_tab(widget_key, targets):
    selected = st.session_state.get(widget_key)
    for target, label in targets.items():
        if selected == label:
            st.session_state["settings_active_tab"] = target
            break


def _remember_settings_selection(memory_key, widget_key):
    st.session_state[memory_key] = st.session_state[widget_key]


def _remember_tab_by_label(memory_key, widget_key, label_to_key):
    """键控 st.tabs 的 on_change 回调：把当前选中标签映射回稳定 key 记忆。"""
    mapped = label_to_key.get(st.session_state.get(widget_key))
    if mapped:
        st.session_state[memory_key] = mapped


def _mount_keyed_tabs(label_keys, widget_base, memory_key, target_session_key=None, stable_keys=None):
    """键控 st.tabs 的统一挂载预置：显式目标 > 记忆 > 首个 TAB。

    st.tabs 带键挂载时若会话无选中值，react-aria 会补发一次选中
    变更事件造成额外一轮 rerun；这里在实例化前预置选中标签，并配合
    on_change 回调把所选标签映射回稳定 key 记忆。传入 on_change 同时
    启用惰性渲染，未选中的 TAB 不执行（面板 .open 为 False）。
    stable_keys 与 label_keys 等长，是记忆与跳转使用的稳定业务键
    （素材能力 TAB 存能力分组 id）；缺省与 label_keys 相同。
    """
    stable_keys = list(stable_keys) if stable_keys is not None else list(label_keys)
    labels = [tr(label_key) for label_key in label_keys]
    label_to_key = dict(zip(labels, stable_keys))
    key_to_label = dict(zip(stable_keys, labels))
    tabs_key = localized_widget_key(widget_base)
    target = None
    if target_session_key:
        target = st.session_state.pop(target_session_key, None)
    remembered = st.session_state.get(memory_key)
    active = (
        target
        if target in stable_keys
        else remembered
        if remembered in stable_keys
        else stable_keys[0]
    )
    # 记忆键是选中状态的唯一事实来源，每次挂载都无条件预置选中标签：
    # 显式目标 > 记忆 > 首个 TAB。组件的既有选中值不能用来短路预置——
    # 同一键在页面与设置弹窗两种容器下元素 id 不同，重挂载时旧值无法
    # 迁移，若跳过预置会回落到首个 TAB 并经挂载同步把记忆覆盖掉。
    # 稳态下记忆与组件选中值一致，预置是无操作；只有记忆被外部改写
    # （弹窗/页面互切、Use 按钮定向、语言切换）时预置才会真正生效。
    st.session_state[tabs_key] = key_to_label[active]
    panels = st.tabs(
        labels,
        key=tabs_key,
        on_change=_remember_tab_by_label,
        args=(memory_key, tabs_key, label_to_key),
    )
    _remember_tab_by_label(memory_key, tabs_key, label_to_key)
    return panels


def _activate_material_primary_source(group, widget_key):
    """素材能力 TAB 的第一优先下拉：写唯一主源键并与创作页控件同步。"""
    selected = st.session_state[widget_key]
    _set_runtime_config("app", "video_source", selected)
    _sync_general_provider_widgets("video_source_select", selected)
    st.session_state["settings_material_group"] = group
    _save_runtime_config()


def _activate_stock_image_source(widget_key):
    """库存图片下拉选择：同步切换视频来源（与能力 TAB 激活同口径）。"""
    selected = st.session_state[widget_key]
    _set_runtime_config("app", "video_source", selected)
    _sync_general_provider_widgets("video_source_select", selected)
    st.session_state["settings_material_group"] = "stock_image"
    _save_runtime_config()


def _initialize_material_navigation(target, settings):
    """把设置弹窗/跳转目标映射为素材能力 TAB 预选（能力即素材分组）。"""
    capability = {
        "stock": "stock_video",
        "video": "ai_video",
        "image": "ai_image",
    }.get(target)
    if not capability:
        source = str(settings.get("video_source", "") or "")
        capability = service_catalog.material_capability_of_source(source)
    if capability not in service_catalog.MATERIAL_CAPABILITY_GROUPS:
        capability = "stock_video"
    st.session_state["settings_material_group"] = capability


def _material_provider_labels():
    return {
        "pexels": tr("Pexels"),
        "pixabay": tr("Pixabay"),
        "coverr": tr("Coverr"),
        "pexels_image": tr("Pexels Images"),
        "pixabay_image": tr("Pixabay Images"),
        "metaso_minimax": tr("Metaso MiniMax H3"),
        "ofox": tr("OFox AI Video"),
        "loomloom": tr("Shengsuan Cloud AI Video"),
        "volcengine_seedance": tr("Volcano Engine Seedance"),
        "infistar": tr("Infistar AI Video"),
        "jalapeno": tr("Jalapeno Cloud AI Video"),
        "wavespeed": tr("WaveSpeed AI Video"),
        "muapi": tr("MuAPI AI Video"),
        "openai_image": tr("OpenAI Compatible Text-to-Image"),
        "codex_image": tr("codex.image.label"),
        "local": tr("Local file"),
    }


def _general_provider_readiness(settings):
    from app.services import chatgpt_oauth, codex_oauth, kimi_code_oauth
    from webui.settings_providers import (
        configured_llm_providers,
        configured_material_providers,
    )

    oauth = {}
    for provider, read_status in (
        ("openai_codex", codex_oauth.account_status),
        ("openai_chatgpt", chatgpt_oauth.account_status),
        ("kimi_code", kimi_code_oauth.is_authorized),
    ):
        try:
            oauth[provider] = bool(read_status())
        except (ValueError, OSError):
            oauth[provider] = False
    return {
        "llm": configured_llm_providers(settings, oauth),
        **configured_material_providers(
            settings, VIDEO_SOURCE_GROUPS, oauth["openai_codex"]
        ),
    }


def _sync_general_provider_widgets(name, value):
    prefix = f"{name}_"
    for widget_key in list(st.session_state):
        if widget_key.startswith(prefix) and not widget_key.endswith("_component"):
            st.session_state[widget_key] = value
    st.session_state[localized_widget_key(name)] = value


def _activate_general_provider(section):
    settings = config.snapshot_config_with_pending(config.app)
    selected = st.session_state.get(
        localized_widget_key(f"settings_general_{section}_provider_select")
    )
    if selected not in _general_provider_readiness(settings).get(section, ()):
        st.session_state["settings_general_activation_error"] = True
        return
    st.session_state.pop("settings_general_activation_error", None)
    if section == "llm":
        _set_runtime_config("app", "llm_provider", selected)
        _sync_general_provider_widgets("llm_provider_select", selected)
    else:
        _set_runtime_config("app", "video_source", selected)
        _sync_general_provider_widgets("video_source_select", selected)
        st.session_state["settings_material_group"] = section
    _save_runtime_config()


def _render_general_settings(settings):
    configured = _general_provider_readiness(settings)
    material_labels = _material_provider_labels()
    llm_labels = {
        provider.provider_id: get_llm_provider_label(provider)
        for provider in LLM_PROVIDER_REGISTRY
    }
    st.subheader(tr("General Providers Title"))
    st.caption(tr("General Providers Help"))
    if st.session_state.pop("settings_general_activation_error", False):
        st.warning(tr("Provider Configuration Changed"))
    cards = (
        ("llm", "LLM Provider", "psychology", "llm"),
        ("ai_video", "AI Video", "movie", "video"),
        ("ai_image", "AI Image", "image", "image"),
        ("stock_video", "Stock Video", "video_library", "stock"),
    )
    for section, title, icon, target in cards:
        labels = llm_labels if section == "llm" else material_labels
        active = (
            settings.get("llm_provider", DEFAULT_LLM_PROVIDER_ID)
            if section == "llm"
            else settings.get("video_source", "pexels")
        )
        is_active_category = section == "llm" or active in VIDEO_SOURCE_GROUPS[section]
        options = configured[section]
        widget_key = localized_widget_key(f"settings_general_{section}_provider_select")
        memory_key = f"settings_general_{section}_provider"
        active_key = f"settings_general_{section}_active_snapshot"
        active_value = active if is_active_category else None
        if st.session_state.get(active_key) != active_value and active_value in options:
            st.session_state[memory_key] = active_value
            st.session_state[widget_key] = active_value
        st.session_state[active_key] = active_value
        remembered = st.session_state.get(memory_key)
        if st.session_state.get(widget_key) not in options:
            st.session_state[widget_key] = (
                remembered
                if remembered in options
                else active
                if active in options
                else options[0]
                if options
                else None
            )
        with st.container(border=True):
            st.subheader(f":material/{icon}: {tr(title)}")
            if is_active_category and active in options:
                st.caption(
                    tr("Active Provider").format(
                        provider=labels.get(active, str(active))
                    )
                )
            if not options:
                st.info(tr("No Configured Providers"))
                st.button(
                    tr("Configure Providers"),
                    key=f"settings_general_configure_{section}",
                    width="stretch",
                    on_click=_open_settings_dialog,
                    args=(target,),
                )
                continue
            selection = st.selectbox(
                tr("Configured Providers"),
                options=options,
                key=widget_key,
                format_func=labels.get,
                index=None,
                on_change=_remember_settings_selection,
                args=(memory_key, widget_key),
            )
            if selection is not None:
                st.session_state[memory_key] = selection
            use_column, configure_column = st.columns(2)
            use_column.button(
                tr("Use Provider"),
                key=f"settings_general_use_{section}",
                type="primary",
                width="stretch",
                disabled=selection is None,
                on_click=_activate_general_provider,
                args=(section,),
            )
            configure_column.button(
                tr("Configure Providers"),
                key=f"settings_general_configure_{section}",
                width="stretch",
                on_click=_open_settings_dialog,
                args=(target,),
            )


def _save_settings_change(section, config_key, widget_key, transform):
    value = st.session_state.get(widget_key)
    if value is not None:
        _set_runtime_config(section, config_key, transform(value))


def _save_settings_endpoint(provider, widget_key):
    endpoint_id = st.session_state.get(widget_key)
    endpoint = next(
        (
            item
            for item in provider.service_endpoints
            if item.endpoint_id == endpoint_id
        ),
        None,
    )
    if endpoint:
        _set_runtime_config(
            "app",
            provider.config_key("base_url"),
            normalize_provider_override(
                endpoint.base_url, provider.effective_default_base_url
            ),
        )


def _save_settings_api_keys(config_key, widget_key):
    _save_material_api_keys(config_key, st.session_state.get(widget_key, ""))


def _render_material_provider_settings(provider):
    app_settings = config.snapshot_config_with_pending(config.app)
    if provider in VIDEO_SOURCE_GROUPS["stock_video"]:
        labels = {
            "pexels": "Pexels API Key",
            "pixabay": "Pixabay API Key",
            "coverr": "Coverr API Key",
        }
        config_key = f"{provider}_api_keys"
        value = st.text_input(
            tr(labels[provider]),
            value=_get_material_api_keys(config_key),
            type="password",
            key=f"{config_key}_input",
            on_change=_save_settings_api_keys,
            args=(config_key, f"{config_key}_input"),
        )
        _save_material_api_keys(config_key, value)
    elif provider == "metaso_minimax":
        st.markdown(f"**{tr('Metaso MiniMax H3')}**")
        metaso_api_key = st.text_input(
            tr("Metaso MiniMax API Key"),
            value=str(app_settings.get("metaso_minimax_api_key", "") or "").strip(),
            type="password",
            help=tr("Metaso MiniMax API Key Help"),
            key="metaso_minimax_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "metaso_minimax_api_key",
                "metaso_minimax_api_key_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "metaso_minimax_api_key", metaso_api_key.strip())
        configured_metaso_base_url = str(
            app_settings.get(
                "metaso_minimax_base_url",
                metaso_minimax.DEFAULT_BASE_URL,
            )
            or metaso_minimax.DEFAULT_BASE_URL
        ).strip()
        metaso_base_url = st.text_input(
            tr("Metaso MiniMax Base URL"),
            value=(
                ""
                if configured_metaso_base_url == metaso_minimax.DEFAULT_BASE_URL
                else configured_metaso_base_url
            ),
            placeholder=metaso_minimax.DEFAULT_BASE_URL,
            key="metaso_minimax_base_url_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "metaso_minimax_base_url",
                "metaso_minimax_base_url_input",
                lambda value: value.strip() or metaso_minimax.DEFAULT_BASE_URL,
            ),
        )
        _set_runtime_config(
            "app",
            "metaso_minimax_base_url",
            metaso_base_url.strip() or metaso_minimax.DEFAULT_BASE_URL,
        )
        configured_metaso_resolution = (
            str(
                app_settings.get(
                    "metaso_minimax_resolution",
                    metaso_minimax.DEFAULT_RESOLUTION,
                )
            )
            .strip()
            .upper()
        )
        metaso_resolution_options = sorted(
            metaso_minimax.SUPPORTED_RESOLUTIONS,
            key=lambda value: value != metaso_minimax.DEFAULT_RESOLUTION,
        )
        resolution_is_valid = (
            configured_metaso_resolution in metaso_minimax.SUPPORTED_RESOLUTIONS
        )
        if not resolution_is_valid:
            # 分辨率直接影响计费。手工配置错误时保留原值并要求用户
            # 主动选择，不能在打开设置弹窗时静默改成价格更高的 2K。
            st.error(
                tr("Metaso MiniMax Invalid Resolution").format(
                    value=configured_metaso_resolution,
                    supported=", ".join(metaso_resolution_options),
                )
            )
        metaso_resolution = st.selectbox(
            tr("Metaso MiniMax Resolution"),
            options=metaso_resolution_options,
            index=(
                metaso_resolution_options.index(configured_metaso_resolution)
                if resolution_is_valid
                else None
            ),
            key="metaso_minimax_resolution_input",
            help=tr("Metaso MiniMax Resolution Help"),
            placeholder=tr("Select Metaso MiniMax Resolution"),
            on_change=_save_settings_change,
            args=(
                "app",
                "metaso_minimax_resolution",
                "metaso_minimax_resolution_input",
                lambda value: value,
            ),
        )
        if metaso_resolution is not None:
            _set_runtime_config("app", "metaso_minimax_resolution", metaso_resolution)
    elif provider == "ofox":
        st.markdown("**OfoxAI**")
        st.caption(f"[OfoxAI]({OFOX_REFERRAL_URL}) · {tr('OFox AI Video Help')}")
        ofox_api_key = st.text_input(
            tr("OFox API Key"),
            value=str(app_settings.get("ofox_api_key", "") or ""),
            type="password",
            key="ofox_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "ofox_api_key",
                "ofox_api_key_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "ofox_api_key", ofox_api_key.strip())
        ofox_model = st.text_input(
            tr("OFox Text-to-Video Model"),
            value=str(
                app_settings.get(
                    "ofox_text_to_video_model",
                    ofox.DEFAULT_MODEL_ID,
                )
                or ofox.DEFAULT_MODEL_ID
            ),
            key="ofox_text_to_video_model_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "ofox_text_to_video_model",
                "ofox_text_to_video_model_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "ofox_text_to_video_model", ofox_model.strip())
        configured_ofox_base_url = str(
            app_settings.get("ofox_base_url", ofox.DEFAULT_BASE_URL)
            or ofox.DEFAULT_BASE_URL
        ).strip()
        ofox_base_url = st.text_input(
            tr("OFox Base URL"),
            value=(
                ""
                if configured_ofox_base_url == ofox.DEFAULT_BASE_URL
                else configured_ofox_base_url
            ),
            placeholder=ofox.DEFAULT_BASE_URL,
            key="ofox_base_url_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "ofox_base_url",
                "ofox_base_url_input",
                lambda value: value.strip() or ofox.DEFAULT_BASE_URL,
            ),
        )
        _set_runtime_config(
            "app",
            "ofox_base_url",
            ofox_base_url.strip() or ofox.DEFAULT_BASE_URL,
        )
        ofox_vendor_options = [
            (tr("OFox Vendor BytePlus"), "byteplus"),
            (tr("OFox Vendor Volcengine"), "volcengine"),
            (tr("OFox Vendor Auto"), ""),
        ]
        configured_ofox_vendor = str(
            app_settings.get("ofox_provider", ofox.DEFAULT_PROVIDER_TYPE) or ""
        ).strip()
        if configured_ofox_vendor not in {value for _, value in ofox_vendor_options}:
            # 用户在 config.toml 手工钉定了其它厂商名时保留该选择，
            # 避免打开设置页就被下拉框覆盖回默认值。
            ofox_vendor_options.append((configured_ofox_vendor, configured_ofox_vendor))
        selected_ofox_vendor = stable_selectbox(
            tr("OFox Upstream Vendor"),
            options=[value for _, value in ofox_vendor_options],
            default_value=configured_ofox_vendor,
            key="ofox_provider_select",
            format_func=lambda value: dict(
                (v, label) for label, v in ofox_vendor_options
            )[value],
            help=tr("OFox Upstream Vendor Help"),
            on_change=_save_settings_change,
            args=(
                "app",
                "ofox_provider",
                localized_widget_key("ofox_provider_select"),
                lambda value: value,
            ),
        )
        _set_runtime_config("app", "ofox_provider", selected_ofox_vendor)
    elif provider == "loomloom":
        st.markdown(f"**{tr('Shengsuan Cloud AI Video')}**")
        app_config_snapshot = config.snapshot_config_with_pending(config.app)
        if (
            str(app_config_snapshot.get("llm_provider", "") or "").lower()
            == "shengsuanyun"
        ):
            # 大模型 Provider 已选胜算云时，视频生成直接复用
            # 同一密钥，不再展示一个容易引起歧义的独立输入框。
            st.caption(tr("Shengsuan Cloud API Key Reused"))
        else:
            configured_loomloom_token = str(
                app_config_snapshot.get("loomloom_api_token", "") or ""
            ).strip()
            loomloom_api_token = st.text_input(
                tr("Shengsuan Cloud API Key"),
                value=configured_loomloom_token,
                type="password",
                key="loomloom_api_token_input",
                help=tr("Shengsuan Cloud API Key Help"),
                placeholder=tr("Shengsuan Cloud API Key Placeholder"),
                on_change=_save_settings_change,
                args=(
                    "app",
                    "loomloom_api_token",
                    "loomloom_api_token_input",
                    lambda value: value.strip(),
                ),
            ).strip()
            _set_runtime_config("app", "loomloom_api_token", loomloom_api_token)
    elif provider == "volcengine_seedance":
        seedance_api_key_value = str(
            app_settings.get("volcengine_seedance_api_key", "") or ""
        ).strip()
        shared_ark_api_key = str(
            app_settings.get("volcengine_api_key", "") or ""
        ).strip()
        environment_ark_api_key = os.getenv("VOLCENGINE_ARK_API_KEY", "").strip()
        seedance_reuses_llm_key = bool(
            not seedance_api_key_value
            and not environment_ark_api_key
            and shared_ark_api_key
        )
        seedance_title = f"**{tr('Volcano Engine Seedance')}**"
        if seedance_reuses_llm_key:
            # 只有复用大模型密钥无法从当前输入框直接看出，保留该提示
            # 可以避免用户误以为必须重复填写；普通配置状态不再赘述。
            seedance_title += f" :blue[{tr('Reusing LLM API Key')}]"
        st.markdown(seedance_title)
        seedance_api_key = st.text_input(
            tr("Volcano Engine Ark API Key"),
            value=seedance_api_key_value,
            type="password",
            help=tr("Volcano Engine Ark API Key Help"),
            key="volcengine_seedance_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "volcengine_seedance_api_key",
                "volcengine_seedance_api_key_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config(
            "app", "volcengine_seedance_api_key", seedance_api_key.strip()
        )
        configured_seedance_model = str(
            app_settings.get(
                "volcengine_seedance_model",
                volcengine_seedance.DEFAULT_MODEL_ID,
            )
            or volcengine_seedance.DEFAULT_MODEL_ID
        ).strip()
        seedance_model = st.text_input(
            tr("Volcano Engine Seedance Model"),
            # 内置默认值通过 placeholder 展示，用户自定义的
            # 模型或接入点 ID 仍作为真实值展示和保存。
            value=(
                ""
                if configured_seedance_model == volcengine_seedance.DEFAULT_MODEL_ID
                else configured_seedance_model
            ),
            placeholder=volcengine_seedance.DEFAULT_MODEL_ID,
            key="volcengine_seedance_model_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "volcengine_seedance_model",
                "volcengine_seedance_model_input",
                lambda value: value.strip() or volcengine_seedance.DEFAULT_MODEL_ID,
            ),
        )
        _set_runtime_config(
            "app",
            "volcengine_seedance_model",
            seedance_model.strip() or volcengine_seedance.DEFAULT_MODEL_ID,
        )
        configured_seedance_base_url = str(
            app_settings.get(
                "volcengine_seedance_base_url",
                volcengine_seedance.DEFAULT_BASE_URL,
            )
            or volcengine_seedance.DEFAULT_BASE_URL
        ).strip()
        seedance_base_url = st.text_input(
            tr("Volcano Engine Ark Base URL"),
            value=(
                ""
                if configured_seedance_base_url == volcengine_seedance.DEFAULT_BASE_URL
                else configured_seedance_base_url
            ),
            placeholder=volcengine_seedance.DEFAULT_BASE_URL,
            key="volcengine_seedance_base_url_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "volcengine_seedance_base_url",
                "volcengine_seedance_base_url_input",
                lambda value: value.strip() or volcengine_seedance.DEFAULT_BASE_URL,
            ),
        )
        _set_runtime_config(
            "app",
            "volcengine_seedance_base_url",
            seedance_base_url.strip() or volcengine_seedance.DEFAULT_BASE_URL,
        )
    elif provider == "infistar":
        st.markdown(f"**{tr('Infistar AI Video')}**")
        st.caption(tr("Infistar Video Key Help"))
        infistar_video_key = st.text_input(
            tr("Infistar Video API Key"),
            value=str(app_settings.get("infistar_video_api_key", "") or ""),
            type="password",
            key="infistar_video_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "infistar_video_api_key",
                "infistar_video_api_key_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "infistar_video_api_key", infistar_video_key.strip())
        infistar_video_base_url = st.text_input(
            tr("Infistar Video Base URL"),
            value=str(app_settings.get("infistar_video_base_url", "") or ""),
            placeholder=infistar_video.DEFAULT_BASE_URL,
            key="infistar_video_base_url_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "infistar_video_base_url",
                "infistar_video_base_url_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config(
            "app", "infistar_video_base_url", infistar_video_base_url.strip()
        )
    elif provider == "jalapeno":
        _render_jalapeno_provider_settings()
    elif provider == "wavespeed":
        wavespeed_api_key = _get_material_api_keys("wavespeed_api_keys")
        st.markdown("**WaveSpeed**")
        wavespeed_api_key = st.text_input(
            tr("WaveSpeed API Key"),
            value=wavespeed_api_key,
            type="password",
            key="wavespeed_api_keys_input",
            on_change=_save_settings_api_keys,
            args=("wavespeed_api_keys", "wavespeed_api_keys_input"),
        )
        _save_material_api_keys("wavespeed_api_keys", wavespeed_api_key)
    elif provider == "muapi":
        st.markdown(f"**{tr('MuAPI AI Video')}**")
        st.caption(tr("MuAPI AI Video Help"))
        muapi_api_key = st.text_input(
            tr("MuAPI API Key"),
            value=str(app_settings.get("muapi_api_key", "") or ""),
            type="password",
            help=tr("MuAPI API Key Help"),
            key="muapi_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "muapi_api_key",
                "muapi_api_key_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "muapi_api_key", muapi_api_key.strip())
        configured_muapi_base_url = str(
            app_settings.get("muapi_base_url", muapi.DEFAULT_BASE_URL)
            or muapi.DEFAULT_BASE_URL
        ).strip()
        muapi_base_url = st.text_input(
            tr("MuAPI Base URL"),
            value=(
                ""
                if configured_muapi_base_url == muapi.DEFAULT_BASE_URL
                else configured_muapi_base_url
            ),
            placeholder=muapi.DEFAULT_BASE_URL,
            key="muapi_base_url_input",
            help=tr("MuAPI Base URL Help"),
            on_change=_save_settings_change,
            args=(
                "app",
                "muapi_base_url",
                "muapi_base_url_input",
                lambda value: value.strip() or muapi.DEFAULT_BASE_URL,
            ),
        )
        _set_runtime_config(
            "app",
            "muapi_base_url",
            muapi_base_url.strip() or muapi.DEFAULT_BASE_URL,
        )
        configured_muapi_endpoint = str(
            app_settings.get("muapi_video_endpoint", muapi.DEFAULT_ENDPOINT)
            or muapi.DEFAULT_ENDPOINT
        ).strip()
        muapi_endpoint = st.text_input(
            tr("MuAPI Video Endpoint"),
            value=(
                ""
                if configured_muapi_endpoint == muapi.DEFAULT_ENDPOINT
                else configured_muapi_endpoint
            ),
            placeholder=muapi.DEFAULT_ENDPOINT,
            key="muapi_video_endpoint_input",
            help=tr("MuAPI Video Endpoint Help"),
            on_change=_save_settings_change,
            args=(
                "app",
                "muapi_video_endpoint",
                "muapi_video_endpoint_input",
                lambda value: value.strip() or muapi.DEFAULT_ENDPOINT,
            ),
        )
        _set_runtime_config(
            "app",
            "muapi_video_endpoint",
            muapi_endpoint.strip() or muapi.DEFAULT_ENDPOINT,
        )
        configured_muapi_resolution = str(
            app_settings.get("muapi_resolution", muapi.DEFAULT_RESOLUTION)
            or muapi.DEFAULT_RESOLUTION
        ).strip()
        muapi_resolution = st.text_input(
            tr("MuAPI Resolution"),
            value=(
                ""
                if configured_muapi_resolution == muapi.DEFAULT_RESOLUTION
                else configured_muapi_resolution
            ),
            placeholder=muapi.DEFAULT_RESOLUTION,
            key="muapi_resolution_input",
            help=tr("MuAPI Resolution Help"),
            on_change=_save_settings_change,
            args=(
                "app",
                "muapi_resolution",
                "muapi_resolution_input",
                lambda value: value.strip() or muapi.DEFAULT_RESOLUTION,
            ),
        )
        _set_runtime_config(
            "app",
            "muapi_resolution",
            muapi_resolution.strip() or muapi.DEFAULT_RESOLUTION,
        )
    elif provider == "codex_image":
        st.markdown(f"**{tr('codex.image.label')}**")
        st.caption(tr("codex.image.help"))
        from webui.codex_models import render_codex_model_selector

        codex_image_model = render_codex_model_selector(
            str(app_settings.get("codex_image_model_name", "") or ""),
            tr,
            prefix="codex_image",
            on_change=lambda model: _set_runtime_config(
                "app", "codex_image_model_name", model
            ),
        )
        _set_runtime_config("app", "codex_image_model_name", codex_image_model)
        codex_image_timeout = st.text_input(
            tr("codex.image.timeout"),
            value=str(app_settings.get("codex_image_timeout") or "300"),
            placeholder="300",
            key="codex_image_timeout_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "codex_image_timeout",
                "codex_image_timeout_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "codex_image_timeout", codex_image_timeout.strip())
        from webui.codex_login import render_codex_login

        with st.container():
            render_codex_login(tr)
    elif provider == "openai_image":
        st.markdown(f"**{tr('OpenAI Compatible Text-to-Image')}**")

        openai_image_base_url = st.text_input(
            tr("OpenAI Image Base URL"),
            value=str(app_settings.get("openai_image_base_url", "") or ""),
            placeholder="https://api.openai.com/v1",
            key="openai_image_base_url_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "openai_image_base_url",
                "openai_image_base_url_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config(
            "app", "openai_image_base_url", openai_image_base_url.strip()
        )

        openai_image_api_key = _get_material_api_keys("openai_image_api_keys")
        openai_image_api_key = st.text_input(
            tr("OpenAI Image API Key"),
            value=openai_image_api_key,
            type="password",
            help=tr("OpenAI Image API Key Help"),
            key="openai_image_api_keys_input",
            on_change=_save_settings_api_keys,
            args=("openai_image_api_keys", "openai_image_api_keys_input"),
        )
        _save_material_api_keys("openai_image_api_keys", openai_image_api_key)

        openai_image_model = st.text_input(
            tr("OpenAI Image Model"),
            value=str(app_settings.get("openai_image_model", "") or ""),
            placeholder="gpt-image-2",
            key="openai_image_model_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "openai_image_model",
                "openai_image_model_input",
                lambda value: value.strip(),
            ),
        )
        _set_runtime_config("app", "openai_image_model", openai_image_model.strip())
        # 只展示参考值，不将 OpenAI 官方端点写成默认配置。
        # 兼容服务的 Base URL 和模型 ID 没有统一值；留空不会让
        # 用户在未知情时误连官方付费接口，也不会覆盖旧配置。
        # 高级参数（尺寸/提示词模板）属于创作面板的项目级参数，不在服务商配置。
        st.caption(tr("OpenAI Image Configuration Example"))


def _render_social_publish_settings(app_settings):
    """国内平台发布区（免费 social-auto-upload 通道，主区）。"""
    st.write(tr("Domestic Auto-Publish Intro").format(repo_url=SAU_REPO_URL))
    with st.expander(tr("Social Auto Upload Setup Guide")):
        st.markdown(tr("Social Auto Upload Setup Steps"))

    is_enabled = app_settings.get("social_publish_enabled", False)
    is_auto = app_settings.get("social_publish_auto_upload", False)

    # 与 Upload-Post 区相同：enabled 与 auto_upload 两键各自独立，
    # 合并成一个复选框会在两键不一致时擅自改写配置。
    social_publish_enabled = st.checkbox(
        tr("Enable Domestic Publishing"),
        value=is_enabled,
        key="social_publish_enabled_checkbox",
        on_change=_save_settings_change,
        args=(
            "app",
            "social_publish_enabled",
            "social_publish_enabled_checkbox",
            lambda value: value,
        ),
    )
    if social_publish_enabled != is_enabled:
        _set_runtime_config("app", "social_publish_enabled", social_publish_enabled)

    social_publish_auto_upload = st.checkbox(
        tr("Enable Domestic Auto-Publish"),
        value=is_auto,
        key="social_publish_auto_upload_checkbox",
        on_change=_save_settings_change,
        args=(
            "app",
            "social_publish_auto_upload",
            "social_publish_auto_upload_checkbox",
            lambda value: value,
        ),
    )
    if social_publish_auto_upload != is_auto:
        _set_runtime_config(
            "app", "social_publish_auto_upload", social_publish_auto_upload
        )

    social_publish_account = st.text_input(
        tr("Publish Account Name"),
        value=app_settings.get("social_publish_account", "default"),
        help=tr("Publish Account Name Help"),
        key="social_publish_account_input",
        on_change=_save_settings_change,
        args=(
            "app",
            "social_publish_account",
            "social_publish_account_input",
            lambda value: value.strip() or "default",
        ),
    )
    if social_publish_account != app_settings.get("social_publish_account", "default"):
        _set_runtime_config(
            "app", "social_publish_account", social_publish_account.strip() or "default"
        )

    platform_options = social_auto_upload.SAU_PLATFORM_ORDER
    saved_platforms = app_settings.get(
        "social_publish_platforms", social_auto_upload.DEFAULT_SAU_PLATFORMS
    )
    # 过滤非法 id，避免损坏的配置让 multiselect 直接报错；空选择保持为空。
    default_platforms = [p for p in saved_platforms if p in platform_options]
    social_publish_platforms = st.multiselect(
        tr("Domestic Platforms"),
        options=platform_options,
        default=default_platforms,
        format_func=lambda p: SOCIAL_PUBLISH_PLATFORM_LABELS.get(p, p),
        key="social_publish_platforms_multiselect",
        on_change=_save_settings_change,
        args=(
            "app",
            "social_publish_platforms",
            "social_publish_platforms_multiselect",
            lambda value: value,
        ),
    )
    if social_publish_platforms != saved_platforms:
        _set_runtime_config(
            "app", "social_publish_platforms", social_publish_platforms
        )

    if "bilibili" in social_publish_platforms:
        saved_tid = app_settings.get("social_publish_bilibili_tid", 21)
        try:
            saved_tid = int(saved_tid)
        except (TypeError, ValueError):
            saved_tid = 21
        social_publish_bilibili_tid = st.number_input(
            tr("Bilibili Partition ID"),
            min_value=1,
            max_value=9999,
            value=saved_tid,
            step=1,
            help=tr("Bilibili Partition Help"),
            key="social_publish_bilibili_tid_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "social_publish_bilibili_tid",
                "social_publish_bilibili_tid_input",
                lambda value: int(value),
            ),
        )
        if int(social_publish_bilibili_tid) != saved_tid:
            _set_runtime_config(
                "app",
                "social_publish_bilibili_tid",
                int(social_publish_bilibili_tid),
            )

    with st.expander(tr("Advanced Publish Settings")):
        sau_cli_path = st.text_input(
            tr("SAU CLI Path"),
            value=app_settings.get("sau_cli_path", "sau"),
            help=tr("SAU CLI Path Help"),
            key="sau_cli_path_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "sau_cli_path",
                "sau_cli_path_input",
                lambda value: value.strip() or "sau",
            ),
        )
        if sau_cli_path != app_settings.get("sau_cli_path", "sau"):
            _set_runtime_config("app", "sau_cli_path", sau_cli_path.strip() or "sau")

        # 浏览器目录由服务层注入 sau 子进程，无需 setx 或重启 WebUI。
        social_publish_browsers_path = st.text_input(
            tr("Publish Browsers Path"),
            value=app_settings.get("social_publish_browsers_path", ""),
            help=tr("Publish Browsers Path Help"),
            key="social_publish_browsers_path_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "social_publish_browsers_path",
                "social_publish_browsers_path_input",
                lambda value: value.strip(),
            ),
        )
        if social_publish_browsers_path != app_settings.get(
            "social_publish_browsers_path", ""
        ):
            _set_runtime_config(
                "app",
                "social_publish_browsers_path",
                social_publish_browsers_path.strip(),
            )

        # 有头模式让用户看到发布自动化全过程，验证码/短信拦截可人工处理；
        # 无桌面的服务器部署才需要关闭。
        social_publish_headed = st.checkbox(
            tr("Publish Headed"),
            value=app_settings.get("social_publish_headed", True),
            help=tr("Publish Headed Help"),
            key="social_publish_headed_checkbox",
            on_change=_save_settings_change,
            args=(
                "app",
                "social_publish_headed",
                "social_publish_headed_checkbox",
                lambda value: value,
            ),
        )
        if social_publish_headed != app_settings.get("social_publish_headed", True):
            _set_runtime_config(
                "app", "social_publish_headed", social_publish_headed
            )

    # 登录态体检：扫码登录必须在真实终端完成，UI 只负责体检和给出修复命令。
    account_name = (social_publish_account or "default").strip() or "default"
    if st.button(
        tr("Check Login Sessions"),
        key="social_publish_check_sessions_button",
        disabled=not social_publish_enabled or not social_publish_platforms,
    ):
        with st.spinner(tr("Checking Login Sessions")):
            report = social_auto_upload.social_auto_upload_service.check_sessions(
                social_publish_platforms, account_name
            )
        if report is None:
            st.toast(tr("Session Check Busy"), icon="⏳")
        else:
            st.session_state["social_publish_session_report"] = report

    report = st.session_state.get("social_publish_session_report")
    if report:
        for platform in social_publish_platforms:
            entry = report.get(platform)
            if not isinstance(entry, dict):
                continue
            label = SOCIAL_PUBLISH_PLATFORM_LABELS.get(platform, platform)
            if entry.get("ok"):
                st.caption(f"✅ {label}")
            else:
                st.caption(f"❌ {label} — {entry.get('detail') or ''}")
                st.code(
                    f"sau {platform} login --account {account_name}",
                    language="bash",
                )


def _render_publish_settings_body(app_settings):
    """国内发布 + Upload-Post 设置体；设置弹窗与一级发布渠道页共用。

    注意：这里必须是普通函数——一级页内联调用；若带 @st.dialog
    装饰器，页面切换会弹出模态框而不是渲染页面内容。
    """
    _render_social_publish_settings(app_settings)
    with st.expander(tr("Overseas Platforms Optional UploadPost")):
        st.caption(tr("Upload-Post Free Tier Note"))
        st.write(
            tr(
                "Automatically publish generated videos to social media using upload-post.com"
            )
        )
        st.info(
            tr("Upload-Post Setup Guide").format(
                api_keys_url=UPLOAD_POST_API_KEYS_URL,
                manage_users_url=UPLOAD_POST_MANAGE_USERS_URL,
            )
        )

        is_enabled = app_settings.get("upload_post_enabled", False)
        is_auto = app_settings.get("upload_post_auto_upload", False)

        # 两个键各自独立:enabled 允许外部流程调用 Upload-Post,
        # auto_upload 才决定渲染完成后是否自动发布。合并成一个复选框会在
        # 两键不一致的配置下,仅打开设置对话框就把 enabled 改写为 False。
        upload_post_enabled = st.checkbox(
            tr("Enable Upload-Post Integration"),
            value=is_enabled,
            key="upload_post_enabled_checkbox",
            on_change=_save_settings_change,
            args=(
                "app",
                "upload_post_enabled",
                "upload_post_enabled_checkbox",
                lambda value: value,
            ),
        )
        if upload_post_enabled != is_enabled:
            _set_runtime_config(
                "app", "upload_post_enabled", upload_post_enabled
            )

        upload_post_auto_upload = st.checkbox(
            tr("Enable Auto-Publish"),
            value=is_auto,
            key="upload_post_auto_upload_checkbox",
            on_change=_save_settings_change,
            args=(
                "app",
                "upload_post_auto_upload",
                "upload_post_auto_upload_checkbox",
                lambda value: value,
            ),
        )
        if upload_post_auto_upload != is_auto:
            _set_runtime_config(
                "app", "upload_post_auto_upload", upload_post_auto_upload
            )

        upload_post_api_key = st.text_input(
            tr("Upload-Post API Key"),
            value=app_settings.get("upload_post_api_key", ""),
            type="password",
            help=tr("Upload-Post API Key Help").format(
                api_keys_url=UPLOAD_POST_API_KEYS_URL
            ),
            key="upload_post_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "upload_post_api_key",
                "upload_post_api_key_input",
                lambda value: value,
            ),
        )
        if upload_post_api_key != app_settings.get("upload_post_api_key", ""):
            _set_runtime_config(
                "app", "upload_post_api_key", upload_post_api_key
            )

        upload_post_username = st.text_input(
            tr("Upload-Post Profile Username"),
            value=app_settings.get("upload_post_username", ""),
            help=tr("Upload-Post Profile Username Help").format(
                manage_users_url=UPLOAD_POST_MANAGE_USERS_URL
            ),
            key="upload_post_username_input",
            on_change=_save_settings_change,
            args=(
                "app",
                "upload_post_username",
                "upload_post_username_input",
                lambda value: value,
            ),
        )
        if upload_post_username != app_settings.get("upload_post_username", ""):
            _set_runtime_config(
                "app", "upload_post_username", upload_post_username
            )

        upload_post_platforms = st.multiselect(
            tr("Platforms"),
            options=["tiktok", "instagram", "youtube"],
            default=app_settings.get(
                "upload_post_platforms", ["tiktok", "instagram"]
            ),
            help="Select platforms to publish to",
            key="upload_post_platforms_multiselect",
            on_change=_save_settings_change,
            args=(
                "app",
                "upload_post_platforms",
                "upload_post_platforms_multiselect",
                lambda value: value,
            ),
        )
        if upload_post_platforms != app_settings.get(
            "upload_post_platforms", ["tiktok", "instagram"]
        ):
            _set_runtime_config(
                "app", "upload_post_platforms", upload_post_platforms
            )

        if "youtube" in upload_post_platforms:
            yt_status_options = ["public", "private", "unlisted"]
            yt_saved = app_settings.get(
                "upload_post_youtube_privacy_status", "public"
            )
            if yt_saved not in yt_status_options:
                yt_saved = "public"
            upload_post_youtube_privacy_status = st.selectbox(
                tr("YouTube Privacy Status"),
                options=yt_status_options,
                index=yt_status_options.index(yt_saved),
                key="upload_post_youtube_privacy_status_selectbox",
                on_change=_save_settings_change,
                args=(
                    "app",
                    "upload_post_youtube_privacy_status",
                    "upload_post_youtube_privacy_status_selectbox",
                    lambda value: value,
                ),
            )
            if upload_post_youtube_privacy_status != app_settings.get(
                "upload_post_youtube_privacy_status", "public"
            ):
                _set_runtime_config(
                    "app",
                    "upload_post_youtube_privacy_status",
                    upload_post_youtube_privacy_status,
                )

            # 受众声明只影响 YouTube 发布，不改变生成内容或其它平台的请求。
            # 使用真正的布尔选项，避免把展示文字或字符串当成 API 参数。
            saved_audience = app_settings.get(
                "upload_post_youtube_made_for_kids", False
            )
            audience_labels = {
                False: tr("Not Made for Kids"),
                True: tr("Made for Kids"),
            }
            made_for_kids = st.selectbox(
                tr("YouTube Audience"),
                options=[False, True],
                # 非法配置保持未选择，不在打开设置时擅自改成非儿童声明。
                index=int(saved_audience)
                if isinstance(saved_audience, bool)
                else None,
                format_func=audience_labels.get,
                help=tr("YouTube Audience Help"),
                key="upload_post_youtube_made_for_kids_selectbox",
                on_change=_save_settings_change,
                args=(
                    "app",
                    "upload_post_youtube_made_for_kids",
                    "upload_post_youtube_made_for_kids_selectbox",
                    lambda value: value,
                ),
            )
            if isinstance(made_for_kids, bool):
                _set_runtime_config(
                    "app", "upload_post_youtube_made_for_kids", made_for_kids
                )


def _render_interface_settings_body(ui_settings):
    """界面设置体（日志开关 + 诊断日志）；弹窗与设置页共用。"""
    hide_log = st.checkbox(
        tr("Hide Log"),
        value=ui_settings.get("hide_log", False),
        key="hide_log_checkbox",
        on_change=_save_settings_change,
        args=("ui", "hide_log", "hide_log_checkbox", lambda value: value),
    )
    _set_runtime_config("ui", "hide_log", hide_log)
    _render_logging_settings()


PROVIDER_TAB_LABEL_KEYS = (
    "Provider Overview Tab",
    "Provider Text Tab",
    "Provider Video Tab",
    "Provider Image Tab",
    "Provider Voiceover Tab",
    "Provider Music Tab",
    "Provider Stock Search Tab",
)

# 素材能力分组 → 服务商配置页承载其 Key 表单的 TAB（素材页跳转用）。
MATERIAL_GROUP_PROVIDER_TAB = {
    "ai_video": "Provider Video Tab",
    "ai_image": "Provider Image Tab",
    "stock_video": "Provider Stock Search Tab",
    "stock_image": "Provider Stock Search Tab",
}

# 配音服务固定展示顺序与默认文案（配音链与 Key 表单共用）。
TTS_SERVER_OPTIONS = (
    ("azure-tts-v1", "Azure TTS V1 (Edge TTS)"),
    ("azure-tts-v2", "Azure TTS V2"),
    ("siliconflow", "SiliconFlow TTS"),
    ("gemini-tts", "Google Gemini TTS"),
    ("mimo-tts", "Xiaomi MiMo TTS"),
    ("minimax-tts", "MiniMax TTS"),
    ("elevenlabs", "ElevenLabs TTS"),
    ("chatterbox", "Chatterbox TTS"),
    ("kokoro", "Kokoro TTS"),
    ("fish_audio", "Fish Audio TTS"),
    ("voxcpm", "VoxCPM TTS"),
)


def _tts_server_label(server_id):
    return dict(TTS_SERVER_OPTIONS).get(server_id, server_id)


def _music_service_ready(service_id):
    """配乐服务的本地就绪检查（口径与服务层一致，不探测连通性）。"""
    if service_id == "sonilo":
        return bool(
            str(config.app.get("sonilo_api_key", "") or "").strip()
            or os.getenv("SONILO_API_KEY", "").strip()
        )
    if service_id == "elevenlabs":
        return bool(
            str(config.elevenlabs.get("api_key", "") or "").strip()
            or os.getenv("ELEVENLABS_API_KEY", "").strip()
        )
    return False


def _service_platform_readiness(app_settings):
    """汇总本地就绪的 LLM 与素材服务集合，供总览矩阵与状态徽标使用。"""
    readiness = _general_provider_readiness(app_settings)
    configured_llm = set(readiness.get("llm", ()))
    configured_material = {
        source
        for group, sources in readiness.items()
        if group != "llm"
        for source in sources
    }
    return configured_llm, configured_material


def _platform_service_ready(platform, configured_llm, configured_material):
    """平台任一已接线服务就绪即视为已配置。"""
    if any(service_id in configured_llm for service_id in platform.llm_ids):
        return True
    if any(service_id in configured_material for service_id in platform.material_ids):
        return True
    if any(
        source_failover.tts_server_available(service_id)
        for service_id in platform.tts_ids
    ):
        return True
    return any(
        _music_service_ready(service_id) for service_id in platform.music_ids
    )


def _platform_label(platform):
    return (
        tr_optional(platform.label_key, fallback_language="en")
        or platform.default_label
    )


def _platform_status_badge(ready):
    if ready:
        return f":green[:material/check_circle: {tr('Provider Configured Badge')}]"
    return (
        f":gray[:material/radio_button_unchecked: "
        f"{tr('Provider Not Configured Badge')}]"
    )


def _render_service_provider_overview(app_settings):
    """总览矩阵：按国内→本地→国际→聚合排序展示平台、能力与就绪状态。"""
    configured_llm, configured_material = _service_platform_readiness(app_settings)
    st.caption(tr("Provider Overview Help"))
    for group in service_catalog.PLATFORM_GROUP_ORDER:
        platforms = [
            platform
            for platform in service_catalog.SERVICE_PLATFORMS
            if platform.group == group
        ]
        if not platforms:
            continue
        st.subheader(tr(service_catalog.GROUP_LABEL_KEYS[group]))
        for platform in platforms:
            ready = _platform_service_ready(
                platform, configured_llm, configured_material
            )
            label = _platform_label(platform)
            capability_text = " · ".join(
                tr(service_catalog.CAPABILITY_LABEL_KEYS[capability])
                for capability in platform.capabilities
            )
            with st.container(border=True):
                info_column, status_column = st.columns([0.72, 0.28])
                with info_column:
                    st.markdown(f"**{label}**")
                    if capability_text:
                        st.caption(capability_text)
                with status_column:
                    st.markdown(_platform_status_badge(ready))


def _material_source_ready(app_settings, provider):
    readiness = _general_provider_readiness(app_settings)
    return any(
        provider in sources
        for group, sources in readiness.items()
        if group != "llm"
    )


def _render_provider_settings_expander(app_settings, provider, expanded=False):
    """服务商配置页的单个素材 Provider 行：状态徽标 + 既有 Key/参数表单。"""
    label = _material_provider_labels().get(provider, provider)
    with st.expander(
        f"{label} {_platform_status_badge(_material_source_ready(app_settings, provider))}",
        expanded=expanded,
    ):
        _render_material_provider_settings(provider)


def _render_ai_video_provider_settings(app_settings):
    """视频生成 TAB：AI 视频与订阅图生视频服务的凭证表单。"""
    st.caption(tr("Provider Video Tab Help"))
    for provider in VIDEO_SOURCE_GROUPS["ai_video"]:
        _render_provider_settings_expander(app_settings, provider)


def _render_ai_image_provider_settings(app_settings):
    """图片生成 TAB：AI 图像服务的凭证表单。"""
    st.caption(tr("Provider Image Tab Help"))
    for provider in VIDEO_SOURCE_GROUPS["ai_image"]:
        _render_provider_settings_expander(app_settings, provider)


def _render_voiceover_provider_settings(app_settings):
    """配音 TAB：TTS 三槽链（第一优先 + 备用 1/2）+ 各服务凭证表单。"""
    tts_server_ids = [server_id for server_id, _ in TTS_SERVER_OPTIONS]
    saved_server = str(config.ui.get("tts_server", "azure-tts-v1") or "azure-tts-v1")
    if saved_server not in tts_server_ids:
        saved_server = "azure-tts-v1"
    primary_widget_key = localized_widget_key("tts_server_primary_select")
    st.session_state[primary_widget_key] = saved_server
    primary_server = st.selectbox(
        tr("Voiceover Service"),
        options=tts_server_ids,
        key=primary_widget_key,
        format_func=_tts_server_label,
        on_change=_save_settings_change,
        args=(
            "ui",
            "tts_server",
            primary_widget_key,
            lambda value: value,
        ),
    )
    _set_runtime_config("ui", "tts_server", primary_server)
    # 与素材链备用槽一致：format_func 纯闭包，标签渲染时预算。
    disabled_label = tr("Backup Slot Disabled")
    for slot in (1, 2):
        backup_config_key = f"tts_server_backup{slot}"
        backup_widget_key = localized_widget_key(f"tts_server_backup{slot}_select")
        saved_backup = str(config.ui.get(backup_config_key, "") or "").strip()
        if saved_backup not in tts_server_ids:
            saved_backup = ""
        st.session_state[backup_widget_key] = saved_backup
        st.selectbox(
            tr(f"Backup Voiceover Service {slot}"),
            options=[""] + tts_server_ids,
            key=backup_widget_key,
            format_func=lambda server_id: (
                disabled_label
                if not server_id
                else _tts_server_label(server_id)
            ),
            on_change=_save_settings_change,
            args=(
                "ui",
                backup_config_key,
                backup_widget_key,
                lambda value: str(value or "").strip(),
            ),
        )
    st.caption(tr("TTS Chain Help"))
    for server_id, label in TTS_SERVER_OPTIONS:
        with st.expander(
            f"{label} {_platform_status_badge(source_failover.tts_server_available(server_id))}",
            expanded=False,
        ):
            _render_tts_provider_settings(server_id)


def _render_tts_provider_settings(server):
    """配音服务的凭证与参数表单（从音频面板抽出的 Key 配置）。"""
    if server == "azure-tts-v1":
        st.caption(tr("Azure Edge TTS Free Hint"))
    elif server == "azure-tts-v2":
        azure_speech_region = st.text_input(
            tr("Speech Region"),
            value=config.azure.get("speech_region", ""),
            key="azure_speech_region_input",
        )
        azure_speech_key = st.text_input(
            tr("Speech Key"),
            value=config.azure.get("speech_key", ""),
            type="password",
            key="azure_speech_key_input",
        )
        _set_runtime_config("azure", "speech_region", azure_speech_region)
        _set_runtime_config("azure", "speech_key", azure_speech_key)
    elif server == "gemini-tts":
        # Gemini TTS 与 Gemini LLM 共用同一份密钥；在服务商配置集中维护。
        gemini_tts_api_key = st.text_input(
            tr("Gemini API Key"),
            value=config.app.get("gemini_api_key", ""),
            type="password",
            key="gemini_tts_api_key_input",
        )
        _set_runtime_config("app", "gemini_api_key", gemini_tts_api_key)
    elif server == "siliconflow":
        siliconflow_api_key = st.text_input(
            tr("SiliconFlow API Key"),
            value=config.siliconflow.get("api_key", ""),
            type="password",
            key="siliconflow_api_key_input",
        )
        _set_runtime_config("siliconflow", "api_key", siliconflow_api_key)
    elif server == "mimo-tts":
        # MiMo TTS 复用 MiMo LLM Provider 的 API Key，只需维护一份密钥。
        mimo_api_key = st.text_input(
            tr("MiMo API Key"),
            value=config.app.get("mimo_api_key", ""),
            type="password",
            key="mimo_tts_api_key_input",
        )
        _set_runtime_config("app", "mimo_api_key", mimo_api_key)
    elif server == "minimax-tts":
        _render_minimax_tts_settings()
    elif server == "elevenlabs":
        _render_elevenlabs_api_key_input("ElevenLabs API Key")
        _elevenlabs_models = [
            "eleven_multilingual_v2",
            "eleven_flash_v2_5",
            "eleven_v3",
        ]
        saved_elevenlabs_model = config.elevenlabs.get(
            "model_id", "eleven_multilingual_v2"
        )
        if saved_elevenlabs_model not in _elevenlabs_models:
            saved_elevenlabs_model = "eleven_multilingual_v2"
        elevenlabs_model = stable_selectbox(
            tr("ElevenLabs Model"),
            options=_elevenlabs_models,
            default_value=saved_elevenlabs_model,
            key="elevenlabs_model_select",
        )
        _set_runtime_config("elevenlabs", "model_id", elevenlabs_model)
    elif server == "fish_audio":
        fish_audio_api_key = st.text_input(
            tr("Fish Audio API Key"),
            value=(
                config.fish_audio.get("api_key", "")
                if hasattr(config, "fish_audio") and isinstance(config.fish_audio, dict)
                else ""
            ),
            type="password",
            key="fish_audio_api_key_input",
        )
        _set_runtime_config("fish_audio", "api_key", fish_audio_api_key)
        _fish_audio_models = [
            "s2.1-pro-free",
            "s2.1-pro",
            "s2-pro",
        ]
        saved_fish_model = (
            config.fish_audio.get("model", "s2.1-pro-free")
            if hasattr(config, "fish_audio") and isinstance(config.fish_audio, dict)
            else "s2.1-pro-free"
        )
        if saved_fish_model not in _fish_audio_models:
            saved_fish_model = "s2.1-pro-free"
        fish_model = stable_selectbox(
            tr("Fish Audio Model"),
            options=_fish_audio_models,
            default_value=saved_fish_model,
            key="fish_audio_model_select",
        )
        _set_runtime_config("fish_audio", "model", fish_model)
    elif server == "voxcpm":
        _sync_voxcpm_api_key_input()
        voxcpm_api_key = st.text_input(
            tr("VoxCPM API Key"),
            type="password",
            key="voxcpm_api_key_input",
        )
        _set_runtime_config("voxcpm", "api_key", voxcpm_api_key)
        voxcpm_model = st.text_input(
            tr("VoxCPM Model ID"),
            value=config.voxcpm.get("model_id", ""),
            key="voxcpm_model_id_input",
            placeholder=tr("VoxCPM Model ID Placeholder"),
        )
        _set_runtime_config("voxcpm", "model_id", voxcpm_model.strip())
        voxcpm_base_url = st.text_input(
            tr("VoxCPM Base URL"),
            value=config.voxcpm.get("base_url") or DEFAULT_VOXCPM_BASE_URL,
            key="voxcpm_base_url_input",
            placeholder=DEFAULT_VOXCPM_BASE_URL,
        )
        _set_runtime_config(
            "voxcpm",
            "base_url",
            (voxcpm_base_url or DEFAULT_VOXCPM_BASE_URL).strip().rstrip("/"),
        )
        st.caption(tr("VoxCPM Reference Audio Notice"))
    elif server == "chatterbox":
        chatterbox_base_url = st.text_input(
            tr("Chatterbox Base URL"),
            value=config.chatterbox.get("base_url") or DEFAULT_CHATTERBOX_BASE_URL,
            key="chatterbox_base_url_input",
            placeholder=tr("Chatterbox Base URL Placeholder"),
        )
        _set_runtime_config(
            "chatterbox", "base_url", (chatterbox_base_url or "").strip()
        )
        chatterbox_api_key = st.text_input(
            tr("Chatterbox API Key"),
            value=config.chatterbox.get("api_key", ""),
            type="password",
            key="chatterbox_api_key_input",
        )
        _set_runtime_config("chatterbox", "api_key", chatterbox_api_key)
        chatterbox_model = st.text_input(
            tr("Chatterbox Model"),
            value=config.chatterbox.get("model_id") or DEFAULT_CHATTERBOX_MODEL,
            key="chatterbox_model_input",
        )
        _set_runtime_config(
            "chatterbox",
            "model_id",
            (chatterbox_model or DEFAULT_CHATTERBOX_MODEL).strip(),
        )
        _saved_chatterbox_voices = (
            _parse_chatterbox_voices(config.chatterbox.get("voices"))
            or DEFAULT_CHATTERBOX_VOICES
        )
        if isinstance(_saved_chatterbox_voices, list):
            _saved_chatterbox_voices = ", ".join(_saved_chatterbox_voices)
        chatterbox_voices = st.text_input(
            tr("Chatterbox Voices"),
            value=str(_saved_chatterbox_voices or ""),
            key="chatterbox_voices_input",
            placeholder=tr("Chatterbox Voices Placeholder"),
        )
        _set_runtime_config(
            "chatterbox",
            "voices",
            _parse_chatterbox_voices(chatterbox_voices),
        )
    elif server == "kokoro":
        kokoro_base_url = st.text_input(
            tr("Kokoro Base URL"),
            value=config.kokoro.get("base_url") or DEFAULT_KOKORO_BASE_URL,
            key="kokoro_base_url_input",
            placeholder=tr("Kokoro Base URL Placeholder"),
        )
        _set_runtime_config(
            "kokoro", "base_url", (kokoro_base_url or "").strip()
        )
        kokoro_api_key = st.text_input(
            tr("Kokoro API Key"),
            value=config.kokoro.get("api_key", ""),
            type="password",
            key="kokoro_api_key_input",
        )
        _set_runtime_config("kokoro", "api_key", kokoro_api_key)
        kokoro_model = st.text_input(
            tr("Kokoro Model"),
            value=config.kokoro.get("model_id") or DEFAULT_KOKORO_MODEL,
            key="kokoro_model_input",
        )
        _set_runtime_config(
            "kokoro",
            "model_id",
            (kokoro_model or DEFAULT_KOKORO_MODEL).strip(),
        )
        _saved_kokoro_voices = (
            _parse_chatterbox_voices(config.kokoro.get("voices"))
            or DEFAULT_KOKORO_VOICES
        )
        if isinstance(_saved_kokoro_voices, list):
            _saved_kokoro_voices = ", ".join(_saved_kokoro_voices)
        kokoro_voices = st.text_input(
            tr("Kokoro Voices"),
            value=str(_saved_kokoro_voices or ""),
            key="kokoro_voices_input",
            placeholder=tr("Kokoro Voices Placeholder"),
        )
        _set_runtime_config(
            "kokoro",
            "voices",
            _parse_chatterbox_voices(kokoro_voices),
        )


def _render_music_provider_settings(app_settings):
    """音乐 TAB：Sonilo 与 ElevenLabs 配乐凭证（从音频面板抽出）。"""
    st.caption(tr("Provider Music Tab Help"))
    with st.container(border=True):
        st.markdown(f"**{tr('Sonilo Background Music')}**")
        configured_key = str(config.app.get("sonilo_api_key", "") or "").strip()
        effective_key = configured_key or os.getenv("SONILO_API_KEY", "").strip()
        entered_key = st.text_input(
            tr("Sonilo API Key"),
            value=effective_key,
            type="password",
            key="sonilo_api_key_input",
        ).strip()
        # 配置值优先于环境变量；仅当用户确实修改输入或本来就使用配置时
        # 写回，避免把环境变量中的 Key 在无操作的情况下复制进 config.toml。
        if configured_key or entered_key != effective_key:
            _set_runtime_config("app", "sonilo_api_key", entered_key)
    with st.container(border=True):
        st.markdown(f"**{tr('ElevenLabs Background Music')}**")
        _render_elevenlabs_api_key_input("ElevenLabs Music API Key")


def _render_stock_search_provider_settings(app_settings):
    """素材搜索 TAB：库存视频服务的 Key（库存图片源共享同批 Key）。"""
    st.caption(tr("Provider Stock Tab Help"))
    for provider in VIDEO_SOURCE_GROUPS["stock_video"]:
        _render_provider_settings_expander(app_settings, provider)
    st.caption(tr("Stock Image Keys Shared Hint"))


def _open_provider_settings_for_group(group):
    """素材能力 TAB 的跳转回调：打开服务商配置并定位到对应 TAB。"""
    st.session_state["service_provider_target_tab"] = (
        MATERIAL_GROUP_PROVIDER_TAB.get(group, "Provider Overview Tab")
    )
    _open_settings_dialog("llm")


def _render_llm_settings_body(app_settings, is_open=True):
    """服务商配置体；设置弹窗与服务商配置页共用。

    七个能力 TAB：总览矩阵 + 文本生成/视频生成/图片生成/配音/音乐/素材搜索。
    API 凭证集中在这里，创作面板只保留生成参数。
    """
    (
        overview_panel,
        text_panel,
        video_panel,
        image_panel,
        tts_panel,
        music_panel,
        stock_panel,
    ) = _mount_keyed_tabs(
        PROVIDER_TAB_LABEL_KEYS,
        "service_provider_tabs",
        "service_provider_active_tab",
        "service_provider_target_tab",
    )
    with overview_panel:
        if overview_panel.open:
            _render_service_provider_overview(app_settings)
    with text_panel:
        if text_panel.open:
            _render_llm_chain_settings(app_settings, is_open)
    with video_panel:
        if video_panel.open:
            _render_ai_video_provider_settings(app_settings)
    with image_panel:
        if image_panel.open:
            _render_ai_image_provider_settings(app_settings)
    with tts_panel:
        if tts_panel.open:
            _render_voiceover_provider_settings(app_settings)
    with music_panel:
        if music_panel.open:
            _render_music_provider_settings(app_settings)
    with stock_panel:
        if stock_panel.open:
            _render_stock_search_provider_settings(app_settings)


def _render_llm_chain_settings(app_settings, is_open=True):
    """文本生成 TAB：LLM 三槽链（第一优先 + 备用 1/2）+ 当前 Provider 表单。"""
    # 下拉顺序、默认 label 和稳定 provider id 全部来自 Registry；locale
    # 只覆盖展示文案，不再让 Main.py 维护第二份 Provider 列表。
    llm_provider_ids = [
        provider.provider_id for provider in LLM_PROVIDER_REGISTRY
    ]
    llm_provider_labels = {
        provider.provider_id: get_llm_provider_label(provider)
        for provider in LLM_PROVIDER_REGISTRY
    }
    saved_llm_provider = app_settings.get(
        "llm_provider", DEFAULT_LLM_PROVIDER_ID
    ).lower()
    if saved_llm_provider not in llm_provider_ids:
        saved_llm_provider = DEFAULT_LLM_PROVIDER_ID

    llm_provider = stable_selectbox(
        tr("LLM Provider"),
        options=llm_provider_ids,
        default_value=saved_llm_provider,
        key="llm_provider_select",
        format_func=lambda provider_id: llm_provider_labels[provider_id],
        on_change=_save_settings_change,
        args=(
            "app",
            "llm_provider",
            localized_widget_key("llm_provider_select"),
            lambda value: value,
        ),
    )
    _set_runtime_config("app", "llm_provider", llm_provider)

    configured_llm = set(_general_provider_readiness(app_settings).get("llm", ()))
    # format_func 必须是纯闭包：标签在渲染时预算，避免 AppTest 在 run 间
    # 重新求值 format_func 时 tr() 回退语言与已渲染 options 不一致。
    disabled_label = tr("Backup Slot Disabled")
    not_configured_suffix = tr("Provider Not Configured Suffix")
    for slot in (1, 2):
        backup_config_key = f"llm_provider_backup{slot}"
        backup_widget_key = localized_widget_key(f"llm_provider_backup{slot}_select")
        saved_backup = str(app_settings.get(backup_config_key, "") or "").strip().lower()
        if saved_backup not in llm_provider_ids:
            saved_backup = ""
        st.session_state[backup_widget_key] = saved_backup
        st.selectbox(
            tr(f"Backup LLM Provider {slot}"),
            options=[""] + llm_provider_ids,
            key=backup_widget_key,
            format_func=lambda provider_id: (
                disabled_label
                if not provider_id
                else llm_provider_labels[provider_id]
                + (
                    ""
                    if provider_id in configured_llm
                    else not_configured_suffix
                )
            ),
            on_change=_save_settings_change,
            args=(
                "app",
                backup_config_key,
                backup_widget_key,
                lambda value: str(value or "").strip().lower(),
            ),
        )
    st.caption(tr("LLM Chain Help"))

    _render_llm_provider_form(app_settings, llm_provider, is_open)


def _render_llm_provider_form(app_settings, llm_provider, is_open=True):
    """当前选中 LLM Provider 的凭证与参数表单（原大模型设置主体）。"""
    # 配置表单和 Provider 说明并排展示，减少长说明在窄列中的换行，
    # 同时充分利用基础设置面板的横向空间。
    llm_form_panel, llm_help_panel = st.columns(
        [0.9, 1.1],
        gap="large",
        vertical_alignment="top",
    )
    llm_helper = llm_help_panel.container()
    llm_provider_spec = get_llm_provider(llm_provider)
    if llm_provider_spec is None:
        # 正常情况下下拉选项全部来自 Registry，不会进入该分支；保留
        # 明确错误用于诊断损坏的 session state 或后续接入遗漏。
        raise RuntimeError(f"unsupported llm provider: {llm_provider}")

    llm_api_key = app_settings.get(
        llm_provider_spec.config_key("api_key"), ""
    )
    configured_llm_base_url = app_settings.get(
        llm_provider_spec.config_key("base_url"), ""
    )
    llm_default_base_url = llm_provider_spec.effective_default_base_url
    llm_base_url = configured_llm_base_url or llm_default_base_url
    llm_model_name = llm_provider_spec.resolve_model_name(
        app_settings.get(llm_provider_spec.config_key("model_name"), "")
    )

    provider_tip_context = {}
    selected_service_endpoint = None
    if llm_provider_spec.service_endpoints:
        # Kimi 等 Provider 的中国站和国际站使用不同账号体系。只让用户
        # 选择服务区域，再由 Registry 同步 API 申请入口和 Base URL，
        # 避免手工组合错误。已有空 Base URL 配置继续沿用中国站，只有
        # 尚未填写 Key 的全新配置才根据界面语言推荐对应入口。
        selected_service_endpoint = (
            llm_provider_spec.select_service_endpoint(
                configured_llm_base_url,
                has_api_key=bool(str(llm_api_key).strip()),
                prefer_international=(
                    st.session_state.get("ui_language", "en") != "zh"
                ),
            )
        )
        endpoint_options = [
            endpoint.endpoint_id
            for endpoint in llm_provider_spec.service_endpoints
        ] + [CUSTOM_LLM_ENDPOINT_ID]
        default_endpoint_id = (
            selected_service_endpoint.endpoint_id
            if selected_service_endpoint
            else CUSTOM_LLM_ENDPOINT_ID
        )
        endpoint_labels = {
            endpoint.endpoint_id: (
                tr_optional(
                    llm_provider_spec.endpoint_label_key(
                        endpoint.endpoint_id
                    ),
                    fallback_language="en",
                )
                or endpoint.default_label
            )
            for endpoint in llm_provider_spec.service_endpoints
        }
        endpoint_labels[CUSTOM_LLM_ENDPOINT_ID] = (
            tr_optional("Custom API Endpoint", fallback_language="en")
            or "Custom API Endpoint"
        )
        with llm_form_panel:
            selected_endpoint_id = stable_selectbox(
                tr_optional(
                    llm_provider_spec.endpoint_selector_label_key,
                    fallback_language="en",
                )
                or tr("API Platform"),
                options=endpoint_options,
                default_value=default_endpoint_id,
                key=f"{llm_provider}_service_endpoint_select",
                on_change=_save_settings_endpoint,
                args=(
                    llm_provider_spec,
                    localized_widget_key(
                        f"{llm_provider}_service_endpoint_select"
                    ),
                ),
                format_func=lambda endpoint_id: endpoint_labels[
                    endpoint_id
                ],
                help=(
                    tr_optional(
                        llm_provider_spec.endpoint_selector_help_key,
                        fallback_language="en",
                    )
                    or None
                ),
            )
        selected_service_endpoint = next(
            (
                endpoint
                for endpoint in llm_provider_spec.service_endpoints
                if endpoint.endpoint_id == selected_endpoint_id
            ),
            None,
        )
        if selected_service_endpoint:
            llm_base_url = selected_service_endpoint.base_url
            provider_tip_context.update(
                {
                    "api_key_url": selected_service_endpoint.api_key_url,
                    "default_base_url": selected_service_endpoint.base_url,
                    "model_docs_url": selected_service_endpoint.model_docs_url,
                }
            )
        else:
            # 自定义模式只保留用户明确保存的地址，不将某个标准区域伪装
            # 成自定义值。输入为空时配置不会持久化，下一次仍回到兼容默认。
            llm_base_url = str(configured_llm_base_url or "").strip()

    if llm_provider == "ollama":
        llm_default_base_url = config.get_default_ollama_base_url()
        if not llm_base_url:
            llm_base_url = llm_default_base_url
        docker_hint = ""
        if config.is_running_in_container():
            docker_hint = tr_optional(
                "llm_provider_tips.ollama.docker_hint",
                fallback_language="en",
            )
        provider_tip_context["docker_hint"] = docker_hint

    tips = get_llm_provider_tips(llm_provider, **provider_tip_context)
    if tips:
        with llm_helper:
            st.info(tips)

    st_llm_api_key = llm_api_key
    if llm_provider_spec.show_api_key:
        st_llm_api_key = llm_form_panel.text_input(
            tr("API Key"),
            value=llm_api_key,
            type="password",
            key=f"{llm_provider}_api_key_input",
            on_change=_save_settings_change,
            args=(
                "app",
                llm_provider_spec.config_key("api_key"),
                f"{llm_provider}_api_key_input",
                lambda value: value,
            ),
        )

    st_llm_base_url = llm_base_url
    if llm_provider_spec.show_base_url:
        st_llm_base_url = llm_form_panel.text_input(
            tr("Base Url"),
            value=llm_base_url,
            key=(
                f"{llm_provider}_base_url_"
                f"{selected_service_endpoint.endpoint_id}_input"
                if selected_service_endpoint
                else f"{llm_provider}_base_url_custom_input"
            ),
            disabled=selected_service_endpoint is not None,
            on_change=_save_settings_change,
            args=(
                "app",
                llm_provider_spec.config_key("base_url"),
                f"{llm_provider}_base_url_"
                f"{selected_service_endpoint.endpoint_id}_input"
                if selected_service_endpoint
                else f"{llm_provider}_base_url_custom_input",
                lambda value, llm_default_base_url=llm_default_base_url: (
                    normalize_provider_override(value, llm_default_base_url)
                ),
            ),
        )
    st_llm_model_name = ""
    if llm_provider == "openai_codex":
        from webui.codex_models import render_codex_model_selector

        with llm_form_panel:
            st_llm_model_name = render_codex_model_selector(
                llm_model_name,
                tr,
                on_change=lambda model, provider=llm_provider_spec: (
                    _set_runtime_config(
                        "app",
                        provider.config_key("model_name"),
                        normalize_provider_override(
                            model, provider.default_model
                        ),
                    )
                ),
            )
    elif llm_provider == "openai_chatgpt":
        from webui.chatgpt_login import render_chatgpt_login
        from webui.chatgpt_models import render_chatgpt_model_selector

        with llm_form_panel:
            if is_open:
                # Keep the nested polling fragment's delta paths separate
                # from the model selector and connection-test controls.
                with st.container(key="chatgpt_login_panel"):
                    render_chatgpt_login(tr)
            st_llm_model_name = render_chatgpt_model_selector(
                llm_model_name,
                tr,
                on_change=lambda model, provider=llm_provider_spec: (
                    _set_runtime_config(
                        "app",
                        provider.config_key("model_name"),
                        normalize_provider_override(
                            model, provider.default_model
                        ),
                    )
                ),
            )
    elif llm_provider == "groq":
        effective_api_key = st_llm_api_key or llm_api_key
        effective_base_url = st_llm_base_url or llm_base_url
        groq_models = get_groq_model_ids(
            api_key=effective_api_key,
            base_url=effective_base_url,
        )

        if groq_models:
            selected_index = 0
            if llm_model_name in groq_models:
                selected_index = groq_models.index(llm_model_name)

            st_llm_model_name = llm_form_panel.selectbox(
                tr("Model Name"),
                options=groq_models,
                index=selected_index,
                key="groq_model_name_select",
                on_change=_save_settings_change,
                args=(
                    "app",
                    llm_provider_spec.config_key("model_name"),
                    "groq_model_name_select",
                    lambda value, llm_provider_spec=llm_provider_spec: (
                        normalize_provider_override(
                            value, llm_provider_spec.default_model
                        )
                    ),
                ),
            )
        else:
            st_llm_model_name = llm_form_panel.text_input(
                tr("Model Name"),
                value=llm_model_name,
                key="groq_model_name_input",
                on_change=_save_settings_change,
                args=(
                    "app",
                    llm_provider_spec.config_key("model_name"),
                    "groq_model_name_input",
                    lambda value, llm_provider_spec=llm_provider_spec: (
                        normalize_provider_override(
                            value, llm_provider_spec.default_model
                        )
                    ),
                ),
            )
            if effective_api_key:
                llm_form_panel.caption(tr("Groq Model List Load Failed"))
            else:
                llm_form_panel.caption(
                    tr("Groq API Key Required for Model List")
                )
    else:
        st_llm_model_name = llm_form_panel.text_input(
            tr("Model Name"),
            value=llm_model_name,
            key=f"{llm_provider}_model_name_input",
            on_change=_save_settings_change,
            args=(
                "app",
                llm_provider_spec.config_key("model_name"),
                f"{llm_provider}_model_name_input",
                lambda value, llm_provider_spec=llm_provider_spec: (
                    normalize_provider_override(
                        value, llm_provider_spec.default_model
                    )
                ),
            ),
        )
    # 输入框展示 Registry 默认值，但配置只保存真实的用户覆盖值。
    # 这样默认模型、Base URL 更新后，未自定义的用户能够自动跟随。
    _set_runtime_config(
        "app",
        llm_provider_spec.config_key("api_key"),
        st_llm_api_key,
    )
    _set_runtime_config(
        "app",
        llm_provider_spec.config_key("base_url"),
        normalize_provider_override(
            st_llm_base_url,
            llm_default_base_url,
        ),
    )
    _set_runtime_config(
        "app",
        llm_provider_spec.config_key("model_name"),
        normalize_provider_override(
            st_llm_model_name,
            llm_provider_spec.default_model,
        ),
    )

    # Provider 专用字段也由 Registry 声明。例如 Cloudflare AI Gateway
    # 需要 Account ID；以后新增类似字段时无需再在 Main.py 增加判断。
    for field in llm_provider_spec.extra_fields:
        field_config_key = llm_provider_spec.config_key(field.config_suffix)
        field_value = llm_form_panel.text_input(
            tr(field.label_key),
            value=(
                app_settings.get(field_config_key, "")
                or field.default_value
            ),
            type="password" if field.secret else "default",
            key=f"{llm_provider}_{field.config_suffix}_input",
            on_change=_save_settings_change,
            args=(
                "app",
                field_config_key,
                f"{llm_provider}_{field.config_suffix}_input",
                lambda value, field=field: normalize_provider_override(
                    value, field.default_value
                ),
            ),
        )
        _set_runtime_config(
            "app",
            field_config_key,
            normalize_provider_override(
                field_value,
                field.default_value,
            ),
        )

    if llm_provider == "openai_codex" and is_open:
        from webui.codex_login import render_codex_login

        with llm_form_panel.container():
            render_codex_login(tr)

    if llm_provider == "kimi_code" and is_open:
        from app.services import kimi_code_oauth
        from webui.kimi_login import render_kimi_login

        # 给嵌套 fragment 独立的容器，轮询重绘不占用后续控件的位置。
        with llm_form_panel.container():
            render_kimi_login(
                kimi_code_oauth.resolve_region(st_llm_base_url), tr
            )

    if llm_form_panel.button(
        tr("Test LLM Connection"),
        key="test_llm_connection_button",
        use_container_width=True,
        type="secondary",
        icon=":material/network_check:",
    ):
        with config.try_runtime_config_lock() as lock_acquired:
            if not lock_acquired:
                llm_form_panel.warning(tr("Runtime Configuration Busy"))
            else:
                with llm_form_panel.spinner(tr("Testing LLM Connection")):
                    connection_ok, connection_error, connection_elapsed = (
                        llm.test_connection()
                    )

        if not lock_acquired:
            connection_ok = None
        elif connection_ok:
            # llm_provider_labels 是 _render_llm_chain_settings 的局部变量；
            # 这里从 Registry 解析 label，避免连接成功路径 NameError。
            llm_form_panel.success(
                tr("LLM Connection Test Succeeded").format(
                    provider=get_llm_provider_label(llm_provider_spec),
                    model=st_llm_model_name or "-",
                    elapsed=f"{connection_elapsed:.2f}",
                )
            )
        else:
            connection_error = format_llm_connection_error(
                llm_provider,
                st_llm_base_url,
                connection_error,
            )
            llm_form_panel.error(
                tr("LLM Connection Test Failed").format(
                    error=connection_error
                )
            )


# 素材能力 TAB 的标题（能力即素材分组，local 不参与备用链）。
MATERIAL_CAPABILITY_TAB_LABEL_KEYS = (
    "Capability Group AI Video",
    "Capability Group AI Image",
    "Capability Group Stock Video",
    "Capability Group Stock Image",
)


def _material_backup_source_options(group):
    return [""] + list(VIDEO_SOURCE_GROUPS[group])


def _render_material_capability_tab(group, app_settings):
    """单个素材能力 TAB：三槽来源链 + 源状态 + Key 集中提示，无任何 Key 输入。"""
    providers = VIDEO_SOURCE_GROUPS[group]
    labels = _material_provider_labels()
    capability_labels = {
        source: labels.get(source, source) for source in providers
    }
    # format_func 必须是纯闭包：渲染时预算标签，避免 run 间重新求值时
    # tr() 回退语言与已渲染 options 不一致。
    disabled_label = tr("Backup Slot Disabled")
    configured_sources = {
        source
        for sources in _general_provider_readiness(app_settings).values()
        if group != "llm"
        for source in sources
    }

    primary_widget_key = localized_widget_key(f"material_primary_{group}_select")
    saved_source = str(app_settings.get("video_source", "") or "")
    default_primary = saved_source if saved_source in providers else providers[0]
    st.session_state[primary_widget_key] = default_primary
    st.selectbox(
        tr("Priority Source"),
        options=providers,
        key=primary_widget_key,
        format_func=capability_labels.get,
        on_change=_activate_material_primary_source,
        args=(group, primary_widget_key),
    )
    st.caption(tr("Material Primary Source Help"))

    for slot in (1, 2):
        backup_config_key = f"video_source_backups_{group}_{slot}"
        backup_widget_key = localized_widget_key(
            f"material_backup{slot}_{group}_select"
        )
        saved_backup = str(app_settings.get(backup_config_key, "") or "").strip()
        if saved_backup not in providers:
            saved_backup = ""
        st.session_state[backup_widget_key] = saved_backup
        st.selectbox(
            tr(f"Backup Source {slot}"),
            options=_material_backup_source_options(group),
            key=backup_widget_key,
            format_func=lambda source_id: (
                disabled_label
                if not source_id
                else capability_labels.get(source_id, source_id)
            ),
            on_change=_save_settings_change,
            args=(
                "app",
                backup_config_key,
                backup_widget_key,
                lambda value: str(value or "").strip(),
            ),
        )
    st.caption(tr("Material Chain Help"))

    with st.container(border=True):
        st.markdown(f"**{tr('Source Status Section')}**")
        for source in providers:
            ready = source in configured_sources
            badge = ":material/check_circle:" if ready else ":material/radio_button_unchecked:"
            status_text = (
                tr("Provider Configured Badge")
                if ready
                else tr("Provider Not Configured Badge")
            )
            st.markdown(
                f"{badge} {capability_labels[source]} · {status_text}"
            )

    st.caption(tr("Material Keys In Provider Page Hint"))
    st.button(
        tr("Open Provider Settings"),
        key=f"material_open_providers_{group}",
        icon=":material/hub:",
        on_click=_open_provider_settings_for_group,
        args=(group,),
    )


def _render_material_settings_body(app_settings):
    """素材来源设置体；设置弹窗与一级素材来源页共用。

    按能力分组为四个 TAB（AI 视频/AI 图片/库存视频/库存图片），每个能力
    支持三槽来源链（第一优先写唯一主源键并与创作页同步；备用 1/2 按能力
    分组存储）。Key 配置全部集中在服务商配置页，这里不再提供任何 Key 输入。
    """
    groups = list(service_catalog.MATERIAL_CAPABILITY_GROUPS)
    panels = _mount_keyed_tabs(
        MATERIAL_CAPABILITY_TAB_LABEL_KEYS,
        "material_capability_tabs",
        "settings_material_group",
        stable_keys=groups,
    )
    for panel, group in zip(panels, groups):
        with panel:
            if panel.open:
                _render_material_capability_tab(group, app_settings)


@st.dialog(
    tr("Settings"),
    width="medium",
    on_dismiss=_dismiss_settings_dialog,
)
def _render_settings_dialog():
    app_settings = config.snapshot_config_with_pending(config.app)
    ui_settings = config.snapshot_config_with_pending(config.ui)
    with st.container():
        # 历史 hide_config 只用于隐藏旧基础设置面板。改为固定设置入口后，该值
        # 不再有用户可见意义，统一迁移为 false，避免旧配置影响后续版本。
        _set_runtime_config("app", "hide_config", False)
        tab_keys = {
            "general": "General Settings Tab",
            "llm": "Service Providers Tab",
            "material": "Material API Tab",
            "publish": "Auto-Publish Settings",
            "interface": "Interface Settings Tab",
            "keys": "Key Backup Tab",
            "cache": "Cache Management Tab",
            "brand": "Brand Theme Tab",
        }
        settings_tab_targets = {key: tr(label) for key, label in tab_keys.items()}
        settings_tabs_key = localized_widget_key("settings_dialog_tabs")
        target_tab = st.session_state.pop("settings_dialog_target_tab", None)
        if target_tab in {"stock", "video", "image", "material"}:
            _initialize_material_navigation(target_tab, app_settings)
        if target_tab in {"stock", "video", "image"}:
            target_tab = "material"
        active = target_tab or st.session_state.get("settings_active_tab", "general")
        if active not in settings_tab_targets:
            active = "general"
        if (
            target_tab
            or st.session_state.get(settings_tabs_key)
            not in settings_tab_targets.values()
        ):
            st.session_state[settings_tabs_key] = settings_tab_targets[active]
        panels = st.tabs(
            list(settings_tab_targets.values()),
            key=settings_tabs_key,
            on_change=_remember_settings_tab,
            args=(settings_tabs_key, settings_tab_targets),
        )
        (
            general_config_panel,
            middle_config_panel,
            right_config_panel,
            publish_config_panel,
            left_config_panel,
            key_backup_panel,
            cache_config_panel,
            brand_panel,
        ) = panels
        _remember_settings_tab(settings_tabs_key, settings_tab_targets)
        with general_config_panel:
            if general_config_panel.open:
                _render_general_settings(app_settings)

        with publish_config_panel:
            if publish_config_panel.open:
                _render_publish_settings_body(app_settings)

        # 左侧面板 - 日志设置
        with left_config_panel:
            if left_config_panel.open:
                _render_interface_settings_body(ui_settings)

        if cache_config_panel.open:
            _render_cache_management_settings(cache_config_panel)
        # 密钥恢复会写回配置并清除密码控件状态，必须在下面渲染这些控件之前执行。
        if key_backup_panel.open:
            _render_key_backup_settings(key_backup_panel)


        # 中间面板 - LLM 设置
        with middle_config_panel:
            if middle_config_panel.open:
                _render_llm_settings_body(app_settings, middle_config_panel.open)

        # 右侧面板 - API 密钥设置
        with right_config_panel:
            if right_config_panel.open:
                _render_material_settings_body(app_settings)

        # 品牌主题面板：与左导航控制区共享会话主题，改动即时生效。
        with brand_panel:
            if brand_panel.open:
                st.caption(tr("Theme Dialog Hint"))
                brand_theme.render_controls("cfset", tr)

    _save_runtime_config()


# -----------------------------------------------------------------------------
# 主生成表单：文案、视频、音频与字幕面板
# -----------------------------------------------------------------------------


def _create_loomloom_script_backend():
    """从当前 WebUI/config.toml 配置创建批量文案客户端。"""
    app_config_snapshot = config.snapshot_config_with_pending(config.app)
    settings = loomloom.LoomLoomSettings.from_mapping(app_config_snapshot)
    return loomloom.LoomLoomScriptBackend(settings)


def _create_loomloom_video_backend():
    """使用项目默认 SkillBot 和当前有效凭证创建视频客户端。"""
    app_config_snapshot = config.snapshot_config_with_pending(config.app)
    settings = loomloom.video_settings_from_mapping(app_config_snapshot)
    return loomloom.LoomLoomVideoBackend(settings)


def _effective_loomloom_api_token():
    """读取 WebUI 尚未落盘或 config.toml 中的胜算云 API Key。"""
    app_config_snapshot = config.snapshot_config_with_pending(config.app)
    return loomloom.resolve_api_token(app_config_snapshot)


def _effective_script_generation_backend():
    """读取包含 WebUI 待保存修改的文案生成方式。"""
    app_config_snapshot = config.snapshot_config_with_pending(config.app)
    backend = str(
        app_config_snapshot.get("script_generation_backend", "local") or "local"
    ).strip()
    return backend if backend in {"local", "loomloom"} else "local"


def _script_generation_method_help(selected_backend):
    """让“文案生成方式”的问号内容严格跟随当前选择。"""
    if selected_backend != "loomloom":
        return tr("Script Generation Method Help")

    app_config_snapshot = config.snapshot_config_with_pending(config.app)
    guidance = [tr("LoomLoom Batch Script Generation Help")]
    if (
        str(app_config_snapshot.get("llm_provider", "") or "").strip().lower()
        == "shengsuanyun"
    ):
        guidance.append(tr("Shengsuan Cloud API Key Reused"))
    guidance.append(tr("Shengsuan Cloud API Key Link"))
    return "\n\n".join(guidance)


def _loomloom_video_scene_prompts(video_terms, subject, scene_count):
    """按素材关键词生成有限数量的场景描述，供视频模型逐段生成素材。"""
    if isinstance(video_terms, str):
        terms = [
            term.strip() for term in re.split(r"[,，\n]", video_terms) if term.strip()
        ]
    elif isinstance(video_terms, list):
        terms = [
            str(term or "").strip() for term in video_terms if str(term or "").strip()
        ]
    else:
        terms = []
    fallback = str(subject or "").strip()
    if not terms and fallback:
        terms = [fallback]
    if not terms:
        return ()
    return tuple(
        (
            terms[index % len(terms)]
            if index < len(terms)
            else f"{terms[index % len(terms)]}; alternative camera angle {index + 1}"
        )
        for index in range(int(scene_count))
    )


def _loomloom_video_signature(batch, credential_fingerprint):
    """将全部计费输入和凭证摘要纳入签名，参数变化后强制重新报价。"""
    payload = {
        "inputRows": [dict(row) for row in batch.input_rows],
        "credentialFingerprint": str(credential_fingerprint or "").strip(),
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _loomloom_video_account_signature(token):
    """服务地址和凭据共同隔离模型目录及报价，不能跨端点复用已确认状态。"""
    values = config.snapshot_config_with_pending(config.app)
    base_url = str(values.get("loomloom_base_url") or loomloom.DEFAULT_BASE_URL).strip().rstrip("/")
    payload = json.dumps([base_url, str(token or "").strip()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_loomloom_video_capability(token, *, force=False):
    """按当前凭证缓存 Profile；刷新失败时保留同一凭证最近的成功结果。"""
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    fingerprint = _loomloom_video_account_signature(normalized_token)
    if st.session_state.get("loomloom_video_capability_fingerprint") != fingerprint:
        st.session_state["loomloom_video_capability"] = None
        st.session_state["loomloom_video_capability_fingerprint"] = fingerprint
        st.session_state["loomloom_video_capability_load_attempt"] = ""
        st.session_state["loomloom_video_capability_error"] = ""

    should_load = force or (
        st.session_state.get("loomloom_video_capability_load_attempt") != fingerprint
    )
    if should_load:
        st.session_state["loomloom_video_capability_load_attempt"] = fingerprint
        try:
            capability = _create_loomloom_video_backend().resolve_video_capability()
        except (loomloom.LoomLoomError, ValueError) as exc:
            logger.warning(
                f"failed to load LoomLoom video capability: error={type(exc).__name__}"
            )
            st.session_state["loomloom_video_capability_error"] = str(exc)
        else:
            st.session_state["loomloom_video_capability"] = capability
            st.session_state["loomloom_video_capability_error"] = ""

    capability = st.session_state.get("loomloom_video_capability")
    return (
        capability if isinstance(capability, loomloom.LoomLoomVideoCapability) else None
    )


def _normalize_loomloom_model_identifier(value):
    """统一展示名和模型 ID 的分隔符、大小写，供本地价格表安全匹配。"""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def _loomloom_video_model_price(model):
    """返回已知模型的（下拉框短价、选中后完整参考价）；未知模型返回空值。"""
    identifiers = {
        _normalize_loomloom_model_identifier(model.model_id),
        _normalize_loomloom_model_identifier(model.display_name),
    }
    for aliases, compact_price, detailed_price in LOOMLOOM_VIDEO_MODEL_PRICES:
        if identifiers.intersection(aliases):
            return compact_price, detailed_price
    return "", ""


def _format_loomloom_video_model_option(model):
    """在模型名右侧展示短价格，避免多档分辨率价格把下拉框撑得过宽。"""
    compact_price, _ = _loomloom_video_model_price(model)
    return f"{model.display_name} · {compact_price}" if compact_price else model.display_name


def _effective_voice_rate_before_audio_panel():
    """视频面板位于音频面板之前，需从现有控件状态或配置读取当前语速。"""
    raw_rate = st.session_state.get(
        localized_widget_key("voice_rate_select"),
        config.ui.get("voice_rate", 1.0),
    )
    try:
        rate = float(raw_rate)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    return rate if math.isfinite(rate) and rate > 0 else 1.0


def _matching_full_voice_preview_duration(script, voice_rate):
    """仅在文案、Provider、音色和语速均未变化时采用完整试听的真实时长。"""
    cached = st.session_state.get("voice_preview_audio")
    if not isinstance(cached, dict) or cached.get("preview_type") != "full":
        return None
    script_digest = hashlib.sha256(str(script or "").encode("utf-8")).hexdigest()
    if cached.get("content_digest") != script_digest:
        return None

    current_tts_server = st.session_state.get(
        localized_widget_key("tts_server_select"),
        config.ui.get("tts_server", "azure-tts-v1"),
    )
    current_voice_name = st.session_state.get(
        localized_widget_key(f"speech_synthesis_select_{current_tts_server}"),
        config.ui.get("voice_name", ""),
    )
    try:
        cached_voice_rate = float(cached.get("voice_rate", 0))
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        cached.get("tts_server") != current_tts_server
        or cached.get("voice_name") != current_voice_name
        or not math.isfinite(cached_voice_rate)
        or not math.isclose(cached_voice_rate, voice_rate)
    ):
        return None

    duration = cached.get("duration")
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        return None
    return float(duration)


def _loomloom_video_coverage_plan(params):
    """按真实或估算旁白时长推荐素材数；不足部分仍由原有循环逻辑补齐。"""
    script = str(params.video_script or "").strip()
    if not script:
        return None

    voice_rate = _effective_voice_rate_before_audio_panel()
    actual_duration = _matching_full_voice_preview_duration(script, voice_rate)
    if actual_duration is not None:
        duration_min = duration_max = actual_duration
        basis_key = "AI Video Duration Basis Actual"
    else:
        estimated = _estimate_voiceover_duration_range(script, voice_rate)
        if not estimated:
            return None
        duration_min, duration_max = estimated
        basis_key = "AI Video Duration Basis Estimated"

    clip_duration = max(float(params.video_clip_duration or 1), 1.0)
    needed_min = max(math.ceil(duration_min / clip_duration), 1)
    needed_max = max(math.ceil(duration_max / clip_duration), needed_min)
    return {
        "script_digest": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "basis_key": basis_key,
        "duration_min": float(duration_min),
        "duration_max": float(duration_max),
        "clip_duration": clip_duration,
        "needed_min": needed_min,
        "needed_max": needed_max,
        # 推荐值优先覆盖保守上界，但绝不突破服务端允许的付费任务上限。
        "recommended_count": min(needed_max, loomloom.MAX_VIDEO_SCENES),
    }


def _format_numeric_range(minimum, maximum, digits=1):
    if math.isclose(float(minimum), float(maximum)):
        return f"{float(maximum):.{digits}f}"
    return f"{float(minimum):.{digits}f}–{float(maximum):.{digits}f}"


def _selected_loomloom_video_model(capability):
    """返回仍在当前 Profile 候选中的用户选择，不做静默回退。"""
    selected_model_id = str(
        st.session_state.get("loomloom_video_model_id", "") or ""
    ).strip()
    eligible_model_ids = {model.model_id for model in capability.models}
    return selected_model_id if selected_model_id in eligible_model_ids else ""


def _current_loomloom_video_quote_context(params):
    """根据当前页面参数构建默认 SkillBot 的视频报价批次。"""
    token = _effective_loomloom_api_token()
    fingerprint = _loomloom_video_account_signature(token) if token else ""
    capability = st.session_state.get("loomloom_video_capability")
    if (
        not isinstance(capability, loomloom.LoomLoomVideoCapability)
        or st.session_state.get("loomloom_video_capability_fingerprint") != fingerprint
    ):
        return None, ""
    model_id = _selected_loomloom_video_model(capability)
    scene_count = int(st.session_state.get("loomloom_video_scene_count", 1) or 1)
    prompts = _loomloom_video_scene_prompts(
        params.video_terms,
        params.video_subject or params.video_script,
        scene_count,
    )
    aspect_ratio = str(
        params.video_aspect.value
        if isinstance(params.video_aspect, VideoAspect)
        else params.video_aspect
    )
    if (
        not token
        or not model_id
        or not prompts
        or aspect_ratio not in capability.aspect_ratios
    ):
        return None, ""
    try:
        batch = _create_loomloom_video_backend().prepare_video_batch(
            subject=params.video_subject or params.video_script,
            scene_prompts=prompts,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
        )
    except (loomloom.LoomLoomError, ValueError):
        return None, ""
    return batch, _loomloom_video_signature(batch, fingerprint)


def _retry_loomloom_video_quote():
    """用户主动重试时解除失败锁；不沿用之前的付费确认。"""
    st.session_state["loomloom_video_quote_error_signature"] = ""
    st.session_state["loomloom_video_quote_error"] = ""
    st.session_state["loomloom_video_confirm_charge"] = False


def _render_loomloom_video_settings(params):
    """渲染默认视频 SkillBot 的报价、报价失效和付费确认流程。"""
    st.caption(tr("Shengsuan Cloud AI Video Help"))
    if (
        str(
            config.snapshot_config_with_pending(config.app).get("llm_provider", "")
            or ""
        ).lower()
        == "shengsuanyun"
    ):
        st.caption(tr("Shengsuan Cloud API Key Reused"))

    token = _effective_loomloom_api_token()

    refresh_models = st.button(
        tr("Refresh AI Video Models"),
        key="loomloom_refresh_video_models",
        use_container_width=True,
        disabled=not token,
    )
    capability = _load_loomloom_video_capability(token, force=refresh_models)
    capability_error = str(
        st.session_state.get("loomloom_video_capability_error", "") or ""
    ).strip()
    if capability_error:
        st.warning(tr("AI Video Model List Load Failed").format(error=capability_error))

    if capability is not None:
        models_by_id = {model.model_id: model for model in capability.models}
        selected_model_id = str(
            st.session_state.get("loomloom_video_model_id", "") or ""
        ).strip()
        if not selected_model_id:
            selected_model_id = capability.default_model_id
            st.session_state["loomloom_video_model_id"] = selected_model_id

        model_options = list(models_by_id)
        if selected_model_id not in models_by_id:
            # 保留已失效的原选择，让用户明确看到状态并主动重选。直接把控件
            # 改成新的默认模型会让旧报价与用户认知不一致。
            model_options.insert(0, selected_model_id)

        selected_model_id = stable_selectbox(
            tr("AI Video Model"),
            options=model_options,
            default_value=selected_model_id,
            key="loomloom_video_model_select",
            format_func=lambda model_id: (
                _format_loomloom_video_model_option(models_by_id[model_id])
                if model_id in models_by_id
                else tr("Unavailable AI Video Model").format(model=model_id)
            ),
        )
        st.session_state["loomloom_video_model_id"] = selected_model_id
        if selected_model_id not in models_by_id:
            st.error(tr("Selected AI Video Model Unavailable"))
        else:
            _, detailed_price = _loomloom_video_model_price(
                models_by_id[selected_model_id]
            )
            if detailed_price:
                st.caption(
                    tr("AI Video Model Reference Price").format(price=detailed_price)
                )

        current_aspect_ratio = str(
            params.video_aspect.value
            if isinstance(params.video_aspect, VideoAspect)
            else params.video_aspect
        )
        if current_aspect_ratio not in capability.aspect_ratios:
            st.error(tr("Selected AI Video Ratio Unavailable"))

    coverage_plan = _loomloom_video_coverage_plan(params)
    pending_autofill_digest = str(
        st.session_state.get("loomloom_video_scene_autofill_digest", "") or ""
    )
    if (
        coverage_plan is not None
        and pending_autofill_digest == coverage_plan["script_digest"]
    ):
        # 只在“刚生成文案”或“刚取得完整试听真实时长”时推荐一次。
        # 消费标记后不再覆盖，用户随后手动调整段数会被完整保留。
        st.session_state["loomloom_video_scene_count"] = coverage_plan[
            "recommended_count"
        ]
        st.session_state["loomloom_video_scene_autofill_digest"] = ""

    scene_count = st.number_input(
        tr("AI Video Scene Count"),
        min_value=1,
        max_value=loomloom.MAX_VIDEO_SCENES,
        step=1,
        key="loomloom_video_scene_count",
    )
    _set_runtime_config("ui", "loomloom_video_scene_count", int(scene_count))
    if coverage_plan is not None:
        coverage_seconds = int(scene_count) * coverage_plan["clip_duration"]
        shortfall_min = max(
            coverage_plan["duration_min"] - coverage_seconds, 0.0
        )
        shortfall_max = max(
            coverage_plan["duration_max"] - coverage_seconds, 0.0
        )
        duration_basis = tr(coverage_plan["basis_key"]).format(
            duration=_format_numeric_range(
                coverage_plan["duration_min"], coverage_plan["duration_max"]
            )
        )
        coverage_message = tr("AI Video Material Coverage").format(
            basis=duration_basis,
            clip=_format_numeric_range(
                coverage_plan["clip_duration"], coverage_plan["clip_duration"]
            ),
            needed=_format_numeric_range(
                coverage_plan["needed_min"], coverage_plan["needed_max"], digits=0
            ),
            count=int(scene_count),
            coverage=_format_numeric_range(coverage_seconds, coverage_seconds),
            shortfall=_format_numeric_range(shortfall_min, shortfall_max),
        )
        if shortfall_max > 0:
            st.warning(coverage_message)
        else:
            st.caption(coverage_message)

    batch, input_signature = _current_loomloom_video_quote_context(params)
    if not token:
        st.warning(tr("Shengsuan Cloud API Key Required"))

    quote_result = st.session_state.get("loomloom_video_quote")
    quoted_batch = st.session_state.get("loomloom_video_batch")
    quote_is_current = bool(
        quote_result is not None
        and quoted_batch is not None
        and st.session_state.get("loomloom_video_input_signature") == input_signature
    )
    # 同一组参数失败后暂停自动请求，避免普通页面交互反复等待服务超时。
    # 签名包含账号、端点与全部计费输入；参数变化或用户主动重试后再询价。
    if st.session_state.get("loomloom_video_quote_error_signature") != input_signature:
        st.session_state["loomloom_video_quote_error_signature"] = ""
        st.session_state["loomloom_video_quote_error"] = ""
    quote_failed = bool(st.session_state.get("loomloom_video_quote_error"))
    # Quote 不创建付费任务，真正执行仍需用户明确勾选确认。
    if (token and batch is not None and not quote_is_current and not quote_failed
            and not _generation_is_busy(_current_generation_task_id())):
        st.session_state["loomloom_video_confirm_charge"] = False
        try:
            quote_result = _create_loomloom_video_backend().quote(batch)
        except (loomloom.LoomLoomError, ValueError) as exc:
            logger.warning(f"failed to quote LoomLoom videos: error={exc}")
            st.session_state["loomloom_video_quote_error_signature"] = input_signature
            st.session_state["loomloom_video_quote_error"] = str(exc) or type(exc).__name__
        else:
            st.session_state["loomloom_video_batch"] = batch
            st.session_state["loomloom_video_quote"] = quote_result
            st.session_state["loomloom_video_input_signature"] = input_signature
            st.session_state["loomloom_video_client_request_id"] = (
                f"changofilm-video-{uuid4()}"
            )
            st.session_state["loomloom_video_confirm_charge"] = False
            logger.info(
                "LoomLoom video quote ready: "
                f"tasks={quote_result.task_count}, currency={quote_result.currency}, "
                f"estimated_payable_t={quote_result.estimated_buyer_payable_t}"
            )

    if st.session_state.get("loomloom_video_quote_error"):
        st.error(st.session_state["loomloom_video_quote_error"])
        st.button(
            tr("Retry AI Video Quote"),
            key="loomloom_retry_video_quote",
            on_click=_retry_loomloom_video_quote,
        )

    quote_result = st.session_state.get("loomloom_video_quote")
    quoted_batch = st.session_state.get("loomloom_video_batch")
    if quote_result is not None and quoted_batch is not None:
        display_amount = (
            quote_result.estimated_buyer_payable_amount
            or f"{quote_result.estimated_buyer_payable_t} T"
        )
        if quote_result.estimated_buyer_payable_t == 0:
            st.warning(tr("AI Video Quote Estimate Incomplete"))
        else:
            st.success(
                tr(
                    "AI Video Quote Summary Singular"
                    if quote_result.task_count == 1
                    else "AI Video Quote Summary"
                ).format(
                    tasks=quote_result.task_count,
                    amount=display_amount,
                    currency=quote_result.currency,
                )
            )
        quote_is_current = (
            st.session_state.get("loomloom_video_input_signature") == input_signature
        )
        if not quote_is_current:
            st.warning(tr("LoomLoom Quote Changed Warning"))
        st.checkbox(
            tr("Confirm AI Video Charge"),
            key="loomloom_video_confirm_charge",
            help=tr("Confirm AI Video Charge Help"),
            disabled=not quote_is_current,
        )


def _loomloom_script_signature(
    *,
    subject,
    language,
    candidate_count,
    duration_seconds,
    style,
    credential_fingerprint,
):
    payload = {
        "subject": str(subject or "").strip(),
        "language": str(language or "auto").strip() or "auto",
        "candidateCount": int(candidate_count),
        "durationSeconds": int(duration_seconds),
        "style": str(style or "").strip(),
        "credentialFingerprint": str(credential_fingerprint or "").strip(),
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _render_local_script_generation(params):
    """保留 ChangoFilm 原有的本地 LLM 脚本生成路径。"""
    if not st.button(
        tr("Generate Video Script and Keywords"),
        key="auto_generate_script",
        use_container_width=True,
        type="secondary",
        icon=":material/auto_awesome:",
    ):
        return

    if not params.video_subject:
        st.toast(tr("Please Enter the Video Subject First"))
        st.warning(tr("Please Enter the Video Subject First"))
        return

    with st.spinner(tr("Generating Video Script and Keywords")):

        def generate_script_and_terms(app_config_snapshot):
            script = llm.generate_script(
                video_subject=params.video_subject,
                language=params.video_language,
                paragraph_number=params.paragraph_number,
                video_script_prompt=params.video_script_prompt,
                custom_system_prompt=params.custom_system_prompt,
                app_config=app_config_snapshot,
            )
            if not script:
                # No keyword request for a script that was not generated.
                return "", []
            terms = llm.generate_terms(
                params.video_subject,
                script,
                amount=8 if params.match_materials_to_script else 5,
                match_script_order=params.match_materials_to_script,
                app_config=app_config_snapshot,
            )
            return script, terms

        script, terms = _run_llm_read_operation(
            "generate_script_and_terms",
            generate_script_and_terms,
        )
        # generate_script() and generate_terms() log the provider error and
        # return "" or [] when the model fails. A generated script may itself
        # quote "Error: ", so only an empty result is a failure.
        if not script:
            st.error(tr("Video Script Generation Failed"))
        else:
            st.session_state["video_script"] = script
            st.session_state["video_terms"] = ", ".join(terms)
            st.session_state["loomloom_video_scene_autofill_digest"] = (
                hashlib.sha256(script.strip().encode("utf-8")).hexdigest()
            )
            if not terms:
                # The generated script is kept; blank keywords are generated
                # from it when the video is made.
                st.error(tr("Video Keywords Generation Failed"))


def _render_loomloom_candidates():
    candidates = tuple(st.session_state.get("loomloom_script_candidates") or ())
    errors = tuple(st.session_state.get("loomloom_candidate_errors") or ())
    if errors:
        st.warning(
            tr("LoomLoom Candidate Errors").format(
                count=len(errors),
                details="; ".join(
                    f"#{error.row_index + 1}: {error.message}" for error in errors
                ),
            )
        )
    if not candidates:
        return

    selected_index = st.radio(
        tr("Choose Script Candidate"),
        options=list(range(len(candidates))),
        key="loomloom_selected_candidate",
        format_func=lambda index: (
            f"#{candidates[index].row_index + 1} {candidates[index].script[:80]}"
        ),
    )
    selected = candidates[selected_index]
    st.code(selected.script, language=None, wrap_lines=True)
    st.caption(", ".join(selected.video_terms))
    if st.button(
        tr("Use Selected Candidate"),
        key="loomloom_apply_candidate",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["video_script"] = selected.script
        st.session_state["video_terms"] = ", ".join(selected.video_terms)
        # 与普通大模型生成文案保持一致：应用新候选后仅推荐一次素材数量。
        st.session_state["loomloom_video_scene_autofill_digest"] = (
            hashlib.sha256(selected.script.strip().encode("utf-8")).hexdigest()
        )
        st.toast(tr("LoomLoom Candidate Applied"))


def _handle_loomloom_poll_error(run_id, exc):
    """对脚本任务轮询错误做有限退避，确定性错误立即停止轮询。"""
    logger.warning(f"failed to poll LoomLoom run: run_id={run_id}, error={exc}")
    failure_count = int(st.session_state.get("loomloom_poll_failure_count", 0) or 0) + 1
    retryable = isinstance(exc, loomloom.LoomLoomAPIError) and exc.retryable
    if not retryable or failure_count >= LOOMLOOM_MAX_POLL_FAILURES:
        st.session_state["loomloom_run_error"] = str(exc)
        st.session_state["loomloom_poll_failure_count"] = 0
        st.session_state["loomloom_poll_retry_after"] = 0.0
        # 查询失败不等于远端付费任务失败。保留 run_id 并暂停自动轮询，让用户
        # 可以继续查询同一个任务；如果直接丢弃 ID 后重新提交，可能重复付费。
        st.session_state["loomloom_poll_paused"] = True
        st.rerun(scope="app")
        return

    retry_delay = min(2**failure_count, 30)
    st.session_state["loomloom_poll_failure_count"] = failure_count
    st.session_state["loomloom_poll_retry_after"] = time.monotonic() + retry_delay
    st.warning(
        tr("LoomLoom Poll Retry Warning").format(
            attempt=failure_count,
            max_attempts=LOOMLOOM_MAX_POLL_FAILURES,
        )
    )


@st.fragment(run_every="2s")
def _render_loomloom_run_progress():
    run_id = str(st.session_state.get("loomloom_run_id", "") or "").strip()
    if not run_id or st.session_state.get("loomloom_poll_paused", False):
        return
    retry_after = float(st.session_state.get("loomloom_poll_retry_after", 0.0) or 0.0)
    retry_wait_seconds = max(0, int(math.ceil(retry_after - time.monotonic())))
    if retry_wait_seconds > 0:
        st.info(
            tr("LoomLoom Poll Retry Pending").format(
                seconds=retry_wait_seconds,
            )
        )
        return
    try:
        backend = _create_loomloom_script_backend()
        run = backend.get_run(run_id)
    except loomloom.LoomLoomError as exc:
        _handle_loomloom_poll_error(run_id, exc)
        return

    st.session_state["loomloom_run_status"] = run.status
    if run.status == "completed":
        try:
            result = backend.get_script_results(run_id)
        except loomloom.LoomLoomError as exc:
            _handle_loomloom_poll_error(run_id, exc)
            return
        st.session_state["loomloom_poll_failure_count"] = 0
        st.session_state["loomloom_poll_retry_after"] = 0.0
        st.session_state["loomloom_poll_paused"] = False
        st.session_state["loomloom_script_candidates"] = result.candidates
        st.session_state["loomloom_candidate_errors"] = result.errors
        st.session_state["loomloom_selected_candidate"] = 0
        st.session_state["loomloom_run_id"] = ""
        st.rerun(scope="app")
        return
    if run.status in {"failed", "cancelled", "canceled"}:
        st.session_state["loomloom_run_error"] = run.first_error_message or run.status
        st.session_state["loomloom_run_id"] = ""
        st.session_state["loomloom_poll_paused"] = False
        st.rerun(scope="app")
        return

    st.session_state["loomloom_poll_failure_count"] = 0
    st.session_state["loomloom_poll_retry_after"] = 0.0
    st.info(
        tr("LoomLoom Run Progress").format(
            completed=run.completed_tasks,
            total=run.total_tasks,
        )
    )


def _render_loomloom_script_generation(params):
    st.caption(tr("LoomLoom Batch Script Generation Help"))
    effective_token = _effective_loomloom_api_token()
    if not effective_token:
        st.warning(tr("Shengsuan Cloud API Key Required"))

    candidate_col, duration_col = st.columns(2)
    candidate_count = candidate_col.number_input(
        tr("Script Candidate Count"),
        min_value=1,
        max_value=loomloom.MAX_SCRIPT_CANDIDATES,
        step=1,
        key="loomloom_candidate_count",
    )
    duration_seconds = duration_col.number_input(
        tr("Target Script Duration Seconds"),
        min_value=10,
        max_value=600,
        step=10,
        key="loomloom_script_duration_seconds",
    )
    _set_runtime_config("ui", "loomloom_candidate_count", int(candidate_count))
    _set_runtime_config(
        "ui", "loomloom_script_duration_seconds", int(duration_seconds)
    )
    input_signature = _loomloom_script_signature(
        subject=params.video_subject,
        language=params.video_language,
        candidate_count=candidate_count,
        duration_seconds=duration_seconds,
        style=params.video_script_prompt,
        credential_fingerprint=(
            hashlib.sha256(effective_token.encode("utf-8")).hexdigest()
            if effective_token
            else ""
        ),
    )

    if st.button(
        tr("Get LoomLoom Quote"),
        key="loomloom_quote_scripts",
        use_container_width=True,
        type="secondary",
        icon=":material/request_quote:",
        disabled=not effective_token or bool(st.session_state.get("loomloom_run_id")),
    ):
        if not params.video_subject:
            st.toast(tr("Please Enter the Video Subject First"))
            st.warning(tr("Please Enter the Video Subject First"))
        else:
            try:
                backend = _create_loomloom_script_backend()
                batch = backend.prepare_script_batch(
                    subject=params.video_subject,
                    candidate_count=int(candidate_count),
                    language=params.video_language,
                    duration_seconds=int(duration_seconds),
                    style=params.video_script_prompt,
                )
                quote_result = backend.quote(batch)
            except (loomloom.LoomLoomError, ValueError) as exc:
                logger.warning(f"failed to quote LoomLoom scripts: error={exc}")
                st.error(str(exc))
            else:
                st.session_state["loomloom_script_batch"] = batch
                st.session_state["loomloom_script_quote"] = quote_result
                st.session_state["loomloom_script_input_signature"] = input_signature
                st.session_state["loomloom_client_request_id"] = f"changofilm-{uuid4()}"
                st.session_state["loomloom_run_id"] = ""
                st.session_state["loomloom_run_status"] = "quoted"
                st.session_state["loomloom_run_error"] = ""
                st.session_state["loomloom_poll_failure_count"] = 0
                st.session_state["loomloom_poll_retry_after"] = 0.0
                st.session_state["loomloom_poll_paused"] = False
                st.session_state["loomloom_script_candidates"] = ()
                st.session_state["loomloom_candidate_errors"] = ()
                st.session_state["loomloom_confirm_charge"] = False
                logger.info(
                    "LoomLoom script quote ready: "
                    f"tasks={quote_result.task_count}, currency={quote_result.currency}, "
                    f"estimated_payable_t={quote_result.estimated_buyer_payable_t}"
                )

    quote_result = st.session_state.get("loomloom_script_quote")
    batch = st.session_state.get("loomloom_script_batch")
    if quote_result is not None and batch is not None:
        display_amount = (
            quote_result.estimated_buyer_payable_amount
            or f"{quote_result.estimated_buyer_payable_t} T"
        )
        st.success(
            tr(
                "LoomLoom Quote Summary Singular"
                if quote_result.task_count == 1
                else "LoomLoom Quote Summary"
            ).format(
                tasks=quote_result.task_count,
                amount=display_amount,
                currency=quote_result.currency,
            )
        )
        quote_is_current = (
            st.session_state.get("loomloom_script_input_signature") == input_signature
        )
        if not quote_is_current:
            st.warning(tr("LoomLoom Quote Changed Warning"))
        confirm_charge = st.checkbox(
            tr("Confirm LoomLoom Charge"),
            key="loomloom_confirm_charge",
            disabled=not quote_is_current,
        )
        run_in_progress = bool(st.session_state.get("loomloom_run_id"))
        if st.button(
            tr("Run LoomLoom Batch"),
            key="loomloom_execute_scripts",
            use_container_width=True,
            type="primary",
            disabled=(not quote_is_current or not confirm_charge or run_in_progress),
        ):
            try:
                execution = _create_loomloom_script_backend().execute(
                    batch,
                    client_request_id=st.session_state["loomloom_client_request_id"],
                    listing_version_id=quote_result.listing_version_id,
                    confirm=True,
                )
            except (loomloom.LoomLoomError, ValueError) as exc:
                logger.warning(f"failed to execute LoomLoom scripts: error={exc}")
                st.error(str(exc))
            else:
                st.session_state["loomloom_run_id"] = execution.run_id
                st.session_state["loomloom_run_status"] = "running"
                st.session_state["loomloom_poll_paused"] = False
                # 一次报价只允许启动一次付费批次。后台状态只依赖 run_id，提交
                # 后即可丢弃报价与幂等请求 ID；失败后用户需要重新报价再重试。
                st.session_state["loomloom_script_batch"] = None
                st.session_state["loomloom_script_quote"] = None
                st.session_state["loomloom_script_input_signature"] = ""
                st.session_state["loomloom_client_request_id"] = ""
                logger.info(
                    f"LoomLoom script run submitted: run_id={execution.run_id}, "
                    f"tasks={len(batch.input_rows)}"
                )
                st.toast(tr("LoomLoom Run Submitted"))

    run_error = str(st.session_state.get("loomloom_run_error", "") or "").strip()
    if run_error:
        st.error(tr("LoomLoom Run Failed").format(error=run_error))
    run_id = str(st.session_state.get("loomloom_run_id", "") or "").strip()
    if run_id and st.session_state.get("loomloom_poll_paused", False):
        retry_col, stop_col = st.columns(2)
        if retry_col.button(
            tr("Resume LoomLoom Status Check"),
            key="loomloom_resume_status_check",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state["loomloom_run_error"] = ""
            st.session_state["loomloom_poll_failure_count"] = 0
            st.session_state["loomloom_poll_retry_after"] = 0.0
            st.session_state["loomloom_poll_paused"] = False
            st.rerun(scope="app")
        if stop_col.button(
            tr("Stop Tracking LoomLoom Run"),
            key="loomloom_stop_tracking_run",
            use_container_width=True,
            type="secondary",
            help=tr("Stop Tracking LoomLoom Run Help"),
        ):
            # 这里只停止本地状态查询，不声称取消远端执行。用户确认放弃跟踪后
            # 才清理 run_id，下一次付费运行仍需重新报价和确认。
            st.session_state["loomloom_run_id"] = ""
            st.session_state["loomloom_run_error"] = ""
            st.session_state["loomloom_poll_paused"] = False
            st.rerun(scope="app")
    # 只有真实运行中的批次才启动两秒轮询，报价阶段和结果展示阶段不创建
    # 定时 fragment，避免用户停留在页面时产生无意义的网络请求和 rerun。
    if run_id and not st.session_state.get("loomloom_poll_paused", False):
        _render_loomloom_run_progress()
    _render_loomloom_candidates()


def _render_route_banner(
    route, page, intro_key, link_label_key, target_page, button_key,
    target_tab_label_key=None,
):
    """创作路线定位横幅：快速成片与专业短剧（向导/脚本方案/系列）。

    render-all 壳下每页都会渲染（隐藏页不占位）；徽章 + 一句定位 +
    跨路线跳转，让两条路线的分工与“同一时间只跑一个任务”的关系显式可见。
    键名带 page 后缀：向导与方案页同属专业路线，同一次 rerun 内不得重键。
    """
    badge_label = tr("Route Quick Badge") if route == "quick" else tr("Route Pro Badge")
    badge_icon = ":material/bolt:" if route == "quick" else ":material/movie:"
    with st.container(key=f"route_banner_{route}_{page}"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            with st.container(key=f"route_badge_{route}_{page}"):
                st.markdown(f"{badge_icon} **{badge_label}**")
            st.button(
                tr(link_label_key),
                key=button_key,
                type="tertiary",
                icon=":material/arrow_forward:",
                width="content",
                on_click=_navigate_to_route,
                args=(target_page, target_tab_label_key),
            )
        st.caption(tr(intro_key))


def _render_script_settings(panel, params):
    """渲染文案设置并更新生成参数。"""
    with panel:
        with st.container(border=True):
            st.write(tr("Video Script Settings"))
            # 标签行需要容纳“配置大模型”入口，因此无法继续使用 text_area
            # 内置标签。把标签和输入框收进同一个字段容器后，可覆盖内部间距，
            # 同时让该字段与页面上的其它表单控件保持一致的外部节奏。
            with st.container(key="video_subject_field"):
                with st.container(
                    key="video_subject_label_row",
                    horizontal=True,
                    vertical_alignment="center",
                    gap="small",
                ):
                    st.markdown(
                        tr("Video Subject"),
                        help=tr("Video Subject Help"),
                        width="content",
                    )
                    st.button(
                        tr("Configure LLM"),
                        key="open_llm_settings_from_subject",
                        type="tertiary",
                        on_click=_open_settings_dialog,
                        args=("llm",),
                    )
                params.video_subject = st.text_area(
                    tr("Video Subject"),
                    placeholder=tr("Video Subject Placeholder"),
                    height=96,
                    key="video_subject",
                    label_visibility="collapsed",
                ).strip()

            video_languages = [
                (tr("Auto Detect"), ""),
            ]
            for code in support_locales:
                video_languages.append((code, code))

            selected_language_code = stable_selectbox(
                tr("Script Language"),
                options=[value for _, value in video_languages],
                default_value=_saved_ui_choice(
                    "video_language",
                    [value for _, value in video_languages],
                    "",
                ),
                key="script_language_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_languages
                )[value],
            )
            params.video_language = selected_language_code
            _set_runtime_config("ui", "video_language", params.video_language)

            # 使用带 key 的局部容器限定折叠入口样式，保持 expander 的原生交互，
            # 同时避免样式误伤页面顶部的“基础设置”等其他折叠区域。
            with st.container(key="advanced_settings_script"):
                with st.expander(tr("Advanced Script Settings"), expanded=False):
                    script_backend_options = ["local", "loomloom"]
                    script_backend_labels = {
                        "local": tr("Local LLM Script Generation"),
                        "loomloom": tr("Shengsuan Cloud Batch Script Generation"),
                    }
                    script_backend_widget_key = localized_widget_key(
                        "script_generation_backend_select"
                    )
                    current_script_backend = st.session_state.get(
                        script_backend_widget_key,
                        _effective_script_generation_backend(),
                    )
                    script_generation_backend = stable_selectbox(
                        tr("Script Generation Method"),
                        options=script_backend_options,
                        default_value=_effective_script_generation_backend(),
                        key="script_generation_backend_select",
                        format_func=lambda value: script_backend_labels[value],
                        help=_script_generation_method_help(current_script_backend),
                    )
                    _set_runtime_config(
                        "app", "script_generation_backend", script_generation_backend
                    )

                    params.paragraph_number = st.slider(
                        tr("Script Paragraph Number"),
                        min_value=llm.MIN_SCRIPT_PARAGRAPH_NUMBER,
                        max_value=llm.MAX_SCRIPT_PARAGRAPH_NUMBER,
                        key="paragraph_number_input",
                    )
                    _set_runtime_config(
                        "ui", "paragraph_number", params.paragraph_number
                    )
                    params.video_script_prompt = st.text_area(
                        tr("Custom Script Requirements"),
                        height=100,
                        max_chars=llm.MAX_SCRIPT_PROMPT_LENGTH,
                        placeholder=tr("Custom Script Requirements Placeholder"),
                        key="video_script_prompt",
                    ).strip()
                    _set_runtime_config(
                        "ui", "video_script_prompt", params.video_script_prompt
                    )

                    system_prompt = st.text_area(
                        tr("Custom System Prompt"),
                        height=240,
                        max_chars=llm.MAX_SCRIPT_SYSTEM_PROMPT_LENGTH,
                        key="custom_system_prompt",
                    ).strip()
                    # 默认内容由服务层统一维护。界面虽然直接展示默认提示词，但只有
                    # 用户实际修改后才随任务传递，避免历史任务固化旧版本默认规则。
                    params.custom_system_prompt = (
                        ""
                        if system_prompt == llm.DEFAULT_SCRIPT_SYSTEM_PROMPT.strip()
                        else system_prompt
                    )
                    _set_runtime_config(
                        "ui", "custom_system_prompt", params.custom_system_prompt
                    )

                    restore_prompt_col, preview_prompt_col = st.columns(2)
                    if restore_prompt_col.button(
                        tr("Restore Default System Prompt"),
                        key="restore_default_system_prompt",
                        icon=":material/restart_alt:",
                        on_click=reset_script_system_prompt,
                        use_container_width=True,
                    ):
                        st.toast(tr("Default System Prompt Restored"))
                    if preview_prompt_col.button(
                        tr("Preview Final Prompt"),
                        key="preview_final_script_prompt",
                        icon=":material/preview:",
                        use_container_width=True,
                    ):
                        render_script_prompt_preview(
                            llm.build_script_prompt(
                                video_subject=params.video_subject,
                                language=params.video_language,
                                paragraph_number=params.paragraph_number,
                                video_script_prompt=params.video_script_prompt,
                                custom_system_prompt=params.custom_system_prompt,
                            )
                        )

            # 模型发现只增强视频素材，不改变用户明确选择的文案 Provider。
            if _effective_script_generation_backend() == "loomloom":
                _render_loomloom_script_generation(params)
            else:
                _render_local_script_generation(params)
            params.video_script = st.text_area(
                tr("Video Script"),
                help=tr("Video Script Help"),
                height=180,
                key="video_script",
            )
            if _effective_script_generation_backend() == "loomloom":
                st.caption(tr("LoomLoom Video Terms Reuse Help"))
            elif st.button(
                tr("Generate Video Keywords"),
                key="auto_generate_terms",
                use_container_width=True,
                type="secondary",
                icon=":material/auto_awesome:",
            ):
                if not params.video_script:
                    # 视频关键词需要基于文案提取，文案为空时提前提示并跳过模型调用。
                    st.toast(tr("Please Enter the Video Subject"))
                    st.warning(tr("Please Enter the Video Subject"))
                else:
                    with st.spinner(tr("Generating Video Keywords")):
                        terms = _run_llm_read_operation(
                            "generate_terms",
                            lambda app_config_snapshot: llm.generate_terms(
                                params.video_subject,
                                params.video_script,
                                amount=8 if params.match_materials_to_script else 5,
                                match_script_order=params.match_materials_to_script,
                                app_config=app_config_snapshot,
                            ),
                        )
                        if not terms:
                            st.error(tr("Video Keywords Generation Failed"))
                        else:
                            st.session_state["video_terms"] = ", ".join(terms)

            params.video_terms = st.text_area(
                tr("Video Keywords"),
                help=tr("Video Keywords Help"),
                key="video_terms",
            )


def _render_image_settings(panel, params):
    """图片设置 TAB：图像动效（项目级参数）+ 库存图片源 + 本地关键帧引擎。

    与视频/音频/字幕面板同为 render-all：每次 rerun 都组装 params，
    保证项目快照/恢复覆盖图像动效。动效仅对本地素材、AI 图像与库存图片源
    生效，其余素材来源下不挂载控件（与旧视频面板口径一致）。API 凭证已
    集中到服务商配置页，这里只保留生成参数与 OpenAI 图像高级参数。
    """
    with panel:
        # 图片 TAB 先于视频 TAB 渲染，params.video_source 尚未组装；
        # 直接读视频来源控件的会话值，回退到含待保存修改的配置快照。
        effective_source = st.session_state.get(
            localized_widget_key("video_source_select")
        ) or str(
            config.snapshot_config_with_pending(config.app).get("video_source", "")
            or ""
        )
        with st.container(border=True):
            st.markdown(f"**{tr('Image Motion Section')}**")
            st.caption(tr("Image Motion Section Help"))
            if (
                effective_source in {"local", "openai_image", "codex_image"}
                or effective_source in material.STOCK_IMAGE_SOURCES
            ):
                image_motion_labels = {
                    ImageMotion.static.value: tr("Static Image"),
                    ImageMotion.zoom.value: tr("Slow Zoom"),
                }
                params.image_motion = ImageMotion(
                    stable_selectbox(
                        tr("Image Motion"),
                        options=list(image_motion_labels),
                        default_value=_saved_ui_choice(
                            "image_motion", list(image_motion_labels), ImageMotion.zoom.value,
                            # 生成任务持锁时，切换语言或素材来源会重建控件；
                            # 此时必须恢复尚未落盘的最新选择，不能写回旧配置值。
                            section=config.snapshot_config_with_pending(config.ui),
                        ),
                        key="image_motion_select",
                        format_func=image_motion_labels.get,
                        help=tr("Image Motion Help"),
                    )
                )
                _set_runtime_config("ui", "image_motion", params.image_motion.value)

        with st.container(border=True):
            st.markdown(f"**{tr('Stock Image Sources Section')}**")
            st.caption(tr("Stock Image Sources Section Help"))
            stock_labels = {
                source: tr("Pexels Images") if base == "pexels" else tr("Pixabay Images")
                for source, base in material.STOCK_IMAGE_SOURCES.items()
            }
            stock_key = localized_widget_key("stock_image_source_select")
            if effective_source in stock_labels:
                # 下拉与实际生效来源保持一致，避免旧会话值误导展示。
                st.session_state[stock_key] = effective_source
            selected_stock = stable_selectbox(
                tr("Stock Image Source"),
                options=list(stock_labels),
                default_value=(
                    effective_source
                    if effective_source in stock_labels
                    else "pexels_image"
                ),
                key="stock_image_source_select",
                format_func=stock_labels.get,
                help=tr("Stock Image Source Help"),
                on_change=_activate_stock_image_source,
                args=(stock_key,),
            )
            st.caption(tr("Stock Image Keys Shared Hint"))
            st.caption(tr("Stock Image Keys Elsewhere Hint"))

        # AI 图像与库存图片服务的 Key 已集中在服务商配置页，创作面板只
        # 保留生成参数；OpenAI 图像高级参数仍属于本项目级参数，留在本页。
        st.caption(tr("Image Provider Elsewhere Hint"))
        st.button(
            tr("Open Provider Settings"),
            key="image_settings_open_providers",
            icon=":material/hub:",
            on_click=_open_provider_settings_for_group,
            args=("ai_image",),
        )

        if effective_source == "openai_image":
            with st.container(border=True):
                st.markdown(f"**{tr('OpenAI Image Advanced Settings')}**")
                openai_image_size = st.text_input(
                    tr("OpenAI Image Size"),
                    value=str(
                        config.snapshot_config_with_pending(config.app).get(
                            "openai_image_size", ""
                        )
                        or ""
                    ),
                    placeholder="1024x1536",
                    help=tr("OpenAI Image Size Help"),
                    key="openai_image_size_input",
                    on_change=_save_settings_change,
                    args=(
                        "app",
                        "openai_image_size",
                        "openai_image_size_input",
                        lambda value: value.strip(),
                    ),
                )
                _set_runtime_config(
                    "app", "openai_image_size", openai_image_size.strip()
                )

                openai_image_prompt_template = st.text_input(
                    tr("OpenAI Image Prompt Template"),
                    value=str(
                        config.snapshot_config_with_pending(config.app).get(
                            "openai_image_prompt_template", ""
                        )
                        or ""
                    ),
                    placeholder="cinematic photo of {term}, photorealistic",
                    help=tr("OpenAI Image Prompt Template Help"),
                    key="openai_image_prompt_template_input",
                    on_change=_save_settings_change,
                    args=(
                        "app",
                        "openai_image_prompt_template",
                        "openai_image_prompt_template_input",
                        lambda value: value.strip(),
                    ),
                )
                _set_runtime_config(
                    "app",
                    "openai_image_prompt_template",
                    openai_image_prompt_template.strip(),
                )

        with st.container(border=True):
            st.markdown(f"**{tr('Local Keyframe Engine Section')}**")
            st.caption(tr("Local Keyframe Engine Help"))
            if st.button(
                tr("Local Engine Probe"),
                key="image_local_engine_probe",
                icon=":material/network_check:",
            ):
                st.session_state["image_local_engine_online"] = (
                    comfy_local.is_online()
                )
            online = st.session_state.get("image_local_engine_online")
            if online is None:
                st.caption(tr("Local Engine Unknown"))
            elif online:
                st.caption(tr("Local Engine Online"))
            else:
                st.caption(tr("Local Engine Offline"))


def _render_video_settings(panel, params):
    """渲染视频设置并返回本次选择的本地素材。"""
    uploaded_files = []
    with panel:
        with st.container(border=True):
            st.write(tr("Video Settings"))
            video_concat_modes = [
                (tr("Sequential"), "sequential"),
                (tr("Random"), "random"),
            ]
            video_source_labels = {
                "pexels": tr("Pexels"),
                "pixabay": tr("Pixabay"),
                "coverr": tr("Coverr"),
                "pexels_image": tr("Pexels Images"),
                "pixabay_image": tr("Pixabay Images"),
                "wavespeed": tr("WaveSpeed AI Video"),
                "volcengine_seedance": tr("Volcano Engine Seedance"),
                "infistar": tr("Infistar AI Video"),
                "jalapeno": tr("Jalapeno Cloud AI Video"),
                "ofox": tr("OFox AI Video"),
                "metaso_minimax": tr("Metaso MiniMax H3"),
                "muapi": tr("MuAPI AI Video"),
                "loomloom": tr("Shengsuan Cloud AI Video"),
                "openai_image": tr("OpenAI Compatible Text-to-Image"),
                "codex_image": tr("codex.image.label"),
                "local": tr("Local file"),
            }
            saved_video_source_name = str(
                config.snapshot_config_with_pending(config.app).get("video_source", "pexels")
                or "pexels"
            )
            params.video_source = grouped_selectbox(
                tr("Video Source"),
                groups=(
                    (tr("Stock Video"), VIDEO_SOURCE_GROUPS["stock_video"]),
                    (tr("Stock Images"), VIDEO_SOURCE_GROUPS["stock_image"]),
                    (tr("AI Video"), VIDEO_SOURCE_GROUPS["ai_video"]),
                    (tr("AI Image"), VIDEO_SOURCE_GROUPS["ai_image"]),
                    (tr("Local Material"), VIDEO_SOURCE_GROUPS["local"]),
                ),
                default_value=saved_video_source_name,
                key="video_source_select",
                format_func=video_source_labels.get,
                settings_label=tr("Configure Material Sources"),
                on_settings=_open_material_settings_dialog,
            )
            _set_runtime_config("app", "video_source", params.video_source)

            loomloom_video_capability = None
            if params.video_source == "loomloom":
                # 尽早读取缓存，使下方画面比例控件直接受当前 Profile 约束。
                # 首次输入 Key 后 Streamlit 会 rerun，此处随即加载一次。
                loomloom_video_capability = _load_loomloom_video_capability(
                    _effective_loomloom_api_token()
                )

            if params.video_source == "infistar":
                st.caption(tr("Infistar AI Video Help"))
                selected_infistar_model = _render_infistar_model_selector()
            if params.video_source == "jalapeno":
                st.caption(tr("Jalapeno Cloud Video Help"))
                snapshot = config.snapshot_config_with_pending(config.app)
                st.caption(tr("Jalapeno Cloud Video Specification").format(
                    model=str(snapshot.get("jalapeno_video_model", "") or jalapeno_video.DEFAULT_MODEL),
                    resolution=str(snapshot.get("jalapeno_video_resolution", "") or jalapeno_video.DEFAULT_RESOLUTION),
                ))
            if params.video_source == "wavespeed":
                st.caption(tr("WaveSpeed AI Video Help"))
            if params.video_source == "volcengine_seedance":
                st.caption(tr("Volcano Engine Seedance Help"))
            if params.video_source == "ofox":
                st.caption(f"[OfoxAI]({OFOX_REFERRAL_URL}) · {tr('OFox AI Video Help')}")
            if params.video_source == "metaso_minimax":
                st.caption(tr("Metaso MiniMax H3 Help"))
            if params.video_source == "muapi":
                st.caption(tr("MuAPI AI Video Help"))
            if params.video_source == "local":
                # Streamlit 的文件类型校验对扩展名大小写敏感，这里同时放行大小写两种形式。
                local_file_types = sorted(
                    extension.removeprefix(".")
                    for extension in LOCAL_MATERIAL_EXTENSIONS
                )
                uploaded_files = st.file_uploader(
                    tr("Upload Local Files"),
                    type=local_file_types
                    + [file_type.upper() for file_type in local_file_types],
                    accept_multiple_files=True,
                    key="local_video_materials_uploader",
                )

            # 文案顺序匹配会从关键词生成到最终合成全程保持叙事顺序，因此开启时
            # 顺序拼接是唯一符合实际执行逻辑的选项。同步控件值可避免界面仍显示
            # “随机拼接”，同时保留用户原选择，关闭后自动恢复。
            sync_script_order_concat_mode()
            selected_concat_mode = stable_selectbox(
                tr("Video Concat Mode"),
                options=[value for _, value in video_concat_modes],
                default_value=_saved_ui_choice(
                    "video_concat_mode",
                    [value for _, value in video_concat_modes],
                    VideoConcatMode.random.value,
                ),
                key="video_concat_mode_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_concat_modes
                )[value],
                disabled=bool(st.session_state.get("match_materials_to_script", False)),
            )
            params.video_concat_mode = VideoConcatMode(selected_concat_mode)

            params.match_materials_to_script = st.checkbox(
                tr("Match Materials to Script Order"),
                help=tr("Match Materials to Script Order Help"),
                key="match_materials_to_script",
                on_change=sync_script_order_concat_mode,
            )
            _set_runtime_config(
                "app",
                "match_materials_to_script",
                params.match_materials_to_script,
            )
            # 顺序匹配开启时，sequential 是派生出的强制值，不应覆盖用户在关闭
            # 该功能时选择的拼接偏好；关闭后仍能恢复此前的 random/sequential。
            if not params.match_materials_to_script:
                _set_runtime_config(
                    "ui", "video_concat_mode", params.video_concat_mode.value
                )

            # 视频转场模式
            video_transition_modes = [
                (tr("None"), VideoTransitionMode.none.value),
                (tr("Shuffle"), VideoTransitionMode.shuffle.value),
                (tr("FadeIn"), VideoTransitionMode.fade_in.value),
                (tr("FadeOut"), VideoTransitionMode.fade_out.value),
                (tr("SlideIn"), VideoTransitionMode.slide_in.value),
                (tr("SlideOut"), VideoTransitionMode.slide_out.value),
                (tr("ZoomIn"), VideoTransitionMode.zoom_in.value),
                (tr("ZoomOut"), VideoTransitionMode.zoom_out.value),
            ]
            selected_transition_mode = stable_selectbox(
                tr("Video Transition Mode"),
                options=[value for _, value in video_transition_modes],
                default_value=_saved_ui_choice(
                    "video_transition_mode",
                    [value for _, value in video_transition_modes],
                    VideoTransitionMode.none.value,
                ),
                key="video_transition_mode_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_transition_modes
                )[value],
            )
            params.video_transition_mode = VideoTransitionMode(selected_transition_mode)
            _set_runtime_config(
                "ui",
                "video_transition_mode",
                params.video_transition_mode.value,
            )

            video_aspect_ratios = [
                (tr("Portrait"), VideoAspect.portrait.value),
                (tr("Landscape"), VideoAspect.landscape.value),
            ]
            if loomloom_video_capability is not None:
                ratio_labels = {value: label for label, value in video_aspect_ratios}
                video_aspect_ratios = [
                    (ratio_labels[value], value)
                    for value in loomloom_video_capability.aspect_ratios
                ]
            # Coverr 库 99% 是 16:9 横屏,默认竖屏会让画面被大量黑边包围。
            # 用 source-specific widget key 让每个 source 各自记忆 aspect 选择:
            #   - 首次切到 coverr → 默认 Landscape(index=1)
            #   - 其他 source 沿用 Portrait(index=0)
            #   - 用户在某 source 下手动改过 aspect,session_state 会记住,
            #     下次回到同一 source 时尊重用户选择,不会再被强制覆盖。
            default_aspect_index = 1 if params.video_source == "coverr" else 0
            video_aspect_values = [value for _, value in video_aspect_ratios]
            video_aspect_config_key = f"video_aspect_{params.video_source}"
            selected_aspect_ratio = stable_selectbox(
                tr("Video Ratio"),
                options=video_aspect_values,
                default_value=_saved_ui_choice(
                    video_aspect_config_key,
                    video_aspect_values,
                    video_aspect_ratios[default_aspect_index][1],
                ),
                key=f"video_aspect_for_{params.video_source}",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_aspect_ratios
                )[value],
            )
            params.video_aspect = VideoAspect(selected_aspect_ratio)
            _set_runtime_config(
                "ui", video_aspect_config_key, params.video_aspect.value
            )

            video_fit_modes = [
                (tr("Fill and Crop"), VideoFitMode.cover.value),
                (tr("Fit with Black Bars"), VideoFitMode.contain.value),
            ]
            selected_fit_mode = stable_selectbox(
                tr("Video Fit Mode"),
                options=[value for _, value in video_fit_modes],
                default_value=_saved_ui_choice(
                    "video_fit_mode",
                    [value for _, value in video_fit_modes],
                    VideoFitMode.cover.value,
                ),
                key="video_fit_mode_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_fit_modes
                )[value],
                help=tr("Video Fit Mode Help"),
            )
            params.video_fit_mode = VideoFitMode(selected_fit_mode)
            _set_runtime_config(
                "ui", "video_fit_mode", params.video_fit_mode.value
            )

            # MiniMax H3 的远端时长范围是 4～15 秒。选择秘塔时使用完整能力
            # 范围，既避免 2/3 秒被按 4 秒计费，也让 WebUI 与 CLI、服务层一致。
            if params.video_source == "infistar":
                # 每种模型先提供实测的固定规格；不把被 API 拒绝的时长发往付费接口。
                video_clip_durations = [infistar_video.MODELS.get(selected_infistar_model, {"seconds": 5})["seconds"]]
            elif params.video_source == "metaso_minimax":
                video_clip_durations = list(
                    range(
                        metaso_minimax.DEFAULT_MIN_DURATION_SECONDS,
                        metaso_minimax.DEFAULT_MAX_DURATION_SECONDS + 1,
                    )
                )
            elif params.video_source == "muapi":
                video_clip_durations = list(
                    range(
                        muapi.DEFAULT_MIN_DURATION_SECONDS,
                        muapi.DEFAULT_MAX_DURATION_SECONDS + 1,
                    )
                )
            else:
                video_clip_durations = [2, 3, 4, 5, 6, 7, 8, 9, 10]
            params.video_clip_duration = stable_selectbox(
                tr("Clip Duration"),
                options=video_clip_durations,
                default_value=_saved_ui_choice(
                    "video_clip_duration",
                    video_clip_durations,
                    5
                    if params.video_source in {"metaso_minimax", "muapi"}
                    else 3,
                ),
                key="video_clip_duration_select",
                help=tr("Clip Duration Help"),
            )
            _set_runtime_config(
                "ui", "video_clip_duration", params.video_clip_duration
            )
            clip_speed_key = localized_widget_key("video_clip_speed_slider")
            # session_state 可能来自旧任务、API 参数或旧版页面状态。控件创建前
            # 统一归一化，既保留合法选择，也确保 slider 始终收到 0.5～2.0
            # 范围内的有限浮点数。
            st.session_state[clip_speed_key] = utils.normalize_clip_speed(
                st.session_state.get(
                    clip_speed_key,
                    _saved_ui_number("video_clip_speed", 1.0, 0.5, 2.0),
                )
            )
            params.video_clip_speed = st.slider(
                tr("Clip Speed"),
                min_value=0.5,
                max_value=2.0,
                step=0.05,
                format="%.2fx",
                key=clip_speed_key,
                help=tr("Clip Speed Help"),
            )
            _set_runtime_config("ui", "video_clip_speed", params.video_clip_speed)
            video_count_options = [1, 2, 3, 4, 5]
            params.video_count = stable_selectbox(
                tr("Number of Videos Generated Simultaneously"),
                options=video_count_options,
                default_value=_saved_ui_choice(
                    "video_count", video_count_options, 1
                ),
                key="video_count_select",
            )
            _set_runtime_config("ui", "video_count", params.video_count)

            # 可复现编排的可选种子：留空保持历史随机行为，填整数后同一批素材
            # 重放同一份剪辑决策。用文本框而非 number_input：0 本身是合法种子，
            # “未指定”必须能用空串表达，数值控件做不到。
            st.session_state.setdefault(
                "video_seed_input", str(config.ui.get("video_seed", "") or "")
            )
            seed_raw = st.text_input(
                tr("Video Seed"),
                key="video_seed_input",
                help=tr("Video Seed Help"),
                placeholder="0-4294967295",
            )
            _set_runtime_config("ui", "video_seed", seed_raw)
            seed_text = str(seed_raw or "").strip()
            if not seed_text:
                params.video_seed = None
            else:
                try:
                    seed_value = int(seed_text, 10)
                    if not 0 <= seed_value <= 0xFFFFFFFF:
                        raise ValueError(seed_text)
                    params.video_seed = seed_value
                except ValueError:
                    params.video_seed = None
                    st.error(tr("Video Seed Invalid"))

            video_codec_options = [
                (tr("Default Video Encoder"), DEFAULT_VIDEO_CODEC_OPTION),
                ("libx264 (CPU)", "libx264"),
                ("NVIDIA NVENC (h264_nvenc)", "h264_nvenc"),
                ("AMD AMF (h264_amf)", "h264_amf"),
                ("Intel QSV (h264_qsv)", "h264_qsv"),
                ("Windows MediaFoundation (h264_mf)", "h264_mf"),
                ("macOS VideoToolbox (h264_videotoolbox)", "h264_videotoolbox"),
            ]
            saved_video_codec = config.app.get(
                "video_codec", DEFAULT_VIDEO_CODEC_OPTION
            )
            saved_video_codec_values = [item[1] for item in video_codec_options]
            if saved_video_codec not in saved_video_codec_values:
                # 旧版本或手工配置可能留下无效值。UI 回到“默认”而不是替用户
                # 固定某个编码器，后端仍会按稳定策略解析为 libx264。
                saved_video_codec = DEFAULT_VIDEO_CODEC_OPTION
            selected_video_codec = stable_selectbox(
                tr("Video Encoder"),
                options=saved_video_codec_values,
                default_value=saved_video_codec,
                key="video_encoder_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in video_codec_options
                )[value],
                help=tr("Video Encoder Help"),
            )
            if selected_video_codec == DEFAULT_VIDEO_CODEC_OPTION:
                # 默认模式不持久化具体编码器，让配置表达“跟随项目默认值”。
                _delete_runtime_config("app", "video_codec")
            else:
                _set_runtime_config("app", "video_codec", selected_video_codec)

            concurrency_options = [1, 2, 4, 6, 8]
            if params.video_source in {"pexels", "pixabay", "coverr"}:
                selected_material_concurrency = stable_selectbox(
                    tr("Material Concurrency"),
                    options=concurrency_options,
                    default_value=_saved_ui_choice(
                        "material_concurrency", concurrency_options, 1, config.app
                    ),
                    key="material_concurrency_select",
                    help=tr("Material Concurrency Help"),
                )
                _set_runtime_config(
                    "app", "material_concurrency", selected_material_concurrency
                )

            selected_clip_concurrency = stable_selectbox(
                tr("Clip Rendering Concurrency"),
                options=concurrency_options,
                default_value=_saved_ui_choice(
                    "video_clip_concurrency", concurrency_options, 1, config.app
                ),
                key="clip_rendering_concurrency_select",
                help=tr("Clip Rendering Concurrency Help"),
            )
            _set_runtime_config(
                "app", "video_clip_concurrency", selected_clip_concurrency
            )

            if params.video_source == "loomloom":
                _render_loomloom_video_settings(params)

            if params.video_source == "wavespeed":
                _render_wavespeed_video_settings(params)
            if params.video_source == "volcengine_seedance":
                _render_seedance_video_settings(params)
            if params.video_source == "infistar":
                st.warning(tr("Infistar Video Billing Notice"))
                st.checkbox(tr("Confirm Infistar Charge"), key="infistar_confirm_charge")
            if params.video_source == "jalapeno":
                _sync_jalapeno_charge_confirmation(params)
                st.warning(tr("Jalapeno Cloud Video Billing Notice"))
                st.checkbox(tr("Confirm Jalapeno Cloud Charge"), key="jalapeno_confirm_charge")
            if params.video_source == "ofox":
                _render_ofox_video_settings(params)
            if params.video_source == "metaso_minimax":
                _render_metaso_minimax_video_settings(params)
            if params.video_source == "muapi":
                _render_muapi_video_settings(params)
    return uploaded_files


def _render_wavespeed_video_settings(params):
    """
    渲染 WaveSpeed 生成数量估算与计费确认。

    生成按条计费，提交前必须让用户看到大致会生成多少段。估算完全在本地
    完成：用配音时长估算区间除以片段时长得到需要覆盖的片段数。素材流程
    本身按需逐段生成、凑够所需时长即停，因此实际生成数以运行时为准，
    估算只用于量级提示，不参与任务执行。
    """
    clip_duration = max(int(params.video_clip_duration or 1), 1)
    video_count = max(int(params.video_count or 1), 1)
    estimated_range = _estimate_voiceover_duration_range(
        str(params.video_script or ""),
        params.voice_rate,
    )
    if estimated_range:
        min_clips = max(math.ceil(estimated_range[0] * video_count / clip_duration), 1)
        max_clips = max(
            math.ceil(estimated_range[1] * video_count / clip_duration), min_clips
        )
        st.warning(
            tr("WaveSpeed Billing Notice").format(min=min_clips, max=max_clips)
        )
    else:
        st.warning(tr("WaveSpeed Billing Notice Without Script"))
    st.checkbox(
        tr("Confirm WaveSpeed Charge"),
        key="wavespeed_confirm_charge",
        help=tr("Confirm WaveSpeed Charge Help"),
    )


def _render_seedance_video_settings(params):
    """展示预计付费任务数量，并要求用户明确确认方舟生成费用。"""
    clip_duration = max(int(params.video_clip_duration or 1), 1)
    video_count = max(int(params.video_count or 1), 1)
    estimated_range = _estimate_voiceover_duration_range(
        str(params.video_script or ""), params.voice_rate
    )
    if estimated_range:
        min_clips = max(math.ceil(estimated_range[0] * video_count / clip_duration), 1)
        max_clips = max(
            math.ceil(estimated_range[1] * video_count / clip_duration), min_clips
        )
        st.warning(
            tr("Volcano Engine Seedance Billing Notice").format(
                min=min_clips, max=max_clips
            )
        )
    else:
        st.warning(tr("Volcano Engine Seedance Billing Notice Without Script"))
    st.checkbox(
        tr("Confirm Volcano Engine Seedance Charge"),
        key="volcengine_seedance_confirm_charge",
        help=tr("Confirm Volcano Engine Seedance Charge Help"),
    )


def _render_jalapeno_provider_settings():
    """默认值直接填入；独立视频配置不依赖当前选择的大模型 Provider。"""
    snapshot = config.snapshot_config_with_pending(config.app)
    st.markdown(f"**{tr('Jalapeno Cloud AI Video')}**")
    key = st.text_input(
        tr("Jalapeno Cloud Video API Key"),
        value=str(snapshot.get("jalapeno_video_api_key", "") or ""),
        type="password",
        key="jalapeno_video_api_key_input",
        help=tr("Jalapeno Cloud Video Key Help"),
        on_change=_save_settings_change,
        args=(
            "app",
            "jalapeno_video_api_key",
            "jalapeno_video_api_key_input",
            lambda value: value.strip(),
        ),
    ).strip()
    _set_runtime_config("app", "jalapeno_video_api_key", key)
    if (
        not key
        and not os.getenv("JALAPENO_VIDEO_API_KEY", "").strip()
        and str(snapshot.get("jalapeno_api_key", "") or "").strip()
    ):
        st.caption(tr("Jalapeno Cloud Video Key Reused"))
    model = st.text_input(
        tr("Jalapeno Cloud Video Model"),
        value=str(
            snapshot.get("jalapeno_video_model", "") or jalapeno_video.DEFAULT_MODEL
        ),
        key="jalapeno_video_model_input",
        on_change=_save_settings_change,
        args=(
            "app",
            "jalapeno_video_model",
            "jalapeno_video_model_input",
            lambda value: value.strip(),
        ),
    ).strip()
    _set_runtime_config("app", "jalapeno_video_model", model)
    base = st.text_input(
        tr("Jalapeno Cloud Video Base URL"),
        value=str(
            snapshot.get("jalapeno_video_base_url", "")
            or jalapeno_video.DEFAULT_TASKS_URL
        ),
        help=tr("Jalapeno Cloud Video Base URL Help"),
        key="jalapeno_video_base_url_input",
        on_change=_save_settings_change,
        args=(
            "app",
            "jalapeno_video_base_url",
            "jalapeno_video_base_url_input",
            lambda value: value.strip(),
        ),
    ).strip()
    _set_runtime_config("app", "jalapeno_video_base_url", base)
    resolution = stable_selectbox(
        tr("Jalapeno Cloud Video Resolution"),
        options=sorted(
            volcengine_seedance.SUPPORTED_RESOLUTIONS, key=lambda value: int(value[:-1])
        ),
        default_value=str(
            snapshot.get("jalapeno_video_resolution", "")
            or jalapeno_video.DEFAULT_RESOLUTION
        ),
        key="jalapeno_video_resolution_select",
        on_change=_save_settings_change,
        args=(
            "app",
            "jalapeno_video_resolution",
            localized_widget_key("jalapeno_video_resolution_select"),
            lambda value: value,
        ),
    )
    _set_runtime_config("app", "jalapeno_video_resolution", resolution)


def _sync_jalapeno_charge_confirmation(params):
    """接入地址、模型、规格或有效 Key 变化后重新确认，避免沿用过期授权。"""
    snapshot = config.snapshot_config_with_pending(config.app)
    signature = _jalapeno_charge_signature(params, snapshot)
    if st.session_state.get("jalapeno_charge_signature") != signature:
        st.session_state["jalapeno_confirm_charge"] = False
        st.session_state["jalapeno_charge_signature"] = signature


def _jalapeno_charge_signature(params, snapshot):
    """使用同一快照检查费用确认，避免渲染与点击提交之间读取不同配置。"""
    return hashlib.sha256(json.dumps([
        jalapeno_video.get_api_key(snapshot),
        snapshot.get("jalapeno_video_base_url", ""),
        snapshot.get("jalapeno_video_model", ""),
        snapshot.get("jalapeno_video_resolution", ""),
        str(params.video_aspect), params.video_clip_duration, params.video_count,
    ]).encode()).hexdigest()


def _render_infistar_model_selector():
    """模型顺序固定为 Seedance、MiniMax、可灵；切换模型后重新确认费用。"""
    snapshot = config.snapshot_config_with_pending(config.app)
    configured = str(snapshot.get("infistar_video_model", "") or infistar_video.DEFAULT_MODEL)
    options = list(infistar_video.MODELS)
    if configured not in options:
        options.append(configured)
        st.error(tr("Infistar Video Invalid Model"))
    model = stable_selectbox(
        tr("Infistar Video Model"), options=options,
        default_value=configured, key="infistar_video_model_select",
        format_func=lambda value: infistar_video.MODELS.get(value, {"label": value})["label"],
    )
    if st.session_state.get("infistar_previous_video_model") != model:
        st.session_state["infistar_confirm_charge"] = False
        st.session_state["infistar_previous_video_model"] = model
    _set_runtime_config("app", "infistar_video_model", model)
    profile = infistar_video.MODELS.get(model)
    if profile:
        st.caption(tr("Infistar Video Specification").format(seconds=profile["seconds"], size=profile["size"]))
        if model == "MiniMax-H3":
            st.info(tr("Infistar MiniMax Landscape Help"))
    return model


def _render_ofox_video_settings(params):
    """展示预计付费任务数量，并要求用户明确确认 OFox 生成费用。"""
    clip_duration = max(int(params.video_clip_duration or 1), 1)
    video_count = max(int(params.video_count or 1), 1)
    estimated_range = _estimate_voiceover_duration_range(
        str(params.video_script or ""), params.voice_rate
    )
    if estimated_range:
        min_clips = max(math.ceil(estimated_range[0] * video_count / clip_duration), 1)
        max_clips = max(
            math.ceil(estimated_range[1] * video_count / clip_duration), min_clips
        )
        st.warning(
            tr("OFox Billing Notice").format(min=min_clips, max=max_clips)
        )
    else:
        st.warning(tr("OFox Billing Notice Without Script"))
    st.checkbox(
        tr("Confirm OFox Charge"),
        key="ofox_confirm_charge",
        help=tr("Confirm OFox Charge Help"),
    )


def _render_metaso_minimax_video_settings(params):
    """展示预计付费任务数量，并要求用户确认秘塔 MiniMax 生成费用。"""
    clip_duration = max(int(params.video_clip_duration or 1), 1)
    video_count = max(int(params.video_count or 1), 1)
    voice_mode = st.session_state.get(
        localized_widget_key("voice_mode_control"),
        config.ui.get("voice_mode"),
    )
    if voice_mode == VOICE_MODE_UPLOAD:
        # 视频设置渲染在音频设置之前，此时无法可靠读取本轮新上传文件的实际
        # 时长。上传模式不再展示按脚本文字推算的数字，避免用户误以为一个
        # 5 秒音频也会按较长文案创建多个付费任务；运行时仍以文件真实时长为准。
        st.warning(
            tr("Metaso MiniMax Billing Notice Uploaded Audio").format(
                resolution=str(
                    config.app.get(
                        "metaso_minimax_resolution",
                        metaso_minimax.DEFAULT_RESOLUTION,
                    )
                    or metaso_minimax.DEFAULT_RESOLUTION
                ),
                duration=clip_duration,
                count=video_count,
            )
        )
    elif estimated_range := _estimate_voiceover_duration_range(
        str(params.video_script or ""), params.voice_rate
    ):
        min_clips = max(math.ceil(estimated_range[0] * video_count / clip_duration), 1)
        max_clips = max(
            math.ceil(estimated_range[1] * video_count / clip_duration), min_clips
        )
        st.warning(
            tr("Metaso MiniMax Billing Notice").format(
                min=min_clips,
                max=max_clips,
                resolution=str(
                    config.app.get(
                        "metaso_minimax_resolution",
                        metaso_minimax.DEFAULT_RESOLUTION,
                    )
                    or metaso_minimax.DEFAULT_RESOLUTION
                ),
            )
        )
    else:
        st.warning(tr("Metaso MiniMax Billing Notice Without Script"))
    st.checkbox(
        tr("Confirm Metaso MiniMax Charge"),
        key="metaso_minimax_confirm_charge",
        help=tr("Confirm Metaso MiniMax Charge Help"),
    )


def _render_muapi_video_settings(params):
    """Show an estimated MuAPI task count and require explicit billing consent."""
    clip_duration = max(int(params.video_clip_duration or 1), 1)
    video_count = max(int(params.video_count or 1), 1)
    if estimated_range := _estimate_voiceover_duration_range(
        str(params.video_script or ""), params.voice_rate
    ):
        min_clips = max(math.ceil(estimated_range[0] * video_count / clip_duration), 1)
        max_clips = max(
            math.ceil(estimated_range[1] * video_count / clip_duration), min_clips
        )
        st.warning(
            tr("MuAPI Billing Notice").format(min=min_clips, max=max_clips)
        )
    else:
        st.warning(tr("MuAPI Billing Notice Without Script"))
    st.checkbox(
        tr("Confirm MuAPI Charge"),
        key="muapi_confirm_charge",
        help=tr("Confirm MuAPI Charge Help"),
    )


def _estimate_voiceover_duration_range(
    text: str, voice_rate: float
) -> tuple[float, float] | None:
    """
    在本地估算完整配音时长，返回保守的上下界秒数。

    该估算只用于帮助用户在调用付费 TTS 前判断文案量级，不参与任务执行。
    中文、日文和韩文按字符速度估算，其它使用空格分词的语言按单词速度估算，
    再计入常见标点停顿。不同 Provider、音色和语气会造成实际偏差，因此界面
    必须展示区间而不是伪精确的单一结果。
    """
    normalized_text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized_text:
        return None

    script_chars = re.findall(
        r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]",
        normalized_text,
    )
    remaining_text = re.sub(
        r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]",
        " ",
        normalized_text,
    )
    words = re.findall(r"\b[\w]+(?:[-'’][\w]+)*\b", remaining_text, re.UNICODE)
    punctuation_count = len(re.findall(r"[,，.。!?！？;；:：]", normalized_text))

    # 4.2 字/秒和 2.6 词/秒接近日常解说语速；标点按 0.12 秒加入轻微停顿。
    # voice_rate 只作为估算修正项。部分生成式 TTS 不严格执行倍率，所以最终
    # 仍保留 ±15% 区间，避免让用户误以为该值等同于服务端真实结果。
    base_seconds = len(script_chars) / 4.2 + len(words) / 2.6 + punctuation_count * 0.12
    if base_seconds <= 0:
        return None

    normalized_rate = max(float(voice_rate or 1.0), 0.1)
    estimated_seconds = base_seconds / normalized_rate
    return (
        round(max(estimated_seconds * 0.85, 1.0), 1),
        round(max(estimated_seconds * 1.15, 1.0), 1),
    )


def _get_voice_preview_sample(voice_name: str) -> str:
    """返回适合当前音色的短试听文案，不使用用户的完整视频文案。"""
    # ElevenLabs 音色缺少明确语言字段时，根据展示名称中的越南语字符选择
    # 试听文案，避免用明显不匹配的语言判断音色效果。
    if voice.is_elevenlabs_voice(voice_name):
        parts = voice_name.split(":", 2)
        display = parts[2] if len(parts) >= 3 else ""
        vietnamese_chars = set("àáâãèéêìíòóôõùúýăđơưÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐƠƯ")
        if any(char in vietnamese_chars for char in display):
            return "Xin chào, đây là đoạn âm thanh thử nghiệm giọng nói."
    return tr("Voice Example")


def _voice_preview_fingerprint(
    *,
    preview_type: str,
    content: str,
    tts_server: str,
    voice_name: str,
    voice_rate: float,
    voice_volume: float,
    provider_signature: dict,
) -> str:
    """生成试听缓存指纹，任一配音参数变化后自动让旧试听结果失效。"""
    payload = {
        "preview_type": preview_type,
        "content": content,
        "tts_server": tts_server,
        "voice_name": voice_name,
        "voice_rate": voice_rate,
        "voice_volume": voice_volume,
        "provider_signature": provider_signature,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _credential_signature(value: str) -> str:
    """
    生成只用于缓存失效判断的凭证摘要。

    摘要不会写入配置、日志或任务文件。用户修改 API Key 后摘要会变化，从而
    强制重新调用当前配音服务，避免旧试听缓存让无效的新凭证看起来可用。
    """
    normalized_value = str(value or "")
    if not normalized_value:
        return ""
    return hashlib.sha256(normalized_value.encode("utf-8")).hexdigest()


def _get_voxcpm_reference_audio() -> bytes | None:
    """Return the current session's normalized reference audio, if any."""
    payload = st.session_state.get(VOXCPM_REFERENCE_AUDIO_SESSION_KEY)
    if not isinstance(payload, dict):
        return None
    audio_bytes = payload.get("audio_bytes")
    return bytes(audio_bytes) if isinstance(audio_bytes, bytes) else None


def _get_voxcpm_reference_audio_digest() -> str:
    payload = st.session_state.get(VOXCPM_REFERENCE_AUDIO_SESSION_KEY)
    if not isinstance(payload, dict):
        return ""
    digest = payload.get("audio_digest")
    return str(digest) if isinstance(digest, str) else ""


def _get_voxcpm_prompt_audio() -> bytes | None:
    payload = st.session_state.get(VOXCPM_PROMPT_AUDIO_SESSION_KEY)
    if not isinstance(payload, dict):
        return None
    audio_bytes = payload.get("audio_bytes")
    return bytes(audio_bytes) if isinstance(audio_bytes, bytes) else None


def _get_voxcpm_prompt_audio_digest() -> str:
    payload = st.session_state.get(VOXCPM_PROMPT_AUDIO_SESSION_KEY)
    if not isinstance(payload, dict):
        return ""
    digest = payload.get("audio_digest")
    return str(digest) if isinstance(digest, str) else ""


def _get_voxcpm_prompt_text() -> str:
    return str(st.session_state.get(VOXCPM_PROMPT_TEXT_SESSION_KEY, "") or "").strip()


def _clear_voxcpm_separate_prompt_audio() -> None:
    st.session_state.pop("voxcpm_prompt_audio_uploader", None)
    st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY, None)


def _clear_voxcpm_prompt_state() -> None:
    _clear_voxcpm_separate_prompt_audio()
    _clear_voxcpm_prompt_transcript()
    st.session_state.pop(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, None)
    st.session_state.pop(VOXCPM_PROMPT_EXAMPLE_MODE_SESSION_KEY, None)


def _clear_voxcpm_prompt_transcript() -> None:
    st.session_state.pop(VOXCPM_PROMPT_TEXT_SESSION_KEY, None)


def _sync_voxcpm_prompt_example_mode(use_separate_prompt_audio: bool) -> None:
    """Invalidate the transcript whenever its effective example changes mode."""
    previous_mode = st.session_state.get(VOXCPM_PROMPT_EXAMPLE_MODE_SESSION_KEY)
    current_mode = bool(use_separate_prompt_audio)
    if previous_mode is not None and bool(previous_mode) != current_mode:
        _clear_voxcpm_prompt_transcript()
    st.session_state[VOXCPM_PROMPT_EXAMPLE_MODE_SESSION_KEY] = current_mode


def _get_voxcpm_effective_prompt_audio() -> bytes | None:
    if not st.session_state.get(VOXCPM_HIGH_FIDELITY_SESSION_KEY, False):
        return None
    if st.session_state.get(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, False):
        return _get_voxcpm_prompt_audio()
    return _get_voxcpm_reference_audio()


def _get_voxcpm_effective_prompt_audio_digest() -> str:
    if not st.session_state.get(VOXCPM_HIGH_FIDELITY_SESSION_KEY, False):
        return ""
    if st.session_state.get(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, False):
        return _get_voxcpm_prompt_audio_digest()
    return _get_voxcpm_reference_audio_digest()


def _get_voxcpm_prompt_validation_error() -> str:
    if not st.session_state.get(VOXCPM_HIGH_FIDELITY_SESSION_KEY, False):
        return ""
    upload_error = st.session_state.get(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY)
    if upload_error:
        return str(upload_error)
    prompt_text = _get_voxcpm_prompt_text()
    if not prompt_text:
        return tr("VoxCPM Prompt Text Required")
    if (
        st.session_state.get(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, False)
        and not _get_voxcpm_prompt_audio()
    ):
        return tr("VoxCPM Prompt Pair Required")
    return ""


def _get_voxcpm_preview_validation_error(
    selected_tts_server: str,
    voice_name: str,
) -> str:
    if selected_tts_server != "voxcpm" and not voice.is_voxcpm_voice(voice_name):
        return ""
    reference_error = st.session_state.get(VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY)
    if reference_error:
        return str(reference_error)
    return _get_voxcpm_prompt_validation_error()


def _sync_voxcpm_reference_audio(uploaded_file) -> bytes | None:
    """Normalize a new upload once and keep only bounded WAV bytes in session."""
    if uploaded_file is None:
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_SESSION_KEY, None)
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY, None)
        _clear_voxcpm_prompt_state()
        st.session_state.pop(VOXCPM_HIGH_FIDELITY_SESSION_KEY, None)
        return None

    upload_size = int(getattr(uploaded_file, "size", 0) or 0)
    if upload_size <= 0:
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_SESSION_KEY, None)
        _clear_voxcpm_prompt_state()
        st.session_state[VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY] = tr(
            "VoxCPM Reference Audio Empty"
        )
        return None
    if upload_size > voice.VOXCPM_REFERENCE_AUDIO_MAX_UPLOAD_BYTES:
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_SESSION_KEY, None)
        _clear_voxcpm_prompt_state()
        st.session_state[VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY] = tr(
            "VoxCPM Reference Audio Upload Too Large"
        ).format(limit=voice.VOXCPM_REFERENCE_AUDIO_MAX_UPLOAD_BYTES // (1024 * 1024))
        return None

    previous_digest = _get_voxcpm_reference_audio_digest()
    raw_audio = uploaded_file.getvalue()
    upload_digest = hashlib.sha256(raw_audio).hexdigest()
    cached = st.session_state.get(VOXCPM_REFERENCE_AUDIO_SESSION_KEY)
    if isinstance(cached, dict) and cached.get("upload_digest") == upload_digest:
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY, None)
        return _get_voxcpm_reference_audio()

    try:
        with st.spinner(tr("Validating VoxCPM Reference Audio")):
            wav_audio = voice.prepare_voxcpm_reference_audio(
                raw_audio,
                Path(str(getattr(uploaded_file, "name", ""))).suffix,
            )
    except ValueError as exc:
        # Do not retain a prior clip after the user selects a replacement that
        # fails validation. Otherwise preview and generation could silently use
        # a different person's voice than the one currently shown in the UI.
        st.session_state.pop(VOXCPM_REFERENCE_AUDIO_SESSION_KEY, None)
        _clear_voxcpm_prompt_state()
        st.session_state[VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY] = str(exc)
        return None

    st.session_state[VOXCPM_REFERENCE_AUDIO_SESSION_KEY] = {
        "upload_digest": upload_digest,
        "audio_digest": hashlib.sha256(wav_audio).hexdigest(),
        "audio_bytes": wav_audio,
    }
    if (
        previous_digest != hashlib.sha256(wav_audio).hexdigest()
        and not st.session_state.get(VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY, False)
    ):
        _clear_voxcpm_prompt_transcript()
    st.session_state.pop(VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY, None)
    return bytes(wav_audio)


def _sync_voxcpm_prompt_audio(uploaded_file) -> bytes | None:
    """Normalize the optional delivery example without persisting its content."""
    if uploaded_file is None:
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY, None)
        return None

    upload_size = int(getattr(uploaded_file, "size", 0) or 0)
    if upload_size <= 0:
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
        st.session_state[VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY] = tr(
            "VoxCPM Prompt Audio Empty"
        )
        return None
    if upload_size > voice.VOXCPM_REFERENCE_AUDIO_MAX_UPLOAD_BYTES:
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
        st.session_state[VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY] = tr(
            "VoxCPM Prompt Audio Upload Too Large"
        ).format(limit=voice.VOXCPM_REFERENCE_AUDIO_MAX_UPLOAD_BYTES // (1024 * 1024))
        return None

    previous_digest = _get_voxcpm_prompt_audio_digest()
    raw_audio = uploaded_file.getvalue()
    upload_digest = hashlib.sha256(raw_audio).hexdigest()
    cached = st.session_state.get(VOXCPM_PROMPT_AUDIO_SESSION_KEY)
    if isinstance(cached, dict) and cached.get("upload_digest") == upload_digest:
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY, None)
        return _get_voxcpm_prompt_audio()

    try:
        with st.spinner(tr("Validating VoxCPM Prompt Audio")):
            wav_audio = voice.prepare_voxcpm_reference_audio(
                raw_audio,
                Path(str(getattr(uploaded_file, "name", ""))).suffix,
            )
    except ValueError as exc:
        st.session_state.pop(VOXCPM_PROMPT_AUDIO_SESSION_KEY, None)
        st.session_state[VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY] = str(exc)
        return None

    st.session_state[VOXCPM_PROMPT_AUDIO_SESSION_KEY] = {
        "upload_digest": upload_digest,
        "audio_digest": hashlib.sha256(wav_audio).hexdigest(),
        "audio_bytes": wav_audio,
    }
    if previous_digest != hashlib.sha256(wav_audio).hexdigest():
        _clear_voxcpm_prompt_transcript()
    st.session_state.pop(VOXCPM_PROMPT_AUDIO_ERROR_SESSION_KEY, None)
    return bytes(wav_audio)


def _get_voice_preview_provider_signature(tts_server: str) -> dict:
    """
    返回会影响试听结果的非敏感 Provider 配置。

    API Key 只以单向摘要参与缓存指纹，原始凭证不会进入缓存或日志。模型、
    服务地址、区域或凭证发生变化时都必须重新生成试听，否则界面可能继续播放
    旧 Provider 配置下的音频，让用户误判当前设置已经生效。
    """
    if tts_server == "azure-tts-v2":
        return {
            "speech_region": config.azure.get("speech_region", ""),
            "credential": _credential_signature(config.azure.get("speech_key", "")),
        }
    if tts_server == "siliconflow":
        return {
            "credential": _credential_signature(config.siliconflow.get("api_key", ""))
        }
    if tts_server == "gemini-tts":
        return {
            "credential": _credential_signature(config.app.get("gemini_api_key", ""))
        }
    if tts_server == "mimo-tts":
        return {"credential": _credential_signature(config.app.get("mimo_api_key", ""))}
    if tts_server == "minimax-tts":
        return {
            "base_url": voice.get_minimax_tts_endpoint(),
            "model_id": config.minimax_tts.get("model_id", ""),
            "voice_id": config.minimax_tts.get("voice_id", ""),
            "credential": _credential_signature(voice.get_minimax_tts_api_key()),
        }
    if tts_server == "elevenlabs":
        return {
            "model_id": config.elevenlabs.get("model_id", ""),
            "credential": _credential_signature(config.elevenlabs.get("api_key", "")),
        }
    if tts_server == "chatterbox":
        return {
            "base_url": config.chatterbox.get("base_url", ""),
            "model_id": config.chatterbox.get("model_id", ""),
            "credential": _credential_signature(config.chatterbox.get("api_key", "")),
        }
    if tts_server == "kokoro":
        return {
            "base_url": config.kokoro.get("base_url", ""),
            "model_id": config.kokoro.get("model_id", ""),
            "credential": _credential_signature(config.kokoro.get("api_key", "")),
        }
    if tts_server == "voxcpm":
        return {
            "base_url": config.voxcpm.get("base_url", ""),
            "model_id": config.voxcpm.get("model_id", ""),
            "voice_id": config.voxcpm.get("voice_id", "default"),
            "credential": _credential_signature(config.voxcpm.get("api_key", "")),
            "reference_audio": _get_voxcpm_reference_audio_digest(),
            "prompt_audio": _get_voxcpm_effective_prompt_audio_digest(),
            "prompt_text": _credential_signature(
                _get_voxcpm_prompt_text()
                if st.session_state.get(VOXCPM_HIGH_FIDELITY_SESSION_KEY, False)
                else ""
            ),
        }
    return {}


def _synthesize_voice_preview(
    *,
    content: str,
    preview_type: str,
    selected_tts_server: str,
    voice_name: str,
    voice_rate: float,
    voice_volume: float,
    voxcpm_reference_audio: bytes | None = None,
    voxcpm_prompt_audio: bytes | None = None,
    voxcpm_prompt_text: str = "",
) -> dict | None:
    """生成一次试听并转为内存缓存，临时文件不会跨会话长期保留。"""
    if selected_tts_server == "chatterbox":
        _sync_chatterbox_config_from_session_state()
    if selected_tts_server == "kokoro":
        _sync_kokoro_config_from_session_state()

    temp_dir = utils.storage_dir("temp", create=True)
    audio_file = os.path.join(temp_dir, f"tmp-voice-{str(uuid4())}.mp3")
    logger.info(
        f"generating {preview_type} voice preview: "
        f"voice={voice_name}, rate={voice_rate}, volume={voice_volume}, "
        f"text_length={len(content)}"
    )
    try:
        with config.try_runtime_config_lock() as lock_acquired:
            if not lock_acquired:
                return {"busy": True}
            tts_kwargs = {
                "text": content,
                "voice_name": voice_name,
                "voice_rate": voice_rate,
                "voice_file": audio_file,
                "voice_volume": voice_volume,
            }
            if voxcpm_reference_audio is not None:
                tts_kwargs["voxcpm_reference_audio"] = voxcpm_reference_audio
            if voxcpm_prompt_audio is not None:
                tts_kwargs["voxcpm_prompt_audio"] = voxcpm_prompt_audio
                tts_kwargs["voxcpm_prompt_text"] = voxcpm_prompt_text
            sub_maker = voice.tts(**tts_kwargs)
        if not sub_maker or not os.path.exists(audio_file):
            logger.error(f"{preview_type} voice preview did not produce an audio file")
            return None

        with open(audio_file, "rb") as file:
            audio_bytes = file.read()
        if not audio_bytes:
            logger.error(f"voice preview audio file is empty: {audio_file}")
            return None

        duration = voice.get_audio_duration(audio_file)
        if (
            not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            logger.warning(
                f"voice preview duration is unavailable: "
                f"preview_type={preview_type}, voice={voice_name}"
            )
            duration = None

        return {
            "audio_bytes": audio_bytes,
            "mime_type": _detect_audio_mime(audio_file, audio_bytes),
            "duration": duration,
            "preview_type": preview_type,
            "sub_maker": sub_maker,
            # 让位于音频面板之前的视频面板只采用与当前设置完全匹配的
            # 完整试听时长；短试听或旧文案绝不能改变推荐素材数。
            "content_digest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "tts_server": selected_tts_server,
            "voice_name": voice_name,
            "voice_rate": float(voice_rate),
        }
    finally:
        # 浏览器播放器使用内存字节，文件读取完即可清理，避免频繁试听积累临时文件。
        try:
            os.remove(audio_file)
        except FileNotFoundError:
            pass
        except OSError as exc:
            # 清理失败不应覆盖真正的 TTS 响应或异常，但需要保留路径和系统错误，
            # 方便排查权限、只读文件系统等环境问题。
            logger.warning(
                f"failed to delete voice preview file {audio_file}: {str(exc)}"
            )


def _render_voice_preview(params, friendly_names, selected_tts_server, voice_name):
    """渲染低成本短试听、完整文案时长估算和按需完整配音预览。"""
    if not friendly_names:
        return

    script_content = str(params.video_script or "").strip()
    estimated_range = _estimate_voiceover_duration_range(
        script_content,
        params.voice_rate,
    )
    if estimated_range:
        st.caption(
            tr("Estimated Voiceover Duration").format(
                min=estimated_range[0],
                max=estimated_range[1],
            )
        )
    else:
        st.caption(tr("Voiceover Script Required"))

    sample_content = _get_voice_preview_sample(voice_name)
    provider_signature = _get_voice_preview_provider_signature(selected_tts_server)
    preview_validation_error = _get_voxcpm_preview_validation_error(
        selected_tts_server,
        voice_name,
    )
    preview_columns = st.columns(2)
    short_preview_requested = preview_columns[0].button(
        tr("Play Voice"),
        key="play_voice_button",
        icon=":material/graphic_eq:",
        use_container_width=True,
        disabled=bool(preview_validation_error),
    )
    full_preview_requested = preview_columns[1].button(
        tr("Generate Full Voiceover Preview"),
        key="generate_full_voiceover_preview_button",
        icon=":material/article:",
        help=tr("Full Voiceover Preview Cost Hint"),
        use_container_width=True,
        disabled=not bool(script_content) or bool(preview_validation_error),
    )

    preview_type = ""
    preview_content = ""
    if short_preview_requested:
        preview_type = "sample"
        preview_content = sample_content
    elif full_preview_requested:
        preview_type = "full"
        preview_content = script_content

    sample_fingerprint = _voice_preview_fingerprint(
        preview_type="sample",
        content=sample_content,
        tts_server=selected_tts_server,
        voice_name=voice_name,
        voice_rate=params.voice_rate,
        voice_volume=params.voice_volume,
        provider_signature=provider_signature,
    )
    full_fingerprint = (
        _voice_preview_fingerprint(
            preview_type="full",
            content=script_content,
            tts_server=selected_tts_server,
            voice_name=voice_name,
            voice_rate=params.voice_rate,
            voice_volume=params.voice_volume,
            provider_signature=provider_signature,
        )
        if script_content
        else ""
    )

    if preview_type:
        requested_fingerprint = (
            sample_fingerprint if preview_type == "sample" else full_fingerprint
        )
        cached_preview = st.session_state.get("voice_preview_audio")
        if (
            not cached_preview
            or cached_preview.get("fingerprint") != requested_fingerprint
        ):
            try:
                with st.spinner(tr("Synthesizing Voice")):
                    preview_result = _synthesize_voice_preview(
                        content=preview_content,
                        preview_type=preview_type,
                        selected_tts_server=selected_tts_server,
                        voice_name=voice_name,
                        voice_rate=params.voice_rate,
                        voice_volume=params.voice_volume,
                        voxcpm_reference_audio=(
                            _get_voxcpm_reference_audio()
                            if selected_tts_server == "voxcpm"
                            else None
                        ),
                        voxcpm_prompt_audio=(
                            _get_voxcpm_effective_prompt_audio()
                            if selected_tts_server == "voxcpm"
                            else None
                        ),
                        voxcpm_prompt_text=(
                            _get_voxcpm_prompt_text()
                            if selected_tts_server == "voxcpm"
                            else ""
                        ),
                    )
            except Exception as exc:
                logger.exception(f"failed to generate {preview_type} voice preview")
                st.error(tr("Voice Preview Failed").format(error=str(exc)))
            else:
                if preview_result and preview_result.get("busy"):
                    st.warning(tr("Voice Preview Busy"))
                elif preview_result:
                    preview_result["fingerprint"] = requested_fingerprint
                    st.session_state["voice_preview_audio"] = preview_result
                    if (
                        preview_type == "full"
                        and params.video_source == "loomloom"
                        and isinstance(preview_result.get("duration"), (int, float))
                        and math.isfinite(preview_result["duration"])
                        and preview_result["duration"] > 0
                    ):
                        # 视频设置先于音频设置渲染。完整试听成功后触发一次 rerun，
                        # 让上方素材数立刻按真实旁白时长重新推荐并刷新覆盖提示。
                        st.session_state["loomloom_video_scene_autofill_digest"] = (
                            preview_result["content_digest"]
                        )
                        st.rerun()
                else:
                    st.error(tr("Voice Preview No Audio"))

    cached_preview = st.session_state.get("voice_preview_audio")
    valid_fingerprints = {sample_fingerprint, full_fingerprint}
    if (
        cached_preview
        and cached_preview.get("fingerprint") in valid_fingerprints
        and cached_preview.get("audio_bytes")
    ):
        # 只在用户本次明确点击“试听音色”时自动播放。Streamlit 的其它控件
        # 也会触发页面 rerun；如果对缓存音频永久开启 autoplay，修改任意设置
        # 都可能让旧试听从头播放。完整试听继续保留手动播放，避免较长音频在
        # 生成完成后意外打断用户。
        should_autoplay = bool(
            short_preview_requested
            and cached_preview.get("preview_type") == "sample"
            and cached_preview.get("fingerprint") == sample_fingerprint
        )
        st.audio(
            cached_preview["audio_bytes"],
            format=cached_preview.get("mime_type", "audio/mp3"),
            autoplay=should_autoplay,
        )
        if cached_preview.get("preview_type") == "full":
            duration = cached_preview.get("duration")
            if isinstance(duration, (int, float)) and duration > 0:
                st.caption(
                    tr("Actual Voiceover Duration").format(duration=f"{duration:.1f}")
                )
            else:
                st.warning(tr("Voice Preview Duration Unavailable"))


def _get_reusable_full_voice_preview(params, voice_mode: str) -> dict | None:
    """
    返回与当前生成参数完全匹配的完整试听缓存。

    只复用完整文案试听，短音色样例永远不能进入正式任务。指纹统一覆盖文案、
    Provider、音色、语速、音量和非敏感配置摘要；任何参数变化都会自然回退到
    正常 TTS 流程。字幕时间轴和有效时长同样是必需条件，避免只复用音频后让
    Edge 字幕链路失去 SubMaker。
    """
    if voice_mode != VOICE_MODE_TTS:
        return None

    script_content = str(params.video_script or "").strip()
    selected_tts_server = config.ui.get("tts_server", "azure-tts-v1")
    if (
        not script_content
        or not params.voice_name
        # 正式视频会在 MoviePy 合成阶段统一应用配音音量；部分 Provider 又会
        # 在 TTS 阶段直接写入音量增益。非默认音量下复用试听可能造成二次增益，
        # 因此先保守回退原流程，避免为少量场景引入 Provider 特判。
        or not math.isclose(float(params.voice_volume), 1.0)
    ):
        return None

    expected_fingerprint = _voice_preview_fingerprint(
        preview_type="full",
        content=script_content,
        tts_server=selected_tts_server,
        voice_name=params.voice_name,
        voice_rate=params.voice_rate,
        voice_volume=params.voice_volume,
        provider_signature=_get_voice_preview_provider_signature(selected_tts_server),
    )
    cached_preview = st.session_state.get("voice_preview_audio")
    if (
        not cached_preview
        or cached_preview.get("fingerprint") != expected_fingerprint
        or cached_preview.get("preview_type") != "full"
        or not cached_preview.get("audio_bytes")
        or cached_preview.get("sub_maker") is None
    ):
        return None

    duration = cached_preview.get("duration")
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        return None

    return {
        "audio_bytes": bytes(cached_preview["audio_bytes"]),
        "audio_digest": hashlib.sha256(cached_preview["audio_bytes"]).hexdigest(),
        "duration": float(duration),
        "sub_maker": cached_preview["sub_maker"],
        "script": script_content,
        "voice_name": params.voice_name,
        "voice_rate": float(params.voice_rate),
        "voice_volume": float(params.voice_volume),
    }


def _sync_minimax_tts_api_key_input():
    """
    同步 MiniMax TTS 密码控件，并返回当前有效 Key。

    TTS 专用 Key 为空时允许复用 MiniMax LLM Key。共享 Key 只用于当前控件和
    请求，不自动复制到 [minimax_tts]，避免同一凭证在配置文件中重复维护。
    """
    widget_key = "minimax_tts_api_key_input"
    configured_key = str(config.minimax_tts.get("api_key", "") or "").strip()
    shared_key = str(
        config.app.get("minimax_api_key", "") or os.getenv("MINIMAX_API_KEY", "") or ""
    ).strip()
    effective_key = configured_key or shared_key
    had_widget_state = widget_key in st.session_state
    entered_key = str(st.session_state.get(widget_key, "") or "").strip()

    if not entered_key and effective_key:
        # 浏览器重连可能重放空密码状态。恢复已配置凭证，防止空值覆盖配置，
        # 同时确保当前 rerun 的试听请求可以直接使用有效 Key。
        st.session_state[widget_key] = effective_key
        entered_key = effective_key
        if had_widget_state:
            logger.debug("restored MiniMax TTS API key after empty session replay")
    elif not had_widget_state:
        st.session_state[widget_key] = effective_key
        entered_key = effective_key

    if entered_key and entered_key != effective_key:
        _set_runtime_config("minimax_tts", "api_key", entered_key)

    return entered_key


def _get_cached_minimax_voices(api_key: str, endpoint: str) -> list[dict[str, str]]:
    """按站点和凭证摘要读取当前会话中的 MiniMax 音色查询结果。"""
    cache = st.session_state.get("minimax_tts_voice_catalog_cache", {})
    cache_key = f"{endpoint}|{_credential_signature(api_key)}"
    cached_voices = cache.get(cache_key, [])
    return cached_voices if isinstance(cached_voices, list) else []


def _cache_minimax_voices(
    api_key: str,
    endpoint: str,
    voices: list[dict[str, str]],
):
    """缓存主动查询到的音色，避免普通控件 rerun 后重复请求 MiniMax。"""
    cache = st.session_state.setdefault("minimax_tts_voice_catalog_cache", {})
    cache_key = f"{endpoint}|{_credential_signature(api_key)}"
    cache[cache_key] = voices


def _get_minimax_voice_options() -> tuple[list[str], dict[str, str]]:
    """从会话缓存读取 MiniMax 音色目录，供音频面板的统一音色选择器使用。

    目录在服务商配置页配音 TAB 主动刷新；未刷新时仅保留配置的 Voice ID，
    原有生成流程不依赖远端音色查询结果。
    """
    effective_api_key = voice.get_minimax_tts_api_key()
    effective_endpoint = voice.get_minimax_tts_endpoint()
    available_voices = _get_cached_minimax_voices(
        effective_api_key, effective_endpoint
    )
    voice_labels = {
        f"minimax:{item['voice_id']}": (
            f"{item['voice_name']} ({item['voice_id']})"
            if item["voice_name"] != item["voice_id"]
            else item["voice_id"]
        )
        for item in available_voices
    }
    configured_voice_id = str(
        config.minimax_tts.get("voice_id", voice.MINIMAX_TTS_DEFAULT_VOICE)
        or voice.MINIMAX_TTS_DEFAULT_VOICE
    ).strip()
    configured_voice = f"minimax:{configured_voice_id}"
    voice_labels.setdefault(configured_voice, configured_voice_id)
    return list(voice_labels), voice_labels


def _render_minimax_tts_settings() -> tuple[list[str], dict[str, str]]:
    """渲染 MiniMax TTS 配置，并返回统一音色选择器使用的选项和文案。"""
    effective_api_key = _sync_minimax_tts_api_key_input()
    effective_api_key = st.text_input(
        tr("MiniMax TTS API Key"),
        type="password",
        key="minimax_tts_api_key_input",
    ).strip()

    dedicated_key = str(config.minimax_tts.get("api_key", "") or "").strip()
    minimax_tts_endpoints = [voice.MINIMAX_TTS_GLOBAL_URL, voice.MINIMAX_TTS_CN_URL]
    effective_endpoint = voice.get_minimax_tts_endpoint()
    if effective_endpoint not in minimax_tts_endpoints:
        effective_endpoint = voice.MINIMAX_TTS_GLOBAL_URL
    minimax_tts_base_url = stable_selectbox(
        tr("MiniMax TTS Endpoint"),
        options=minimax_tts_endpoints,
        default_value=effective_endpoint,
        key="minimax_tts_endpoint_select",
        # 复用 LLM Key 时必须跟随 LLM 所在区域，避免界面允许选择一个实际
        # 不会生效的地址；填写独立 TTS Key 后即可单独选择站点。
        disabled=not dedicated_key,
    )
    if dedicated_key:
        _set_runtime_config("minimax_tts", "base_url", minimax_tts_base_url)

    configured_model = config.minimax_tts.get(
        "model_id", voice.MINIMAX_TTS_DEFAULT_MODEL
    )
    if configured_model not in voice.MINIMAX_TTS_MODELS:
        configured_model = voice.MINIMAX_TTS_DEFAULT_MODEL
    minimax_tts_model = stable_selectbox(
        tr("MiniMax TTS Model"),
        options=list(voice.MINIMAX_TTS_MODELS),
        default_value=configured_model,
        key="minimax_tts_model_select",
    )
    _set_runtime_config("minimax_tts", "model_id", minimax_tts_model)

    if st.button(
        tr("Load MiniMax Voices"),
        key="load_minimax_voices_button",
        icon=":material/refresh:",
        use_container_width=True,
    ):
        try:
            available_voices = voice.get_minimax_voice_catalog(
                api_key=effective_api_key,
                endpoint=minimax_tts_base_url,
                voice_type="all",
            )
        except Exception as exc:
            # 这里必须把异常暴露给用户并记录日志。账号区域不匹配、Key 权限不足
            # 或网络失败都很常见，静默返回空列表会让用户误以为账号没有音色。
            logger.warning(f"load MiniMax voices failed: {exc}")
            st.error(tr("MiniMax Voices Load Failed").format(error=str(exc)))
        else:
            _cache_minimax_voices(
                effective_api_key,
                minimax_tts_base_url,
                available_voices,
            )
            st.success(tr("MiniMax Voices Loaded").format(count=len(available_voices)))

    available_voices = _get_cached_minimax_voices(
        effective_api_key,
        minimax_tts_base_url,
    )
    voice_labels = {
        f"minimax:{item['voice_id']}": (
            f"{item['voice_name']} ({item['voice_id']})"
            if item["voice_name"] != item["voice_id"]
            else item["voice_id"]
        )
        for item in available_voices
    }
    configured_voice_id = str(
        config.minimax_tts.get("voice_id", voice.MINIMAX_TTS_DEFAULT_VOICE)
        or voice.MINIMAX_TTS_DEFAULT_VOICE
    ).strip()
    configured_voice = f"minimax:{configured_voice_id}"
    # 尚未点击获取音色、接口暂时不可用或配置使用列表外克隆音色时，仍保留
    # 当前 Voice ID，确保原有生成流程不依赖远端音色查询结果。
    voice_labels.setdefault(configured_voice, configured_voice_id)
    return list(voice_labels), voice_labels


def _sync_elevenlabs_api_key_input():
    """
    同步 ElevenLabs 密码控件、持久化配置和环境变量，并返回当前有效 Key。

    Streamlit 在浏览器标签页连接到重启后的服务时，可能重放一个空的密码控件
    状态。这个空值无法与用户主动清空可靠区分，因此当配置文件或环境变量仍有
    Key 时，优先恢复有效值，防止空状态覆盖配置并确保本次 rerun 能立即加载
    音色。需要彻底删除 Key 时应修改配置文件或环境变量，避免重连误判。
    """
    widget_key = "elevenlabs_api_key_input"
    configured_key = str(config.elevenlabs.get("api_key", "") or "").strip()
    env_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    effective_key = configured_key or env_key
    had_widget_state = widget_key in st.session_state
    entered_key = str(st.session_state.get(widget_key, "") or "").strip()

    if not entered_key and effective_key:
        # 重连后的空状态不能覆盖有效凭证，同时必须在渲染音色列表之前恢复，
        # 否则配置文件虽然没有被清空，当前页面仍会使用空 Key 请求 ElevenLabs。
        st.session_state[widget_key] = effective_key
        entered_key = effective_key
        if had_widget_state:
            logger.debug("restored ElevenLabs API key after empty session replay")
    elif not had_widget_state:
        # 先初始化再创建控件，避免同时传 value 和 session_state 触发 Streamlit
        # 的默认值冲突警告；没有任何 Key 时初始化为空即可。
        st.session_state[widget_key] = entered_key

    if entered_key and entered_key != effective_key:
        # 用户主动输入的新值才落入 config.toml。环境变量作为有效值回填时不会
        # 被复制到文件，容器或部署平台注入的密钥仍只保留在运行环境中。
        for cache_key in list(st.session_state.keys()):
            if str(cache_key).startswith("elevenlabs_voices_"):
                del st.session_state[cache_key]
        _set_runtime_config("elevenlabs", "api_key", entered_key)

    return entered_key


def _sync_voxcpm_api_key_input():
    """恢复 VoxCPM 密码控件在重连时被 Streamlit 重放的空状态。"""
    widget_key = "voxcpm_api_key_input"
    configured_key = str(config.voxcpm.get("api_key", "") or "").strip()
    had_widget_state = widget_key in st.session_state
    entered_key = str(st.session_state.get(widget_key, "") or "").strip()

    if not entered_key and configured_key:
        # 浏览器重连可能重放空密码状态。保留已保存凭据，避免本次 rerun
        # 通过 _set_runtime_config 把 config.toml 中的有效 Key 覆盖为空。
        st.session_state[widget_key] = configured_key
        entered_key = configured_key
        if had_widget_state:
            logger.debug("restored VoxCPM API key after empty session replay")
    elif not had_widget_state:
        st.session_state[widget_key] = entered_key

    return entered_key


def _render_elevenlabs_api_key_input(label_key):
    """
    渲染 ElevenLabs TTS 与配乐共用的唯一 API Key 输入状态。

    同一页面若为 TTS 和配乐分别使用两个 widget key，Streamlit 会各自保留旧值，
    后渲染的输入框还会覆盖共享配置。这里统一使用一个 key，并集中处理环境变量
    回填、配置更新和音色缓存失效，确保界面显示与后台任务始终读取同一个值。
    """
    _sync_elevenlabs_api_key_input()
    return st.text_input(
        tr(label_key),
        type="password",
        key="elevenlabs_api_key_input",
    ).strip()


def _render_background_music_settings(params):
    """渲染背景音乐来源与音量设置，并返回本次待保存的上传文件。"""
    uploaded_bgm_file = None
    previous_bgm_type = st.session_state.get("last_rendered_bgm_type")
    st.divider()
    bgm_options = [
        (tr("No Background Music"), ""),
        (tr("Random Background Music"), "random"),
        (tr("Preset Song"), "preset"),
        (tr("Custom Background Music"), "custom"),
        (tr("Sonilo Background Music"), "sonilo"),
        (tr("ElevenLabs Background Music"), "elevenlabs"),
    ]
    selected_bgm_type = stable_selectbox(
        tr("Background Music Source"),
        options=[value for _, value in bgm_options],
        default_value=_saved_ui_choice(
            "bgm_type",
            [value for _, value in bgm_options],
            "random",
        ),
        key="bgm_type_select",
        format_func=lambda value: dict((v, label) for label, v in bgm_options)[value],
    )
    params.bgm_type = selected_bgm_type
    _set_runtime_config("ui", "bgm_type", params.bgm_type)
    if params.bgm_type == "sonilo":
        # Sonilo Key 在服务商配置页音乐 TAB 统一维护；这里只在缺失时提示。
        if not _music_service_ready("sonilo"):
            st.caption(tr("Music Key Elsewhere Hint"))
    elif params.bgm_type == "elevenlabs":
        # ElevenLabs Key 在服务商配置页统一维护；这里只在缺失时提示。
        if not _music_service_ready("elevenlabs"):
            st.caption(tr("Music Key Elsewhere Hint"))

    bgm_volume_options = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    params.bgm_volume = stable_selectbox(
        tr("Background Music Volume"),
        options=bgm_volume_options,
        default_value=_saved_ui_choice("bgm_volume", bgm_volume_options, 0.2),
        key="bgm_volume_select",
        format_func=lambda value: f"{int(value * 100)}%",
        disabled=not params.bgm_type,
    )
    _set_runtime_config("ui", "bgm_volume", params.bgm_volume)
    bgm_enabled = bgm_service.should_use_bgm(params.bgm_type, params.bgm_volume)

    if params.bgm_type == "custom":
        uploaded_bgm_file = st.file_uploader(
            tr("Upload Background Music"),
            type=[
                extension.removeprefix(".")
                for extension in bgm_service.SUPPORTED_BGM_EXTENSIONS
            ],
            accept_multiple_files=False,
            key="custom_bgm_uploader",
            help=tr("Upload Background Music Help"),
            # Streamlit 默认会在控件上展示全局 200MB 上限。这里必须与服务层
            # 30MB 硬限制保持一致，避免界面允许选择、提交时才被服务端拒绝。
            max_upload_size=bgm_service.MAX_BGM_UPLOAD_BYTES // (1024 * 1024),
        )
        if uploaded_bgm_file is not None and bgm_enabled:
            try:
                safe_name = bgm_service.sanitize_upload_filename(uploaded_bgm_file.name)
                # Streamlit 在调整音量等任意控件后都会重新执行页面。使用内容哈希
                # 区分上传文件，并在当前会话内缓存完整解码结果，既不能只凭同名、
                # 同大小文件误用旧结果，也避免每次 rerun 都重复调用 FFmpeg。
                validation_key = (
                    safe_name,
                    uploaded_bgm_file.size,
                    hashlib.sha256(uploaded_bgm_file.getbuffer()).hexdigest(),
                )
                cached_validation = st.session_state.get("custom_bgm_validation")
                if (
                    not cached_validation
                    or cached_validation.get("key") != validation_key
                ):
                    try:
                        bgm_service.validate_bgm_upload(
                            uploaded_bgm_file.name, uploaded_bgm_file
                        )
                    except bgm_service.BgmUploadError as exc:
                        cached_validation = {
                            "key": validation_key,
                            "error": str(exc),
                            "error_type": "upload",
                        }
                        # 同一个文件指纹的失败结果会进入会话缓存，因此这里只在
                        # 首次真实执行校验时记录一次，避免普通控件 rerun 刷屏。
                        logger.warning(
                            "WebUI background music validation rejected: "
                            f"name={safe_name}, error={str(exc)}"
                        )
                    except bgm_service.BgmServiceError as exc:
                        cached_validation = {
                            "key": validation_key,
                            "error": str(exc),
                            "error_type": "service",
                        }
                        logger.error(
                            "WebUI background music validation failed: "
                            f"name={safe_name}, error={str(exc)}"
                        )
                    else:
                        cached_validation = {
                            "key": validation_key,
                            "error": "",
                            "error_type": "",
                        }
                    st.session_state["custom_bgm_validation"] = cached_validation

                if cached_validation.get("error"):
                    if cached_validation.get("error_type") == "service":
                        raise bgm_service.BgmServiceError(cached_validation["error"])
                    raise bgm_service.BgmUploadError(cached_validation["error"])
            except bgm_service.BgmUploadError:
                # 非法文件不能沿用上一次有效上传的名称，否则任务参数可能仍指向
                # 历史 BGM。保留 UploadedFile 返回值，让用户点击生成时仍会被最终
                # 服务端校验拦截，而不是静默生成一条没有背景音乐的视频。
                params.bgm_file = ""
                st.error(tr("Invalid Background Music"))
            except bgm_service.BgmServiceError:
                params.bgm_file = ""
                st.error(tr("Background Music Validation Failed"))
            else:
                # 完整解码校验通过后才展示播放器和“已就绪”。文件仍只在点击
                # 生成时持久化，用户仅预览或随后移除文件不会污染 storage/bgm。
                uploaded_mime_type = str(getattr(uploaded_bgm_file, "type", "") or "")
                preview_mime_type = (
                    uploaded_mime_type
                    if uploaded_mime_type.startswith("audio/")
                    else mimetypes.guess_type(safe_name)[0] or "audio/mpeg"
                )
                st.audio(uploaded_bgm_file, format=preview_mime_type)
                st.info(f"{tr('Background Music Ready')}: {safe_name}")
                params.bgm_file = safe_name

        # Streamlit 会在条件控件暂时不渲染时清理其 widget state。
        # 从其它 BGM 来源切回时用已持久化值恢复；同一来源下
        # 用户主动清空时 previous_bgm_type 不变，因此不会被旧值反弹。
        if previous_bgm_type != "custom":
            st.session_state["custom_bgm_file_input"] = _saved_ui_text(
                "custom_bgm_file"
            )
        custom_bgm_file = st.text_input(
            tr("Custom Background Music File"),
            key="custom_bgm_file_input",
            disabled=uploaded_bgm_file is not None,
        )
        _set_runtime_config(
            "ui", "custom_bgm_file", custom_bgm_file.strip()
        )
        if uploaded_bgm_file is None and custom_bgm_file and bgm_enabled:
            # 文件名由服务层映射到 storage/bgm 或 resource/songs 后校验，
            # UI 不接受两个白名单目录之外的任意路径。
            params.bgm_file = custom_bgm_file.strip()
        elif not bgm_enabled:
            # 上传控件继续保留用户已选择的文件，调高音量后的下一次 rerun 会自动
            # 完整校验；当前任务参数必须清空，避免 0 音量任务保存或解析该文件。
            params.bgm_file = ""

    if params.bgm_type == "preset":
        # 服务层已经统一完成扩展名、临时文件和符号链接校验。这里直接复用其
        # 结果，避免 UI 维护第二套枚举规则，后续新增格式时也不会出现差异。
        available_song_paths = bgm_service.list_builtin_bgm_files()
        songs_by_name = {
            os.path.basename(song_path): song_path for song_path in available_song_paths
        }
        available_songs = list(songs_by_name)
        if not available_songs:
            st.warning(tr("No Background Music Available"))
            params.bgm_file = ""
        else:
            default_preset_song = _saved_ui_text("preset_song", available_songs[0])
            requested_preset_song = st.session_state.get(
                localized_widget_key("preset_song_select"), default_preset_song
            )
            if requested_preset_song not in available_songs:
                # 历史任务或其它版本导出的设置可能引用当前安装中不存在的歌曲。
                # 明确提示后由 stable_selectbox 回退第一首，避免静默换歌。
                st.warning(tr("Selected Background Music Unavailable"))
            selected_song = stable_selectbox(
                tr("Preset Song"),
                options=available_songs,
                default_value=(
                    default_preset_song
                    if default_preset_song in available_songs
                    else available_songs[0]
                ),
                key="preset_song_select",
            )
            _set_runtime_config("ui", "preset_song", selected_song)
            # 用户选择歌曲后立即提供在线试听。播放器读取的是刚刚通过服务层
            # 白名单校验得到的真实路径，不接受页面输入的任意文件路径。
            selected_song_path = songs_by_name[selected_song]
            preview_mime_type = (
                mimetypes.guess_type(selected_song_path)[0] or "audio/mpeg"
            )
            preview_available = True
            try:
                # Streamlit 读取路径失败时会把 OSError 包装成内部异常，导致下面
                # 无法按文件错误处理。先自行读取字节，既保持播放器行为，也让
                # Docker 挂载短暂失效、权限变化等情况稳定落入可控分支。
                selected_song_bytes = Path(selected_song_path).read_bytes()
            except OSError as exc:
                preview_available = False
                # 文件可能在枚举后被其它进程删除。试听失败不能中断页面或视频
                # 参数编辑，但需要保留日志以便定位运行环境和挂载问题。
                logger.warning(
                    "failed to preview preset background music: "
                    f"name={selected_song}, error={str(exc)}"
                )
                st.warning(tr("Background Music Preview Failed"))
            else:
                st.audio(selected_song_bytes, format=preview_mime_type)
            if bgm_enabled and preview_available:
                params.bgm_file = selected_song
            else:
                params.bgm_file = ""

    if params.bgm_type == "sonilo":
        if previous_bgm_type != "sonilo":
            st.session_state["sonilo_bgm_prompt_input"] = _saved_ui_text(
                "sonilo_bgm_prompt",
                max_length=sonilo_service.MAX_PROMPT_LENGTH,
            )
        params.video_music_prompt = st.text_input(
            tr("Sonilo Music Prompt"),
            key="sonilo_bgm_prompt_input",
            max_chars=sonilo_service.MAX_PROMPT_LENGTH,
            help=tr("Sonilo Music Prompt Help"),
        ).strip()
        _set_runtime_config(
            "ui", "sonilo_bgm_prompt", params.video_music_prompt
        )
        if params.video_count > 1:
            st.warning(tr("Sonilo Multiple Videos Warning"))
        if st.button(
            tr("Test Sonilo Connection"),
            key="test_sonilo_connection_button",
            use_container_width=True,
        ):
            try:
                sonilo_service.test_connection()
            except sonilo_service.SoniloError as exc:
                logger.warning(f"Sonilo connection test failed: {exc}")
                st.error(tr("Sonilo Connection Test Failed").format(error=str(exc)))
            else:
                st.success(tr("Sonilo Connection Test Succeeded"))
    elif params.bgm_type == "elevenlabs":
        if previous_bgm_type != "elevenlabs":
            st.session_state["elevenlabs_music_prompt_input"] = _saved_ui_text(
                "elevenlabs_music_prompt",
                max_length=elevenlabs_music_service.MAX_PROMPT_LENGTH,
            )
        params.video_music_prompt = st.text_input(
            tr("ElevenLabs Music Prompt"),
            key="elevenlabs_music_prompt_input",
            max_chars=elevenlabs_music_service.MAX_PROMPT_LENGTH,
            help=tr("ElevenLabs Music Prompt Help"),
        ).strip()
        _set_runtime_config(
            "ui", "elevenlabs_music_prompt", params.video_music_prompt
        )
        if params.video_count > 1:
            st.warning(tr("ElevenLabs Multiple Videos Warning"))
        if st.button(
            tr("Test ElevenLabs Connection"),
            key="test_elevenlabs_music_connection_button",
            use_container_width=True,
        ):
            try:
                elevenlabs_music_service.test_connection()
            except elevenlabs_music_service.ElevenLabsPaidPlanRequiredError:
                st.error(tr("ElevenLabs Paid Plan Required"))
            except elevenlabs_music_service.ElevenLabsMusicError as exc:
                logger.warning(f"ElevenLabs connection test failed: {exc}")
                st.error(tr("ElevenLabs Connection Test Failed").format(error=str(exc)))
            else:
                st.success(tr("ElevenLabs Connection Test Succeeded"))
    if params.bgm_type == "sonilo" and bgm_enabled and not sonilo_service.is_enabled():
        # 音量为 0 时任务层不会生成或混合 Sonilo 配乐，因此无需提示 Key；
        # 该判断与任务入口共用服务层规则，避免界面提示和实际执行条件分叉。
        st.warning(tr("Sonilo API Key Required"))
    elif (
        params.bgm_type == "elevenlabs"
        and bgm_enabled
        and not elevenlabs_music_service.is_enabled()
    ):
        st.warning(tr("ElevenLabs API Key Required"))
    st.session_state["last_rendered_bgm_type"] = params.bgm_type
    return uploaded_bgm_file


def _voice_rate_not_supported_help(tts_server, voice_name):
    """
    Return the help for the disabled speed selector when the provider has no
    numeric speed parameter (Gemini TTS, MiMo TTS and VoxCPM), or "" when it
    applies the speed. The disabled selector keeps the saved speed.
    """
    if tts_server == "gemini-tts" or (voice_name and voice.is_gemini_voice(voice_name)):
        return tr("Gemini TTS Speed Not Supported")
    if tts_server == "mimo-tts" or (voice_name and voice.is_mimo_voice(voice_name)):
        return tr("MiMo TTS Speed Not Supported")
    if tts_server == "voxcpm" or (voice_name and voice.is_voxcpm_voice(voice_name)):
        return tr("VoxCPM Speed Not Supported")
    return ""


def _render_audio_settings(panel, params):
    """渲染音频设置并返回上传音频与当前配音模式。"""
    with panel:
        with st.container(border=True):
            st.write(tr("Audio Settings"))

            # 配音方式是音频设置的一级状态，负责明确区分自动配音、用户上传和无配音。
            # 旧配置没有 voice_mode 时，根据原 tts_server 的无配音哨兵保持兼容。
            saved_tts_server = config.ui.get("tts_server", "azure-tts-v1")
            saved_voice_mode = config.ui.get("voice_mode")
            if saved_voice_mode not in {
                VOICE_MODE_TTS,
                VOICE_MODE_UPLOAD,
                VOICE_MODE_NONE,
            }:
                saved_voice_mode = (
                    VOICE_MODE_NONE
                    if saved_tts_server == voice.NO_VOICE_NAME
                    else VOICE_MODE_TTS
                )
            voice_mode_options = [VOICE_MODE_TTS, VOICE_MODE_UPLOAD, VOICE_MODE_NONE]
            voice_mode_labels = {
                VOICE_MODE_TTS: tr("Automatic Voiceover"),
                VOICE_MODE_UPLOAD: tr("Upload Voiceover"),
                VOICE_MODE_NONE: tr("No Voiceover"),
            }
            voice_mode = stable_segmented_control(
                tr("Voiceover Mode"),
                options=voice_mode_options,
                default_value=saved_voice_mode,
                key="voice_mode_control",
                format_func=lambda value: voice_mode_labels[value],
                width="stretch",
            )
            _set_runtime_config("ui", "voice_mode", voice_mode)
            tts_mode_enabled = voice_mode == VOICE_MODE_TTS

            # 配音服务与备用链在服务商配置页统一维护；这里按已保存的服务
            # 渲染音色列表等生成参数，不再提供服务下拉与 Key 输入。
            tts_server_values = [server_id for server_id, _ in TTS_SERVER_OPTIONS]
            if saved_tts_server not in tts_server_values:
                saved_tts_server = "azure-tts-v1"
            selected_tts_server = saved_tts_server

            _set_runtime_config("ui", "tts_server", selected_tts_server)

            # 服务说明紧跟 Provider 选择，先告诉用户需要准备什么，再进入音色和
            # 凭证配置。没有说明的 Provider 不渲染空提示块。
            if tts_mode_enabled:
                provider_tips = get_tts_provider_tips(selected_tts_server)
                if provider_tips:
                    st.info(provider_tips)

            # MiniMax 的音色目录在服务商配置页主动刷新；这里从会话缓存
            # 读取，未刷新时仍保留配置的 Voice ID 供选择。
            minimax_voices = []
            minimax_voice_labels = {}
            if tts_mode_enabled and selected_tts_server == "minimax-tts":
                minimax_voices, minimax_voice_labels = _get_minimax_voice_options()

            # 根据选择的TTS服务器获取声音列表
            filtered_voices = []
            saved_voice_name = config.ui.get("voice_name", "")

            if not tts_mode_enabled:
                # 上传音频和无配音模式不加载远程音色，减少无意义的网络请求和界面噪音。
                filtered_voices = []
            elif selected_tts_server == "siliconflow":
                # 获取硅基流动的声音列表
                filtered_voices = voice.get_siliconflow_voices()
            elif selected_tts_server == "gemini-tts":
                # 获取Gemini TTS的声音列表
                filtered_voices = voice.get_gemini_voices()
            elif selected_tts_server == "mimo-tts":
                # 获取 Xiaomi MiMo TTS 的预置音色列表
                filtered_voices = voice.get_mimo_voices()
            elif selected_tts_server == "minimax-tts":
                filtered_voices = minimax_voices
            elif selected_tts_server == "elevenlabs":
                # Key 在服务商配置页维护；这里读取配置/环境变量加载音色列表。
                saved_elevenlabs_api_key = str(
                    config.elevenlabs.get("api_key", "")
                    or os.getenv("ELEVENLABS_API_KEY", "")
                    or ""
                ).strip()
                cache_key = f"elevenlabs_voices_{saved_elevenlabs_api_key}"
                if cache_key not in st.session_state:
                    st.session_state[cache_key] = voice.get_elevenlabs_voices(
                        saved_elevenlabs_api_key
                    )
                filtered_voices = st.session_state[cache_key]
            elif selected_tts_server == "chatterbox":
                # 自托管 Chatterbox 服务的预置音色（[chatterbox] voices 在服务商配置页维护）
                filtered_voices = voice.get_chatterbox_voices()
            elif selected_tts_server == "kokoro":
                # 自托管 Kokoro 服务的音色：[kokoro] voices 为空时从服务端 /audio/voices 读取
                filtered_voices = _get_kokoro_voice_options(saved_voice_name)
            elif selected_tts_server == "fish_audio":
                filtered_voices = voice.get_fish_audio_voices()
            elif selected_tts_server == "voxcpm":
                filtered_voices = voice.get_voxcpm_voices()
            else:
                # 获取Azure的声音列表
                all_voices = voice.get_all_azure_voices(filter_locals=None)

                # 根据选择的TTS服务器筛选声音
                for v in all_voices:
                    if selected_tts_server == "azure-tts-v2":
                        # V2版本的声音名称中包含"v2"
                        if "V2" in v:
                            filtered_voices.append(v)
                    else:
                        # V1版本的声音名称中不包含"v2"
                        if "V2" not in v:
                            filtered_voices.append(v)

            def _friendly(v):
                if voice.is_no_voice(v):
                    return tr("No Voice Selected")
                if voice.is_elevenlabs_voice(v):
                    parts = v.split(":", 2)
                    return parts[2] if len(parts) >= 3 else v
                if voice.is_chatterbox_voice(v) or voice.is_kokoro_voice(v):
                    name = v.split(":", 1)[1] if ":" in v else v
                    return name.replace("-Female", "").replace("-Male", "")
                if voice.is_minimax_voice(v):
                    return minimax_voice_labels.get(v, v.split(":", 1)[1])
                if voice.is_fish_audio_voice(v):
                    parts = v.split(":", 2)
                    display_name = parts[2] if len(parts) >= 3 else v
                    return (
                        display_name.replace("Female", tr("Female"))
                        .replace("Male", tr("Male"))
                    )
                if voice.is_voxcpm_voice(v):
                    return v.split(":", 1)[1] or DEFAULT_VOXCPM_VOICE
                return (
                    v.replace("Female", tr("Female"))
                    .replace("Male", tr("Male"))
                    .replace("Neural", "")
                )

            friendly_names = {v: _friendly(v) for v in filtered_voices}

            # Gemini 旧目录把推测的性别放在值里（例如 Charon-Male）。按基础
            # voice name 映射到新的官方风格值，升级后继续保留用户原来的音色。
            if (
                selected_tts_server == "gemini-tts"
                and saved_voice_name not in friendly_names
            ):
                saved_gemini_voice = voice.parse_gemini_voice_name(saved_voice_name)
                saved_voice_name = next(
                    (
                        candidate
                        for candidate in filtered_voices
                        if voice.parse_gemini_voice_name(candidate)
                        == saved_gemini_voice
                    ),
                    saved_voice_name,
                )

            saved_voice_name_index = 0

            # 检查保存的声音是否在当前筛选的声音列表中
            if saved_voice_name in friendly_names:
                saved_voice_name_index = list(friendly_names.keys()).index(
                    saved_voice_name
                )
            else:
                # 如果不在，则根据当前UI语言选择一个默认声音
                for i, v in enumerate(filtered_voices):
                    if v.lower().startswith(st.session_state["ui_language"].lower()):
                        saved_voice_name_index = i
                        break

            # 如果没有找到匹配的声音，使用第一个声音
            if saved_voice_name_index >= len(friendly_names) and friendly_names:
                saved_voice_name_index = 0

            # 确保有声音可选
            if tts_mode_enabled and friendly_names:
                voice_name = stable_selectbox(
                    tr("Voiceover Voice"),
                    options=list(friendly_names.keys()),
                    default_value=list(friendly_names.keys())[saved_voice_name_index],
                    key=f"speech_synthesis_select_{selected_tts_server}",
                    format_func=lambda value: friendly_names.get(
                        value,
                        str(value).removeprefix("minimax:"),
                    ),
                    # MiniMax 支持用户直接输入列表外的克隆或生成音色 ID；其它
                    # Provider 维持原选择器行为，不扩大本次修改的影响范围。
                    accept_new_options=selected_tts_server == "minimax-tts",
                )

                if selected_tts_server == "minimax-tts":
                    custom_voice_id = str(voice_name or "").strip()
                    if custom_voice_id and not voice.is_minimax_voice(custom_voice_id):
                        voice_name = f"minimax:{custom_voice_id}"
                    if voice.is_minimax_voice(voice_name):
                        _set_runtime_config(
                            "minimax_tts",
                            "voice_id",
                            voice_name.split(":", 1)[1],
                        )

                params.voice_name = voice_name
                if not voice.is_no_voice(voice_name):
                    # 占位 sentinel 仅用于非自动模式的禁用展示，不覆盖用户上一次
                    # 真正选择的音色，切回自动配音后可以恢复原设置。
                    _set_runtime_config("ui", "voice_name", voice_name)
            elif tts_mode_enabled:
                # 如果没有声音可选，显示提示信息
                st.warning(
                    tr(
                        "No voices available for the selected TTS server. Please select another server."
                    )
                )
                voice_name = ""
                params.voice_name = ""
                _set_runtime_config("ui", "voice_name", "")
            else:
                # 非自动配音模式不显示音色控件，只复用保存值维持参数结构稳定。
                voice_name = saved_voice_name or voice.NO_VOICE_NAME
                params.voice_name = voice_name

            # 各配音服务的凭证与端点已集中在服务商配置页维护；音频面板只
            # 保留本次任务的生成参数（音色/语速/音量/试听/参考音频等）。
            if tts_mode_enabled and (
                selected_tts_server == "voxcpm"
                or (voice_name and voice.is_voxcpm_voice(voice_name))
            ):
                uploaded_reference_audio = st.file_uploader(
                    tr("VoxCPM Reference Audio"),
                    type=list(voice.VOXCPM_REFERENCE_AUDIO_FILE_TYPES),
                    key="voxcpm_reference_audio_uploader",
                    help=tr("VoxCPM Reference Audio Help"),
                )
                reference_audio = _sync_voxcpm_reference_audio(
                    uploaded_reference_audio
                )
                st.caption(tr("VoxCPM Reference Audio Notice"))
                reference_audio_error = st.session_state.get(
                    VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY
                )
                if reference_audio_error:
                    st.error(
                        tr("VoxCPM Reference Audio Invalid").format(
                            error=reference_audio_error
                        )
                    )

                if reference_audio:
                    high_fidelity_enabled = st.toggle(
                        tr("VoxCPM High Fidelity Delivery"),
                        key=VOXCPM_HIGH_FIDELITY_SESSION_KEY,
                        help=tr("VoxCPM High Fidelity Delivery Help"),
                    )
                    if high_fidelity_enabled:
                        use_separate_prompt_audio = st.toggle(
                            tr("VoxCPM Separate Prompt Audio"),
                            key=VOXCPM_SEPARATE_PROMPT_AUDIO_SESSION_KEY,
                            help=tr("VoxCPM Separate Prompt Audio Help"),
                        )
                        _sync_voxcpm_prompt_example_mode(use_separate_prompt_audio)
                        if use_separate_prompt_audio:
                            prompt_audio_file = st.file_uploader(
                                tr("VoxCPM Prompt Audio"),
                                type=list(voice.VOXCPM_REFERENCE_AUDIO_FILE_TYPES),
                                key="voxcpm_prompt_audio_uploader",
                                help=tr("VoxCPM Prompt Audio Help"),
                            )
                            _sync_voxcpm_prompt_audio(prompt_audio_file)
                        else:
                            _clear_voxcpm_separate_prompt_audio()
                        effective_prompt_audio = _get_voxcpm_effective_prompt_audio()
                        if st.button(
                            tr("Transcribe VoxCPM Prompt Audio"),
                            key="transcribe_voxcpm_prompt_audio_button",
                            icon=":material/transcribe:",
                            help=tr("Transcribe VoxCPM Prompt Audio Help"),
                            use_container_width=True,
                            disabled=not bool(effective_prompt_audio),
                        ):
                            try:
                                with st.spinner(tr("Transcribing VoxCPM Prompt Audio")):
                                    recognized_text = subtitle.transcribe_audio_bytes(
                                        effective_prompt_audio
                                    )
                            except Exception:
                                logger.exception(
                                    "failed to transcribe VoxCPM prompt audio"
                                )
                                recognized_text = ""
                            if recognized_text:
                                st.session_state[VOXCPM_PROMPT_TEXT_SESSION_KEY] = (
                                    recognized_text
                                )
                                st.toast(tr("VoxCPM Prompt Audio Transcribed"))
                            else:
                                st.error(tr("VoxCPM Prompt Audio Transcription Failed"))
                        st.text_area(
                            tr("VoxCPM Prompt Text"),
                            key=VOXCPM_PROMPT_TEXT_SESSION_KEY,
                            help=tr("VoxCPM Prompt Text Help"),
                            height=100,
                        )
                        st.caption(tr("VoxCPM Prompt Transcript Review"))
                        prompt_error = _get_voxcpm_prompt_validation_error()
                        if prompt_error:
                            st.error(
                                tr("VoxCPM Prompt Invalid").format(
                                    error=prompt_error
                                )
                            )
                    else:
                        _clear_voxcpm_prompt_state()

            # Chatterbox/Kokoro 等自托管服务的凭证与端点已在服务商配置页维护；
            # 音频面板只按已保存配置渲染音色列表。

            # 三种模式只渲染当前任务真正需要的控件。自动配音可调音量和语速；
            # 上传音频只需要文件和音量；无配音不再展示无效设置。
            params.voice_name = (
                voice.NO_VOICE_NAME if voice_mode == VOICE_MODE_NONE else voice_name
            )
            params.voice_volume = 1.0
            params.voice_rate = 1.0
            uploaded_audio_file = None
            voice_volume_options = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0]
            voice_rate_options = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0]

            if tts_mode_enabled:
                voice_control_cols = st.columns(2)
                with voice_control_cols[0]:
                    params.voice_volume = stable_selectbox(
                        tr("Voiceover Volume"),
                        options=voice_volume_options,
                        default_value=_saved_ui_choice(
                            "voice_volume", voice_volume_options, 1.0
                        ),
                        key="voice_volume_select",
                        format_func=lambda value: f"{int(value * 100)}%",
                        help=tr("Voiceover Volume Help"),
                    )

                with voice_control_cols[1]:
                    speed_not_supported_help = _voice_rate_not_supported_help(
                        selected_tts_server, voice_name
                    )
                    params.voice_rate = stable_selectbox(
                        tr("Voiceover Speed"),
                        options=voice_rate_options,
                        default_value=_saved_ui_choice(
                            "voice_rate", voice_rate_options, 1.0
                        ),
                        key="voice_rate_select",
                        format_func=lambda value: f"{value:.1f}×",
                        help=speed_not_supported_help or tr("Voiceover Speed Help"),
                        disabled=bool(speed_not_supported_help),
                    )
                _set_runtime_config("ui", "voice_volume", params.voice_volume)
                _set_runtime_config("ui", "voice_rate", params.voice_rate)

                # 试听必须位于音量和语速控件之后，确保调用使用当前控件值。
                _render_voice_preview(
                    params,
                    friendly_names,
                    selected_tts_server,
                    voice_name,
                )
            elif voice_mode == VOICE_MODE_UPLOAD:
                custom_audio_file_types = sorted(
                    extension.removeprefix(".") for extension in CUSTOM_AUDIO_EXTENSIONS
                )
                uploaded_audio_file = st.file_uploader(
                    tr("Upload Voiceover File"),
                    type=custom_audio_file_types
                    + [file_type.upper() for file_type in custom_audio_file_types],
                    accept_multiple_files=False,
                    key="custom_audio_file_uploader",
                    help=tr("Upload Voiceover File Help"),
                )
                params.voice_volume = stable_selectbox(
                    tr("Voiceover Volume"),
                    options=voice_volume_options,
                    default_value=_saved_ui_choice(
                        "voice_volume", voice_volume_options, 1.0
                    ),
                    key="voice_volume_select",
                    format_func=lambda value: f"{int(value * 100)}%",
                    help=tr("Voiceover Volume Help"),
                )
                _set_runtime_config("ui", "voice_volume", params.voice_volume)
                if uploaded_audio_file:
                    st.audio(uploaded_audio_file, format="audio/mp3")
                    st.info(
                        tr(
                            "Custom audio will be used directly. TTS synthesis will be skipped for this task."
                        )
                    )
            uploaded_bgm_file = _render_background_music_settings(params)
    return uploaded_audio_file, uploaded_bgm_file, voice_mode


def _render_subtitle_settings(panel, params):
    """渲染字幕设置并更新生成参数。"""
    with panel:
        with st.container(border=True):
            st.write(tr("Subtitle Settings"))
            st.session_state.setdefault(
                "subtitle_enabled_checkbox",
                _saved_ui_bool(
                    "subtitle_enabled",
                    DEFAULT_SUBTITLE_SETTINGS["subtitle_enabled"],
                ),
            )
            params.subtitle_enabled = st.checkbox(
                tr("Enable Subtitles"),
                key="subtitle_enabled_checkbox",
            )
            _set_runtime_config("ui", "subtitle_enabled", params.subtitle_enabled)
            subtitle_settings_disabled = not params.subtitle_enabled
            font_names = get_all_fonts()
            saved_font_name = config.ui.get(
                "font_name", DEFAULT_SUBTITLE_SETTINGS["font_name"]
            )
            saved_font_name_index = 0
            if saved_font_name in font_names:
                saved_font_name_index = font_names.index(saved_font_name)
            params.font_name = stable_selectbox(
                tr("Font"),
                options=font_names,
                default_value=font_names[saved_font_name_index] if font_names else "",
                key="font_name_select",
                disabled=subtitle_settings_disabled,
            )
            _set_runtime_config("ui", "font_name", params.font_name)

            subtitle_positions = [
                (tr("Top"), "top"),
                (tr("Center"), "center"),
                (tr("Bottom"), "bottom"),
                (tr("2/3 from Bottom"), "two_thirds_bottom"),
                (tr("Custom"), "custom"),
            ]
            saved_subtitle_position = config.ui.get(
                "subtitle_position", DEFAULT_SUBTITLE_SETTINGS["subtitle_position"]
            )
            saved_position_index = 2
            for i, (_, pos_value) in enumerate(subtitle_positions):
                if pos_value == saved_subtitle_position:
                    saved_position_index = i
                    break
            selected_subtitle_position = stable_selectbox(
                tr("Position"),
                options=[value for _, value in subtitle_positions],
                default_value=subtitle_positions[saved_position_index][1],
                key="subtitle_position_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in subtitle_positions
                ).get(value, value),
                disabled=subtitle_settings_disabled,
            )
            params.subtitle_position = selected_subtitle_position
            _set_runtime_config("ui", "subtitle_position", params.subtitle_position)

            # Subtitle Display Mode (Sentence vs Single Word)
            subtitle_display_modes = [
                (tr("Sentence by Sentence"), "sentence"),
                (tr("Single Word (Word by Word)"), "word_by_word"),
            ]
            saved_display_mode = config.ui.get(
                "subtitle_display_mode",
                DEFAULT_SUBTITLE_SETTINGS["subtitle_display_mode"],
            )
            saved_mode_idx = 0
            for i, (_, mode_val) in enumerate(subtitle_display_modes):
                if mode_val == saved_display_mode:
                    saved_mode_idx = i
                    break
            selected_display_mode = stable_selectbox(
                tr("Display Mode"),
                options=[val for _, val in subtitle_display_modes],
                default_value=subtitle_display_modes[saved_mode_idx][1],
                key="subtitle_display_mode_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in subtitle_display_modes
                ).get(value, value),
                help=tr("Word-by-word Timing Help"),
                disabled=subtitle_settings_disabled,
            )
            params.subtitle_display_mode = selected_display_mode
            _set_runtime_config(
                "ui", "subtitle_display_mode", params.subtitle_display_mode
            )

            # Subtitle Animation (None vs Pop Spring)
            subtitle_animations = [
                (tr("None (Animation)"), "none"),
                (tr("Pop Up (Spring)"), "pop_spring"),
            ]
            saved_anim = config.ui.get(
                "subtitle_animation",
                DEFAULT_SUBTITLE_SETTINGS["subtitle_animation"],
            )
            saved_anim_idx = 0
            for i, (_, anim_val) in enumerate(subtitle_animations):
                if anim_val == saved_anim:
                    saved_anim_idx = i
                    break
            selected_anim = stable_selectbox(
                tr("Subtitle Animation"),
                options=[val for _, val in subtitle_animations],
                default_value=subtitle_animations[saved_anim_idx][1],
                key="subtitle_animation_select",
                format_func=lambda value: dict(
                    (v, label) for label, v in subtitle_animations
                ).get(value, value),
                disabled=subtitle_settings_disabled,
            )
            params.subtitle_animation = selected_anim
            _set_runtime_config(
                "ui", "subtitle_animation", params.subtitle_animation
            )

            if params.subtitle_position == "custom":
                saved_custom_position = config.ui.get(
                    "custom_position", DEFAULT_SUBTITLE_SETTINGS["custom_position"]
                )
                st.session_state.setdefault(
                    "custom_position_input", str(saved_custom_position)
                )
                custom_position = st.text_input(
                    tr("Custom Position (% from top)"),
                    key="custom_position_input",
                    disabled=subtitle_settings_disabled,
                )
                try:
                    params.custom_position = float(custom_position)
                    if params.custom_position < 0 or params.custom_position > 100:
                        st.error(tr("Please enter a value between 0 and 100"))
                    else:
                        _set_runtime_config(
                            "ui", "custom_position", params.custom_position
                        )
                except ValueError:
                    st.error(tr("Please enter a valid number"))

            # 非中文语言的颜色标签通常比中文更长。为颜色选择器保留适当宽度，
            # 避免标签换行，同时仍给字号滑块保留足够的可操作空间。
            font_cols = st.columns([0.42, 0.58])
            with font_cols[0]:
                saved_text_fore_color = config.ui.get(
                    "text_fore_color", DEFAULT_SUBTITLE_SETTINGS["text_fore_color"]
                )
                st.session_state.setdefault("font_color_picker", saved_text_fore_color)
                params.text_fore_color = st.color_picker(
                    tr("Font Color"),
                    key="font_color_picker",
                    disabled=subtitle_settings_disabled,
                )
                _set_runtime_config("ui", "text_fore_color", params.text_fore_color)

            with font_cols[1]:
                saved_font_size = config.ui.get(
                    "font_size", DEFAULT_SUBTITLE_SETTINGS["font_size"]
                )
                st.session_state.setdefault("font_size_slider", saved_font_size)
                params.font_size = st.slider(
                    tr("Font Size"),
                    30,
                    100,
                    key="font_size_slider",
                    disabled=subtitle_settings_disabled,
                )
                _set_runtime_config("ui", "font_size", params.font_size)

            stroke_cols = st.columns([0.42, 0.58])
            with stroke_cols[0]:
                st.session_state.setdefault(
                    "stroke_color_picker",
                    _saved_ui_color(
                        "stroke_color", DEFAULT_SUBTITLE_SETTINGS["stroke_color"]
                    ),
                )
                params.stroke_color = st.color_picker(
                    tr("Stroke Color"),
                    key="stroke_color_picker",
                    disabled=subtitle_settings_disabled,
                )
                _set_runtime_config("ui", "stroke_color", params.stroke_color)
            with stroke_cols[1]:
                st.session_state.setdefault(
                    "stroke_width_slider",
                    _saved_ui_number(
                        "stroke_width",
                        DEFAULT_SUBTITLE_SETTINGS["stroke_width"],
                        0.0,
                        10.0,
                    ),
                )
                params.stroke_width = st.slider(
                    tr("Stroke Width"),
                    0.0,
                    10.0,
                    key="stroke_width_slider",
                    disabled=subtitle_settings_disabled,
                )
                _set_runtime_config("ui", "stroke_width", params.stroke_width)

            # 背景开关的本地化名称普遍比颜色标签更长，因此让开关占据略多空间。
            subtitle_bg_cols = st.columns([0.55, 0.45])
            saved_subtitle_background_enabled = config.ui.get(
                "subtitle_background_enabled",
                DEFAULT_SUBTITLE_SETTINGS["subtitle_background_enabled"],
            )
            st.session_state.setdefault(
                "subtitle_background_enabled_checkbox",
                saved_subtitle_background_enabled,
            )
            with subtitle_bg_cols[0]:
                subtitle_background_enabled = st.checkbox(
                    tr("Enable Subtitle Background"),
                    key="subtitle_background_enabled_checkbox",
                    disabled=subtitle_settings_disabled,
                )
            _set_runtime_config(
                "ui",
                "subtitle_background_enabled",
                subtitle_background_enabled,
            )

            # 背景颜色和圆角样式都从属于字幕背景开关。子控件始终保留在页面中，
            # 父开关关闭时统一禁用，避免一个控件消失而另一个控件禁用造成布局跳动。
            # 颜色值仍保存在 UI 配置中，重新启用背景后可以恢复用户之前的选择；
            # 传给生成服务的参数则设为 False，确保关闭状态不会实际渲染背景。
            saved_subtitle_background_color = config.ui.get(
                "subtitle_background_color",
                DEFAULT_SUBTITLE_SETTINGS["subtitle_background_color"],
            )
            st.session_state.setdefault(
                "subtitle_background_color_picker",
                saved_subtitle_background_color,
            )
            with subtitle_bg_cols[1]:
                selected_subtitle_background_color = st.color_picker(
                    tr("Subtitle Background Color"),
                    key="subtitle_background_color_picker",
                    disabled=subtitle_settings_disabled
                    or not subtitle_background_enabled,
                )
            _set_runtime_config(
                "ui",
                "subtitle_background_color",
                selected_subtitle_background_color,
            )
            params.text_background_color = (
                selected_subtitle_background_color
                if subtitle_background_enabled
                else False
            )

            saved_rounded_subtitle_background = config.ui.get(
                "rounded_subtitle_background",
                DEFAULT_SUBTITLE_SETTINGS["rounded_subtitle_background"],
            )
            # 背景关闭时，圆角背景没有可渲染的底色。这里禁用控件但保留原配置，
            # 用户下次重新开启字幕背景后，可以继续使用之前保存的圆角偏好。
            rounded_background_disabled = (
                subtitle_settings_disabled or not subtitle_background_enabled
            )
            st.session_state.setdefault(
                "rounded_subtitle_background_checkbox",
                saved_rounded_subtitle_background,
            )
            selected_rounded_subtitle_background = st.checkbox(
                tr("Rounded Subtitle Background"),
                help=tr("Rounded Subtitle Background Help"),
                disabled=rounded_background_disabled,
                key="rounded_subtitle_background_checkbox",
            )
            params.rounded_subtitle_background = (
                selected_rounded_subtitle_background
                if subtitle_background_enabled
                else False
            )
            if not subtitle_settings_disabled and subtitle_background_enabled:
                _set_runtime_config(
                    "ui",
                    "rounded_subtitle_background",
                    selected_rounded_subtitle_background,
                )

            if video.subtitle_colors_are_indistinguishable(params):
                # 同色配置仍然是合法的用户选择，因此只在字幕设置区域就近提示，
                # 不阻止生成。用户可以根据实际视觉需求决定是否继续。
                st.warning(tr("Subtitle Colors Are Indistinguishable"))

            subtitle_preview_text = params.video_script or params.video_subject
            selected_font_path = os.path.join(font_dir, params.font_name)
            if (
                params.subtitle_enabled
                and subtitle_preview_text
                and not video.subtitle_font_supports_text(
                    selected_font_path, subtitle_preview_text
                )
            ):
                st.warning(tr("Subtitle Font Does Not Support Text"))

            if st.button(
                tr("Restore Default Subtitle Settings"),
                key="restore_default_subtitle_settings",
                icon=":material/restart_alt:",
                on_click=reset_subtitle_settings,
                use_container_width=True,
            ):
                st.toast(tr("Default Subtitle Settings Restored"))


def _stage_task_audio(audio_path, audio_bytes):
    """Publish task-local audio only after the complete write succeeds."""
    descriptor = None
    staged_path = None
    try:
        descriptor, staged_path = tempfile.mkstemp(
            dir=os.path.dirname(audio_path), prefix=".task-audio-", suffix=".tmp"
        )
        with os.fdopen(descriptor, "wb") as file:
            descriptor = None  # The file context now owns the descriptor.
            file.write(audio_bytes)
        os.replace(staged_path, audio_path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if staged_path is not None:
            try:
                os.unlink(staged_path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning(f"failed to remove staged task audio: {exc}")


def _render_generation_controls(
    params, uploaded_files, uploaded_audio_file, uploaded_bgm_file, voice_mode,
    panel=None,
):
    """
    校验生成依赖、提交任务，并渲染日志与成片结果。

    返回本次页面执行是否成功提交了新任务。提交前已经请求非阻塞保存，调用方
    据此跳过页面末尾的重复请求。主脚本必须及时结束，定时 Fragment 才能持续
    刷新进度和任务日志。
    """
    # panel 非空时渲染进中列底部常驻操作栏；为空保持旧的当前上下文行为。
    with contextlib.nullcontext() if panel is None else panel:
        restore_upload_requirements = st.session_state.get(
            "task_restore_upload_requirements", {}
        )
        has_local_materials = bool(
            uploaded_files or st.session_state.get("local_video_materials", [])
        )
        has_custom_audio = bool(uploaded_audio_file)
        unmet_restore_requirements = _get_unmet_restore_upload_requirements(
            restore_upload_requirements,
            video_source=params.video_source,
            voice_name=params.voice_name or "",
            has_local_materials=has_local_materials,
            has_custom_audio=has_custom_audio,
            voice_mode=voice_mode,
        )
        if "local_materials" in unmet_restore_requirements:
            st.warning(tr("Task Restore Local Materials Warning"))
        if "custom_audio" in unmet_restore_requirements:
            st.warning(tr("Task Restore Custom Audio Warning"))
        if restore_upload_requirements and not unmet_restore_requirements:
            # 用户已重新上传文件，或主动切换了素材来源/音色。此时历史任务的上传依赖
            # 已经得到明确处理，清除标记，避免后续普通生成继续显示旧提示。
            st.session_state.pop("task_restore_upload_requirements", None)

        _render_settings_transfer(params)

        generation_busy = _generation_is_busy(_current_generation_task_id())
        project_locked = _project_is_locked()
        # 脚本方案页的「确认并生成」与主按钮共用同一条提交链路：
        # 方案页先渲染，把 confirmed 方案写入会话，这里同一次 rerun 消费。
        plan_generate_requested = bool(
            st.session_state.pop("plan_generate_requested", False)
        )
        start_button = st.button(
            tr("Generating Video") if generation_busy else tr("Generate Video"),
            use_container_width=True,
            type="primary",
            key="generate_video_button",
            on_click=_prepare_generation_task,
            disabled=generation_busy or project_locked,
            help=(
                tr("Project Locked Generate Help")
                if project_locked
                else tr("Generate Video Route Help")
            ),
        )
        render_onboarding_tour()
        if start_button or plan_generate_requested:
            if plan_generate_requested:
                _prepare_generation_task()
            _save_runtime_config()
            task_id = st.session_state.get("pending_generation_task_id") or str(uuid4())
            execute_payload = st.session_state.pop("script_plan_execute_payload", None)
            if execute_payload is not None:
                # 方案驱动执行（B4/B5）：携带 confirmed 方案时旁白由方案
                # 编译，素材源/画幅/音色随方案对齐；快速路径零变化。
                try:
                    params.script_plan = ScriptPlan.model_validate(execute_payload)
                except ValidationError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"plan execute payload rejected: {exc}")
                    st.error(tr("Plan Execute Invalid"))
                    st.stop()
                exec_plan = params.script_plan
                params.video_subject = (
                    exec_plan.title or exec_plan.logline or task_id
                )
                params.video_aspect = VideoAspect(exec_plan.aspect)
                params.plan_target_duration = exec_plan.target_duration
                params.voice_name = exec_plan.voice.name
                params.voice_rate = exec_plan.voice.rate
                if all(
                    scene.engine in {"local_fl2v", "local_i2v"}
                    for scene in exec_plan.scenes
                ):
                    params.video_source = "local"
                elif params.video_source not in {"pexels", "pixabay", "coverr"}:
                    params.video_source = "pexels"
            _add_active_generation_task(
                task_id,
                subject=params.video_subject or params.video_script or task_id,
            )
            if not params.video_subject and not params.video_script:
                _remove_active_generation_task(task_id)
                st.error(tr("Video Script and Subject Cannot Both Be Empty"))
                st.stop()

            voxcpm_reference_audio = None
            voxcpm_prompt_audio = None
            voxcpm_prompt_text = ""
            if voice.is_voxcpm_voice(params.voice_name or ""):
                reference_audio_error = st.session_state.get(
                    VOXCPM_REFERENCE_AUDIO_ERROR_SESSION_KEY
                )
                if reference_audio_error:
                    _remove_active_generation_task(task_id)
                    st.error(
                        tr("VoxCPM Reference Audio Invalid").format(
                            error=reference_audio_error
                        )
                    )
                    st.stop()
                voxcpm_reference_audio = _get_voxcpm_reference_audio()
                prompt_validation_error = _get_voxcpm_prompt_validation_error()
                if prompt_validation_error:
                    _remove_active_generation_task(task_id)
                    st.error(
                        tr("VoxCPM Prompt Invalid").format(
                            error=prompt_validation_error
                        )
                    )
                    st.stop()
                voxcpm_prompt_audio = _get_voxcpm_effective_prompt_audio()
                voxcpm_prompt_text = _get_voxcpm_prompt_text()

            if params.video_source not in [
                "infistar",
                "jalapeno",
                "pexels",
                "pixabay",
                "coverr",
                "wavespeed",
                "volcengine_seedance",
                "ofox",
                "metaso_minimax",
                "muapi",
                "loomloom",
                "openai_image",
                "codex_image",
                "pexels_image",
                "pixabay_image",
                "local",
            ]:
                _remove_active_generation_task(task_id)
                st.error(tr("Please Select a Valid Video Source"))
                st.stop()

            if params.video_source == "pexels" and not config.app.get(
                "pexels_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Pexels API Key"))
                st.stop()

            if params.video_source == "pixabay" and not config.app.get(
                "pixabay_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Pixabay API Key"))
                st.stop()

            if params.video_source == "pexels_image" and not config.app.get(
                "pexels_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Pexels API Key"))
                st.stop()

            if params.video_source == "pixabay_image" and not config.app.get(
                "pixabay_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Pixabay API Key"))
                st.stop()

            if params.video_source == "coverr" and not config.app.get(
                "coverr_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Coverr API Key"))
                st.stop()

            if params.video_source == "wavespeed" and not config.app.get(
                "wavespeed_api_keys", ""
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the WaveSpeed API Key"))
                st.stop()

            if params.video_source == "wavespeed" and not st.session_state.get(
                "wavespeed_confirm_charge", False
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Confirm WaveSpeed Charge Required"))
                st.stop()

            if params.video_source == "volcengine_seedance" and not (
                volcengine_seedance.is_enabled(
                    config.snapshot_config_with_pending(config.app)
                )
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Volcano Engine Ark API Key"))
                st.stop()

            if params.video_source == "volcengine_seedance" and not st.session_state.get(
                "volcengine_seedance_confirm_charge", False
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Confirm Volcano Engine Seedance Charge Required"))
                st.stop()

            if params.video_source == "jalapeno":
                try:
                    snapshot = config.snapshot_config_with_pending(config.app)
                    jalapeno_video_endpoint = jalapeno_video.endpoint(snapshot)
                    if (not st.session_state.get("jalapeno_confirm_charge", False)
                            or _jalapeno_charge_signature(params, snapshot)
                            != st.session_state.get("jalapeno_charge_signature")):
                        raise jalapeno_video.JalapenoVideoError(tr("Confirm Jalapeno Cloud Charge Required"))
                except jalapeno_video.JalapenoVideoError as exc:
                    _remove_active_generation_task(task_id)
                    st.error(str(exc))
                    st.stop()

            if params.video_source == "infistar":
                try:
                    snapshot = config.snapshot_config_with_pending(config.app)
                    if not infistar_video.is_enabled(snapshot):
                        raise infistar_video.InfistarVideoError(tr("Please Enter the Infistar API Key"))
                    infistar_video.model_id(snapshot)
                    if not st.session_state.get("infistar_confirm_charge", False):
                        raise infistar_video.InfistarVideoError(tr("Confirm Infistar Charge Required"))
                except infistar_video.InfistarVideoError as exc:
                    _remove_active_generation_task(task_id)
                    st.error(str(exc))
                    st.stop()

            if params.video_source == "ofox" and not (
                ofox.is_enabled(config.snapshot_config_with_pending(config.app))
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the OFox API Key"))
                st.stop()

            if params.video_source == "ofox" and not st.session_state.get(
                "ofox_confirm_charge", False
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Confirm OFox Charge Required"))
                st.stop()

            if params.video_source == "metaso_minimax" and not (
                metaso_minimax.is_enabled(
                    config.snapshot_config_with_pending(config.app)
                )
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the Metaso MiniMax API Key"))
                st.stop()

            if params.video_source == "metaso_minimax" and not st.session_state.get(
                "metaso_minimax_confirm_charge", False
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Confirm Metaso MiniMax Charge Required"))
                st.stop()

            if params.video_source == "muapi" and not (
                muapi.is_enabled(config.snapshot_config_with_pending(config.app))
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Enter the MuAPI API Key"))
                st.stop()

            if params.video_source == "muapi" and not st.session_state.get(
                "muapi_confirm_charge", False
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Confirm MuAPI Charge Required"))
                st.stop()

            if params.video_source == "codex_image":
                from app.services import codex_image, codex_oauth

                try:
                    codex_image.capture_context(
                        config.snapshot_config_with_pending(config.app)
                    )
                except codex_oauth.CodexError as error:
                    _remove_active_generation_task(task_id)
                    st.error(tr(error.key).format(**error.params))
                    st.stop()

            if params.video_source == "openai_image" and not material.is_openai_image_enabled(
                config.snapshot_config_with_pending(config.app)
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Please Configure the OpenAI Image Source"))
                st.stop()

            loomloom_video_request = None
            if params.video_source == "loomloom":
                current_batch, current_signature = _current_loomloom_video_quote_context(
                    params
                )
                quoted_batch = st.session_state.get("loomloom_video_batch")
                quote_result = st.session_state.get("loomloom_video_quote")
                quote_is_current = bool(
                    current_batch is not None
                    and isinstance(quoted_batch, loomloom.LoomLoomVideoBatch)
                    and quote_result is not None
                    and st.session_state.get("loomloom_video_input_signature")
                    == current_signature
                )
                if not quote_is_current:
                    _remove_active_generation_task(task_id)
                    st.error(tr("AI Video Quote Required"))
                    st.stop()
                if not st.session_state.get("loomloom_video_confirm_charge", False):
                    _remove_active_generation_task(task_id)
                    st.error(tr("Confirm AI Video Charge Required"))
                    st.stop()
                try:
                    video_backend = _create_loomloom_video_backend()
                    loomloom_video_request = loomloom.LoomLoomConfirmedVideoRequest(
                        settings=video_backend.settings,
                        batch=current_batch,
                        listing_version_id=quote_result.listing_version_id,
                        client_request_id=st.session_state[
                            "loomloom_video_client_request_id"
                        ],
                    )
                    loomloom_video_request.validate()
                except (loomloom.LoomLoomError, ValueError) as exc:
                    _remove_active_generation_task(task_id)
                    st.error(str(exc))
                    st.stop()

            if (
                params.bgm_type == "sonilo"
                and bgm_service.should_use_bgm(params.bgm_type, params.bgm_volume)
                and not sonilo_service.is_enabled()
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("Sonilo API Key Required"))
                st.stop()

            if (
                params.bgm_type == "elevenlabs"
                and bgm_service.should_use_bgm(params.bgm_type, params.bgm_volume)
                and not elevenlabs_music_service.is_enabled()
            ):
                _remove_active_generation_task(task_id)
                st.error(tr("ElevenLabs API Key Required"))
                st.stop()

            if (
                params.video_source == "local"
                and not has_local_materials
                and params.script_plan is None
            ):
                # 本地素材为空时继续执行会先产生 TTS/字幕，最后才在素材预处理阶段失败。
                # 在任务启动前拦截，可以避免无意义的 API 调用和中间文件。
                # 方案驱动执行的本地场景自带关键帧链，不需要上传素材。
                _remove_active_generation_task(task_id)
                st.error(tr("Please Upload Local Materials First"))
                st.stop()

            if voice_mode == VOICE_MODE_UPLOAD and not uploaded_audio_file:
                # 上传音频是用户显式选择的配音方式，缺少文件时不能静默退回 TTS。
                # 在任务启动前拦截，避免产生与用户选择不一致的成片。
                _remove_active_generation_task(task_id)
                st.error(tr("Please Upload Voiceover File First"))
                st.stop()

            if "custom_audio" in unmet_restore_requirements:
                # 历史自定义音频不能自动回填。用户尚未重新上传且也没有主动更换音色时，
                # 必须阻止静默退回 TTS，否则重新生成的结果会与原任务语音不一致。
                _remove_active_generation_task(task_id)
                st.error(tr("Task Restore Custom Audio Warning"))
                st.stop()

            if uploaded_bgm_file and bgm_service.should_use_bgm(
                params.bgm_type, params.bgm_volume
            ):
                try:
                    saved_bgm_name = bgm_service.save_bgm_upload(
                        uploaded_bgm_file.name, uploaded_bgm_file
                    )
                except bgm_service.BgmUploadError as exc:
                    _remove_active_generation_task(task_id)
                    logger.warning(f"WebUI background music upload rejected: {str(exc)}")
                    st.error(tr("Invalid Background Music"))
                    st.stop()
                except bgm_service.BgmServiceError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"WebUI background music upload failed: {str(exc)}")
                    st.error(tr("Background Music Validation Failed"))
                    st.stop()
                # 保存成功后只把文件名写入任务参数。视频服务会在两个 BGM 白名单
                # 目录中重新解析，避免把服务器绝对路径持久化或展示给用户。
                params.bgm_file = saved_bgm_name
            elif uploaded_bgm_file:
                # 0 音量时视频服务不会使用任何 BGM，因此不再把已经预览的上传文件
                # 持久化到 storage。用户之后调高音量时可直接再次点击生成完成保存。
                params.bgm_file = ""

            if uploaded_audio_file:
                try:
                    task_dir = utils.task_dir(task_id)
                    custom_audio_path = _build_uploaded_file_path(
                        uploaded_audio_file,
                        task_dir,
                        CUSTOM_AUDIO_EXTENSIONS,
                        "custom-audio",
                    )
                    # Voiceover uploads previously bypassed the same full-decode
                    # and size checks used for background-music uploads. Validate
                    # before storing or scheduling the generation task.
                    bgm_service.validate_bgm_upload(
                        uploaded_audio_file.name, uploaded_audio_file
                    )
                    _stage_task_audio(custom_audio_path, uploaded_audio_file.getbuffer())
                except OSError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"failed to persist uploaded task audio: {exc}")
                    st.error(tr("Video Generation Failed"))
                    st.stop()
                except bgm_service.BgmUploadError as exc:
                    _remove_active_generation_task(task_id)
                    logger.warning(f"WebUI custom audio upload rejected: {exc}")
                    st.error(str(exc))
                    st.stop()
                except bgm_service.BgmServiceError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"WebUI custom audio validation failed: {exc}")
                    st.error(str(exc))
                    st.stop()
                except ValueError:
                    _remove_active_generation_task(task_id)
                    st.error(tr("Unsupported Upload File Type"))
                    st.stop()
                params.custom_audio_file = custom_audio_path

            if uploaded_files:
                # 每次重新上传时都以本次选择的素材为准，避免旧素材不断重复追加。
                try:
                    params.video_materials, persisted_local_materials = (
                        _save_uploaded_local_materials(uploaded_files)
                    )
                except material_upload_service.MaterialUploadError as exc:
                    _remove_active_generation_task(task_id)
                    logger.warning(f"WebUI local material upload rejected: {exc}")
                    st.error(str(exc))
                    st.stop()
                except material_upload_service.MaterialServiceError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"WebUI local material upload failed: {exc}")
                    st.error(str(exc))
                    st.stop()
                # 将已上传并保存到本地的视频素材写入会话，供后续只改文案时直接复用。
                st.session_state["local_video_materials"] = persisted_local_materials
            elif (
                params.video_source == "local" and st.session_state["local_video_materials"]
            ):
                # 当用户没有重新上传文件时，复用最近一次已经保存到磁盘的本地素材列表。
                params.video_materials = []
                for material_entry in st.session_state["local_video_materials"]:
                    m = MaterialInfo()
                    m.provider = material_entry.get("provider", "local")
                    m.url = material_entry.get("url", "")
                    m.duration = material_entry.get("duration", 0)
                    if m.url:
                        params.video_materials.append(m)

            reusable_voice_preview = _get_reusable_full_voice_preview(
                params,
                voice_mode,
            )
            if reusable_voice_preview:
                # 试听缓存只存在当前 Streamlit 会话。提交前把音频写入目标任务目录，
                # 后台线程随后只读取任务自己的文件；即使页面 rerun、浏览器关闭或
                # 用户试听其它音色，也不会影响已经入队的生成任务。
                try:
                    preview_audio_file = os.path.join(
                        utils.task_dir(task_id),
                        "audio.mp3",
                    )
                    _stage_task_audio(preview_audio_file, reusable_voice_preview["audio_bytes"])
                except OSError as exc:
                    _remove_active_generation_task(task_id)
                    logger.error(f"failed to persist preview task audio: {exc}")
                    st.error(tr("Video Generation Failed"))
                    st.stop()
                reusable_voice_preview.pop("audio_bytes")
                reusable_voice_preview["audio_file"] = preview_audio_file
                logger.info(
                    f"reuse full voice preview for task: "
                    f"task_id={task_id}, duration={reusable_voice_preview['duration']:.2f}s"
                )

            try:
                st.toast(tr("Generating Video"))
                logger.info(tr("Start Generating Video"))
                logger.info(utils.to_json(params))
                submitted_task_id = webui_task.submit_generation(
                    task_id=task_id,
                    params=params,
                    capture_logs=not config.ui.get("hide_log", False),
                    voice_preview=reusable_voice_preview,
                    loomloom_video_request=loomloom_video_request,
                    voxcpm_reference_audio=voxcpm_reference_audio,
                    voxcpm_prompt_audio=voxcpm_prompt_audio,
                    voxcpm_prompt_text=voxcpm_prompt_text,
                    **({"jalapeno_video_endpoint": jalapeno_video_endpoint}
                       if params.video_source == "jalapeno" else {}),
                )
                if loomloom_video_request is not None:
                    # 一个报价只允许提交一次。后台请求自带稳定幂等 ID；提交成功后
                    # 清除页面报价，下一次生成必须重新询价和确认。
                    st.session_state["loomloom_video_batch"] = None
                    st.session_state["loomloom_video_quote"] = None
                    st.session_state["loomloom_video_input_signature"] = ""
                    st.session_state["loomloom_video_client_request_id"] = ""
            except Exception:
                _remove_active_generation_task(task_id)
                st.error(tr("Video Generation Failed"))
                st.stop()

            if isinstance(submitted_task_id, str) and submitted_task_id != task_id:
                _remove_active_generation_task(task_id)
                task_id = submitted_task_id
                _add_active_generation_task(task_id, subject=params.video_subject)
            st.session_state["current_generation_task_id"] = task_id
            st.query_params["generation_task"] = task_id
            # 提交即落盘项目快照并绑定会话：任务目录从此可被项目切换器加载。
            submitted_params_dump = params.model_dump(mode="json")
            _write_project_params(task_id, submitted_params_dump)
            _bind_current_project(task_id, submitted_params_dump)
            logger.info(f"WebUI generation task submitted: task_id={task_id}")
            if webui_task.is_generation_active(task_id):
                st.rerun()

    return start_button


# -----------------------------------------------------------------------------
# 脚本方案专业模式（B7）：创作向导 / 脚本方案 / 系列管理
# -----------------------------------------------------------------------------

WIZARD_GENRES = (
    ("urban_revenge", "Genre Urban Revenge"),
    ("period_romance", "Genre Period Romance"),
    ("suspense", "Genre Suspense"),
    ("healing", "Genre Healing"),
    ("scifi", "Genre Scifi"),
    ("custom", "Genre Custom"),
)
# cloud_ai 尚未接入任务编排（保留升级项），下拉框不提供该选项；
# 导入的旧方案若含 cloud_ai 场景，渲染时回退 stock 并提示。
PLAN_ENGINE_OPTIONS = ("stock", "local_fl2v", "local_i2v")
PLAN_ENGINE_LABELS = {
    "stock": "Plan Engine Stock",
    "local_fl2v": "Plan Engine Local FL2V",
    "local_i2v": "Plan Engine Local I2V",
    "cloud_ai": "Plan Engine Cloud AI",
}
PLAN_TRANSITION_OPTIONS = ("none", "fade", "slide", "zoom", "match_cut")
PLAN_TRANSITION_LABELS = {
    "none": "Transition None",
    "fade": "Transition Fade",
    "slide": "Transition Slide",
    "zoom": "Transition Zoom",
    "match_cut": "Transition Match Cut",
}
EPISODE_STATUS_LABELS = {
    "draft": "Episode Status Draft",
    "confirmed": "Episode Status Confirmed",
    "rendered": "Episode Status Rendered",
}
_LOCAL_ENGINES_STATUS_TTL_SECONDS = 15.0


def _local_engines_status_cached():
    """引擎就绪度探针的会话级 TTL 缓存：render-all 壳下每次 rerun 都
    渲染仪表盘，不能每次都发三个 HTTP 探针；fragment 定时刷新负责续探。"""
    cached = st.session_state.get("local_engines_status_cache")
    now = time.time()
    if cached and now - cached[0] < _LOCAL_ENGINES_STATUS_TTL_SECONDS:
        return cached[1]
    try:
        status = comfy_local.local_engines_status()
    except Exception as exc:
        logger.warning(f"local engines status probe failed: {exc}")
        status = {
            "comfyui": {"online": False},
            "acestep": {"online": False},
            "ollama": {"online": False},
        }
    st.session_state["local_engines_status_cache"] = (now, status)
    return status


@st.fragment(run_every="15s")
def _render_local_engine_dashboard(key_prefix):
    # 白话名称 + 状态点；离线只置灰提示，不抛异常（快速模式不受影响）。
    status = _local_engines_status_cached()
    cols = st.columns([1, 1, 1, 1.2])
    for col, engine, label_key in zip(
        cols,
        ("comfyui", "acestep", "ollama"),
        ("Local Video Engine", "Local Music Engine", "Local Writer Engine"),
    ):
        online = bool(status.get(engine, {}).get("online"))
        dot = "🟢" if online else "⚪"
        col.markdown(f"**{dot} {tr(label_key)}**")
        col.caption(tr("Engine Online") if online else tr("Engine Offline"))
    with cols[3]:
        if st.button(
            tr("Local Bundle Preset"),
            key=f"{key_prefix}_local_bundle",
            icon="⚡",
            width="stretch",
            help=tr("Engine Status Help"),
        ):
            # 一键本地全家桶：编剧引擎切 ollama，模型为空时补推荐默认；
            # 画面/音乐引擎由方案逐场景选择，不在这里改全局素材源。
            _set_runtime_config("app", "llm_provider", "ollama")
            if not str(config.app.get("ollama_model_name", "") or "").strip():
                _set_runtime_config("app", "ollama_model_name", "gemma4:26b")
            _save_runtime_config()
            st.toast(tr("Local Bundle Applied"))


def _plan_reset_widgets():
    """AI 重生成/导入/切换草稿后清除场景控件的会话值，让下一次渲染
    从新方案的 value 重新初始化（Streamlit 控件状态优先于 value 参数）。"""
    fixed_keys = {
        "plan_quality_tier", "plan_title_field", "plan_logline_field",
        "plan_style_tone", "plan_style_palette", "plan_style_camera",
        "plan_voice_name", "plan_voice_rate",
    }
    for key in list(st.session_state.keys()):
        if str(key).startswith("plan_scene_") or key in fixed_keys:
            del st.session_state[key]


def _plan_mutate(plan_id, mutator, *, confirm=False):
    """草稿的锁内读→改→校验→写。编辑一律回退 draft 并 revision++；
    confirm=True 只置 confirmed（付费门禁重新生效的入口）。失败不写盘，
    错误存入会话由页面顶部横幅展示。"""
    try:
        payload = plan_store.load_plan(plan_id)
        if payload is None:
            raise plan_store.PlanStoreError(f"plan draft missing: {plan_id}")
        plan = ScriptPlan.model_validate(payload)
        mutator(plan)
        if confirm:
            plan.status = "confirmed"
        else:
            plan.status = "draft"
            plan.revision += 1
        updated = plan.model_dump(mode="json", by_alias=True)
        plan_store.save_plan(updated, plan_id=plan_id)
    except (plan_store.PlanStoreError, ValidationError, ValueError) as exc:
        st.session_state["plan_edit_error"] = str(exc)
        return None
    st.session_state.pop("plan_edit_error", None)
    return updated


def _plan_scene_field_changed(plan_id, scene_id, field, widget_key):
    value = st.session_state.get(widget_key)
    if value is None:
        # _plan_reset_widgets 删除会话键后（AI 重生成/导入/切换草稿），
        # Streamlit 重建控件时可能以 None 重放 on_change——控件重置产物，
        # 非用户编辑。目标字段均不可空，跳过以免把 None 写进模型。
        return

    def mutate(plan):
        scene = next(s for s in plan.scenes if s.id == scene_id)
        if field == "keywords":
            scene.keywords = [
                term.strip() for term in str(value or "").split(",")
                if term.strip()
            ]
        elif field == "narration":
            scene.narration = str(value or "")
            estimated = estimate_scene_duration(scene.narration)
            if estimated > 0:
                scene.est_duration = estimated
        else:
            setattr(scene, field, value)

    _plan_mutate(plan_id, mutate)


def _plan_setting_changed(plan_id, path, widget_key):
    value = st.session_state.get(widget_key)
    if value is None:
        # 同 _plan_scene_field_changed：重置产物 None 不是用户编辑；
        # pydantic 默认不校验赋值，放行会让 null 进 model_dump 而被
        # save_plan 拒绝（用户实测 quality_tier literal_error）。
        return

    def mutate(plan):
        target = plan
        parts = path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)

    _plan_mutate(plan_id, mutate)


def _plan_reorder_scenes(plan_id, scene_id, delta):
    def mutate(plan):
        index = next(i for i, s in enumerate(plan.scenes) if s.id == scene_id)
        target = index + delta
        if target < 0 or target >= len(plan.scenes):
            return
        scenes = plan.scenes
        scenes[index], scenes[target] = scenes[target], scenes[index]
        for order, scene in enumerate(scenes, start=1):
            scene.order = order
            # 调序后共享边界帧约束不再成立：统一解除共享并置 unknown，
            # 由后续关键帧链重新建立（与 Demo 的重算语义一致）。
            scene.keyframe.shared_with_prev = False
            scene.relation_to_prev = "establish" if order == 1 else "unknown"

    _plan_mutate(plan_id, mutate)


def _plan_delete_scene(plan_id, scene_id):
    def mutate(plan):
        if len(plan.scenes) <= 1:
            raise ValueError("a plan must keep at least one scene")
        plan.scenes = [s for s in plan.scenes if s.id != scene_id]
        for order, scene in enumerate(plan.scenes, start=1):
            scene.order = order
            scene.keyframe.shared_with_prev = False
            scene.relation_to_prev = "establish" if order == 1 else "unknown"

    _plan_mutate(plan_id, mutate)


def _plan_add_scene(plan_id):
    def mutate(plan):
        used = {s.id for s in plan.scenes}
        index = len(plan.scenes) + 1
        while f"s{index}" in used:
            index += 1
        plan.scenes.append(
            ScriptScene(id=f"s{index}", order=len(plan.scenes) + 1, est_duration=5.0)
        )

    _plan_mutate(plan_id, mutate)


def _wizard_characters_snapshot(characters):
    st.session_state["wizard_characters_snapshot"] = characters


def _render_wizard_page():
    # 仪表盘只在所属 TAB 活动时渲染：render-all 壳下非活动页不发
    # HTTP 探针（避免干扰无关页面的网络断言/离线环境）。
    if _pro_tab_active("Creation Wizard"):
        _render_local_engine_dashboard("wizard_dashboard")
    st.subheader(tr("Creation Wizard"))
    st.caption(tr("Wizard Intro"))

    st.markdown(f"**{tr('Wizard Section Idea')}**")
    st.text_area(
        tr("Wizard Story Idea"),
        key="wizard_story_idea",
        placeholder=tr("Wizard Story Idea Placeholder"),
        height=90,
    )
    idea_cols = st.columns([2, 1, 1])
    with idea_cols[0]:
        # 标签在渲染期预算好：format_func 闭包只查字典，不在序列化期
        # 读会话态（AppTest 裸线程重调时没有 ui_language）。
        genre_labels = {genre: tr(label) for genre, label in WIZARD_GENRES}
        st.selectbox(
            tr("Wizard Genre"),
            options=[genre for genre, _ in WIZARD_GENRES],
            format_func=genre_labels.get,
            key="wizard_genre",
        )
    with idea_cols[1]:
        st.number_input(
            tr("Wizard Episode Duration"),
            min_value=30, max_value=300, value=60, step=10,
            key="wizard_episode_duration",
        )
    with idea_cols[2]:
        st.number_input(
            tr("Wizard Episode Count"),
            min_value=1, max_value=12, value=3, step=1,
            key="wizard_episode_count",
        )

    st.markdown(f"**{tr('Wizard Section Characters')}**")
    st.caption(tr("Wizard Characters Help"))
    edited_characters = st.data_editor(
        [{"name": "", "voice_name": "", "appearance_prompt": ""}],
        num_rows="dynamic",
        key="wizard_characters_editor",
        column_config={
            "name": st.column_config.TextColumn(tr("Wizard Character Name")),
            "voice_name": st.column_config.TextColumn(
                tr("Wizard Character Voice"),
                help="zh-CN-XiaoxiaoNeural / zh-CN-YunxiNeural",
            ),
            "appearance_prompt": st.column_config.TextColumn(
                tr("Wizard Character Appearance")
            ),
        },
        width="stretch",
    )
    _wizard_characters_snapshot(edited_characters)

    st.markdown(f"**{tr('Wizard Section Generate')}**")
    if st.button(
        tr("Wizard Generate"),
        key="wizard_generate_button",
        type="primary",
        icon=":material/auto_awesome:",
        width="stretch",
        disabled=_generation_is_busy(_current_generation_task_id()),
    ):
        idea = str(st.session_state.get("wizard_story_idea", "") or "").strip()
        if not idea:
            st.error(tr("Wizard Idea Required"))
        else:
            genre = st.session_state.get("wizard_genre", "urban_revenge")
            duration = float(st.session_state.get("wizard_episode_duration", 60))
            count = int(st.session_state.get("wizard_episode_count", 3))
            characters = [
                character
                for character in st.session_state.get(
                    "wizard_characters_snapshot", []
                )
                if str(character.get("name", "") or "").strip()
            ]
            with st.spinner(tr("Wizard Generating")):
                payload = llm.generate_script_plan(
                    video_subject=idea,
                    language=str(config.app.get("video_language", "") or ""),
                    target_duration=duration,
                    aspect="9:16",
                )
            if payload is None:
                st.error(tr("Wizard Generate Failed"))
            else:
                try:
                    series = Series(
                        id=series_store.new_series_id(),
                        title=idea[:60],
                        genre_template=genre,
                        characters=[
                            SeriesCharacter(
                                id=f"c{index}",
                                name=str(character["name"]).strip(),
                                voice_name=str(
                                    character.get("voice_name", "") or ""
                                ).strip(),
                                appearance_prompt=str(
                                    character.get("appearance_prompt", "") or ""
                                ).strip(),
                            )
                            for index, character in enumerate(characters, start=1)
                        ],
                        episodes=[
                            SeriesEpisode(
                                id=f"ep{index}",
                                seq=index,
                                title=idea[:40] if index == 1 else "",
                            )
                            for index in range(1, count + 1)
                        ],
                    )
                    series_store.save_series(series)
                    plan_id = plan_store.save_plan(payload)
                    series_store.bind_episode_plan(series.id, "ep1", plan_id)
                except (
                    series_store.SeriesStoreError,
                    plan_store.PlanStoreError,
                    ValidationError,
                    ValueError,
                ) as exc:
                    logger.error(f"wizard series creation failed: {exc}")
                    st.error(f"{tr('Wizard Generate Failed')}: {exc}")
                else:
                    st.session_state["script_plan_current_id"] = plan_id
                    _plan_reset_widgets()
                    st.toast(tr("Wizard Created"))
                    _navigate_to_page("plan")


def _plan_draft_picked():
    st.session_state["script_plan_current_id"] = st.session_state.get(
        "plan_draft_picker"
    )
    _plan_reset_widgets()


def _render_plan_page():
    if _pro_tab_active("Script Plan"):
        _render_local_engine_dashboard("plan_dashboard")
    st.subheader(tr("Script Plan"))
    edit_error = st.session_state.get("plan_edit_error")
    if edit_error:
        st.error(f"{tr('Plan Edit Failed')}: {edit_error}")

    summaries = plan_store.list_plans()
    current_id = st.session_state.get("script_plan_current_id")
    if summaries:
        ids = [item["id"] for item in summaries]
        labels = {
            item["id"]: (
                f"{item['title'] or item['id']} · "
                f"{tr('Plan Status Confirmed' if item['status'] == 'confirmed' else 'Plan Status Draft')}"
                f" · r{item['revision']}"
            )
            for item in summaries
        }
        st.selectbox(
            tr("Plan Draft Picker"),
            options=ids,
            index=ids.index(current_id) if current_id in ids else 0,
            format_func=lambda plan_id: labels[plan_id],
            key="plan_draft_picker",
            on_change=_plan_draft_picked,
        )
        current_id = st.session_state.get("plan_draft_picker", current_id)

    payload = None
    if current_id:
        try:
            payload = plan_store.load_plan(current_id)
        except plan_store.PlanStoreError as exc:
            st.error(f"{tr('Plan Edit Failed')}: {exc}")
            st.session_state.pop("script_plan_current_id", None)
            current_id = None

    if payload is None:
        st.info(tr("Plan Empty Hint"))
        subject = st.text_input(tr("Plan New Subject"), key="plan_new_subject")
        if st.button(
            tr("Plan Generate"),
            key="plan_generate_button",
            type="primary",
            icon=":material/auto_awesome:",
            disabled=_generation_is_busy(_current_generation_task_id()),
        ):
            if not subject.strip():
                st.error(tr("Wizard Idea Required"))
            else:
                with st.spinner(tr("Plan Generating")):
                    generated = llm.generate_script_plan(
                        video_subject=subject.strip(),
                        language=str(config.app.get("video_language", "") or ""),
                        target_duration=60.0,
                    )
                if generated is None:
                    st.error(tr("Plan Generate Failed"))
                else:
                    try:
                        plan_id = plan_store.save_plan(generated)
                    except plan_store.PlanStoreError as exc:
                        st.error(f"{tr('Plan Generate Failed')}: {exc}")
                    else:
                        st.session_state["script_plan_current_id"] = plan_id
                        _plan_reset_widgets()
                        st.rerun()
        return

    plan = ScriptPlan.model_validate(payload)
    total = plan.estimated_total_duration()
    header_cols = st.columns([1.4, 1, 1, 1.6])
    status_key = (
        "Plan Status Confirmed" if plan.status == "confirmed"
        else "Plan Status Draft"
    )
    header_cols[0].markdown(
        f"**{'🟠' if plan.status == 'draft' else '🟢'} {tr(status_key)}** · "
        f"{plan.title or current_id}"
    )
    header_cols[1].caption(f"{tr('Plan Revision')} r{plan.revision}")
    header_cols[2].caption(
        f"{tr('Plan Scenes Count')}: {len(plan.scenes)}"
    )
    header_cols[3].caption(
        f"{tr('Plan Target Duration')} {plan.target_duration:.0f}s · "
        f"{tr('Plan Estimated Duration')} {total:.1f}s"
    )
    st.progress(min(total / plan.target_duration, 1.0) if plan.target_duration else 0.0)
    for warning in plan.duration_warnings():
        st.warning(f"{tr('Plan Duration Over')}: {warning['message']}")

    action_cols = st.columns([1.2, 1, 1, 1, 1.4])
    with action_cols[0]:
        tier_labels = {"draft": tr("Plan Tier Draft"), "final": tr("Plan Tier Final")}
        st.radio(
            tr("Plan Quality Tier"),
            options=["draft", "final"],
            index=["draft", "final"].index(plan.quality_tier),
            format_func=tier_labels.get,
            horizontal=True,
            key="plan_quality_tier",
            on_change=_plan_setting_changed,
            args=(current_id, "quality_tier", "plan_quality_tier"),
        )
    with action_cols[1]:
        regenerate_clicked = st.button(
            tr("Plan Regenerate"),
            key="plan_regenerate_button",
            icon=":material/refresh:",
            width="stretch",
            disabled=_generation_is_busy(_current_generation_task_id()),
        )
    with action_cols[2]:
        st.download_button(
            tr("Plan Export JSON"),
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name=f"{plan.title or current_id}.json",
            mime="application/json",
            key="plan_export_button",
            width="stretch",
        )
    with action_cols[3]:
        confirm_clicked = st.button(
            tr("Plan Confirm"),
            key="plan_confirm_button",
            width="stretch",
            disabled=plan.status == "confirmed",
        )
    with action_cols[4]:
        execute_clicked = st.button(
            tr("Plan Confirm And Generate"),
            key="plan_execute_button",
            type="primary",
            icon=":material/play_arrow:",
            width="stretch",
            disabled=(
                _generation_is_busy(_current_generation_task_id())
                or _project_is_locked()
            ),
        )

    import_cols = st.columns([2, 1])
    with import_cols[0]:
        imported_file = st.file_uploader(
            tr("Plan Import JSON"), type=["json"], key="plan_import_uploader"
        )
    with import_cols[1]:
        delete_clicked = st.button(
            tr("Plan Delete Draft"),
            key="plan_delete_button",
            icon=":material/delete:",
            width="stretch",
        )

    if regenerate_clicked:
        with st.spinner(tr("Plan Generating")):
            generated = llm.generate_script_plan(
                video_subject=plan.title or plan.logline,
                language=str(config.app.get("video_language", "") or ""),
                target_duration=plan.target_duration,
                aspect=plan.aspect,
                voice_name=plan.voice.name,
                series_id=plan.series_id,
                episode_id=plan.episode_id,
            )
        if generated is None:
            st.error(tr("Plan Generate Failed"))
        else:
            try:
                new_plan = ScriptPlan.model_validate(generated)
                locked_old = [s for s in plan.scenes if s.locked]
                for old_scene in locked_old:
                    index = old_scene.order - 1
                    if index < len(new_plan.scenes):
                        target = new_plan.scenes[index]
                        target.narration = old_scene.narration
                        target.visual = old_scene.visual
                        target.keywords = list(old_scene.keywords)
                        target.est_duration = old_scene.est_duration
                        target.locked = True
                new_plan.revision = plan.revision + 1
                plan_store.save_plan(
                    new_plan.model_dump(mode="json", by_alias=True),
                    plan_id=current_id,
                )
            except (plan_store.PlanStoreError, ValidationError) as exc:
                st.error(f"{tr('Plan Generate Failed')}: {exc}")
            else:
                _plan_reset_widgets()
                if locked_old:
                    st.toast(tr("Plan Locked Scenes Kept"))
                st.rerun()

    if imported_file is not None:
        marker = f"{imported_file.name}:{imported_file.size}"
        if st.session_state.get("plan_import_last") != marker:
            st.session_state["plan_import_last"] = marker
            try:
                imported_payload = json.loads(imported_file.getvalue())
                imported_payload["status"] = "draft"
                imported_payload["revision"] = (
                    int(imported_payload.get("revision", 1)) + 1
                )
                plan_id = plan_store.save_plan(imported_payload)
            except (ValueError, TypeError, plan_store.PlanStoreError) as exc:
                st.error(f"{tr('Plan Import Invalid')}: {exc}")
            else:
                st.session_state["script_plan_current_id"] = plan_id
                _plan_reset_widgets()
                st.toast(tr("Plan Imported"))
                st.rerun()

    if confirm_clicked:
        if _plan_mutate(current_id, lambda _plan: None, confirm=True):
            st.toast(tr("Plan Confirmed"))
            st.rerun()

    if delete_clicked:
        plan_store.delete_plan(current_id)
        st.session_state.pop("script_plan_current_id", None)
        _plan_reset_widgets()
        st.toast(tr("Plan Draft Deleted"))
        st.rerun()

    if execute_clicked:
        if any(not scene.narration.strip() for scene in plan.scenes):
            st.error(tr("Plan Narration Required"))
        else:
            confirmed = _plan_mutate(current_id, lambda _plan: None, confirm=True)
            if confirmed:
                st.session_state["script_plan_execute_payload"] = confirmed
                st.session_state["plan_generate_requested"] = True
                st.toast(tr("Plan Execute Requested"))

    with st.expander(tr("Plan Settings")):
        setting_cols = st.columns(2)
        with setting_cols[0]:
            st.text_input(
                tr("Plan Title Field"), value=plan.title, key="plan_title_field",
                on_change=_plan_setting_changed,
                args=(current_id, "title", "plan_title_field"),
            )
            st.text_input(
                tr("Plan Logline"), value=plan.logline, key="plan_logline_field",
                on_change=_plan_setting_changed,
                args=(current_id, "logline", "plan_logline_field"),
            )
            st.text_input(
                tr("Plan Voice Name"), value=plan.voice.name, key="plan_voice_name",
                on_change=_plan_setting_changed,
                args=(current_id, "voice.name", "plan_voice_name"),
            )
            st.number_input(
                tr("Plan Voice Rate"), value=plan.voice.rate, step=0.1,
                min_value=0.5, max_value=2.0, key="plan_voice_rate",
                on_change=_plan_setting_changed,
                args=(current_id, "voice.rate", "plan_voice_rate"),
            )
        with setting_cols[1]:
            st.text_input(
                tr("Plan Style Tone"), value=plan.style.tone, key="plan_style_tone",
                on_change=_plan_setting_changed,
                args=(current_id, "style.tone", "plan_style_tone"),
            )
            st.text_input(
                tr("Plan Style Palette"), value=plan.style.palette,
                key="plan_style_palette",
                on_change=_plan_setting_changed,
                args=(current_id, "style.palette", "plan_style_palette"),
            )
            st.text_input(
                tr("Plan Style Camera"), value=plan.style.camera,
                key="plan_style_camera",
                on_change=_plan_setting_changed,
                args=(current_id, "style.camera", "plan_style_camera"),
            )

    for scene in plan.scenes:
        with st.container(key=f"plan_scene_card_{scene.id}", border=True):
            head_cols = st.columns([3, 1, 0.8, 0.8, 0.8])
            head_cols[0].markdown(
                f"**{scene.id}** · {scene.est_duration:.1f}s"
                + (" 🔗" if scene.keyframe.shared_with_prev else "")
            )
            head_cols[1].checkbox(
                tr("Plan Scene Locked"),
                value=scene.locked,
                key=f"plan_scene_locked_{scene.id}",
                on_change=_plan_scene_field_changed,
                args=(current_id, scene.id, "locked", f"plan_scene_locked_{scene.id}"),
            )
            head_cols[2].button(
                "↑", key=f"plan_scene_up_{scene.id}", help=tr("Plan Scene Move Up"),
                on_click=_plan_reorder_scenes, args=(current_id, scene.id, -1),
            )
            head_cols[3].button(
                "↓", key=f"plan_scene_down_{scene.id}", help=tr("Plan Scene Move Down"),
                on_click=_plan_reorder_scenes, args=(current_id, scene.id, 1),
            )
            head_cols[4].button(
                "🗑", key=f"plan_scene_delete_{scene.id}", help=tr("Plan Scene Delete"),
                on_click=_plan_delete_scene, args=(current_id, scene.id),
            )
            st.text_area(
                tr("Plan Scene Narration"),
                value=scene.narration,
                key=f"plan_scene_narration_{scene.id}",
                height=90,
                on_change=_plan_scene_field_changed,
                args=(
                    current_id, scene.id, "narration",
                    f"plan_scene_narration_{scene.id}",
                ),
            )
            scene_cols = st.columns([1, 2])
            with scene_cols[0]:
                st.number_input(
                    tr("Plan Scene Est Duration"),
                    value=scene.est_duration,
                    min_value=0.5, max_value=120.0, step=0.5, format="%.1f",
                    key=f"plan_scene_est_{scene.id}",
                    on_change=_plan_scene_field_changed,
                    args=(current_id, scene.id, "est_duration", f"plan_scene_est_{scene.id}"),
                )
            with scene_cols[1]:
                st.text_input(
                    tr("Plan Scene Visual"),
                    value=scene.visual,
                    key=f"plan_scene_visual_{scene.id}",
                    on_change=_plan_scene_field_changed,
                    args=(current_id, scene.id, "visual", f"plan_scene_visual_{scene.id}"),
                )
            st.text_input(
                tr("Plan Scene Keywords"),
                value=", ".join(scene.keywords),
                key=f"plan_scene_keywords_{scene.id}",
                on_change=_plan_scene_field_changed,
                args=(current_id, scene.id, "keywords", f"plan_scene_keywords_{scene.id}"),
            )
            engine_cols = st.columns(2)
            engine_value = scene.engine if scene.engine in PLAN_ENGINE_OPTIONS else "stock"
            if scene.engine not in PLAN_ENGINE_OPTIONS:
                st.warning(f"{scene.id}: {tr('Plan Engine Cloud AI')} → {tr('Plan Engine Stock')}")
            # 同 wizard_genre：渲染期预算标签，序列化期不读会话态。
            engine_labels = {value: tr(label) for value, label in PLAN_ENGINE_LABELS.items()}
            transition_labels = {
                value: tr(label) for value, label in PLAN_TRANSITION_LABELS.items()
            }
            with engine_cols[0]:
                st.selectbox(
                    tr("Plan Scene Engine"),
                    options=list(PLAN_ENGINE_OPTIONS),
                    index=PLAN_ENGINE_OPTIONS.index(engine_value),
                    format_func=engine_labels.get,
                    key=f"plan_scene_engine_{scene.id}",
                    on_change=_plan_scene_field_changed,
                    args=(current_id, scene.id, "engine", f"plan_scene_engine_{scene.id}"),
                )
            with engine_cols[1]:
                st.selectbox(
                    tr("Plan Scene Transition"),
                    options=list(PLAN_TRANSITION_OPTIONS),
                    index=PLAN_TRANSITION_OPTIONS.index(scene.transition_to_next),
                    format_func=transition_labels.get,
                    key=f"plan_scene_transition_{scene.id}",
                    on_change=_plan_scene_field_changed,
                    args=(
                        current_id, scene.id, "transition_to_next",
                        f"plan_scene_transition_{scene.id}",
                    ),
                )

    if st.button(tr("Plan Scene Add"), key="plan_scene_add_button", icon=":material/add:"):
        _plan_add_scene(current_id)
        st.rerun()


def _series_character_appearance_changed(series_id, character_id, widget_key):
    value = str(st.session_state.get(widget_key, "") or "")

    def mutate(series):
        character = next(c for c in series.characters if c.id == character_id)
        character.appearance_prompt = value

    try:
        series_store.update_series(series_id, mutate)
    except series_store.SeriesStoreError as exc:
        st.session_state["series_edit_error"] = str(exc)


def _series_reference_lock_changed(series_id, character_id, basename, widget_key):
    try:
        if st.session_state.get(widget_key):
            series_store.lock_reference_image(series_id, character_id, basename)
        else:
            series_store.unlock_reference_image(series_id, character_id, basename)
    except series_store.SeriesStoreError as exc:
        st.session_state["series_edit_error"] = str(exc)


def _render_series_page():
    st.subheader(tr("Series Library"))
    edit_error = st.session_state.get("series_edit_error")
    if edit_error:
        st.error(f"{tr('Series Load Failed')}: {edit_error}")
    summaries = series_store.list_series()
    create_cols = st.columns([3, 1])
    with create_cols[1]:
        if st.button(
            tr("Series Create"), key="series_create_button",
            icon=":material/add:", width="stretch",
        ):
            _navigate_to_page("wizard")
    if not summaries:
        st.info(tr("Series Empty Hint"))
        return
    with create_cols[0]:
        # 渲染期预算标签（含 tr）：序列化期重调 format_func 时不再读
        # 会话态/重拼文案，与 plan_draft_picker 同惯例。
        series_labels = {
            item["id"]: (
                f"{item['title'] or item['id']} · "
                f"{tr('Series Episodes Count')} {item['episodes']} · "
                f"{tr('Series Characters Count')} {item['characters']}"
            )
            for item in summaries
        }
        selected_id = st.selectbox(
            tr("Series Picker"),
            options=[item["id"] for item in summaries],
            format_func=lambda sid: series_labels.get(sid, sid),
            key="series_picker",
        )
    try:
        series = series_store.load_series(selected_id)
    except series_store.SeriesStoreError as exc:
        st.error(f"{tr('Series Load Failed')}: {exc}")
        return
    if series is None:
        st.info(tr("Series Empty Hint"))
        return
    st.caption(
        f"{tr('Series Genre')}: {tr(dict(WIZARD_GENRES).get(series.genre_template, 'Genre Custom'))}"
    )

    episodes_tab, characters_tab = st.tabs(
        [tr("Series Episodes Tab"), tr("Series Characters Tab")],
        key="series_detail_tabs",
    )
    with episodes_tab:
        for episode in series.episodes:
            with st.container(key=f"series_episode_{episode.id}", border=True):
                ep_cols = st.columns([3, 1])
                ep_cols[0].markdown(
                    f"**EP{episode.seq} {episode.title or ''}** · "
                    f"{tr(EPISODE_STATUS_LABELS[episode.status])}"
                )
                if episode.logline:
                    st.caption(f"{tr('Series Episode Logline')}: {episode.logline}")
                if episode.hook:
                    st.caption(f"{tr('Series Episode Hook')}: {episode.hook}")
                with ep_cols[1]:
                    if episode.plan_id:
                        if st.button(
                            tr("Series Open Plan"),
                            key=f"series_open_plan_{episode.id}",
                            width="stretch",
                        ):
                            st.session_state["script_plan_current_id"] = episode.plan_id
                            _plan_reset_widgets()
                            _navigate_to_page("plan")
                    else:
                        st.caption(tr("Series No Plan"))
    with characters_tab:
        for character in series.characters:
            with st.container(key=f"series_character_{character.id}", border=True):
                st.markdown(
                    f"**{character.name or character.id}** · "
                    f"{tr('Series Character Role')}: {character.role}"
                )
                st.caption(
                    f"{tr('Series Character Voice')}: {character.voice_name or '—'}"
                )
                st.text_input(
                    tr("Series Character Appearance"),
                    value=character.appearance_prompt,
                    key=f"series_char_appearance_{series.id}_{character.id}",
                    on_change=_series_character_appearance_changed,
                    args=(
                        series.id, character.id,
                        f"series_char_appearance_{series.id}_{character.id}",
                    ),
                )
                st.caption(tr("Series Reference Images"))
                for index, relative in enumerate(character.reference_images):
                    image_path = series_store.series_dir(series.id) / relative
                    ref_cols = st.columns([1, 1, 1])
                    if image_path.is_file():
                        ref_cols[0].image(str(image_path), width=96)
                    basename = Path(relative).name
                    locked = series_store.is_reference_locked(
                        series.id, character.id, basename
                    )
                    lock_widget_key = (
                        f"series_ref_lock_{series.id}_{character.id}_{index}"
                    )
                    ref_cols[1].checkbox(
                        tr("Series Reference Locked"),
                        value=locked,
                        key=lock_widget_key,
                        on_change=_series_reference_lock_changed,
                        args=(series.id, character.id, basename, lock_widget_key),
                    )
                    if ref_cols[2].button(
                        tr("Series Reference Delete"),
                        key=f"series_ref_del_{series.id}_{character.id}_{index}",
                    ):
                        try:
                            series_store.remove_reference_image(
                                series.id, character.id, basename
                            )
                            st.rerun()
                        except series_store.SeriesStoreError:
                            st.error(tr("Series Reference Delete Refused"))
                uploaded_ref = st.file_uploader(
                    tr("Series Reference Upload"),
                    type=["png", "jpg", "jpeg", "webp"],
                    key=f"series_ref_upload_{series.id}_{character.id}",
                )
                if uploaded_ref is not None:
                    marker = f"{uploaded_ref.name}:{uploaded_ref.size}"
                    last_key = f"series_ref_last_{series.id}_{character.id}"
                    if st.session_state.get(last_key) != marker:
                        st.session_state[last_key] = marker
                        try:
                            series_store.add_reference_image(
                                series.id, character.id, uploaded_ref.getvalue(),
                                suffix=Path(uploaded_ref.name).suffix or ".png",
                            )
                            st.toast(tr("Series Reference Added"))
                            st.rerun()
                        except series_store.SeriesStoreError as exc:
                            st.error(str(exc))


# -----------------------------------------------------------------------------
# 三列应用壳：左导航 / 中功能页 / 右生成日志
# -----------------------------------------------------------------------------

NAV_PAGES = (
    ("quick", "Nav Quick Film", ":material/bolt:", "creation"),
    ("pro", "Nav Pro Drama", ":material/movie:", "creation"),
    ("tasks", "Task Manager", ":material/checklist:", "publish"),
    ("publish_history", "Publish History Tab", ":material/history:", "publish"),
    ("llm", "Service Providers Tab", ":material/hub:", "config"),
    ("material", "Material API Tab", ":material/video_library:", "config"),
    ("publish", "Auto-Publish Settings", ":material/send:", "config"),
    ("presets", "Preset Library", ":material/tune:", "config"),
    ("settings", "Settings", ":material/settings:", "config"),
)
NAV_PAGE_IDS = tuple(page for page, _, _, _ in NAV_PAGES)
# 旧一级创作页 → 新两路线 + TAB 下标：历史会话/测试/深链仍可用旧 id 导航。
LEGACY_CREATION_PAGES = {
    "script": ("quick", 0),
    "video": ("quick", 2),
    "audio": ("quick", 3),
    "subtitle": ("quick", 4),
    "wizard": ("pro", 0),
    "plan": ("pro", 1),
    "series": ("pro", 2),
}
QUICK_TAB_LABEL_KEYS = (
    "Tab Script",
    "Image Settings",
    "Tab Video",
    "Tab Audio",
    "Tab Subtitle",
)
PRO_TAB_LABEL_KEYS = (
    "Creation Wizard",
    "Script Plan",
    "Series Library",
    "Image Settings",
    "Tab Video",
    "Tab Audio",
    "Tab Subtitle",
)
NAV_GROUP_LABELS = {
    "creation": "Nav Group Creation",
    "publish": "Nav Group Publish",
    "config": "Nav Group Config",
}


def _request_creation_tab(page, tab_label_key=None):
    """登记路线页 TAB 预选请求（回调/渲染期都安全，不碰控件键）。

    st.tabs 带键挂载时若会话无选中值，react-aria 会补发一次选中
    变更事件，on_change="rerun" 据此再跑一整轮 render-all（导航延迟
    翻倍）。请求在下一轮 st.tabs 实例化前消费：显式跳转用目标 TAB，
    否则用影子键里的上次选中，挂载即稳定且保留用户的 TAB 记忆。
    控件键直写在渲染期会撞 already-instantiated（页内旧 id 跳转按钮
    是 if st.button 而非 on_click），故统一走请求旗标。
    """
    if page not in ("quick", "pro"):
        return
    st.session_state["creation_tab_request"] = (page, tab_label_key)


def _consume_creation_tab_request(active_page):
    """st.tabs 实例化前消费预选请求；无请求且无选中值时预置首 TAB。"""
    if active_page not in ("quick", "pro"):
        st.session_state.pop("creation_tab_request", None)
        return
    tabs_key = "quick_tabs" if active_page == "quick" else "pro_tabs"
    label_keys = (
        QUICK_TAB_LABEL_KEYS if active_page == "quick" else PRO_TAB_LABEL_KEYS
    )
    labels = [tr(key) for key in label_keys]
    request = st.session_state.pop("creation_tab_request", None)
    selected = None
    if request and request[0] == active_page:
        if request[1]:
            selected = tr(request[1])
        else:
            selected = st.session_state.get(f"{tabs_key}_last")
    if selected not in labels:
        selected = st.session_state.get(tabs_key)
    if selected not in labels:
        selected = labels[0]
    st.session_state[tabs_key] = selected
    st.session_state[f"{tabs_key}_last"] = selected


def _navigate_to_page(page):
    if page in LEGACY_CREATION_PAGES:
        # 旧创作页 id（向导/方案页内跳转等）归一到路线 + 对应 TAB。
        route, tab_index = LEGACY_CREATION_PAGES[page]
        label_keys = QUICK_TAB_LABEL_KEYS if route == "quick" else PRO_TAB_LABEL_KEYS
        _request_creation_tab(route, label_keys[tab_index])
        page = route
    if page in NAV_PAGE_IDS:
        st.session_state["active_page"] = page
        _request_creation_tab(page)
    # 导航可能来自 fragment 内的按钮（任务计数、移动端更多菜单），
    # 显式整页 rerun 才能切换中列页面。
    st.rerun(scope="app")


def _navigate_to_route(page, tab_label_key=None):
    """路线横幅跳转：切页的同时预选目标 TAB（请求旗标，挂载前消费）。"""
    st.session_state["active_page"] = page
    _request_creation_tab(page, tab_label_key)
    st.rerun(scope="app")


def _pro_tab_active(label_key):
    """专业页某个 TAB 是否选中：未交互过时默认首 TAB（向导）。"""
    if st.session_state.get("active_page") != "pro":
        return False
    selected = st.session_state.get("pro_tabs")
    # 语言切换后旧标签失效：与 st.tabs 的回退行为一致，视为首 TAB。
    if selected not in [tr(key) for key in PRO_TAB_LABEL_KEYS]:
        selected = None
    if selected is None:
        return label_key == PRO_TAB_LABEL_KEYS[0]
    return selected == tr(label_key)


def _toggle_nav_collapsed():
    _set_runtime_config(
        "ui", "nav_collapsed", not _saved_ui_bool("nav_collapsed", False)
    )
    _save_runtime_config()


def _toggle_log_collapsed():
    collapsing = not _saved_ui_bool("log_collapsed", False)
    _set_runtime_config("ui", "log_collapsed", collapsing)
    if collapsing:
        st.session_state.pop("log_overlay_user_open", None)
    else:
        # 窄屏（761–1500）展开偏好默认呈现竖轨；只有用户主动展开
        # 才升为右侧浮层，避免首屏浮层盖住顶栏与中列。
        st.session_state["log_overlay_user_open"] = True
    _save_runtime_config()


def _open_log_overlay():
    """窄屏自动竖轨的展开入口：服务端仍是展开态，只补用户展开标记。"""
    st.session_state["log_overlay_user_open"] = True
    st.rerun(scope="app")


def _toggle_mobile_log():
    """窄屏日志浮层开关：会话级状态，不污染桌面端收起偏好。

    打开时若桌面偏好为收起，则顺带展开——用户明确要看日志，
    浮层内容需要展开态的完整日志 UI。
    """
    opening = not st.session_state.get("mobile_log_open", False)
    st.session_state["mobile_log_open"] = opening
    if opening and _saved_ui_bool("log_collapsed", False):
        _set_runtime_config("ui", "log_collapsed", False)
        _save_runtime_config()
    st.rerun(scope="app")


def _close_mobile_log():
    st.session_state["mobile_log_open"] = False
    st.rerun(scope="app")


def _render_shell_shortcuts():
    # Ctrl+B / Ctrl+J 分别收起/展开左导航与右日志。实测约束：
    # 1) 监听函数的创建与 addEventListener 调用都必须在顶层窗口 realm
    #    完成（整体包在 host.eval 里）——从 iframe realm 发起的注册
    #    收不到可信键盘事件（合成事件可以，极易误判）；
    # 2) 每次渲染都重新 remove+add（幂等自愈）：一次性注册的监听器
    #    在后续 rerun 后会失效，会话级守卫也不可靠（未重新渲染的组件
    #    会被 Streamlit 移除，height=0 的 iframe 可能未及执行脚本）。
    # 监听器用捕获阶段：交互后 Streamlit 会在冒泡路径上拦截 keydown。
    # 跨帧访问受限时静默降级为按钮操作。
    components.html(
        """
        <script>
        try {
            window.parent.eval(`(() => {
                if (!window.__changoFilmShellShortcutHandler) {
                    window.__changoFilmShellShortcutHandler = (event) => {
                        if (!event.ctrlKey || event.shiftKey || event.altKey || event.metaKey) {
                            return;
                        }
                        const key = String(event.key || "").toLowerCase();
                        const selector = key === "b" ? ".st-key-nav_column_toggle"
                            : key === "j" ? ".st-key-log_column_toggle" : null;
                        if (!selector) {
                            return;
                        }
                        // Streamlit 会为按钮渲染隐藏的宽度测量克隆，
                        // 必须选中可见按钮而不是第一个匹配。
                        const candidates = document.querySelectorAll(selector + " button");
                        let button = null;
                        for (const candidate of candidates) {
                            if (candidate.offsetWidth > 0 || candidate.offsetHeight > 0) {
                                button = candidate;
                                break;
                            }
                        }
                        if (button) {
                            event.preventDefault();
                            button.click();
                        }
                    };
                }
                const handler = window.__changoFilmShellShortcutHandler;
                document.removeEventListener("keydown", handler, true);
                document.addEventListener("keydown", handler, true);
            })()`);
        } catch (err) { /* 跨帧受限时降级为按钮操作 */ }
        </script>
        """,
        height=0,
    )


def _render_nav_tasks_button_static(active_page, processing_count, collapsed):
    st.button(
        _task_manager_label(processing_count),
        key="nav_page_tasks",
        icon=":material/checklist:",
        type="primary" if active_page == "tasks" else "tertiary",
        on_click=_navigate_to_page,
        args=("tasks",),
        width="stretch",
        # 展开态按钮文本已可见，悬浮提示冗余；仅收起态（纯图标）保留。
        help=tr("Task Manager") if collapsed else None,
    )


@st.fragment(run_every="2s")
def _render_nav_tasks_button(active_page, collapsed):
    # 有处理中任务时才定时重绘这一个按钮，不打断中列表单输入。
    # 计数归零时做一次整页刷新切回静态渲染停止定时器（唯一的
    # 主动整页刷新，发生在批次完成这个有意义的时刻）。
    processing_count = _count_processing_tasks(_collect_task_summaries())
    if processing_count == 0:
        st.rerun(scope="app")
    _render_nav_tasks_button_static(active_page, processing_count, collapsed)


def _render_nav_tasks_entry(active_page, collapsed):
    # 任务徽章只在有处理中任务时启动 2s 轮询；空闲时静态渲染
    # （计数在每次整页 rerun 重算，外部创建的任务仍能捕获），
    # 避免没有任何任务时导航 fragment 也每 2 秒扫描任务目录。
    processing_count = _count_processing_tasks(_collect_task_summaries())
    if processing_count > 0:
        _render_nav_tasks_button(active_page, collapsed)
    else:
        _render_nav_tasks_button_static(active_page, processing_count, collapsed)


def _render_nav_sidebar(active_page, collapsed):
    with st.container(
        key="nav_sidebar_collapsed" if collapsed else "nav_sidebar_expanded"
    ):
        toggle_label = (
            tr("Expand Navigation") if collapsed else tr("Collapse Navigation")
        )
        st.button(
            toggle_label,
            key="nav_column_toggle",
            icon=(
                ":material/chevron_right:" if collapsed else ":material/chevron_left:"
            ),
            on_click=_toggle_nav_collapsed,
            width="stretch",
            help=toggle_label if collapsed else None,
        )
        brand_theme.render_nav_brand(collapsed)
        current_group = None
        for page, label_key, icon, group in NAV_PAGES:
            if group != current_group:
                current_group = group
                st.caption(tr(NAV_GROUP_LABELS[group]))
            if page == "tasks":
                _render_nav_tasks_entry(active_page, collapsed)
                continue
            st.button(
                tr(label_key),
                key=f"nav_page_{page}",
                icon=icon,
                type="primary" if page == active_page else "tertiary",
                on_click=_navigate_to_page,
                args=(page,),
                width="stretch",
                # 展开态文本可见无需悬浮提示；收起态纯图标时保留。
                help=tr(label_key) if collapsed else None,
            )
        if not collapsed:
            # 常驻品牌主题控制区：改动经 on_change 同步会话主题并整页重渲染。
            brand_theme.render_controls("cfnav", tr)
    _render_shell_shortcuts()


def _render_generation_log_column(collapsed):
    with st.container(
        key="log_column_collapsed" if collapsed else "log_column_expanded"
    ):
        # 窄屏浮层专用的关闭按钮：桌面端由 CSS 隐藏，
        # 只改会话级 mobile_log_open，不动桌面端的收起偏好。
        st.button(
            tr("Close Generation Logs"),
            key="mobile_log_close",
            icon=":material/close:",
            on_click=_close_mobile_log,
            width="stretch",
            help=tr("Close Generation Logs"),
        )
        if not collapsed:
            # 761–1500 自动竖轨专用展开按钮：此时服务端仍是展开态，
            # 普通切换按钮语义是“收起”，点了会像死按钮；CSS 只在该
            # 窄屏 band 显示本按钮并隐藏普通切换。
            st.button(
                tr("Expand Generation Logs"),
                key="log_overlay_open_button",
                icon=":material/chevron_right:",
                on_click=_open_log_overlay,
                width="stretch",
                help=tr("Expand Generation Logs"),
            )
        toggle_label = (
            tr("Expand Generation Logs")
            if collapsed
            else tr("Collapse Generation Logs")
        )
        st.button(
            toggle_label,
            key="log_column_toggle",
            icon=(
                ":material/chevron_right:" if collapsed else ":material/chevron_left:"
            ),
            on_click=_toggle_log_collapsed,
            width="stretch",
            help=toggle_label,
        )
        if collapsed:
            return
        st.caption(tr("Generation Logs Title"))
        if not _current_generation_task_id():
            st.caption(tr("Generation Logs Empty"))
            return
        _render_current_generation_task()


@st.fragment(run_every="2s")
def _render_tasks_page():
    # 任务页沿用旧 popover 的定时刷新；发布历史已拆到独立一级页。
    _render_task_manager_panel(include_publish_history=False)


@st.fragment(run_every="2s")
def _render_publish_history_page():
    _render_publish_history(publish_history.list_publish_history(limit=100))


def _render_settings_page():
    app_settings = config.snapshot_config_with_pending(config.app)
    ui_settings = config.snapshot_config_with_pending(config.ui)
    tabs = st.tabs(
        [
            tr("General Settings Tab"),
            tr("Interface Settings Tab"),
            tr("Key Backup Tab"),
            tr("Cache Management Tab"),
        ],
        key="settings_page_tabs",
        on_change="rerun",
    )
    general_tab, interface_tab, keys_tab, cache_tab = tabs
    with general_tab:
        if general_tab.open:
            _render_general_settings(app_settings)
    with interface_tab:
        if interface_tab.open:
            _render_interface_settings_body(ui_settings)
    # 密钥恢复会写回配置并清除密码控件状态，必须在这些控件渲染之前执行。
    if keys_tab.open:
        _render_key_backup_settings(keys_tab)
    if cache_tab.open:
        _render_cache_management_settings(cache_tab)


def _render_active_feature_page(active_page):
    if active_page in {"quick", "pro"}:
        # 两条创作路线的控件已经在 main_settings_grid 中全量渲染，
        # 这里只负责非创作页的惰性加载。
        return
    with st.container(key=f"feature_page_{active_page}"):
        # tasks/publish_history 已在中心列全量渲染（popover 契约），
        # 这里只负责其余非创作页的惰性加载。
        if active_page == "presets":
            # 预设库控件键独立，不与设置弹窗冲突，无需让位。
            _render_presets_page()
            return
        if st.session_state.get("settings_dialog_open", False):
            # 设置弹窗与一级页共用同一批控件；弹窗打开时让位，避免重复键。
            st.info(tr("Settings Dialog Open Hint"))
            return
        app_settings = config.snapshot_config_with_pending(config.app)
        if active_page == "llm":
            _render_llm_settings_body(app_settings)
        elif active_page == "material":
            _render_material_settings_body(app_settings)
        elif active_page == "publish":
            _render_publish_settings_body(app_settings)
        elif active_page == "settings":
            _render_settings_page()


def _render_mobile_tab_bar(active_page, mobile_log_open):
    # 窄屏底部 tab 栏：四个创作页 + 日志浮层开关 + “更多”入口；
    # 桌面端由 CSS 隐藏。
    with st.container(key="mobile_tab_bar", horizontal=True, gap="small"):
        for page, label_key, icon, _ in NAV_PAGES[:2]:
            st.button(
                tr(label_key),
                key=f"nav_mobile_{page}",
                icon=icon,
                type="primary" if page == active_page else "tertiary",
                on_click=_navigate_to_page,
                args=(page,),
                width="stretch",
                help=tr(label_key),
            )
        st.button(
            tr("Generation Logs Title"),
            key="nav_mobile_log",
            icon=":material/article:",
            type="primary" if mobile_log_open else "tertiary",
            on_click=_toggle_mobile_log,
            width="stretch",
            help=tr("Generation Logs Title"),
        )
        with st.popover(
            tr("More Pages"),
            icon=":material/more_horiz:",
            key="nav_mobile_more",
            width="stretch",
        ):
            for page, label_key, icon, _ in NAV_PAGES[2:]:
                st.button(
                    tr(label_key),
                    key=f"nav_mobile_page_{page}",
                    icon=icon,
                    type="primary" if page == active_page else "tertiary",
                    on_click=_navigate_to_page,
                    args=(page,),
                    width="stretch",
                )


def _render_application():
    """渲染三列壳：顶部栏、左导航、中功能页、右生成日志与底部常驻操作栏。"""
    _apply_pending_project_switch()
    # 预设应用的三选决议可能把参数写入 settings_preset_payload，
    # 必须先于下面的预设回填执行。
    _apply_pending_preset_apply()
    # 回填必须在顶栏之前：切换器标签读当前绑定，若回填晚于顶栏渲染，
    # 加载完成的那一 run 顶栏仍显示旧项目名。
    preset_applied = _apply_pending_settings_preset()
    restore_applied = _apply_pending_task_restore()
    _render_top_bar()

    if st.session_state.get("settings_dialog_open", False):
        _render_settings_dialog()

    preset_applied_name = st.session_state.pop("preset_applied_name", None)
    if preset_applied:
        if preset_applied_name:
            st.success(tr("Preset Applied").format(name=preset_applied_name))
        else:
            st.success(tr("Settings Preset Imported"))

    restore_candidate_id = st.session_state.get("task_restore_candidate_id")
    if restore_candidate_id:
        _render_task_restore_dialog(restore_candidate_id)
    restore_succeeded = st.session_state.pop("task_restore_succeeded", False)
    if restore_applied or restore_succeeded:
        st.success(tr("Task Configuration Loaded"))

    switch_candidate = st.session_state.get("project_switch_candidate")
    if switch_candidate and not st.session_state.get("project_switch_action"):
        _render_project_switch_dialog(switch_candidate)
    if st.session_state.pop("project_new_blank_done", False):
        st.toast(tr("Project New Blank Done"), icon="📄")
    if st.session_state.pop("project_save_as_new_done", False):
        st.toast(tr("Saved As New Project"), icon="📄")
    if st.session_state.pop("project_save_as_new_failed", False):
        st.error(tr("Project Switch Failed"))
    if st.session_state.pop("project_switch_failed", False):
        st.error(tr("Project Switch Failed"))

    preset_candidate = st.session_state.get("preset_apply_candidate")
    if preset_candidate and not st.session_state.get("preset_apply_action"):
        _render_preset_apply_dialog(preset_candidate)
    preset_delete_candidate = st.session_state.get("preset_delete_candidate")
    if preset_delete_candidate:
        _render_preset_delete_dialog(preset_delete_candidate)
    if st.session_state.pop("preset_apply_refused", False):
        st.toast(tr("Project Locked Preset Refused"), icon="🔒")
    deleted_name = st.session_state.pop("preset_deleted_name", None)
    if deleted_name:
        st.toast(tr("Preset Deleted").format(name=deleted_name), icon="🗑️")
    if st.session_state.pop("preset_apply_failed", False):
        st.error(tr("Preset Apply Failed"))
    if st.session_state.pop("preset_delete_failed", False):
        st.error(tr("Preset Delete Failed"))

    active_page = st.session_state.get("active_page", "quick")
    if active_page in LEGACY_CREATION_PAGES:
        # 旧一级创作页 id 归一到两路线，并预选对应 TAB（请求旗标，
        # 下方 st.tabs 挂载前消费，不直写控件键）。
        route, tab_index = LEGACY_CREATION_PAGES[active_page]
        label_keys = QUICK_TAB_LABEL_KEYS if route == "quick" else PRO_TAB_LABEL_KEYS
        _request_creation_tab(route, label_keys[tab_index])
        active_page = route
        st.session_state["active_page"] = route
    if active_page not in NAV_PAGE_IDS:
        active_page = "quick"
    nav_collapsed = _saved_ui_bool("nav_collapsed", False)
    log_collapsed = _saved_ui_bool("log_collapsed", False)
    mobile_log_open = bool(st.session_state.get("mobile_log_open", False))
    nav_width = 64 if nav_collapsed else 232
    log_width = 48 if log_collapsed else 380

    # 三列先用数值权重占位；实际像素宽度由 styles.css 依据
    # app_shell_n*_l*_m* 状态键锁定，收起/展开不依赖运行时测量。
    # _m 后缀仅供窄屏媒体查询判断日志浮层是否打开；_o 标记用户
    # 主动展开过日志，窄屏据此在自动竖轨与右侧浮层之间切换。
    with st.container(
        key=(
            f"app_shell_n{nav_width}_l{log_width}_m{int(mobile_log_open)}"
            f"_o{int(bool(st.session_state.get('log_overlay_user_open', False)))}"
        )
    ):
        nav_col, page_col, log_col = st.columns(
            [nav_width, 1000, log_width],
            gap="medium",
            vertical_alignment="top",
        )

    with nav_col:
        _render_nav_sidebar(active_page, nav_collapsed)

    with page_col:
        with st.container(key=f"active_page_{active_page}"):
            # 锁定横幅只在创作页显示：CSS 以横幅为锚禁用创作区指针事件；
            # 配置页不受项目锁定影响。
            if _project_is_locked() and active_page in ("quick", "pro"):
                _render_project_lock_banner()
            # 路线横幅置于 TAB 栏之上：任何 TAB 下都能看到定位与跨路线
            # 跳转（埋在文案 TAB 内会导致其它 TAB 下不可达）。
            if active_page == "quick":
                _render_route_banner(
                    "quick", "quick", "Route Quick Intro",
                    "Route Quick To Plan", "pro", "route_quick_to_plan",
                    "Script Plan",
                )
            elif active_page == "pro":
                _render_route_banner(
                    "pro", "pro", "Route Pro Intro",
                    "Route Pro To Quick", "quick", "route_pro_to_quick",
                )
            # 创作区 IA：快速成片 / 专业短剧 两个一级页，其余全部 TAB 化。
            # 七个渲染器（文案/图片/视频/音频/字幕/向导/方案/系列）每次
            # rerun 恰好渲染一次：活动路线页的 st.tabs 会服务端全量渲染
            # 所有 TAB 面板（params 组装不漂移）；未安置的渲染器进
            # creation_fallback 隐藏容器（CSS 常隐），保持 render-all 契约。
            with st.container(key="main_settings_grid"):
                fallback = st.container(key="creation_fallback")
                # 挂载前消费 TAB 预选请求（含首次进页预置），避免
                # react-aria 补发选中事件触发额外整轮 rerun。
                _consume_creation_tab_request(active_page)
                if active_page == "quick":
                    (
                        script_panel,
                        image_panel,
                        video_panel,
                        audio_panel,
                        subtitle_panel,
                    ) = st.tabs(
                        [tr(key) for key in QUICK_TAB_LABEL_KEYS],
                        key="quick_tabs",
                        on_change="rerun",
                    )
                    with fallback:
                        wizard_panel = st.container(key="fb_wizard")
                        plan_panel = st.container(key="fb_plan")
                        series_panel = st.container(key="fb_series")
                elif active_page == "pro":
                    (
                        wizard_panel,
                        plan_panel,
                        series_panel,
                        image_panel,
                        video_panel,
                        audio_panel,
                        subtitle_panel,
                    ) = st.tabs(
                        [tr(key) for key in PRO_TAB_LABEL_KEYS],
                        key="pro_tabs",
                        on_change="rerun",
                    )
                    with fallback:
                        script_panel = st.container(key="fb_script")
                if active_page in ("quick", "pro"):
                    # 影子键记录当前选中：页内切 TAB 后导航离开再回来，
                    # 预置值仍是用户最后选中的 TAB（控件清理不带走记忆）。
                    _tabs_key = "quick_tabs" if active_page == "quick" else "pro_tabs"
                    _tabs_now = st.session_state.get(_tabs_key)
                    if _tabs_now:
                        st.session_state[f"{_tabs_key}_last"] = _tabs_now
                else:
                    with fallback:
                        script_panel = st.container(key="fb_script")
                        image_panel = st.container(key="fb_image")
                        video_panel = st.container(key="fb_video")
                        audio_panel = st.container(key="fb_audio")
                        subtitle_panel = st.container(key="fb_subtitle")
                        wizard_panel = st.container(key="fb_wizard")
                        plan_panel = st.container(key="fb_plan")
                        series_panel = st.container(key="fb_series")

            params = VideoParams(video_subject="")
            params.match_materials_to_script = bool(
                st.session_state.get("match_materials_to_script", False)
            )
            _render_script_settings(script_panel, params)
            _render_image_settings(image_panel, params)

            uploaded_files = _render_video_settings(video_panel, params)
            uploaded_audio_file, uploaded_bgm_file, voice_mode = _render_audio_settings(
                audio_panel, params
            )

            _render_subtitle_settings(subtitle_panel, params)

            # 任务管理/发布历史沿用旧顶栏 popover 的契约：行级操作按钮
            # 在每次 rerun 都必须存在（headless 回归测试依赖）；非活动
            # 时与创作页一样仅由 CSS st-key 约定隐藏。
            # 定时轮询只在所属页活动时启动：render-all 壳下隐藏页的
            # 2s fragment 会永不停止地重建任务面板与发布历史（磁盘扫描
            # + 隐藏节点替换），占用脚本线程并导致活动页背景重渲染/
            # 滚动漂移。非活动时改静态渲染：元素仍全部存在，只是不再
            # 注册定时器（面板内全是无状态按钮，切换不丢控件状态）。
            with st.container(key="page_tasks"):
                if active_page == "tasks":
                    _render_tasks_page()
                else:
                    _render_task_manager_panel(include_publish_history=False)
            with st.container(key="page_publish_history"):
                if active_page == "publish_history":
                    _render_publish_history_page()
                else:
                    _render_publish_history(
                        publish_history.list_publish_history(limit=100)
                    )

            # 向导/脚本方案/系列管理（B7）沿用 render-all 壳决策：草稿与
            # 编辑状态全部在 session_state/磁盘；专业页活动时安置在 TAB，
            # 否则进隐藏 fallback。wizard_wrap/series_wrap 键供锁定 CSS
            # 豁免（新建草稿不受已完成项目锁定影响）。
            with wizard_panel:
                with st.container(key="wizard_wrap"):
                    _render_wizard_page()
            with plan_panel:
                with st.container(key="plan_wrap"):
                    _render_plan_page()
            with series_panel:
                with st.container(key="series_wrap"):
                    _render_series_page()

            _render_active_feature_page(active_page)
            action_bar = st.container(key="action_bar")

    with log_col:
        _render_generation_log_column(log_collapsed)

    _render_mobile_tab_bar(active_page, mobile_log_open)

    generation_submitted = _render_generation_controls(
        params,
        uploaded_files,
        uploaded_audio_file,
        uploaded_bgm_file,
        voice_mode,
        panel=action_bar,
    )

    # 生成分支在启动后台线程前已经请求过保存。普通控件交互继续请求非阻塞保存；
    # 如果后台任务正在使用配置，配置层会在任务结束时自动应用并落盘最新值。
    if not generation_submitted:
        _save_runtime_config()

    _finalize_project_binding(params)


_render_application()

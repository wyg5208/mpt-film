"""任务预检的备用源解析（服务商配置的三槽链）。

主源不可用（未配置 Key / 缺少必填项）时按备用槽自动切换，避免生成直接失败。
就绪口径与 webui/settings_providers.py 的"已配置"检查一致：只检查本地配置
是否齐全，不做真实连通性探测；切换动作只改本次任务参数，不写回 config.toml。
"""

from dataclasses import dataclass

from loguru import logger

from app.config import config
from app.models.service_catalog import material_capability_of_source
from app.services import (
    infistar_video,
    jalapeno_video,
    loomloom,
    material,
    metaso_minimax,
    muapi,
    ofox,
    volcengine_seedance,
    voice,
)

# 主源切换永不进入 local：本地素材依赖本次任务的上传文件，切换后没有可用素材。
NON_FALLBACK_SOURCES = {"local"}

# 库存类来源的 Key 配置键（口径同 webui/settings_providers.py）。
STOCK_KEY_CONFIG = {
    "pexels": "pexels_api_keys",
    "pixabay": "pixabay_api_keys",
    "coverr": "coverr_api_keys",
    "wavespeed": "wavespeed_api_keys",
    # 库存图片源与库存视频共用同一批 Key。
    "pexels_image": "pexels_api_keys",
    "pixabay_image": "pixabay_api_keys",
}

# 配音服务的本地配置要求：None=免费/自托管默认可用；(配置节, 键)=需要凭证。
# MiniMax TTS 复用 MiniMax LLM Provider 的 Key（voice.get_minimax_tts_api_key）。
TTS_SERVER_REQUIREMENTS = {
    "azure-tts-v1": None,
    "azure-tts-v2": ("azure", "speech_key"),
    "siliconflow": ("siliconflow", "api_key"),
    "gemini-tts": ("app", "gemini_api_key"),
    "mimo-tts": ("app", "mimo_api_key"),
    "minimax-tts": ("minimax_tts", "api_key", "app", "minimax_api_key"),
    "elevenlabs": ("elevenlabs", "api_key"),
    "chatterbox": None,
    "kokoro": None,
    "fish_audio": ("fish_audio", "api_key"),
    "voxcpm": ("voxcpm", "api_key"),
}

# 自动切换配音服务时可选默认音色的服务：音色列表来自本地静态目录，
# 不依赖远端 API；MiniMax/ElevenLabs 音色需在线拉取，不参与自动切换。
_AUTO_VOICE_SERVERS = {
    "azure-tts-v1",
    "azure-tts-v2",
    "siliconflow",
    "gemini-tts",
    "mimo-tts",
    "chatterbox",
    "kokoro",
    "fish_audio",
    "voxcpm",
}


def _has_keys(value) -> bool:
    """逗号分隔或列表形式的 Key 中是否存在至少一个非空项。"""
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return False
    return any(isinstance(item, str) and item.strip() for item in values)


def _default_section_getter(name: str) -> dict:
    return dict(getattr(config, name, {}) or {})


def video_source_available(
    source_id: str,
    settings,
    *,
    codex_connected: bool = False,
) -> bool:
    """单个素材来源的就绪检查；只验证本地配置齐全，不做连通性探测。"""
    if source_id == "local":
        return True
    key_config = STOCK_KEY_CONFIG.get(source_id)
    if key_config:
        return _has_keys(settings.get(key_config))
    if source_id == "metaso_minimax":
        return bool(metaso_minimax.is_enabled(settings))
    if source_id == "ofox":
        return bool(ofox.is_enabled(settings))
    if source_id == "volcengine_seedance":
        return bool(volcengine_seedance.is_enabled(settings))
    if source_id == "infistar":
        return bool(infistar_video.is_enabled(settings))
    if source_id == "jalapeno":
        return bool(jalapeno_video.is_enabled(settings))
    if source_id == "muapi":
        return bool(muapi.is_enabled(settings))
    if source_id == "openai_image":
        return bool(material.is_openai_image_enabled(settings))
    if source_id == "codex_image":
        return bool(codex_connected)
    if source_id == "loomloom":
        try:
            loomloom.video_settings_from_mapping(settings)
        except (loomloom.LoomLoomConfigurationError, ValueError, TypeError):
            return False
        return True
    # 未知来源按可用处理，交由任务自身的逐源预检给出明确错误。
    return True


@dataclass(frozen=True, slots=True)
class VideoSourceResolution:
    """视频来源链解析结果；source 为空表示整条链都不可用。"""

    source: str
    primary: str
    switched: bool
    attempts: tuple[tuple[str, bool], ...]


def resolve_video_source(
    app_config,
    *,
    preferred: str | None = None,
    codex_connected: bool = False,
) -> VideoSourceResolution:
    """按 [主源, 备用1, 备用2] 解析首个可用的素材来源。

    备用槽按主源所属能力分组读取（ai_video/ai_image/stock_video/stock_image），
    跨能力不互备；local 只能作为主源，不作为备用目标。
    """
    primary = str(preferred or app_config.get("video_source", "") or "").strip()
    candidates = [primary]
    capability = material_capability_of_source(primary)
    if capability:
        for slot in ("1", "2"):
            backup = str(
                app_config.get(f"video_source_backups_{capability}_{slot}", "") or ""
            ).strip()
            if backup and backup not in candidates and backup not in NON_FALLBACK_SOURCES:
                candidates.append(backup)

    attempts: list[tuple[str, bool]] = []
    for source in candidates:
        available = video_source_available(
            source, app_config, codex_connected=codex_connected
        )
        attempts.append((source, available))
        if available:
            switched = source != primary
            if switched:
                logger.warning(
                    f"video source {primary!r} unavailable; "
                    f"switched to backup source {source!r}"
                )
            return VideoSourceResolution(
                source=source,
                primary=primary,
                switched=switched,
                attempts=tuple(attempts),
            )

    logger.error(
        f"no usable video source in fallback chain: "
        f"{[name for name, _ in attempts]}"
    )
    return VideoSourceResolution(
        source="", primary=primary, switched=False, attempts=tuple(attempts)
    )


def tts_server_available(server_id: str, section_getter=_default_section_getter) -> bool:
    """配音服务是否已在本地配置凭证；免费/自托管服务视为可用。"""
    requirement = TTS_SERVER_REQUIREMENTS.get(server_id, ("__missing__", ""))
    if requirement is None:
        return True
    if requirement[0] == "__missing__":
        return False
    if len(requirement) == 2:
        section, key = requirement
        return bool(str(section_getter(section).get(key, "") or "").strip())
    # 多候选凭证（任一非空即可）：MiniMax TTS 独立 Key 或复用 LLM Key。
    for index in range(0, len(requirement), 2):
        section, key = requirement[index], requirement[index + 1]
        if str(section_getter(section).get(key, "") or "").strip():
            return True
    return False


def _pick_fallback_voice(server_id: str, language: str) -> str:
    """为自动切换到的配音服务挑一个默认音色；失败返回空串。"""
    try:
        if server_id == "azure-tts-v1":
            candidates = [
                name
                for name in voice.get_all_azure_voices()
                if "V2" not in name
            ]
        elif server_id == "azure-tts-v2":
            candidates = [
                name
                for name in voice.get_all_azure_voices()
                if "V2" in name
            ]
        elif server_id == "siliconflow":
            candidates = voice.get_siliconflow_voices()
        elif server_id == "gemini-tts":
            candidates = voice.get_gemini_voices()
        elif server_id == "mimo-tts":
            candidates = voice.get_mimo_voices()
        elif server_id == "chatterbox":
            candidates = voice.get_chatterbox_voices()
        elif server_id == "kokoro":
            candidates = voice.get_kokoro_voices(fallback=True)
        elif server_id == "fish_audio":
            candidates = voice.get_fish_audio_voices()
        elif server_id == "voxcpm":
            candidates = voice.get_voxcpm_voices()
        else:
            return ""
    except Exception as exc:  # 音色列表来自本地/远端混合来源，失败即视为不可切换
        logger.warning(f"failed to list voices for {server_id}: {exc}")
        return ""

    if not candidates:
        return ""
    lang = str(language or "").strip().lower()
    if lang:
        for name in candidates:
            if name.lower().startswith(lang):
                return name
        base_lang = lang.split("-")[0]
        for name in candidates:
            if name.lower().startswith(base_lang):
                return name
    return candidates[0]


@dataclass(frozen=True, slots=True)
class TtsServerResolution:
    """配音链解析结果；server 为空表示整条链都不可用。"""

    server: str
    voice_name: str
    primary_server: str
    switched: bool
    attempts: tuple[tuple[str, bool], ...]


def resolve_tts_server(
    ui_config,
    *,
    language: str = "",
    section_getter=_default_section_getter,
) -> TtsServerResolution:
    """按 [主配音, 备用1, 备用2] 解析首个可用的配音服务并给出默认音色。"""
    primary = str(ui_config.get("tts_server", "") or "").strip()
    candidates = [primary]
    for slot in ("1", "2"):
        backup = str(ui_config.get(f"tts_server_backup{slot}", "") or "").strip()
        if backup and backup not in candidates:
            candidates.append(backup)

    attempts: list[tuple[str, bool]] = []
    for server in candidates:
        available = tts_server_available(server, section_getter)
        if available and server not in _AUTO_VOICE_SERVERS and server != primary:
            # 在线拉取音色列表的服务无法安全自动挑选音色，不参与自动切换。
            available = False
        attempts.append((server, available))
        if available:
            switched = server != primary
            voice_name = ""
            if switched:
                voice_name = _pick_fallback_voice(server, language)
                if not voice_name:
                    # 挑不到可用音色等同不可用，继续尝试下一家。
                    continue
                logger.warning(
                    f"tts server {primary!r} unavailable; switched to backup "
                    f"{server!r} with default voice {voice_name!r}"
                )
            return TtsServerResolution(
                server=server,
                voice_name=voice_name,
                primary_server=primary,
                switched=switched,
                attempts=tuple(attempts),
            )

    logger.error(
        f"no usable tts server in fallback chain: "
        f"{[name for name, _ in attempts]}"
    )
    return TtsServerResolution(
        server="", voice_name="", primary_server=primary,
        switched=False, attempts=tuple(attempts),
    )


@dataclass(frozen=True, slots=True)
class LlmChainResolution:
    """LLM 备用链解析结果；chain 顺序即重试顺序。"""

    chain: tuple[str, ...]
    primary: str


def resolve_llm_chain(app_config) -> LlmChainResolution:
    """按 [主 Provider, 备用1, 备用2] 返回 LLM 重试链。"""
    primary = str(app_config.get("llm_provider", "") or "").strip().lower()
    chain = [primary]
    for slot in ("1", "2"):
        backup = str(app_config.get(f"llm_provider_backup{slot}", "") or "").strip().lower()
        if backup and backup not in chain:
            chain.append(backup)
    return LlmChainResolution(chain=tuple(chain), primary=primary)

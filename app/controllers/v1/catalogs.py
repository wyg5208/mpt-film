"""只读参考数据 API（迁移方案 1.8）：配音目录 / LLM 目录 / 视频源 / 字体 / 预设。

预设库与 webui/Main.py 的 ``_render_settings_transfer`` 使用同一落盘位置
（``storage/presets``，UUID 文件名），但本模块不导入 Streamlit 侧代码：
API 进程与 Streamlit 进程互相独立，导入 Main.py 会拉起整个 UI。
"""

import json
import os
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Body, Depends, Query, Request
from loguru import logger

from app.config import config
from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.llm_provider import LLM_PROVIDER_REGISTRY
from app.services import provider_readiness
from app.services import voice as voice_service
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

# 与 Main.py 一致：预设只描述生成参数，素材/配音/配乐是本机路径，
# 带到另一台机器只会指向不存在的文件。
PRESET_EXCLUDED_PARAM_KEYS = frozenset(
    {
        "video_materials",
        "custom_audio_file",
        "bgm_file",
    }
)
PRESET_SCHEMA = "changofilm.settings-preset"
PRESET_VERSION = 1
_MAX_PRESET_BYTES = 2 * 1024 * 1024
_PRESET_FILE_RE = re.compile(r"^[0-9a-fA-F-]{36}\.json$")

# 内置预设（与 webui/Main.py BUILTIN_PRESETS 同源的常量副本：控制器禁止
# 导入 Streamlit 侧代码，内置预设又是代码常量不落盘，故在此镜像；
# 修改预设内容时两处必须同步）。
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


@router.get("/voices", summary="Dubbing voice catalog, optionally by language")
def list_voices(request: Request, language: str | None = Query(None)):
    filter_locals = [language] if language else None
    return utils.get_response(
        200, {"voices": voice_service.get_all_azure_voices(filter_locals=filter_locals)}
    )


@router.get("/llm-providers", summary="LLM provider registry metadata")
def list_llm_providers(request: Request):
    providers = []
    for provider in LLM_PROVIDER_REGISTRY:
        providers.append(
            {
                "provider_id": provider.provider_id,
                "label_key": provider.label_key,
                "default_label": provider.default_label,
                "show_api_key": provider.show_api_key,
                "show_base_url": provider.show_base_url,
                "service_endpoints": [
                    {
                        "endpoint_id": endpoint.endpoint_id,
                        "default_label": endpoint.default_label,
                        "label_key": provider.endpoint_label_key(endpoint.endpoint_id),
                        "base_url": endpoint.base_url,
                        "api_key_url": endpoint.api_key_url,
                    }
                    for endpoint in provider.service_endpoints
                ],
                "endpoint_selector_label_key": (
                    provider.endpoint_selector_label_key
                    if provider.service_endpoints
                    else None
                ),
                "endpoint_selector_help_key": (
                    provider.endpoint_selector_help_key
                    if provider.service_endpoints
                    else None
                ),
                "requires_api_key": provider.requires_api_key,
                "requires_model_name": provider.requires_model_name,
                "requires_base_url": provider.requires_base_url,
                "default_model": provider.default_model,
                "default_base_url": provider.effective_default_base_url,
                "api_key_url": provider.effective_api_key_url(),
                "extra_fields": [
                    {
                        "config_suffix": field.config_suffix,
                        "required": field.required,
                        "default_value": field.default_value,
                    }
                    for field in provider.extra_fields
                ],
            }
        )
    return utils.get_response(200, {"providers": providers})


@router.get("/video-sources", summary="Video source groups + local readiness")
def list_video_sources(request: Request):
    settings = dict(config.app)
    try:
        from app.services import codex_oauth

        codex_connected = bool(codex_oauth.account_status())
    except Exception:
        codex_connected = False
    readiness = provider_readiness.configured_material_providers(
        settings,
        provider_readiness.VIDEO_SOURCE_GROUPS,
        codex_connected=codex_connected,
    )
    groups = [
        {
            "group": group,
            "providers": list(providers),
            "configured": list(readiness.get(group, ())),
        }
        # local 组无需远端配置，不参与就绪度输出（与 provider_readiness 一致）。
        for group, providers in provider_readiness.VIDEO_SOURCE_GROUPS.items()
        if group != "local"
    ]
    return utils.get_response(200, {"groups": groups})


@router.get("/fonts", summary="Fonts available under the font directory")
def list_fonts(request: Request):
    font_dir = utils.font_dir()
    fonts = []
    try:
        with os.scandir(font_dir) as entries:
            for entry in entries:
                name = entry.name
                if name.startswith("."):
                    continue
                if not name.lower().endswith((".ttf", ".otf", ".ttc")):
                    continue
                if entry.is_file(follow_symlinks=False):
                    fonts.append({"name": name, "file": name})
    except OSError as exc:
        logger.warning(f"font directory unavailable: dir={font_dir}, error={exc}")
    fonts.sort(key=lambda item: item["name"].casefold())
    return utils.get_response(200, {"fonts": fonts})


def _preset_dir() -> str:
    return utils.storage_dir("presets", create=True)


def _preset_path(preset_id: str):
    """非法或越界 ID 返回 None（与 Main.py 预设库同一防线）。"""
    try:
        normalized_id = str(UUID(str(preset_id)))
    except (ValueError, TypeError, AttributeError):
        return None
    root = os.path.realpath(_preset_dir())
    candidate = os.path.realpath(os.path.join(root, f"{normalized_id}.json"))
    if not candidate.startswith(root + os.sep):
        return None
    return candidate


def _read_preset_file(path: str):
    try:
        if os.path.getsize(path) > _MAX_PRESET_BYTES:
            return None
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


@router.get("/service-platforms", summary="Service platform capability + readiness matrix")
def service_platforms(request: Request):
    """服务商总览矩阵：与 Main.py `_render_service_provider_overview` 同源，
    按 国内→本地→国际→聚合 排序，平台就绪 = 任一已接线服务就绪。"""
    from app.models import service_catalog
    from app.services import provider_readiness, source_failover
    from app.controllers.v1 import settings as settings_controller

    app_settings = dict(config.app)
    oauth_status = {}
    for provider_id, probe in (
        ("openai_codex", settings_controller._codex_connected),
        ("openai_chatgpt", settings_controller._chatgpt_connected),
        ("kimi_code", settings_controller._kimi_connected),
    ):
        try:
            oauth_status[provider_id] = bool(probe())
        except Exception:
            oauth_status[provider_id] = False
    configured_llm = set(
        provider_readiness.configured_llm_providers(app_settings, oauth_status)
    )
    configured_material = {
        source
        for sources in provider_readiness.configured_material_providers(
            app_settings,
            provider_readiness.VIDEO_SOURCE_GROUPS,
            codex_connected=oauth_status.get("openai_codex", False),
        ).values()
        for source in sources
    }

    def _music_ready(service_id: str) -> bool:
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

    def _platform_ready(platform) -> bool:
        if any(service_id in configured_llm for service_id in platform.llm_ids):
            return True
        if any(service_id in configured_material for service_id in platform.material_ids):
            return True
        if any(
            source_failover.tts_server_available(service_id)
            for service_id in platform.tts_ids
        ):
            return True
        return any(_music_ready(service_id) for service_id in platform.music_ids)

    groups = []
    for group in service_catalog.PLATFORM_GROUP_ORDER:
        platforms = [
            platform
            for platform in service_catalog.SERVICE_PLATFORMS
            if platform.group == group
        ]
        if not platforms:
            continue
        groups.append(
            {
                "group": group,
                "label_key": service_catalog.GROUP_LABEL_KEYS[group],
                "platforms": [
                    {
                        "platform_id": platform.platform_id,
                        "label_key": platform.label_key,
                        "default_label": platform.default_label,
                        "capabilities": list(platform.capabilities),
                        "ready": _platform_ready(platform),
                    }
                    for platform in platforms
                ],
            }
        )
    return utils.get_response(200, {"groups": groups})


# 与 webui/Main.py TTS_SERVER_OPTIONS 同源的常量副本：控制器禁止导入
# Streamlit 侧代码，配音链的服务清单在此镜像；修改清单时两处必须同步。
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


@router.get("/tts-servers", summary="Voiceover service chain + local readiness")
def list_tts_servers(request: Request):
    """配音服务清单与本地就绪徽标（与 Main.py 配音 TAB 同口径）。"""
    from app.services import source_failover

    servers = [
        {
            "id": server_id,
            "label": label,
            "available": bool(source_failover.tts_server_available(server_id)),
        }
        for server_id, label in TTS_SERVER_OPTIONS
    ]
    return utils.get_response(200, {"servers": servers})


@router.post("/llm/test", summary="Test the current LLM provider connection")
def test_llm_connection(request: Request):
    """与 Streamlit「测试模型连接」同源：复用 llm.test_connection 发起
    一次最小请求，验证当前 Provider 的实际生成链路。"""
    from app.services import llm as llm_service

    ok, error, elapsed = llm_service.test_connection()
    return utils.get_response(
        200,
        {
            "ok": bool(ok),
            "error": "" if ok else str(error),
            "elapsed": round(float(elapsed), 2),
        },
    )


@router.get("/comfy/probe", summary="Local keyframe engine (ComfyUI) health probe")
def comfy_probe(request: Request):
    """与 Streamlit 图片面板的 "Local Engine Probe" 同源：只读健康探测，
    离线只回 online=false，不抛异常（comfy_local.is_online 已吞异常）。"""
    from app.services import comfy_local

    return utils.get_response(
        200, {"online": comfy_local.is_online(), "base_url": comfy_local._base_url()}
    )


@router.get("/presets", summary="List stored parameter presets")
def list_presets(request: Request):
    root = _preset_dir()
    items = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if not _PRESET_FILE_RE.match(entry.name):
                    continue
                payload = _read_preset_file(entry.path)
                if payload is None:
                    continue
                items.append(
                    {
                        "id": entry.name[: -len(".json")],
                        "name": payload.get("name", ""),
                        "params": payload.get("params", {}),
                    }
                )
    except OSError as exc:
        logger.warning(f"preset library scan failed: error={exc}")
    items.sort(key=lambda item: item["name"].casefold())
    # 内置预设排最前（与 Main.py 预设库一致）：不可删除、无落盘时间。
    builtins = [
        {
            "id": preset_id,
            "name": name_key,
            "params": dict(overrides),
            "builtin": True,
            "saved_at": None,
        }
        for preset_id, name_key, overrides in BUILTIN_PRESETS
    ]
    for item in items:
        path = _preset_path(item["id"])
        saved_at = None
        try:
            if path and os.path.isfile(path):
                saved_at = datetime.fromtimestamp(
                    os.path.getmtime(path), timezone.utc
                ).isoformat(timespec="seconds")
        except OSError:
            pass
        item.update({"builtin": False, "saved_at": saved_at})
    return utils.get_response(200, {"presets": builtins + items})


@router.post("/presets", summary="Store a named parameter preset")
def create_preset(request: Request, payload: dict = Body(...)):
    name = str(payload.get("name") or "").strip()
    params = payload.get("params")
    if not name or len(name) > 120:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="preset name must be 1-120 characters",
        )
    if not isinstance(params, dict) or not params:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="preset params must be a non-empty object",
        )
    clean_params = {
        key: value
        for key, value in params.items()
        if key not in PRESET_EXCLUDED_PARAM_KEYS
    }
    preset_id = str(uuid4())
    body = json.dumps(
        {
            "schema": PRESET_SCHEMA,
            "version": PRESET_VERSION,
            "name": name,
            "params": clean_params,
        },
        ensure_ascii=False,
    )
    if len(body.encode("utf-8")) > _MAX_PRESET_BYTES:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=413,
            message="preset exceeds the size limit",
        )
    path = _preset_path(preset_id)
    temp_path = f"{path}.part"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=500,
            message=f"preset storage failed: {exc}",
        )
    return utils.get_response(
        200, {"id": preset_id, "name": name, "params": clean_params}
    )


@router.delete("/presets/{preset_id}", summary="Delete a stored preset")
def delete_preset(request: Request, preset_id: str):
    path = _preset_path(preset_id)
    if path is None or not os.path.isfile(path):
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=f"preset not found: {preset_id}",
        )
    os.remove(path)
    return utils.get_response(200, {"deleted": str(UUID(preset_id))})

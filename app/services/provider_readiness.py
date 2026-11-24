"""服务商本地就绪度判定（迁移方案 1.3：自 webui/settings_providers.py 下沉）。

Streamlit 与 API（``GET /api/v1/settings/overview``）共用本模块，零逻辑重复。
这些检查绝不发起网络请求：就绪度只表示配置齐全，不保证远端调用可用。
"""

import shutil
from pathlib import Path

from app.config import config
from app.models.llm_provider import LLM_PROVIDER_REGISTRY
from app.services import (
    infistar_video,
    jalapeno_video,
    loomloom,
    material,
    metaso_minimax,
    muapi,
    ofox,
    volcengine_seedance,
)

# 与 webui/Main.py 的 VIDEO_SOURCE_GROUPS 保持同一业务顺序；local 组不参与
# 就绪度渲染（上传素材无需远端配置）。
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


def _text(value):
    return str(value or "").strip()


def _has_keys(value):
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return False
    return any(isinstance(item, str) and item.strip() for item in values)


def _claude_cli_available(configured_path):
    command = configured_path or "claude"
    return bool(
        shutil.which(command) or (configured_path and Path(configured_path).is_file())
    )


def configured_llm_providers(settings, oauth_status):
    """返回本地必填字段/凭据已配置齐全的注册表 provider id 列表。"""
    configured = []
    for provider in LLM_PROVIDER_REGISTRY:
        key = _text(settings.get(provider.config_key("api_key")))
        saved_model = _text(settings.get(provider.config_key("model_name")))
        saved_base = _text(settings.get(provider.config_key("base_url")))
        model = provider.resolve_model_name(saved_model)
        base = provider.resolve_base_url(saved_base)
        if provider.provider_id == "ollama":
            base = base or config.get_default_ollama_base_url()
        if provider.provider_id in {"openai_codex", "openai_chatgpt", "kimi_code"}:
            if not oauth_status.get(provider.provider_id, False):
                continue
        elif provider.provider_id == "claude_code":
            if not _claude_cli_available(
                _text(settings.get(provider.config_key("cli_path")))
            ):
                continue
        elif not provider.requires_api_key and not (
            key
            or (saved_model and saved_model != provider.default_model)
            or (saved_base and saved_base != provider.effective_default_base_url)
        ):
            # Registry defaults alone do not demonstrate a configured local gateway.
            continue
        if provider.requires_api_key and not key:
            continue
        if provider.requires_model_name and not model:
            continue
        if provider.requires_base_url and not base:
            continue
        if any(
            field.required
            and not _text(
                settings.get(provider.config_key(field.config_suffix))
                or field.default_value
            )
            for field in provider.extra_fields
        ):
            continue
        configured.append(provider.provider_id)
    return tuple(configured)


def configured_material_providers(settings, groups, codex_connected=False):
    """按素材类别返回已配置的服务商，保持组内声明顺序。"""
    enabled = {
        provider: _has_keys(settings.get(f"{provider}_api_keys"))
        for provider in ("pexels", "pixabay", "coverr", "wavespeed")
    }
    # 库存图片源与库存视频共用同一批 API Key，就绪度直接复用。
    enabled["pexels_image"] = enabled["pexels"]
    enabled["pixabay_image"] = enabled["pixabay"]
    enabled.update(
        {
            "metaso_minimax": metaso_minimax.is_enabled(settings),
            "ofox": ofox.is_enabled(settings),
            "volcengine_seedance": volcengine_seedance.is_enabled(settings),
            "infistar": infistar_video.is_enabled(settings),
            "jalapeno": jalapeno_video.is_enabled(settings),
            "muapi": muapi.is_enabled(settings),
            "openai_image": material.is_openai_image_enabled(settings),
            "codex_image": bool(
                codex_connected and _text(settings.get("codex_image_model_name"))
            ),
        }
    )
    try:
        loomloom.video_settings_from_mapping(settings)
    except (loomloom.LoomLoomConfigurationError, ValueError, TypeError):
        enabled["loomloom"] = False
    else:
        enabled["loomloom"] = True
    return {
        group: tuple(provider for provider in providers if enabled.get(provider, False))
        for group, providers in groups.items()
        if group != "local"
    }

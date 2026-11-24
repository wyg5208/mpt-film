"""设置编辑 API（迁移方案 1.3）。

分区快照、脱敏、部分更新、服务商就绪度、日志选项与 Key 备份/恢复。
写入统一走现成的 ``config.update_config_values_nonblocking``，保留
pending 语义：生成中的任务继续使用其确认时的配置快照。

脱敏红线（方案 4.D）：任何设置类响应都不出现密钥原文；Key 备份导出
同样只回脱敏视图，恢复接口则接收用户主动提供的原文值。
"""

from typing import Any

from fastapi import Body, Depends, Request

from app.config import config
from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import provider_readiness
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

# 与 webui/Main.py 的凭据判定保持同一套后缀语义。
CREDENTIAL_KEY_SUFFIXES = (
    "api_key",
    "api_keys",
    "api_token",
    "access_key",
    "secret_key",
    "speech_key",
)
# ui 分区只保存界面偏好，不含任何凭据，备份时整体跳过（同 Main.py）。
KEY_BACKUP_EXCLUDED_SECTIONS = frozenset({"ui"})
# 只恢复密钥而不恢复配套配置项时，凭据仍然不可用；与 Main.py 备份范围一致。
CREDENTIAL_COMPANION_KEYS = {
    "azure": ("speech_region",),
}

LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR")

# 运行期分区名→config 模块属性：必须读包装对象（如 config.app）而非
# _cfg 里的原始 dict，两者不共享写入。
_SECTION_NAMES = (
    "app",
    "whisper",
    "proxy",
    "azure",
    "siliconflow",
    "minimax_tts",
    "elevenlabs",
    "chatterbox",
    "kokoro",
    "fish_audio",
    "voxcpm",
    "ui",
    "diagnostics",
)


def _live_sections() -> dict:
    sections = {}
    for name in _SECTION_NAMES:
        value = getattr(config, name, None)
        if value is None:
            raw = getattr(config, "_cfg", {}).get(name)
            if isinstance(raw, dict):
                value = raw
        if value is not None:
            sections[name] = value
    return sections


def _section_or_404(request: Request, section: str):
    """返回运行期分区对象（写回 pending 队列依赖对象身份）。"""

    value = _live_sections().get(section)
    if value is None:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=f"unknown settings section: {section}",
        )
    return value


def _is_credential_key(key: str) -> bool:
    return str(key).endswith(CREDENTIAL_KEY_SUFFIXES)


def _is_backup_config_key(section_name: str, key: str) -> bool:
    """凭据本身及其配套配置项都属于密钥备份范围（对齐 Main.py）。"""
    if _is_credential_key(key):
        return True
    return key in CREDENTIAL_COMPANION_KEYS.get(section_name, ())


def mask_credential(value: Any) -> dict:
    """把凭据折叠成永不泄露原文的脱敏视图。"""
    text = str(value).strip() if isinstance(value, str) else ""
    items = None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        text = ",".join(items)
    if not text:
        return {"configured": False, "masked": ""}
    # 保留可辨识的 sk- 前缀与末 4 位，中间一律省略（方案 1.3 示例 "sk-…3f2a"）。
    prefix = "sk-" if text.startswith("sk-") else ""
    tail = text[-4:]
    return {"configured": True, "masked": f"{prefix}…{tail}"}


def _mask_section_snapshot(section) -> dict:
    snapshot = {}
    for key, value in section.items():
        if _is_credential_key(key):
            snapshot[key] = mask_credential(value)
        else:
            snapshot[key] = value
    return snapshot


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
    return value


@router.get("/settings/overview", summary="Provider readiness overview")
def settings_overview(request: Request):
    """服务商就绪度：与 Streamlit 通用页快捷入口共用 provider_readiness。"""

    settings = dict(config.app)
    oauth_status = {}
    for provider_id, probe in (
        ("openai_codex", _codex_connected),
        ("openai_chatgpt", _chatgpt_connected),
        ("kimi_code", _kimi_connected),
    ):
        try:
            oauth_status[provider_id] = bool(probe())
        except Exception:
            # 就绪度是本地判断，凭据探测失败按未连接处理，不阻断页面。
            oauth_status[provider_id] = False
    return utils.get_response(
        200,
        {
            "llm": {
                "configured": list(
                    provider_readiness.configured_llm_providers(settings, oauth_status)
                ),
                "oauth_status": oauth_status,
            },
            "material": {
                group: list(providers)
                for group, providers in provider_readiness.configured_material_providers(
                    settings,
                    provider_readiness.VIDEO_SOURCE_GROUPS,
                    codex_connected=oauth_status.get("openai_codex", False),
                ).items()
            },
        },
    )


def _codex_connected() -> bool:
    from app.services import codex_oauth

    return codex_oauth.account_status()


def _chatgpt_connected() -> bool:
    from app.services import chatgpt_oauth

    return chatgpt_oauth.account_status()


def _kimi_connected() -> bool:
    from app.services import kimi_code_oauth

    return kimi_code_oauth.is_authorized()


@router.get("/settings/logging", summary="Current logging options")
def get_logging_options_endpoint(request: Request):
    from app.utils.logging_utils import get_logging_options

    level, log_requests = get_logging_options()
    return utils.get_response(200, {"level": level, "log_requests": log_requests})


@router.post("/settings/logging", summary="Update logging options")
def update_logging(request: Request, payload: dict = Body(...)):
    level = payload.get("level")
    log_requests = payload.get("log_requests")
    if level is not None and str(level).upper() not in LOG_LEVELS:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message=f"level must be one of {', '.join(LOG_LEVELS)}",
        )
    if log_requests is not None and not isinstance(log_requests, bool):
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="log_requests must be a boolean",
        )
    from app.utils.logging_utils import get_logging_options

    current_level, current_log_requests = get_logging_options()
    applied = config.update_logging_options(
        str(level).upper() if level is not None else current_level,
        current_log_requests if log_requests is None else bool(log_requests),
    )
    next_level, next_log_requests = get_logging_options()
    return utils.get_response(
        200,
        {
            "applied": bool(applied),
            "level": next_level,
            "log_requests": next_log_requests,
        },
    )


@router.get("/settings/keys/backup", summary="Export key-scoped settings (masked)")
def keys_backup(request: Request):
    """按 Main.py ``_collect_key_backup`` 的备份范围导出脱敏视图。"""

    sections = _live_sections()
    backup = {}
    for section_name, section in sections.items():
        if section_name in KEY_BACKUP_EXCLUDED_SECTIONS:
            continue
        entries = {}
        for key, value in section.items():
            if not _is_backup_config_key(section_name, key):
                continue
            if _is_credential_key(key):
                entries[key] = mask_credential(value)
            else:
                normalized = _normalize_backup_value(value)
                if normalized is not None:
                    entries[key] = normalized
        if entries:
            backup[section_name] = entries
    count = sum(len(entries) for entries in backup.values())
    return utils.get_response(
        200,
        {
            "schema": "changofilm.key-backup",
            "version": 1,
            "masked": True,
            "count": count,
            "keys": backup,
        },
    )


@router.post("/settings/keys/restore", summary="Restore keys from a backup payload")
def keys_restore(request: Request, payload: dict = Body(...)):
    """校验 ``keys`` 对象并按 Main.py 备份范围应用（值由用户主动提供）。"""

    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, dict) or not keys:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="key backup file contains no restorable keys",
        )
    sections = _live_sections()
    restored = {}
    for section_name, entries in keys.items():
        if section_name not in sections or section_name in KEY_BACKUP_EXCLUDED_SECTIONS:
            continue
        if not isinstance(entries, dict):
            continue
        section_entries = {}
        for key, value in entries.items():
            if not _is_backup_config_key(section_name, key):
                continue
            # 脱敏视图不可回写：拒绝 {configured, masked} 对象，防止把掩码存成真值。
            if isinstance(value, dict) and "masked" in value:
                raise HttpException(
                    task_id=base.get_task_id(request),
                    status_code=400,
                    message=f"{section_name}.{key}: masked value cannot be restored",
                )
            normalized = _normalize_backup_value(value)
            if normalized is not None:
                section_entries[key] = normalized
        if section_entries:
            restored[section_name] = section_entries

    if not restored:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="key backup file contains no restorable keys",
        )

    applied = True
    for section_name, section_entries in restored.items():
        applied = (
            config.update_config_values_nonblocking(
                sections[section_name], section_entries
            )
            and applied
        )
    return utils.get_response(
        200,
        {
            "applied": bool(applied),
            "restored_count": sum(len(v) for v in restored.values()),
        },
    )


@router.get("/settings/{section}", summary="Snapshot a settings section (masked)")
def get_settings_section(request: Request, section: str):
    return utils.get_response(200, _mask_section_snapshot(_section_or_404(request, section)))


@router.put("/settings/{section}", summary="Partially update a settings section")
def update_settings_section(request: Request, section: str, payload: dict = Body(...)):
    current = _section_or_404(request, section)
    if not isinstance(payload, dict) or not payload:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="payload must be a non-empty object",
        )
    changes = {}
    for key, value in payload.items():
        # 键白名单：分区现有键 + 凭据后缀键（允许新增 provider 密钥）。
        if key not in current and not _is_credential_key(key):
            raise HttpException(
                task_id=base.get_task_id(request),
                status_code=400,
                message=f"unknown key in section {section}: {key}",
            )
        if isinstance(value, dict):
            raise HttpException(
                task_id=base.get_task_id(request),
                status_code=400,
                message=f"{section}.{key}: provide a raw value, not a masked object",
            )
        changes[key] = value

    applied = config.update_config_values_nonblocking(current, changes)
    return utils.get_response(
        200,
        {
            "applied": bool(applied),
            "updated_keys": sorted(changes),
            "pending": not applied,
        },
    )

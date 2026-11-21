# -*- coding: utf-8 -*-
"""系列层持久化（B6）：storage/series/{id}/series.json + characters/{cid}/ 参考图。

原子写 + OS 锁沿用 video_project.py `_atomic_json`/`_lock` 惯例（直接复用，
避免两套实现漂移）。Character Bible 参考图内容寻址命名：重生成形象=换 seed
重掷参考图组，旧图保留可回退；人工锁定的图 AI 不得覆盖/删除。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from loguru import logger
from pydantic import ValidationError

from app.models.schema import Series
from app.services.video_project import ProjectError, _atomic_json, _lock
from app.utils import utils

# 与 video_project 相同的 id 约束：拒绝路径穿越/空白 id。
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
# 剧集状态机：大纲前态（plan_id=null）仍是 draft；只允许前向迁移。
_EPISODE_TRANSITIONS = {
    "draft": {"confirmed"},
    "confirmed": {"rendered"},
    "rendered": set(),
}


class SeriesStoreError(ValueError):
    pass


def _safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SeriesStoreError(
            f"{label} id must be 1–64 letters, digits, underscores or hyphens"
        )
    return value


def new_series_id() -> str:
    return f"sr-{uuid4().hex[:12]}"


def series_root() -> Path:
    return Path(utils.storage_dir("series", create=True))


def series_dir(series_id: str) -> Path:
    return series_root() / _safe_id(series_id, "series")


def _series_file(series_id: str) -> Path:
    return series_dir(series_id) / "series.json"


def _lock_file(series_id: str) -> Path:
    return series_dir(series_id) / ".lock"


def _read_series(series_id: str) -> Series:
    """fail-closed：文件缺失返回 None 由调用方处理；损坏/版本不符直接报错。"""
    file = _series_file(series_id)
    if not file.is_file():
        raise SeriesStoreError(f"series not found: {series_id}")
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
        return Series.model_validate(payload)
    except (OSError, ValueError, ValidationError) as exc:
        raise SeriesStoreError(
            f"series {series_id} failed validation (fail-closed): {exc}"
        ) from exc


def save_series(series: Series) -> Path:
    """整份系列原子落盘。调用方负责先 load→修改→save（锁内读改写）。"""
    _safe_id(series.id, "series")
    file = _series_file(series.id)
    try:
        with _lock(_lock_file(series.id)):
            _atomic_json(file, series.model_dump(mode="json", by_alias=True))
    except ProjectError as exc:
        raise SeriesStoreError(str(exc)) from exc
    return file


def load_series(series_id: str) -> Series | None:
    """不存在返回 None；存在但损坏时 fail-closed 抛 SeriesStoreError。"""
    _safe_id(series_id, "series")
    if not _series_file(series_id).is_file():
        return None
    return _read_series(series_id)


def list_series() -> list[dict]:
    """系列清单（UI 列表页）：损坏的系列跳过并告警，不阻断其它系列。"""
    root = series_root()
    summaries = []
    for entry in sorted(root.iterdir()) if root.is_dir() else []:
        if not entry.is_dir() or not (entry / "series.json").is_file():
            continue
        try:
            series = _read_series(entry.name)
        except SeriesStoreError as exc:
            logger.warning(f"skip unreadable series: {exc}")
            continue
        summaries.append(
            {
                "id": series.id,
                "title": series.title,
                "genre_template": series.genre_template,
                "characters": len(series.characters),
                "episodes": len(series.episodes),
            }
        )
    return summaries


def update_series(series_id: str, mutate) -> Series:
    """锁内读→改→写。mutate(series) 原地修改；返回保存后的系列。"""
    _safe_id(series_id, "series")
    try:
        with _lock(_lock_file(series_id)):
            series = _read_series(series_id)
            mutate(series)
            # 修改后重新校验（id 重复/seq 连续性等由模型守卫）。
            series = Series.model_validate(series.model_dump(mode="json", by_alias=True))
            _atomic_json(
                _series_file(series_id), series.model_dump(mode="json", by_alias=True)
            )
    except ProjectError as exc:
        raise SeriesStoreError(str(exc)) from exc
    return series


# ---------------------------------------------------------------------------
# 角色参考图：内容寻址 + 人工锁定
# ---------------------------------------------------------------------------


def _character_dir(series_id: str, character_id: str) -> Path:
    return series_dir(series_id) / "characters" / _safe_id(character_id, "character")


def _locks_file(series_id: str, character_id: str) -> Path:
    return _character_dir(series_id, character_id) / "locks.json"


def _read_locks(series_id: str, character_id: str) -> set[str]:
    file = _locks_file(series_id, character_id)
    if not file.is_file():
        return set()
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
        return {str(name) for name in payload.get("locked", [])}
    except (OSError, ValueError):
        return set()


def add_reference_image(
    series_id: str, character_id: str, data: bytes, *, suffix: str = ".png"
) -> str:
    """内容寻址存入 characters/{cid}/{sha256}{ext}，并登记到系列档案。

    同字节重复添加幂等；绝不覆盖已有文件（旧图保留可回退）。返回相对
    系列目录的路径（与 series.json 中 reference_images 的存储形式一致）。
    """
    if not data:
        raise SeriesStoreError("reference image is empty")
    suffix = (suffix or ".png").lower()
    if suffix not in _IMAGE_SUFFIXES:
        raise SeriesStoreError(f"unsupported reference image suffix: {suffix}")
    digest = hashlib.sha256(data).hexdigest()
    name = f"{digest}{suffix}"
    relative = f"characters/{character_id}/{name}"
    target = _character_dir(series_id, character_id) / name

    def mutate(series: Series) -> None:
        character = next(
            (c for c in series.characters if c.id == character_id), None
        )
        if character is None:
            raise SeriesStoreError(
                f"character not found in series {series_id}: {character_id}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            # 先写临时文件再发布，避免半截图进入档案。
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
        if relative not in character.reference_images:
            character.reference_images.append(relative)

    update_series(series_id, mutate)
    return relative


def lock_reference_image(series_id: str, character_id: str, name: str) -> None:
    """人工锁定：AI 重生成/清理不得覆盖或删除该图。"""
    locks = _read_locks(series_id, character_id)
    locks.add(Path(name).name)
    _atomic_json(
        _locks_file(series_id, character_id), {"locked": sorted(locks)}
    )


def is_reference_locked(series_id: str, character_id: str, name: str) -> bool:
    return Path(name).name in _read_locks(series_id, character_id)


def unlock_reference_image(series_id: str, character_id: str, name: str) -> None:
    """解除人工锁定（UI 开关）；不触碰图片文件本身。"""
    locks = _read_locks(series_id, character_id)
    locks.discard(Path(name).name)
    _atomic_json(
        _locks_file(series_id, character_id), {"locked": sorted(locks)}
    )


def remove_reference_image(series_id: str, character_id: str, name: str) -> None:
    """从档案移除参考图；人工锁定的图拒绝删除（AI 不得覆盖人工选择）。"""
    basename = Path(name).name
    if is_reference_locked(series_id, character_id, basename):
        raise SeriesStoreError(
            f"reference image is human-locked and cannot be removed: {basename}"
        )
    relative = f"characters/{character_id}/{basename}"

    def mutate(series: Series) -> None:
        character = next(
            (c for c in series.characters if c.id == character_id), None
        )
        if character is None:
            raise SeriesStoreError(
                f"character not found in series {series_id}: {character_id}"
            )
        character.reference_images = [
            ref for ref in character.reference_images if ref != relative
        ]

    update_series(series_id, mutate)
    target = _character_dir(series_id, character_id) / basename
    target.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 剧集状态机与 plan 绑定
# ---------------------------------------------------------------------------


def bind_episode_plan(series_id: str, episode_id: str, plan_id: str) -> Series:
    def mutate(series: Series) -> None:
        episode = next((e for e in series.episodes if e.id == episode_id), None)
        if episode is None:
            raise SeriesStoreError(
                f"episode not found in series {series_id}: {episode_id}"
            )
        episode.plan_id = plan_id

    return update_series(series_id, mutate)


def set_episode_status(series_id: str, episode_id: str, status: str) -> Series:
    """draft → confirmed → rendered 前向迁移；非法迁移 fail-closed。"""
    def mutate(series: Series) -> None:
        episode = next((e for e in series.episodes if e.id == episode_id), None)
        if episode is None:
            raise SeriesStoreError(
                f"episode not found in series {series_id}: {episode_id}"
            )
        allowed = _EPISODE_TRANSITIONS.get(episode.status, set())
        if status not in allowed:
            raise SeriesStoreError(
                f"episode {episode_id} cannot move {episode.status} → {status} "
                "(state machine: draft → confirmed → rendered)"
            )
        episode.status = status

    return update_series(series_id, mutate)
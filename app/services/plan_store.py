"""脚本方案草稿库（B7 WebUI 脚本方案页的持久化后端）。

任务目录里的 script-plan.json 是执行产物（task_artifacts）；这里是执行前
的草稿库：storage/plans/{plan_id}.json。模型校验 fail-closed（extra=forbid），
原子写复用 task_artifacts 的同目录临时文件惯例，锁复用 video_project 的
条带锁惯例。系列剧集通过 series_store.bind_episode_plan 引用 plan_id。
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from uuid import uuid4

from loguru import logger
from pydantic import ValidationError

from app.models.schema import ScriptPlan
from app.services.task_artifacts import _write_json_atomic
from app.utils import utils


class PlanStoreError(ValueError):
    """草稿库读写失败（损坏文件、非法 ID、校验拒绝）。"""


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_LOCKS = tuple(threading.RLock() for _ in range(64))


def _lock(plan_id: str):
    return _LOCKS[hash(plan_id) % len(_LOCKS)]


def _safe_id(plan_id: str) -> str:
    value = str(plan_id or "")
    if not _ID.match(value):
        raise PlanStoreError(f"invalid plan id: {plan_id!r}")
    return value


def new_plan_id() -> str:
    return f"pl-{uuid4().hex[:12]}"


def plans_root() -> Path:
    """草稿库根目录。测试通过 patch plan_store.plans_root 注入临时目录。"""
    return Path(utils.storage_dir("plans", create=True))


def _plan_file(plan_id: str) -> Path:
    return plans_root() / f"{_safe_id(plan_id)}.json"


def save_plan(payload: dict, plan_id: str | None = None) -> str:
    """校验并原子落盘一份方案草稿，返回 plan_id。

    校验失败抛 PlanStoreError（导入畸形 JSON 必须拒绝，不静默丢弃）。
    修订号由调用方维护；这里只保证落盘内容与模型一致。
    """
    try:
        plan = ScriptPlan.model_validate(payload)
    except ValidationError as exc:
        raise PlanStoreError(f"script plan validation failed: {exc}") from exc
    target_id = _safe_id(plan_id) if plan_id else new_plan_id()
    target = _plan_file(target_id)
    with _lock(target_id):
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(target, plan.model_dump(mode="json", by_alias=True))
    return target_id


def load_plan(plan_id: str) -> dict | None:
    """读取草稿；不存在返回 None，损坏/校验失败抛 PlanStoreError（fail-closed）。"""
    file = _plan_file(plan_id)
    try:
        with file.open("r", encoding="utf-8") as plan_file:
            payload = json.load(plan_file)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanStoreError(f"failed to read plan {plan_id}: {exc}") from exc
    try:
        ScriptPlan.model_validate(payload)
    except ValidationError as exc:
        raise PlanStoreError(
            f"stored plan {plan_id} failed validation: {exc}"
        ) from exc
    return payload


def list_plans() -> list[dict]:
    """草稿清单（UI 列表）：损坏的草稿跳过并告警，不阻断其它草稿。"""
    root = plans_root()
    summaries = []
    for file in sorted(root.glob("pl-*.json")):
        plan_id = file.stem
        try:
            payload = load_plan(plan_id)
        except PlanStoreError as exc:
            logger.warning(f"skip corrupt plan draft: {exc}")
            continue
        if payload is None:
            continue
        summaries.append(
            {
                "id": plan_id,
                "title": payload.get("title", ""),
                "status": payload.get("status", "draft"),
                "revision": payload.get("revision", 1),
                "scenes": len(payload.get("scenes", [])),
                "series_id": payload.get("series_id"),
                "episode_id": payload.get("episode_id"),
            }
        )
    return summaries


def delete_plan(plan_id: str) -> bool:
    """删除草稿；不存在返回 False。系列引用由调用方负责解除。"""
    file = _plan_file(plan_id)
    with _lock(_safe_id(plan_id)):
        try:
            file.unlink()
            return True
        except FileNotFoundError:
            return False
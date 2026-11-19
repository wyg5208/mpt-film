"""发布历史：以追加式 JSONL 记录每一次跨平台发布尝试。

任务状态里的 cross_post_* 字段只保留"最近一次"发布结果，重启后还会丢失；
发布历史独立落盘（storage/publish_history.jsonl），供任务管理的"发布历史"
TAB 展示与重新发布。写入是 best-effort：历史写失败绝不能影响发布主链路。
"""

import json
import os
import threading
import time

from loguru import logger

from app.utils import utils

_write_lock = threading.Lock()


def history_file() -> str:
    return os.path.join(utils.storage_dir(create=True), "publish_history.jsonl")


def record_publish(entry: dict) -> None:
    """追加一条发布记录；任何异常只记日志，不向调用方抛出。"""
    try:
        payload = dict(entry)
        payload.setdefault("recorded_at", time.time())
        line = json.dumps(payload, ensure_ascii=False)
        with _write_lock:
            with open(history_file(), "a", encoding="utf-8") as file:
                file.write(line + "\n")
    except Exception as exc:
        logger.warning(f"failed to record publish history: {exc}")


def list_publish_history(limit: int = 200) -> list[dict]:
    """按时间倒序返回发布记录；损坏行跳过，文件不存在返回空列表。"""
    try:
        with open(history_file(), encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.warning(f"failed to read publish history: {exc}")
        return []

    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("task_id"):
            entries.append(entry)
    entries.sort(
        key=lambda e: e.get("finished_at") or e.get("recorded_at") or 0,
        reverse=True,
    )
    return entries[: max(0, limit)]
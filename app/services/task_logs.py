"""任务日志缓冲（迁移方案 1.2 / Phase 0 抽取）。

从 ``webui_task.py`` 抽出进程级 deque 日志缓冲与读取，供 Streamlit Fragment 轮询
与 SSE/REST 流式端点共用同一事实源。这是对 Streamlit 路径唯一的“不改变行为”的
抽取：``webui_task`` 改为委托到本模块，既有属性名（``_task_logs``、
``_task_logs_lock``、``get_task_logs``、``TASK_LOG_REFRESH_INTERVAL_SECONDS``）在
``webui_task`` 命名空间中仍可解析到同一对象。
"""

import threading
from collections import deque

_task_logs: dict[str, deque[str]] = {}
_task_logs_lock = threading.RLock()
_MAX_LOG_TASKS = 20
_MAX_LOG_RECORDS_PER_TASK = 1000
# Streamlit 无法由后台线程直接推送组件更新，只能通过 Fragment 轮询。0.5 秒足以
# 让 WebUI 日志接近终端实时输出，又不会像高频刷新那样持续占用浏览器资源。
TASK_LOG_REFRESH_INTERVAL_SECONDS = 0.5


def append_task_log(task_id: str, message: str) -> None:
    """按任务保存有限数量的日志，供 Fragment 轮询与 SSE 安全读取。"""
    with _task_logs_lock:
        records = _task_logs.get(task_id)
        if records is None:
            # 只保留最近任务的日志，避免服务长时间运行后持续占用内存。
            # dict 保持插入顺序；任务日志仅用于界面诊断，淘汰最早记录不影响任务。
            if len(_task_logs) >= _MAX_LOG_TASKS:
                oldest_task_id = next(iter(_task_logs))
                _task_logs.pop(oldest_task_id, None)
            records = deque(maxlen=_MAX_LOG_RECORDS_PER_TASK)
            _task_logs[task_id] = records
        records.append(message.rstrip())


def get_task_logs(task_id: str) -> list[str]:
    """返回日志快照，避免渲染/推送期间持有后台线程使用的锁。"""
    with _task_logs_lock:
        return list(_task_logs.get(task_id, ()))


def get_task_logs_after(task_id: str, after: int = -1, tail: int | None = None) -> tuple[list[tuple[int, str]], int]:
    """返回 ``(records, latest_seq)``，records 为 ``(index, line)`` 且 index > after。

    用于 SSE 断线重连后 REST 兜底补齐缺口（``GET /tasks/{id}/logs?after=<seq>&tail=<n>``）。
    ``tail`` 限制返回条数（取最近的 tail 条）。
    """
    with _task_logs_lock:
        records = list(_task_logs.get(task_id, ()))
    latest_seq = len(records) - 1
    indexed = [
        (index, line) for index, line in enumerate(records) if index > after
    ]
    if tail is not None and tail >= 0:
        indexed = indexed[-tail:]
    return indexed, latest_seq

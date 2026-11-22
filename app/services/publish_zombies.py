"""僵尸发布进程探测器：找出上一代 WebUI 遗留的孤儿 sau 发布进程树。

背景：重启/杀掉 WebUI 只终止 WebUI 本身，它派生的 sau.exe → node →
chromium 进程树会变成孤儿继续后台上传（同账号双开抬高风控概率，
2026-11-19 小红书僵尸任务实测遗留 3 天）。本服务让 WebUI 自己发现并
一键清理这些孤儿，无需用户开任务管理器。

纪律（与杀进程经验一致）：
- 只认命令行身份（sau.exe + 平台 + upload-video/upload-note），绝不按
  映像名或端口乱杀；
- 只判定"直接父进程已死（或父 PID 被复用）"的孤儿；父进程健在的
  外部任务（用户终端手动发布、另一个 WebUI 实例）一律不碰；
- 本进程活子进程注册表（social_auto_upload.live_publish_pids）双保险；
- 杀灭前对目标 PID 重新做一次命令行身份核验，核验不过拒绝执行。

零新增 Python 依赖：进程快照用一次 PowerShell CIM 查询取全量
PID/父PID/名称/命令行/创建时间，结果缓存 20 秒供 2s 刷新的 UI 复用。
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime

from loguru import logger

from app.services.social_auto_upload import live_publish_pids

_SCAN_TTL_SECONDS = 20.0
# 孤儿判定宽限期：父进程刚退出、子进程正在收尾的瞬态不算僵尸。
_MIN_ORPHAN_AGE_SECONDS = 60
_SNAPSHOT_TIMEOUT_SECONDS = 30

# 命令行身份：sau.exe <平台> upload-video/upload-note（路径可带引号）。
_PUBLISH_COMMAND_RE = re.compile(
    r"\bsau(?:\.exe)?[\"']?\s+"
    r"(douyin|tencent|xiaohongshu|bilibili|kuaishou|weibo|baijiahao)\s+"
    r"(upload-video|upload-note)\b",
    re.IGNORECASE,
)
# CIM CreationDate 经 ConvertTo-Json 序列化为 /Date(毫秒)/。
_WMI_DATE_RE = re.compile(r"/Date\((\d+)\)/")

_snapshot_lock = threading.Lock()
_snapshot_cache: dict = {"ts": 0.0, "processes": None}


def _parse_created_ts(value) -> float:
    """把 CIM 创建时间（/Date(ms)/ 或 ISO 字符串）解析为 epoch 秒。"""
    if not value:
        return 0.0
    text = str(value)
    match = _WMI_DATE_RE.search(text)
    if match:
        return int(match.group(1)) / 1000.0
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def _normalize(raw: dict) -> dict:
    return {
        "pid": int(raw.get("ProcessId") or 0),
        "ppid": int(raw.get("ParentProcessId") or 0),
        "name": str(raw.get("Name") or ""),
        "cmdline": str(raw.get("CommandLine") or ""),
        "created_ts": _parse_created_ts(raw.get("CreationDate")),
    }


def _query_processes(extra_filter: str = "") -> list[dict]:
    """一次 CIM 查询取进程快照；失败返回空列表（探测失败不阻塞 UI）。"""
    where = f" -Filter '{extra_filter}'" if extra_filter else ""
    # PowerShell 5.1 默认按 OEM 代码页写 stdout，中文标题会乱码；
    # 强制 UTF-8 输出后再 ConvertTo-Json。
    script = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        f"Get-CimInstance Win32_Process{where} | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate | "
        "ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_SNAPSHOT_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(result.stdout or "[]")
    except Exception as exc:
        logger.debug(f"zombie scan: process snapshot failed: {exc}")
        return []
    if isinstance(data, dict):
        data = [data]
    return [_normalize(item) for item in data if isinstance(item, dict)]


def _process_snapshot(force: bool = False) -> list[dict]:
    """带 TTL 缓存的全量进程快照；非 Windows 平台恒为空。"""
    if sys.platform != "win32":
        return []
    with _snapshot_lock:
        fresh = (
            _snapshot_cache["processes"] is not None
            and time.monotonic() - _snapshot_cache["ts"] < _SCAN_TTL_SECONDS
        )
        if fresh and not force:
            return _snapshot_cache["processes"]
    processes = _query_processes()
    with _snapshot_lock:
        _snapshot_cache["ts"] = time.monotonic()
        _snapshot_cache["processes"] = processes
    return processes


def invalidate_cache() -> None:
    """杀灭后立刻失效缓存，让下一次 UI 刷新看到真实结果。"""
    with _snapshot_lock:
        _snapshot_cache["ts"] = 0.0
        _snapshot_cache["processes"] = None


def _is_publish_process(proc: dict) -> bool:
    return proc["name"].lower() == "sau.exe" and bool(
        _PUBLISH_COMMAND_RE.search(proc["cmdline"])
    )


def _arg_value(cmdline: str, flag: str) -> str:
    """从命令行提取 --flag 的值（带引号或裸值到下一个 --flag 为止）。"""
    quoted = re.search(rf"{flag}\s+\"([^\"]*)\"", cmdline)
    if quoted:
        return quoted.group(1)
    bare = re.search(rf"{flag}\s+(.*?)(?=\s--|\s*$)", cmdline)
    return bare.group(1).strip() if bare else ""


def _parent_is_dead(proc: dict, by_pid: dict) -> bool:
    """直接父进程已死，或父 PID 已被复用（现持有者出生晚于子进程）。

    只看直接父进程：整条祖先链几乎必然终止于已退出的 userinit 等，
    沿链上溯会把用户终端里手动跑的发布也误判成孤儿。
    """
    parent = by_pid.get(proc["ppid"])
    if parent is None:
        return True
    if (
        proc["created_ts"]
        and parent["created_ts"]
        and parent["created_ts"] > proc["created_ts"]
    ):
        return True
    return False


def detect_zombies(processes: list[dict] | None = None, now: float | None = None) -> list[dict]:
    """返回僵尸发布进程列表（按存活时长降序）。

    processes 传入时跳过缓存快照（测试注入用）；生产走缓存 CIM 快照。
    """
    snapshot = processes if processes is not None else _process_snapshot()
    if not snapshot:
        return []
    now = time.time() if now is None else now
    by_pid = {proc["pid"]: proc for proc in snapshot}
    live = live_publish_pids()
    me = os.getpid()
    zombies = []
    for proc in snapshot:
        if not _is_publish_process(proc):
            continue
        if proc["pid"] in live or proc["ppid"] == me:
            continue
        if not _parent_is_dead(proc, by_pid):
            continue
        age = now - proc["created_ts"] if proc["created_ts"] else None
        if age is not None and age < _MIN_ORPHAN_AGE_SECONDS:
            continue
        match = _PUBLISH_COMMAND_RE.search(proc["cmdline"])
        zombies.append(
            {
                "pid": proc["pid"],
                "platform": match.group(1).lower(),
                "action": match.group(2).lower(),
                "account": _arg_value(proc["cmdline"], "--account") or "default",
                "title": _arg_value(proc["cmdline"], "--title"),
                "file": _arg_value(proc["cmdline"], "--file"),
                "started_ts": proc["created_ts"],
                "age_seconds": int(age) if age is not None else None,
            }
        )
    zombies.sort(key=lambda z: z["age_seconds"] or 0, reverse=True)
    return zombies


def kill_zombie(pid: int) -> dict:
    """整树终止一个僵尸发布进程；杀灭前重新核验命令行身份。

    返回 {"success", "detail"}；进程已自行退出按成功处理（目标已达成）。
    """
    if sys.platform != "win32":
        return {"success": False, "detail": "zombie kill is only supported on Windows"}
    if pid in live_publish_pids():
        return {"success": False, "detail": f"PID {pid} is a live publish of this WebUI"}
    candidates = _query_processes(extra_filter=f"ProcessId={pid}")
    proc = next((p for p in candidates if p["pid"] == pid), None)
    if proc is None:
        invalidate_cache()
        return {"success": True, "detail": f"PID {pid} already exited"}
    if not _is_publish_process(proc):
        # PID 复用/身份不符：宁可漏杀不可误杀。
        return {
            "success": False,
            "detail": f"PID {pid} is no longer a sau publish process; refused to kill",
        }
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            # taskkill 按控制台 OEM 代码页输出（中文系统为 GBK）。
            encoding="oem",
            errors="replace",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        return {"success": False, "detail": f"taskkill failed: {exc}"}
    invalidate_cache()
    detail = (result.stdout or "").strip() or (result.stderr or "").strip()
    if result.returncode == 0:
        logger.info(f"zombie publish tree killed: PID {pid} ({proc['cmdline'][:120]})")
        return {"success": True, "detail": detail}
    logger.warning(f"zombie kill failed for PID {pid}: {detail}")
    return {"success": False, "detail": detail}
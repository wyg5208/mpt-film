"""僵尸发布进程探测器测试：全部注入假进程快照，不杀真实进程。

核心纪律守卫：只认 sau 发布命令行身份；只判直接父进程已死的孤儿；
父进程健在的外部任务（终端手动发布/另一个 WebUI）绝不误报；
杀灭前重新核验身份，核验不过拒绝执行。
"""
import os
import subprocess
import time
from unittest.mock import Mock, patch

import pytest

from app.services import publish_zombies as pz
from app.services import social_auto_upload as sau


NOW = 1_800_000_000.0
OLD = NOW - 3 * 86400  # 3 天前出生


def _proc(pid, ppid, name="sau.exe", cmdline=None, created=OLD):
    if cmdline is None:
        cmdline = (
            f'"D:\\sau\\.venv\\Scripts\\sau.exe" xiaohongshu upload-video '
            f'--account default --file "D:\\tasks\\t1\\final-1.mp4" '
            f'--title "画蛇添足｜聪明反被聪明误" --headed'
        )
    return {
        "pid": pid,
        "ppid": ppid,
        "name": name,
        "cmdline": cmdline,
        "created_ts": created,
    }


@pytest.fixture(autouse=True)
def _fresh_cache():
    pz.invalidate_cache()
    yield
    pz.invalidate_cache()


def test_orphan_publish_is_detected_with_parsed_fields():
    snapshot = [_proc(34008, 36692)]  # 父进程 36692 不在快照里 → 已死
    zombies = pz.detect_zombies(processes=snapshot, now=NOW)
    assert len(zombies) == 1
    zombie = zombies[0]
    assert zombie["pid"] == 34008
    assert zombie["platform"] == "xiaohongshu"
    assert zombie["action"] == "upload-video"
    assert zombie["account"] == "default"
    assert zombie["title"] == "画蛇添足｜聪明反被聪明误"
    assert zombie["file"] == "D:\\tasks\\t1\\final-1.mp4"
    assert zombie["age_seconds"] == 3 * 86400


def test_own_live_child_is_never_flagged():
    me = os.getpid()
    snapshot = [_proc(111, me)]
    assert pz.detect_zombies(processes=snapshot, now=NOW) == []


def test_live_registry_excludes_even_if_parent_looks_dead():
    snapshot = [_proc(222, 36692)]
    with patch.object(pz, "live_publish_pids", return_value={222}):
        assert pz.detect_zombies(processes=snapshot, now=NOW) == []


def test_external_publish_with_living_parent_is_not_flagged():
    # 用户终端手动发布：sau ← powershell（健在）← 已死的祖先进程。
    # 只看直接父进程，沿祖先链上溯会把手动任务误判成孤儿。
    snapshot = [
        _proc(333, 444),
        _proc(444, 999, name="powershell.exe", cmdline="powershell -NoProfile", created=OLD - 10),
    ]
    assert pz.detect_zombies(processes=snapshot, now=NOW) == []


def test_reused_parent_pid_counts_as_dead():
    # 父 PID 被复用：现持有者出生晚于子进程 → 真父进程已死。
    snapshot = [
        _proc(555, 666),
        _proc(666, 1, name="python.exe", cmdline="python unrelated.py", created=NOW - 10),
    ]
    zombies = pz.detect_zombies(processes=snapshot, now=NOW)
    assert [z["pid"] for z in zombies] == [555]


def test_non_publish_processes_are_ignored():
    snapshot = [
        _proc(777, 1, name="chrome.exe", cmdline="chrome --type=renderer"),
        _proc(778, 1, name="python.exe", cmdline="python main.py"),
        _proc(779, 1, cmdline='"D:\\sau\\sau.exe" douyin check --account default'),
        _proc(780, 1, cmdline='"D:\\sau\\sau.exe" xiaohongshu login --account default'),
    ]
    assert pz.detect_zombies(processes=snapshot, now=NOW) == []


def test_upload_note_is_also_a_publish_identity():
    snapshot = [
        _proc(781, 1, cmdline='"D:\\sau\\sau.exe" xiaohongshu upload-note --account default --title "图文"'),
    ]
    zombies = pz.detect_zombies(processes=snapshot, now=NOW)
    assert [z["pid"] for z in zombies] == [781]
    assert zombies[0]["action"] == "upload-note"


def test_grace_period_skips_fresh_orphans():
    snapshot = [_proc(888, 1, created=NOW - 30)]
    assert pz.detect_zombies(processes=snapshot, now=NOW) == []
    snapshot = [_proc(888, 1, created=NOW - 120)]
    assert [z["pid"] for z in pz.detect_zombies(processes=snapshot, now=NOW)] == [888]


def test_unknown_creation_time_still_flags_orphan():
    snapshot = [_proc(889, 1, created=0.0)]
    zombies = pz.detect_zombies(processes=snapshot, now=NOW)
    assert [z["pid"] for z in zombies] == [889]
    assert zombies[0]["age_seconds"] is None


def test_zombies_sorted_by_age_desc():
    snapshot = [
        _proc(901, 1, created=NOW - 3600),
        _proc(902, 1, created=NOW - 86400),
    ]
    assert [z["pid"] for z in pz.detect_zombies(processes=snapshot, now=NOW)] == [902, 901]


def test_empty_snapshot_returns_empty():
    assert pz.detect_zombies(processes=[], now=NOW) == []


def test_parse_created_ts_wmi_and_iso():
    assert pz._parse_created_ts("/Date(1763546846000)/") == 1763546846.0
    assert pz._parse_created_ts(None) == 0.0
    assert pz._parse_created_ts("garbage") == 0.0
    assert pz._parse_created_ts("2026-11-19T15:07:26") > 0


def test_kill_refuses_when_identity_changed():
    # PID 复用后目标已不是 sau 发布进程：宁可漏杀不可误杀。
    foreign = _proc(34008, 1, name="python.exe", cmdline="python unrelated.py")
    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "_query_processes", return_value=[foreign]),
        patch.object(pz.subprocess, "run") as taskkill,
    ):
        result = pz.kill_zombie(34008)
    assert result["success"] is False
    assert "refused" in result["detail"]
    taskkill.assert_not_called()


def test_kill_refuses_live_registry_pid():
    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "live_publish_pids", return_value={34008}),
        patch.object(pz, "_query_processes") as query,
        patch.object(pz.subprocess, "run") as taskkill,
    ):
        result = pz.kill_zombie(34008)
    assert result["success"] is False
    query.assert_not_called()
    taskkill.assert_not_called()


def test_kill_verifies_identity_then_kills_whole_tree():
    target = _proc(34008, 36692)
    completed = Mock(returncode=0, stdout="SUCCESS", stderr="")
    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "_query_processes", return_value=[target]) as query,
        patch.object(pz.subprocess, "run", return_value=completed) as taskkill,
    ):
        result = pz.kill_zombie(34008)
    assert result["success"] is True
    # 杀灭前必须重新拉取该 PID 的命令行做身份核验。
    assert query.call_args.kwargs["extra_filter"] == "ProcessId=34008"
    assert taskkill.call_args.args[0] == ["taskkill", "/F", "/T", "/PID", "34008"]


def test_kill_already_exited_is_success():
    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "_query_processes", return_value=[]),
        patch.object(pz.subprocess, "run") as taskkill,
    ):
        result = pz.kill_zombie(34008)
    assert result["success"] is True
    assert "already exited" in result["detail"]
    taskkill.assert_not_called()


def test_kill_taskkill_failure_reports_detail():
    target = _proc(34008, 36692)
    completed = Mock(returncode=128, stdout="", stderr="Access is denied.")
    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "_query_processes", return_value=[target]),
        patch.object(pz.subprocess, "run", return_value=completed),
    ):
        result = pz.kill_zombie(34008)
    assert result["success"] is False
    assert "Access is denied" in result["detail"]


def test_non_windows_degrades_gracefully():
    with patch.object(pz.sys, "platform", "linux"):
        assert pz.detect_zombies() == []
        assert pz.kill_zombie(1)["success"] is False


def test_snapshot_cache_ttl_and_invalidation():
    calls = []

    def fake_query(extra_filter=""):
        calls.append(extra_filter)
        return [_proc(34008, 36692)]

    with (
        patch.object(pz.sys, "platform", "win32"),
        patch.object(pz, "_query_processes", side_effect=fake_query),
    ):
        first = pz._process_snapshot()
        second = pz._process_snapshot()
        assert first is second
        assert len(calls) == 1
        pz.invalidate_cache()
        pz._process_snapshot()
        assert len(calls) == 2


def test_run_command_registers_and_unregisters_live_pid():
    proc = Mock()
    proc.pid = 4321
    seen = {}

    def communicate(timeout=None):
        seen["during"] = sau.live_publish_pids()
        return "ok", ""

    proc.communicate.side_effect = communicate
    proc.returncode = 0
    with patch.object(sau.subprocess, "Popen", return_value=proc):
        code, _, _ = sau._run_command(["sau", "douyin", "upload-video"], 1800)
    assert code == 0
    assert 4321 in seen["during"]
    assert 4321 not in sau.live_publish_pids()


def test_run_command_unregisters_pid_on_timeout():
    proc = Mock()
    proc.pid = 4322
    proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="sau", timeout=1800)
    with (
        patch.object(sau.subprocess, "Popen", return_value=proc),
        patch.object(sau, "_kill_process_tree"),
    ):
        code, _, _ = sau._run_command(["sau", "douyin", "upload-video"], 1800)
    assert code == -1
    assert 4322 not in sau.live_publish_pids()
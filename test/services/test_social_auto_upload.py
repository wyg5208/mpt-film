"""social-auto-upload（sau CLI）服务层测试：全部 mock 子进程，不触网不起浏览器。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.services import social_auto_upload as sau


LIVE_CONFIG = {
    "social_publish_enabled": True,
    "social_publish_auto_upload": True,
    "social_publish_account": "creator",
    "sau_cli_path": "sau",
    "social_publish_bilibili_tid": 21,
    "social_publish_platforms": ["douyin", "bilibili"],
}


@pytest.fixture
def video_file():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "video.mp4"
        path.write_bytes(b"fixture")
        yield str(path)


def _upload(video_path, platforms=None, side_effect=None, run_mock=None):
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.shutil, "which", return_value="C:/fake/sau.exe"),
        patch.object(
            sau, "_run_command", side_effect=side_effect or (lambda args, timeout, env=None, on_output=None: (0, "ok", ""))
        ) as runner,
    ):
        result = sau.social_auto_upload_service.upload_video(
            video_path, "标题", desc="简介", tags=["#美食", "#日常"], platforms=platforms
        )
    return result, runner


def test_success_publishes_every_platform_serially(video_file):
    result, runner = _upload(video_file, platforms=["douyin", "bilibili"])
    assert result["success"] is True
    assert runner.call_count == 2
    assert [call.args[0][1] for call in runner.call_args_list] == ["douyin", "bilibili"]
    assert result["results"]["douyin"] == {"platform": "douyin", "success": True}
    assert result["results"]["bilibili"]["success"] is True


def test_single_platform_failure_is_not_overall_success(video_file):
    def flaky(args, timeout, env=None, on_output=None):
        if args[1] == "douyin":
            return 1, "", "session expired"
        return 0, "ok", ""

    result, _ = _upload(video_file, platforms=["douyin", "bilibili"], side_effect=flaky)
    assert result["success"] is False
    assert "douyin" in result["error"]
    assert "session expired" in result["results"]["douyin"]["error"]
    assert result["results"]["bilibili"]["success"] is True


def test_command_arguments_follow_sau_contract(video_file):
    result, runner = _upload(video_file, platforms=["bilibili"])
    assert result["success"] is True
    args = runner.call_args.args[0]
    assert args[0] == "C:/fake/sau.exe"
    assert args[1:3] == ["bilibili", "upload-video"]
    assert args[args.index("--account") + 1] == "creator"
    assert args[args.index("--file") + 1] == video_file
    assert args[args.index("--title") + 1] == "标题"
    assert args[args.index("--desc") + 1] == "简介"
    # llm  hashtags carry '#'; sau --tags expects bare comma-separated tags.
    assert args[args.index("--tags") + 1] == "美食,日常"
    assert args[args.index("--tid") + 1] == "21"


def test_non_bilibili_platform_has_no_tid(video_file):
    _, runner = _upload(video_file, platforms=["douyin"])
    assert "--tid" not in runner.call_args.args[0]


def test_timeout_kills_process_tree():
    proc = Mock()
    proc.pid = 4321
    proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="sau", timeout=1800)
    with (
        patch.object(sau.subprocess, "Popen", return_value=proc),
        patch.object(sau.subprocess, "run") as taskkill,
        patch.object(sau.sys, "platform", "win32"),
    ):
        code, _, err = sau._run_command(["sau", "douyin", "upload-video"], 1800)
    assert code == -1
    assert "timed out" in err
    proc.kill.assert_called_once()
    # Windows 必须清理 Playwright 派生的浏览器孙进程。
    assert taskkill.call_args.args[0][:4] == ["taskkill", "/F", "/T", "/PID"]
    assert taskkill.call_args.args[0][4] == "4321"


def test_missing_cli_fails_with_install_hint(video_file):
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.shutil, "which", return_value=None),
        patch.object(sau.os.path, "isfile", return_value=False),
    ):
        assert sau.social_auto_upload_service.is_configured() is False
        result = sau.social_auto_upload_service.upload_video(video_file, "标题")
    assert result["success"] is False
    assert "CLI not found" in result["error"]


def test_unsupported_platform_is_rejected(video_file):
    result, runner = _upload(video_file, platforms=["youtube"])
    assert result["success"] is False
    assert "unsupported" in result["error"]
    runner.assert_not_called()


def test_missing_video_file_is_rejected():
    result, runner = _upload("Z:/definitely/missing.mp4")
    assert result["success"] is False
    assert "not found" in result["error"]
    runner.assert_not_called()


def test_disabled_channel_skips_publish(video_file):
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG, social_publish_enabled=False)),
        patch.object(sau, "_run_command") as runner,
    ):
        result = sau.social_auto_upload_service.upload_video(video_file, "标题")
    assert result["success"] is False
    assert "not enabled" in result["error"]
    runner.assert_not_called()


def test_account_snapshot_is_frozen_at_queue_time():
    snapshot = {
        "social_publish_enabled": True,
        "social_publish_account": "queued",
        "sau_cli_path": "queued-sau",
        "social_publish_bilibili_tid": 7,
        "social_publish_browsers_path": "B:/queued-browsers",
        "social_publish_headed": False,
    }
    with patch.object(sau.config, "app", dict(LIVE_CONFIG)):
        service = sau.SocialAutoUploadService(snapshot)
        assert service.account == "queued"
        assert service.bilibili_tid == 7
        assert service.browsers_path == "B:/queued-browsers"
        assert service.headed is False
        assert service.snapshot_account() == snapshot
        # 活配置随后改变不影响已排队任务使用的快照。
        assert service._account_setting("sau_cli_path", "sau") == "queued-sau"


def test_invalid_tid_falls_back_to_default():
    with patch.object(sau.config, "app", dict(LIVE_CONFIG, social_publish_bilibili_tid="abc")):
        assert sau.social_auto_upload_service.bilibili_tid == 21


def test_resolve_cli_falls_back_to_bundled_install():
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.shutil, "which", return_value=None),
        patch.object(sau, "_bundled_cli_path", return_value="B:/bundled/sau.exe"),
    ):
        assert sau.social_auto_upload_service.resolve_cli() == "B:/bundled/sau.exe"


def test_resolve_cli_explicit_wrong_path_does_not_fall_back():
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG, sau_cli_path="Z:/wrong/sau.exe")),
        patch.object(sau.shutil, "which", return_value=None),
        patch.object(sau, "_bundled_cli_path", return_value="B:/bundled/sau.exe"),
    ):
        # 显式配置错误路径时不应静默改用其他安装，避免掩盖配置错误。
        assert sau.social_auto_upload_service.resolve_cli() is None


def test_check_sessions_reports_per_platform():
    def checker(args, timeout, env=None, on_output=None):
        assert args[2] == "check"
        if args[1] == "douyin":
            return 0, "session valid", ""
        return 1, "", "cookie expired"

    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.shutil, "which", return_value="C:/fake/sau.exe"),
        patch.object(sau, "_run_command", side_effect=checker),
    ):
        report = sau.social_auto_upload_service.check_sessions(["douyin", "tencent"])
    assert report["douyin"]["ok"] is True
    assert report["tencent"]["ok"] is False
    assert "cookie expired" in report["tencent"]["detail"]


def test_check_sessions_refuses_concurrent_runs():
    assert sau._check_lock.acquire(blocking=False)
    try:
        assert sau.social_auto_upload_service.check_sessions(["douyin"]) is None
    finally:
        sau._check_lock.release()


def test_is_sau_platform_routing_membership():
    for platform in ("douyin", "tencent", "xiaohongshu", "bilibili", "kuaishou", "weibo", "baijiahao"):
        assert sau.is_sau_platform(platform)
    for platform in ("tiktok", "instagram", "youtube", "", None):
        assert not sau.is_sau_platform(platform)


def test_command_env_prefers_explicit_ui_config(tmp_path):
    with (
        patch.object(
            sau.config, "app", dict(LIVE_CONFIG, social_publish_browsers_path=str(tmp_path))
        ),
        patch.dict(sau.os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "X:/system-env"}),
    ):
        env = sau.social_auto_upload_service._command_env()
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path)


def test_command_env_keeps_system_env_when_unconfigured():
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.dict(sau.os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "X:/system-env"}),
    ):
        env = sau.social_auto_upload_service._command_env()
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "X:/system-env"


def test_command_env_falls_back_to_bundled_browsers():
    environ = {k: v for k, v in sau.os.environ.items() if k != "PLAYWRIGHT_BROWSERS_PATH"}
    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.os, "environ", environ),
        patch.object(sau, "_bundled_browsers_path", return_value="B:/bundled"),
    ):
        env = sau.social_auto_upload_service._command_env()
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "B:/bundled"


def test_command_env_ignores_missing_configured_dir():
    with (
        patch.object(
            sau.config,
            "app",
            dict(LIVE_CONFIG, social_publish_browsers_path="Z:/definitely/missing"),
        ),
        patch.dict(sau.os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "X:/system-env"}),
    ):
        env = sau.social_auto_upload_service._command_env()
    # 配置目录不存在时不应把无效路径传给子进程。
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "X:/system-env"


def test_upload_and_check_pass_env_to_subprocess(video_file):
    with (
        patch.object(
            sau.config, "app", dict(LIVE_CONFIG, social_publish_browsers_path="B:/ui-config")
        ),
        patch.object(sau.shutil, "which", return_value="C:/fake/sau.exe"),
        patch.object(sau.os.path, "isdir", return_value=True),
        patch.object(
            sau, "_run_command", side_effect=lambda args, timeout, env=None, on_output=None: (0, "ok", "")
        ) as runner,
    ):
        sau.social_auto_upload_service.upload_video(video_file, "标题", platforms=["douyin"])
        sau.social_auto_upload_service.check_sessions(["douyin"])
    assert runner.call_count == 2
    for call in runner.call_args_list:
        assert call.kwargs["env"]["PLAYWRIGHT_BROWSERS_PATH"] == "B:/ui-config"


def test_run_command_streams_stdout_and_stderr_lines_live():
    # 真实子进程验证流式模式：sau 的 loguru 控制台日志写在 stdout，
    # 两路都必须逐行实时回调，否则发布队列面板看不到日志。
    lines = []
    code, stdout, stderr = sau._run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('out-line'); print('err-line', file=sys.stderr)",
        ],
        30,
        on_output=lines.append,
    )
    assert code == 0
    assert "out-line" in stdout
    assert "err-line" in stderr
    assert "out-line" in lines
    assert "err-line" in lines


def test_upload_defaults_to_headed_browser(video_file):
    _, runner = _upload(video_file, platforms=["douyin", "bilibili"])
    douyin_args, bili_args = [call.args[0] for call in runner.call_args_list]
    # 默认有头：用户可观察自动化并人工处理验证码，降低风控拦截。
    assert "--headed" in douyin_args
    assert "--headless" not in douyin_args
    # B 站走 biliup（无浏览器），CLI 不接受 headed/headless 参数。
    assert "--headed" not in bili_args
    assert "--headless" not in bili_args


def test_upload_headless_when_disabled(video_file):
    with (
        patch.object(
            sau.config, "app", dict(LIVE_CONFIG, social_publish_headed=False)
        ),
        patch.object(sau.shutil, "which", return_value="C:/fake/sau.exe"),
        patch.object(
            sau, "_run_command", side_effect=lambda args, timeout, env=None, on_output=None: (0, "ok", "")
        ) as runner,
    ):
        sau.social_auto_upload_service.upload_video(video_file, "标题", platforms=["douyin"])
    args = runner.call_args.args[0]
    assert "--headless" in args
    assert "--headed" not in args


def test_upload_passes_output_callback_to_runner(video_file):
    def callback(line):
        pass

    with (
        patch.object(sau.config, "app", dict(LIVE_CONFIG)),
        patch.object(sau.shutil, "which", return_value="C:/fake/sau.exe"),
        patch.object(
            sau, "_run_command", side_effect=lambda args, timeout, env=None, on_output=None: (0, "ok", "")
        ) as runner,
    ):
        sau.social_auto_upload_service.upload_video(
            video_file, "标题", platforms=["douyin"], on_output=callback
        )
    assert runner.call_args.kwargs["on_output"] is callback
"""
social-auto-upload (sau CLI) integration for publishing videos to domestic
platforms: Douyin, WeChat Channels (tencent), Xiaohongshu, Bilibili, and the
optional Kuaishou / Weibo / Baijiahao channels.

Upstream: https://github.com/dreammis/social-auto-upload (MIT)

sau 是独立安装的外部工具（独立仓库 + 独立 venv），这里只通过子进程调用，
不引入任何 Python 依赖。返回契约与 upload_post.py 对齐
（{"success", "results", "error"}），使 task.py 的发布状态机零改动复用。
"""
import os
import shutil
import subprocess
import sys
import threading
from typing import Optional

from loguru import logger

from app.config import config


# 走 sau 通道的平台 id。视频号在上游 CLI 中的平台名是 tencent。
_SAU_PLATFORMS = {
    "douyin",
    "tencent",
    "xiaohongshu",
    "bilibili",
    "kuaishou",
    "weibo",
    "baijiahao",
}
# 核心四平台在前，可选平台在后；WebUI 多选框沿用该顺序。
SAU_PLATFORM_ORDER = [
    "douyin",
    "tencent",
    "xiaohongshu",
    "bilibili",
    "kuaishou",
    "weibo",
    "baijiahao",
]
DEFAULT_SAU_PLATFORMS = ["douyin", "tencent", "xiaohongshu", "bilibili"]

_PLATFORM_TIMEOUT_SECONDS = 1800
_CHECK_TIMEOUT_SECONDS = 120
_ERROR_TAIL_LENGTH = 500


def _bundled_browsers_path() -> str:
    """项目自带的浏览器目录；存在时发布/体检无需用户手动 setx。"""
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    candidate = os.path.join(root, "opensources", "pw-browsers")
    return candidate if os.path.isdir(candidate) else ""


def _bundled_cli_path() -> str:
    """项目自带的 sau 安装（独立 venv）；存在时无需配置 sau_cli_path。"""
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    exe = "sau.exe" if sys.platform == "win32" else "sau"
    candidate = os.path.join(
        root, "opensources", "social-auto-upload", ".venv", bin_dir, exe
    )
    return candidate if os.path.isfile(candidate) else ""

# 登录态体检会启动浏览器，禁止 UI 重复点击造成并发体检。
_check_lock = threading.Lock()


def is_sau_platform(platform: str) -> bool:
    return (platform or "").strip().lower() in _SAU_PLATFORMS


def _output_tail(text: str) -> str:
    value = (text or "").strip()
    return value[-_ERROR_TAIL_LENGTH:] if len(value) > _ERROR_TAIL_LENGTH else value


def _kill_process_tree(proc: subprocess.Popen, drain: bool = True) -> None:
    """超时后清理子进程树；Playwright 会派生浏览器孙进程，单杀父进程会残留。

    drain=False 用于流式模式：管道已由读线程接管，不能再调 communicate。
    """
    try:
        proc.kill()
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            logger.warning(f"failed to kill sau process tree {proc.pid}: {exc}")
    if drain:
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass


def _run_command(
    args: list[str],
    timeout: int,
    env: dict | None = None,
    on_output=None,
) -> tuple[int, str, str]:
    """执行 sau 命令；超时按失败处理并清理进程树，返回 (code, stdout, stderr)。

    传入 on_output 时逐行实时回调 stdout/stderr（sau 的 loguru 控制台
    handler 写在 stdout，业务日志文件另行落盘），供发布队列面板展示
    实时日志；不传时保持原有 communicate 行为。
    """
    popen_kwargs = {}
    if sys.platform == "win32":
        # WebUI 后台发布不应弹出控制台窗口；有头浏览器窗口不受此影响。
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        **popen_kwargs,
    )
    timeout_error = f"sau command timed out after {timeout}s: {' '.join(args[:3])}"
    if on_output is None:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, stdout or "", stderr or ""
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            return -1, "", timeout_error

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def _pump(stream, sink, callback) -> None:
        try:
            for line in stream:
                sink.append(line)
                if callback is not None:
                    try:
                        callback(line.rstrip("\r\n"))
                    except Exception:
                        # 日志回调失败不得影响发布本身。
                        pass
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    pumps = [
        threading.Thread(target=_pump, args=(proc.stdout, stdout_chunks, on_output), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, stderr_chunks, on_output), daemon=True),
    ]
    for pump in pumps:
        pump.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc, drain=False)
        for pump in pumps:
            pump.join(timeout=5)
        return -1, "".join(stdout_chunks), timeout_error
    for pump in pumps:
        pump.join(timeout=10)
    return proc.returncode, "".join(stdout_chunks), "".join(stderr_chunks)


class SocialAutoUploadService:
    def __init__(self, account: dict | None = None):
        # 与 UploadPostService 相同：后台发布必须沿用排队时的配置快照，
        # 之后修改 WebUI 不应改变已排队视频的账号或 CLI 路径。
        self._account = dict(account) if account is not None else None

    def snapshot_account(self) -> dict:
        settings = dict(config.app if self._account is None else self._account)
        return {
            "social_publish_enabled": settings.get("social_publish_enabled", False),
            "social_publish_account": settings.get("social_publish_account", "default"),
            "sau_cli_path": settings.get("sau_cli_path", "sau"),
            "social_publish_bilibili_tid": settings.get(
                "social_publish_bilibili_tid", 21
            ),
            "social_publish_browsers_path": settings.get(
                "social_publish_browsers_path", ""
            ),
            "social_publish_headed": settings.get("social_publish_headed", True),
        }

    def _account_setting(self, key: str, default):
        settings = config.app if self._account is None else self._account
        return settings.get(key, default)

    @property
    def enabled(self) -> bool:
        return self._account_setting("social_publish_enabled", False)

    @property
    def platforms(self) -> list:
        return config.app.get("social_publish_platforms", DEFAULT_SAU_PLATFORMS)

    @property
    def auto_upload(self) -> bool:
        return config.app.get("social_publish_auto_upload", False)

    @property
    def account(self) -> str:
        return self._account_setting("social_publish_account", "default")

    @property
    def bilibili_tid(self) -> int:
        value = self._account_setting("social_publish_bilibili_tid", 21)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 21

    def resolve_cli(self) -> str | None:
        """把配置的 CLI 路径解析为可执行文件；找不到返回 None。

        保持默认值 `sau` 时，PATH 上找不到则回退到项目自带的
        opensources/social-auto-upload 安装，避免新手漏填路径。
        """
        configured = str(
            self._account_setting("sau_cli_path", "sau") or "sau"
        ).strip()
        if os.path.isfile(configured):
            return configured
        found = shutil.which(configured)
        if found:
            return found
        if configured == "sau":
            bundled = _bundled_cli_path()
            if bundled:
                return bundled
        return None

    @property
    def browsers_path(self) -> str:
        return str(
            self._account_setting("social_publish_browsers_path", "") or ""
        ).strip()

    @property
    def headed(self) -> bool:
        # 国内平台风控对无头浏览器敏感，且用户需要看到自动化操作过程
        # （验证码/短信拦截只有可见窗口才能人工处理），默认有头。
        return bool(self._account_setting("social_publish_headed", True))

    def _command_env(self) -> dict:
        """为 sau 子进程注入 PLAYWRIGHT_BROWSERS_PATH。

        优先级：UI 显式配置 > 系统环境变量 > 项目自带 opensources/pw-browsers。
        这样用户无需 setx，也不必为了环境变量重启 WebUI。
        """
        env = os.environ.copy()
        configured = self.browsers_path
        if configured:
            if os.path.isdir(configured):
                env["PLAYWRIGHT_BROWSERS_PATH"] = configured
            else:
                logger.warning(
                    "configured social_publish_browsers_path does not exist: "
                    f"{configured}"
                )
            return env
        if not env.get("PLAYWRIGHT_BROWSERS_PATH"):
            bundled = _bundled_browsers_path()
            if bundled:
                env["PLAYWRIGHT_BROWSERS_PATH"] = bundled
        return env

    def is_configured(self) -> bool:
        return bool(self.enabled and self.resolve_cli())

    def _base_command(self, platform: str) -> list[str] | None:
        cli = self.resolve_cli()
        if not cli:
            return None
        return [cli, platform]

    def upload_video(
        self,
        video_path: str,
        title: str,
        desc: str = "",
        tags: Optional[list] = None,
        platforms: Optional[list] = None,
        account: Optional[str] = None,
        tid: Optional[int] = None,
        on_output=None,
    ) -> dict:
        """逐平台串行发布一个视频；任何失败都收敛为结果字典，不抛异常。"""
        if not self.enabled:
            return {
                "success": False,
                "error": "social-auto-upload publishing is not enabled",
            }
        if platforms is None:
            platforms = self.platforms
        platforms = [
            str(platform).strip().lower()
            for platform in platforms
            if str(platform).strip()
        ]
        unsupported = [p for p in platforms if p not in _SAU_PLATFORMS]
        if unsupported:
            return {
                "success": False,
                "error": "unsupported social-auto-upload platforms: "
                + ", ".join(unsupported),
            }
        if not platforms:
            return {"success": False, "error": "no platforms configured"}
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return {"success": False, "error": f"Video file not found: {video_path}"}
        if not self.resolve_cli():
            return {
                "success": False,
                "error": "social-auto-upload CLI not found; install it and set "
                "sau_cli_path in the publish settings",
            }

        account_name = str(account or self.account or "default").strip() or "default"
        # llm.py 的 hashtags 带 # 前缀；sau --tags 约定逗号分隔的裸标签。
        tag_text = ",".join(
            str(tag).lstrip("#").strip() for tag in (tags or []) if str(tag).strip()
        )
        partition = self.bilibili_tid if tid is None else int(tid)
        command_env = self._command_env()

        results = {}
        for platform in platforms:
            args = self._base_command(platform) + [
                "upload-video",
                "--account", account_name,
                "--file", video_path,
                "--title", title or "",
                "--desc", desc or "",
            ]
            if tag_text:
                args += ["--tags", tag_text]
            if platform == "bilibili":
                args += ["--tid", str(partition)]
            # sau upload-video 默认 headless；显式传参避免依赖 conf.py。
            # B 站走 biliup 命令行（无浏览器），不接受 headed/headless 参数。
            if platform != "bilibili":
                args += ["--headed"] if self.headed else ["--headless"]

            logger.info(
                f"publishing video to {platform} via social-auto-upload "
                f"(account={account_name})..."
            )
            try:
                code, stdout, stderr = _run_command(
                    args, _PLATFORM_TIMEOUT_SECONDS, env=command_env, on_output=on_output
                )
            except Exception as exc:
                # CLI 损坏、权限不足等同步异常同样只影响发布状态。
                logger.exception(f"sau {platform} upload crashed: {exc}")
                results[platform] = {
                    "platform": platform,
                    "success": False,
                    "error": f"sau {platform} failed to start: {exc}",
                }
                continue

            if code == 0:
                logger.success(f"video published to {platform}")
                results[platform] = {"platform": platform, "success": True}
            else:
                detail = _output_tail(stderr) or _output_tail(stdout)
                error = f"sau {platform} exited with code {code}"
                if detail:
                    error += f": {detail}"
                logger.warning(error)
                results[platform] = {
                    "platform": platform,
                    "success": False,
                    "error": error,
                }

        failures = [
            platform for platform, entry in results.items() if not entry["success"]
        ]
        if failures:
            return {
                "success": False,
                "results": results,
                "error": "social-auto-upload failed platforms: "
                + ", ".join(failures),
            }
        return {"success": True, "results": results}

    def check_sessions(
        self, platforms: list, account: Optional[str] = None
    ) -> dict | None:
        """逐平台体检登录态；已有体检在运行时返回 None，避免并发浏览器。"""
        if not _check_lock.acquire(blocking=False):
            return None
        try:
            account_name = str(account or self.account or "default").strip() or "default"
            command_env = self._command_env()
            report = {}
            for platform in platforms:
                platform = str(platform).strip().lower()
                if platform not in _SAU_PLATFORMS:
                    report[platform] = {
                        "ok": False,
                        "detail": f"unsupported platform: {platform}",
                    }
                    continue
                args = self._base_command(platform)
                if not args:
                    report[platform] = {
                        "ok": False,
                        "detail": "social-auto-upload CLI not found",
                    }
                    continue
                try:
                    code, stdout, stderr = _run_command(
                        args + ["check", "--account", account_name],
                        _CHECK_TIMEOUT_SECONDS,
                        env=command_env,
                    )
                except Exception as exc:
                    report[platform] = {"ok": False, "detail": str(exc)}
                    continue
                detail = _output_tail(stdout) or _output_tail(stderr)
                report[platform] = {"ok": code == 0, "detail": detail}
            return report
        finally:
            _check_lock.release()


# Singleton instance
social_auto_upload_service = SocialAutoUploadService()


def cross_post_video(
    video_path: str,
    title: str,
    desc: str = "",
    tags: Optional[list] = None,
    platforms: Optional[list] = None,
    account: Optional[str] = None,
    tid: Optional[int] = None,
    account_snapshot: dict | None = None,
    on_output=None,
) -> dict:
    service = (
        SocialAutoUploadService(account_snapshot)
        if account_snapshot is not None
        else social_auto_upload_service
    )
    return service.upload_video(
        video_path,
        title,
        desc=desc,
        tags=tags,
        platforms=platforms,
        account=account,
        tid=tid,
        on_output=on_output,
    )
import argparse
import sys

import uvicorn
from loguru import logger

from app.config import config

STREAMLIT_FLAGS = [
    "--server.address=0.0.0.0",
    "--server.port=8501",
    "--browser.serverAddress=127.0.0.1",
    "--server.enableCORS=True",
    "--browser.gatherUsageStats=False",
    "--client.toolbarMode=minimal",
    "--logger.hideWelcomeMessage=True",
    "--server.showEmailPrompt=False",
]


def run_web(host: str, port: int) -> None:
    """FastAPI + 内嵌 React 构建产物的单源启动方式（迁移方案 Phase 3.1）。"""
    logger.info(
        "start changofilm web (API + SPA), docs: http://127.0.0.1:"
        + str(port)
        + "/docs"
    )
    # FFmpeg 探测已经移到 app/services/task.py 的共享任务流水线里，这样
    # API、CLI 和 WebUI 三条路径都能统一覆盖，这里不再单独检查。
    uvicorn.run(
        app="app.asgi:app",
        host=host,
        port=port,
        reload=config.reload_debug,
        log_level="warning",
    )


def run_streamlit() -> None:
    """保留 Streamlit 回归安全网入口（Phase 3 观察期结束前不下线）。"""
    import subprocess

    logger.info("start changofilm streamlit (legacy WebUI) on http://127.0.0.1:8501")
    sys.exit(
        subprocess.call(
            [sys.executable, "-m", "streamlit", "run", "./webui/Main.py"]
            + STREAMLIT_FLAGS
        )
    )


def main() -> None:
    argv = sys.argv[1:]
    # 仅当首个参数是已知子命令（或显式帮助）时才进入 argparse；其余调用保持旧
    # 入口行为，直接用运行时配置起 uvicorn。这样既兼容历史 `python main.py`，
    # 也不会被进程内残留 argv（如 test_main.py 用 runpy 触发时 pytest 自己的
    # 参数）误判成非法子命令而 SystemExit。
    if argv and argv[0] in ("web", "streamlit", "-h", "--help"):
        parser = argparse.ArgumentParser(prog="changofilm")
        sub = parser.add_subparsers(dest="command")

        web = sub.add_parser(
            "web", help="FastAPI + embedded React SPA (single origin)"
        )
        web.add_argument("--host", default=config.listen_host)
        web.add_argument("--port", type=int, default=config.listen_port)

        sub.add_parser(
            "streamlit", help="Legacy Streamlit WebUI (regression safety net)"
        )

        args = parser.parse_args(argv)
        if args.command == "streamlit":
            run_streamlit()
            return
        if args.command == "web":
            run_web(args.host, args.port)
            return

    run_web(config.listen_host, config.listen_port)


if __name__ == "__main__":
    main()

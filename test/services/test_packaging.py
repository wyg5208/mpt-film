"""验证安装入口、可写目录与资源初始化的关键边界。"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app import launcher, paths


def test_source_checkout_keeps_legacy_paths(monkeypatch):
    monkeypatch.delenv("CHANGOFILM_HOME", raising=False)
    monkeypatch.delenv("MPT_HOME", raising=False)
    assert paths.runtime_root() == paths.SOURCE_ROOT
    assert paths.resource_directory("fonts") == paths.SOURCE_ROOT / "resource/fonts"


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_installed_data_is_in_user_directory(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(paths, "is_source_checkout", lambda: False)
    monkeypatch.setattr(paths.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for key in ("CHANGOFILM_HOME", "MPT_HOME", "LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(key, raising=False)
    expected = {
        "darwin": tmp_path / "Library/Application Support/ChangoFilm",
        "win32": tmp_path / "AppData/Local/ChangoFilm",
        "linux": tmp_path / ".local/share/ChangoFilm",
    }
    assert paths.runtime_root() == expected[platform]


def test_explicit_home_and_linux_xdg_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("CHANGOFILM_HOME", str(tmp_path / "explicit"))
    assert paths.runtime_root() == tmp_path / "explicit"
    monkeypatch.delenv("CHANGOFILM_HOME")
    monkeypatch.delenv("MPT_HOME", raising=False)
    monkeypatch.setattr(paths, "is_source_checkout", lambda: False)
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths.runtime_root() == tmp_path / "xdg/ChangoFilm"


def test_legacy_mpt_home_env_still_accepted(monkeypatch, tmp_path):
    """品牌升级后旧 MPT_HOME 仍可用，新 CHANGOFILM_HOME 优先。"""
    monkeypatch.delenv("CHANGOFILM_HOME", raising=False)
    monkeypatch.setenv("MPT_HOME", str(tmp_path / "legacy-home"))
    assert paths.runtime_root() == tmp_path / "legacy-home"
    monkeypatch.setenv("CHANGOFILM_HOME", str(tmp_path / "new-home"))
    assert paths.runtime_root() == tmp_path / "new-home"


def test_brand_data_dir_migrates_legacy_directory(tmp_path):
    legacy = tmp_path / "MoneyPrinterTurbo"
    (legacy / "tasks").mkdir(parents=True)
    (legacy / "tasks" / "params.json").write_text("{}", encoding="utf-8")
    target = paths._brand_data_dir(tmp_path)
    assert target == tmp_path / "ChangoFilm"
    assert not legacy.exists()
    assert (target / "tasks" / "params.json").read_text(encoding="utf-8") == "{}"


def test_brand_data_dir_prefers_existing_new_directory(tmp_path):
    legacy = tmp_path / "MoneyPrinterTurbo"
    legacy.mkdir()
    (legacy / "old.txt").write_text("old", encoding="utf-8")
    target = tmp_path / "ChangoFilm"
    target.mkdir()
    (target / "new.txt").write_text("new", encoding="utf-8")
    assert paths._brand_data_dir(tmp_path) == target
    assert (target / "new.txt").read_text(encoding="utf-8") == "new"
    assert (legacy / "old.txt").read_text(encoding="utf-8") == "old"


def test_brand_data_dir_copy_fallback_keeps_legacy_backup(monkeypatch, tmp_path):
    legacy = tmp_path / "MoneyPrinterTurbo"
    legacy.mkdir()
    (legacy / "config.toml").write_text("data", encoding="utf-8")

    def _fail_rename(src, dst):
        raise OSError("cross-device link")

    monkeypatch.setattr(paths.os, "rename", _fail_rename)
    target = paths._brand_data_dir(tmp_path)
    assert target == tmp_path / "ChangoFilm"
    assert (target / "config.toml").read_text(encoding="utf-8") == "data"
    # 复制降级时旧目录保留为备份，不删除用户数据。
    assert (legacy / "config.toml").read_text(encoding="utf-8") == "data"


def test_concurrent_resource_seeding_preserves_existing_files(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    fonts = bundle / "resource/fonts"
    fonts.mkdir(parents=True)
    (fonts / "default.ttf").write_bytes(b"complete font" * 10000)
    (fonts / "custom.ttf").write_bytes(b"bundled original")
    home = tmp_path / "user"
    target = home / "resource/fonts"
    target.mkdir(parents=True)
    (target / "custom.ttf").write_bytes(b"user font")
    monkeypatch.setattr(paths, "is_source_checkout", lambda: False)
    monkeypatch.setattr(paths, "BUNDLED_ROOT", bundle)
    monkeypatch.setenv("CHANGOFILM_HOME", str(home))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: paths.resource_directory("fonts"), range(8)))
    assert results == [target] * 8
    assert (target / "default.ttf").read_bytes() == (fonts / "default.ttf").read_bytes()
    assert (target / "custom.ttf").read_bytes() == b"user font"
    assert not list(target.glob(".resource-*"))


def test_cli_preserves_arguments_and_exit_status(monkeypatch):
    import cli

    seen = []
    monkeypatch.setattr(cli, "run_cli", lambda args: seen.append(args) or 2)
    assert launcher.main(["cli", "--video-script", "中文", "--stop-at", "script"]) == 2
    assert seen == [["--video-script", "中文", "--stop-at", "script"]]


def test_webui_launch_uses_current_python_and_bundled_ui(monkeypatch):
    called = []
    monkeypatch.setattr(launcher, "_available_port", lambda host: 8504)
    monkeypatch.setattr(launcher.subprocess, "call", lambda command: called.append(command) or 0)
    assert launcher.main(["webui", "--headless"]) == 0
    command = called[0]
    assert command[:3] == [launcher.sys.executable, "-m", "streamlit"]
    assert Path(command[4]) == paths.SOURCE_ROOT / "webui/Main.py"
    assert "--server.address=127.0.0.1" in command
    assert "--server.port=8504" in command
    assert "--server.headless=true" in command


def test_explicit_webui_port_does_not_auto_switch(monkeypatch):
    monkeypatch.setattr(launcher, "_available_port", lambda _: pytest.fail("unexpected scan"))
    monkeypatch.setattr(launcher.subprocess, "call", lambda command: 1)
    assert launcher.main(["webui", "--port", "8501"]) == 1


@pytest.mark.parametrize("port", ["0", "65536", "invalid"])
def test_invalid_port_is_rejected(port):
    with pytest.raises(SystemExit) as exc:
        launcher.main(["webui", "--port", port])
    assert exc.value.code == 2


def test_sdist_and_wheel_allowlists_exclude_private_files():
    import tomllib

    project = tomllib.loads((paths.SOURCE_ROOT / "pyproject.toml").read_text())
    build = project["tool"]["hatch"]["build"]["targets"]
    assert project["project"]["scripts"]["changofilm"] == "app.launcher:main"
    assert build["wheel"]["force-include"]["cli.py"] == "app/cli.py"
    for entry in build["sdist"]["include"]:
        assert entry not in ("/config.toml", "/storage", "/AGENTS.md", "/.env")
    assert "app" in build["wheel"]["packages"]
    assert "webui" in build["wheel"]["packages"]


def test_cli_stdout_contains_only_json(tmp_path):
    env = os.environ.copy()
    env["CHANGOFILM_HOME"] = str(tmp_path / "data")
    result = subprocess.run(
        [sys.executable, str(paths.SOURCE_ROOT / "cli.py"), "--video-script", "本地测试",
         "--stop-at", "script"],
        cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["script"] == "本地测试"
    assert "load config" in result.stderr


@pytest.mark.parametrize("media_type", ["image/png", "audio/mpeg", "video/mp4"])
def test_streamlit_media_responses_keep_valid_asgi_headers(media_type):
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    from starlette.testclient import TestClient
    from streamlit.web.server.starlette.starlette_gzip_middleware import SelectiveGZipMiddleware

    async def media(request):
        return Response(b"media payload" * 200, media_type=media_type)

    app = SelectiveGZipMiddleware(Starlette(routes=[Route("/media", media)]))
    with TestClient(app) as client:
        result = client.get("/media", headers={"Accept-Encoding": "gzip"})
    assert result.status_code == 200
    assert result.content == b"media payload" * 200

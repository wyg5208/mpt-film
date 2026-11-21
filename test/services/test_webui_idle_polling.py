"""UI 加载稳定性契约：空闲时不得注册周期性重渲染源。

背景（2026-11-21 用户反馈“网页总是重复加载、渲染和漂移”）：
render-all 壳下隐藏页的 2s fragment 曾无条件轮询（任务面板磁盘扫描 +
发布历史重读 + 隐藏节点替换），导航任务徽章空闲时也每 2 秒扫描任务
目录，版本检查完成后还会在启动 1–3 秒后无请求地整页 rerun 抢焦点。
本文件把修复后的三条契约钉死，防止回归。
"""
import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.services import publish_history, version_checker
from app.services import state as sm
from app.utils import utils

# 与 test_webui_headless_task_actions 相同：moviepy/numpy 的平台解析必须
# 先于任何 monkeypatch 完成。
from app.services import material as _material  # noqa: F401

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
TREE = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))


def _function_def(name):
    return next(
        node for node in ast.walk(TREE)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _container_with(key):
    """找到 `with st.container(key=...)` 的 With 节点。"""
    for node in ast.walk(TREE):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "container"
                and any(
                    kw.arg == "key"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value == key
                    for kw in call.keywords
                )
            ):
                return node
    raise AssertionError(f"container key={key} not found")


def _calls_in(node):
    names = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Attribute):
            names.add(call.func.attr)
        elif isinstance(call.func, ast.Name):
            names.add(call.func.id)
    return names


def _gating_if(container):
    """容器体内必须有一个 If，且 orelse 非空（静态回退分支）。"""
    ifs = [stmt for stmt in container.body if isinstance(stmt, ast.If)]
    assert len(ifs) == 1, "page container must gate polling behind exactly one If"
    gate = ifs[0]
    assert gate.orelse, "inactive page must still render statically (headless contract)"
    return gate


def test_tasks_page_polls_only_when_active():
    gate = _gating_if(_container_with("page_tasks"))
    assert ast.unparse(gate.test) == "active_page == 'tasks'"
    assert "_render_tasks_page" in _calls_in(gate)
    assert "_render_task_manager_panel" in _calls_in(gate.orelse[0])


def test_publish_history_polls_only_when_active():
    gate = _gating_if(_container_with("page_publish_history"))
    assert ast.unparse(gate.test) == "active_page == 'publish_history'"
    assert "_render_publish_history_page" in _calls_in(gate)
    assert "_render_publish_history" in _calls_in(gate.orelse[0])


def test_version_check_completion_does_not_force_app_rerun():
    body = _function_def("_render_pending_version_check")
    for call in ast.walk(body):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            assert call.func.attr != "rerun", (
                "version check completion must not steal focus/scroll with an "
                "unsolicited full-app rerun shortly after startup"
            )


def test_nav_tasks_badge_polls_only_while_processing():
    entry = _function_def("_render_nav_tasks_entry")
    ifs = [stmt for stmt in entry.body if isinstance(stmt, ast.If)]
    assert len(ifs) == 1
    gate = ifs[0]
    assert ast.unparse(gate.test) == "processing_count > 0"
    assert "_render_nav_tasks_button" in _calls_in(gate)
    assert "_render_nav_tasks_button_static" in _calls_in(gate.orelse[0])
    # fragment 内计数归零必须切回静态（停止定时器）。
    fragment = _function_def("_render_nav_tasks_button")
    assert "rerun" in _calls_in(fragment)


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "storage" / "tasks"
    task_dir = tasks_dir / "idle-test"
    task_dir.mkdir(parents=True)
    (task_dir / "final-1.mp4").write_bytes(b"test video payload")
    monkeypatch.setattr(utils, "task_dir", lambda: str(tasks_dir))
    monkeypatch.setattr(sm.state, "get_all_tasks", lambda *_a, **_k: ([], 0))
    monkeypatch.setattr(
        publish_history, "list_publish_history", lambda *_a, **_k: []
    )
    with patch.object(config, "try_save_config", return_value=True), patch.object(
        version_checker,
        "poll_available_update",
        return_value=version_checker.UpdateCheckSnapshot(complete=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60)
        yield app


def test_idle_default_run_keeps_task_buttons_and_navigates(isolated_app):
    app = isolated_app
    app.run()
    assert not app.exception
    # headless 契约：非活动页的行级按钮仍必须存在（静态渲染分支）。
    assert any(
        str(button.key).startswith("play_task_all_idle-test")
        for button in app.button
    )
    assert any(str(button.key) == "nav_page_tasks" for button in app.button)

    app.button(key="nav_page_tasks").click()
    app.run()
    assert not app.exception
    assert app.session_state["active_page"] == "tasks"

    app.button(key="nav_page_publish_history").click()
    app.run()
    assert not app.exception
    assert app.session_state["active_page"] == "publish_history"
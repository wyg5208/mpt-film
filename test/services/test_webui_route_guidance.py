"""创作路线引导契约：快速成片与专业短剧（向导/脚本方案/系列）显式区分。

背景（2026-11-21 用户反馈“两条路线似乎没有关联”）：两条创作路线共用
同一条生成提交链路（同一时间只运行一个任务），但 UI 上曾没有任何定位
说明或互相跳转。本文件钉死路线横幅的存在、跳转行为与 i18n 全量覆盖。
IA 重构后跳转目标为路线页 + 预选 TAB（quick_tabs/pro_tabs 会话键）。
"""
import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.services import publish_history, version_checker
from app.services import state as sm
from app.utils import utils

# 与 test_webui_idle_polling 相同：moviepy/numpy 的平台解析必须先于
# 任何 monkeypatch 完成。
from app.services import material as _material  # noqa: F401

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
TREE = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))

ROUTE_KEYS = [
    "Route Quick Badge",
    "Route Pro Badge",
    "Route Quick Intro",
    "Route Pro Intro",
    "Route Wizard Intro",
    "Route Quick To Plan",
    "Route Pro To Quick",
    "Route Wizard To Plan",
    "Generate Video Route Help",
]
LOCALES = [
    "az", "ca", "de", "en", "es", "fr", "id",
    "it", "ko", "pt", "ru", "tr", "vi", "zh",
]


def _function_def(name):
    return next(
        node for node in ast.walk(TREE)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _banner_calls(function_name):
    """收集函数体内 _render_route_banner(...) 的位置参数常量。

    第 7 参（目标 TAB label key）可省略：省略时补 None。
    """
    calls = []
    for node in ast.walk(_function_def(function_name)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_render_route_banner"
        ):
            assert len(node.args) in (6, 7), "banner call args must be 6 or 7"
            assert all(isinstance(arg, ast.Constant) for arg in node.args)
            values = [arg.value for arg in node.args]
            if len(values) == 6:
                values.append(None)
            calls.append(values)
    return calls


def test_route_banners_live_at_page_level_above_tabs():
    # IA 重构后横幅置于 TAB 栏之上（任何 TAB 下可达），不再埋在各渲染器内。
    calls = _banner_calls("_render_application")
    assert len(calls) == 2
    quick, pro = calls
    assert quick == [
        "quick", "quick", "Route Quick Intro", "Route Quick To Plan",
        "pro", "route_quick_to_plan", "Script Plan",
    ]
    assert pro == [
        "pro", "pro", "Route Pro Intro", "Route Pro To Quick",
        "quick", "route_pro_to_quick", None,
    ]
    for renderer in (
        "_render_script_settings", "_render_plan_page", "_render_wizard_page"
    ):
        assert _banner_calls(renderer) == [], renderer


def test_generate_button_explains_route_relationship():
    source = ast.unparse(_function_def("_render_generation_controls"))
    assert "Generate Video Route Help" in source


def test_route_keys_translated_and_non_empty_in_all_locales():
    for locale in LOCALES:
        path = ROOT_DIR / "webui" / "i18n" / f"{locale}.json"
        data = json.loads(path.read_text(encoding="utf-8"))["Translation"]
        for key in ROUTE_KEYS:
            assert key in data, f"{locale} missing {key}"
            assert data[key].strip(), f"{locale} has empty {key}"


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "storage" / "tasks"
    tasks_dir.mkdir(parents=True)
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


def test_route_banners_navigate_between_routes(isolated_app):
    app = isolated_app
    app.session_state["ui_language"] = "zh"
    app.run()
    assert not app.exception
    # 页级横幅：默认快速页只有 quick 横幅；pro 横幅在专业页活动时渲染。
    assert any(str(b.key) == "route_quick_to_plan" for b in app.button)

    zh = json.loads(
        (ROOT_DIR / "webui" / "i18n" / "zh.json").read_text(encoding="utf-8")
    )["Translation"]

    app.button(key="route_quick_to_plan").click()
    app.run()
    assert not app.exception
    assert app.session_state["active_page"] == "pro"
    assert app.session_state["pro_tabs"] == zh["Script Plan"]
    assert any(str(b.key) == "route_pro_to_quick" for b in app.button)

    app.button(key="route_pro_to_quick").click()
    app.run()
    assert not app.exception
    assert app.session_state["active_page"] == "quick"
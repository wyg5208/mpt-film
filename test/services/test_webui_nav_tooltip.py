"""左导航悬浮提示契约：展开态无 help 提示，收起态保留。

背景（2026-11-21 用户反馈“展开的左侧菜单每次悬停都弹出按钮文本提示，
没有必要”）：展开态按钮文本已可见，help 悬浮提示冗余，应取消；
收起态按钮只剩图标，悬浮提示是唯一的文字线索，必须保留。
"""
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.services import publish_history, version_checker
from app.services import state as sm
from app.utils import utils

# 与 test_webui_creation_ia 相同：moviepy/numpy 的平台解析必须先于
# 任何 monkeypatch 完成。
from app.services import material as _material  # noqa: F401

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"

NAV_BUTTON_KEYS = [
    "nav_page_quick",
    "nav_page_pro",
    "nav_page_tasks",
    "nav_page_publish_history",
    "nav_page_llm",
    "nav_page_material",
    "nav_page_publish",
    "nav_page_presets",
    "nav_page_settings",
    "nav_column_toggle",
]


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
        app.session_state["ui_language"] = "zh"
        yield app


def _nav_buttons(app):
    return {
        str(button.key): button
        for button in app.button
        if str(button.key) in NAV_BUTTON_KEYS
    }


def test_expanded_nav_buttons_have_no_hover_help(isolated_app):
    """展开态：全部导航按钮（含任务徽章与收起切换）不带 help 提示。"""
    app = isolated_app
    with patch.object(
        config, "ui", dict(config.ui, nav_collapsed=False)
    ):
        app.run()
    assert not app.exception
    buttons = _nav_buttons(app)
    assert set(buttons) == set(NAV_BUTTON_KEYS)
    for key, button in buttons.items():
        assert button.help == "", f"{key} 展开态不应有悬浮提示"


def test_collapsed_nav_buttons_keep_hover_help(isolated_app):
    """收起态：纯图标按钮必须保留 help 提示，且与按钮文案一致。"""
    app = isolated_app
    with patch.object(
        config, "ui", dict(config.ui, nav_collapsed=True)
    ):
        app.run()
    assert not app.exception
    buttons = _nav_buttons(app)
    assert set(buttons) == set(NAV_BUTTON_KEYS)
    for key, button in buttons.items():
        assert button.help, f"{key} 收起态必须保留悬浮提示"
        if key != "nav_page_tasks":
            # 页面按钮与切换按钮的提示即其文案；任务徽章文案可能带
            # 处理中计数后缀，只要求提示非空。
            assert button.help == button.label
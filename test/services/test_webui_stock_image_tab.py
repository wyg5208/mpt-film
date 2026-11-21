"""图片设置 TAB 库存图片下载源契约：选择同步、动效门控与共用 Key 让位。

背景（2026-11-21 用户反馈“图片配置只有 AI 图片生成，缺少库存图片下载
源”）：图片 TAB 新增库存图片区（Pexels/Pixabay 图片），选择后立即同步
视频来源；API Key 与同名库存视频共用，设置弹窗/素材来源页渲染本体时
本 TAB 让位，避免重复控件；图像动效对库存图片源同样挂载。
"""
import json
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
ZH = json.loads(
    (ROOT_DIR / "webui" / "i18n" / "zh.json").read_text(encoding="utf-8")
)["Translation"]
EN = json.loads(
    (ROOT_DIR / "webui" / "i18n" / "en.json").read_text(encoding="utf-8")
)["Translation"]

STOCK_KEYS = [
    "Stock Images",
    "Pexels Images",
    "Pixabay Images",
    "Stock Image Sources Section",
    "Stock Image Sources Section Help",
    "Stock Image Source",
    "Stock Image Source Help",
    "Stock Image Keys Shared Hint",
    "Stock Image Keys Elsewhere Hint",
]
LOCALES = [
    "az", "ca", "de", "en", "es", "fr", "id",
    "it", "ko", "pt", "ru", "tr", "vi", "zh",
]


def _select(app, key):
    return next(
        v for v in app.selectbox
        if v.key == key or str(v.key).startswith(key + "_")
    )


def _has_select(app, key):
    return any(
        v.key == key or str(v.key).startswith(key + "_")
        for v in app.selectbox
    )


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


def test_stock_image_keys_translated_and_non_empty_in_all_locales():
    for locale in LOCALES:
        data = json.loads(
            (ROOT_DIR / "webui" / "i18n" / f"{locale}.json").read_text(
                encoding="utf-8"
            )
        )["Translation"]
        for key in STOCK_KEYS:
            assert key in data, f"{locale} missing {key}"
            assert data[key].strip(), f"{locale} has empty {key}"


def test_stock_select_syncs_video_source_and_shared_keys(isolated_app):
    app = isolated_app
    with patch.object(
        config, "app", dict(config.app, video_source="local", llm_provider="openai")
    ):
        app.run()
        assert not app.exception
        stock = _select(app, "stock_image_source_select")
        assert stock.label == ZH["Stock Image Source"]
        # AppTest 的 options 是 format_func 之后的展示文案，value 仍是业务值。
        assert stock.options == [ZH["Pexels Images"], ZH["Pixabay Images"]]
        # 当前来源不是库存图片时，下拉默认展示 Pexels 图片但不改写来源。
        assert stock.value == "pexels_image"
        assert config.app["video_source"] == "local"
        # 共用 Key 表单默认按 Pexels 渲染在图片 TAB 内。
        assert any(
            str(t.key) == "pexels_api_keys_input" for t in app.text_input
        )

        stock.select("pixabay_image").run()
        assert not app.exception
        # 选择后立即同步到视频来源配置与会话控件值。
        assert config.app["video_source"] == "pixabay_image"
        assert app.session_state["video_source_select_zh"] == "pixabay_image"
        assert _select(app, "stock_image_source_select").value == "pixabay_image"
        # Key 表单跟随选择切换到 Pixabay，且与库存视频共用同一控件键。
        assert any(
            str(t.key) == "pixabay_api_keys_input" for t in app.text_input
        )
        assert not any(
            str(t.key) == "pexels_api_keys_input" for t in app.text_input
        )
        # 库存图片源下图像动效必须挂载。
        assert _has_select(app, "image_motion_select")


def test_stock_motion_gate_follows_effective_source(isolated_app):
    app = isolated_app
    with patch.object(
        config, "app", dict(config.app, video_source="pexels", llm_provider="openai")
    ):
        app.run()
        assert not app.exception
        # 库存视频源不挂载动效（与旧视频面板口径一致）。
        assert not _has_select(app, "image_motion_select")
        assert _has_select(app, "stock_image_source_select")

        # 默认值已是 pexels_image，必须选不同项才会触发 on_change 同步。
        _select(app, "stock_image_source_select").select("pixabay_image").run()
        assert not app.exception
        assert config.app["video_source"] == "pixabay_image"
        assert _has_select(app, "image_motion_select")


def test_stock_shared_keys_render_exactly_once_and_yield(isolated_app):
    app = isolated_app

    def count():
        return sum(
            1 for t in app.text_input if str(t.key) == "pexels_api_keys_input"
        )

    with patch.object(
        config, "app", dict(config.app, video_source="local", llm_provider="openai")
    ):
        app.run()
        assert not app.exception
        assert count() == 1  # 快速成片页的图片 TAB
        app.session_state["active_page"] = "material"
        app.run()
        assert not app.exception
        assert count() == 1  # 素材来源页本体，图片 TAB 让位
        app.session_state["active_page"] = "quick"
        app.session_state["settings_dialog_open"] = True
        app.session_state["settings_active_tab"] = "material"
        app.run()
        assert not app.exception
        assert count() == 1  # 设置弹窗素材 TAB 本体，图片 TAB 让位


def test_stock_select_labels_follow_language_switch(isolated_app):
    app = isolated_app
    with patch.object(
        config, "app", dict(config.app, video_source="local", llm_provider="openai")
    ):
        app.run()
        assert not app.exception
        _select(app, "stock_image_source_select").select("pixabay_image").run()
        assert not app.exception
        _select(app, "top_language_code_selector").select("en").run()
        assert not app.exception
        stock = _select(app, "stock_image_source_select")
        assert stock.label == EN["Stock Image Source"]
        # 语言切换重建控件后选择不能丢失。
        assert stock.value == "pixabay_image"
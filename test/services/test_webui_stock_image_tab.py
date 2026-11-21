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
        # Key 表单已集中到服务商配置页：图片 TAB 只保留提示，不再渲染任何
        # 库存 Key 输入。
        assert not any(
            str(t.key) in {"pexels_api_keys_input", "pixabay_api_keys_input"}
            for t in app.text_input
        )
        assert ZH["Stock Image Keys Elsewhere Hint"] in [
            str(item.value) for item in app.caption
        ]

        stock.select("pixabay_image").run()
        assert not app.exception
        # 选择后立即同步到视频来源配置与会话控件值。
        assert config.app["video_source"] == "pixabay_image"
        assert app.session_state["video_source_select_zh"] == "pixabay_image"
        assert _select(app, "stock_image_source_select").value == "pixabay_image"
        # Key 表单仍在服务商配置页：切换来源后图片 TAB 同样没有 Key 输入。
        assert not any(
            str(t.key) in {"pexels_api_keys_input", "pixabay_api_keys_input"}
            for t in app.text_input
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


def test_stock_shared_keys_render_only_on_provider_stock_tab(isolated_app):
    """共用 Key 表单只存在于服务商配置页素材搜索 TAB，任何素材入口都让位。"""
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
        assert count() == 0  # 快速成片页的图片 TAB 只保留参数与提示
        app.session_state["active_page"] = "material"
        app.run()
        assert not app.exception
        assert count() == 0  # 素材来源页能力 TAB 同样不含 Key 输入
        app.session_state["active_page"] = "quick"
        app.session_state["settings_dialog_open"] = True
        app.session_state["settings_active_tab"] = "material"
        app.run()
        assert not app.exception
        assert count() == 0  # 设置弹窗素材 TAB 本体也让位

        # 唯一的 Key 表单在服务商配置页素材搜索 TAB 中；弹窗中途换 TAB
        # 必须走定向目标键（settings_active_tab 只在首次挂载生效）。
        app.session_state["settings_dialog_target_tab"] = "llm"
        app.session_state["service_provider_target_tab"] = "Provider Stock Search Tab"
        app.run()
        assert not app.exception
        assert count() == 1


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
"""Brand theme module contracts: light/dark mode, CSS output and settings hosts.

v1.9.0：左导航 LOGO 与常驻主题面板撤场，主题设置迁入设置页与设置弹窗
「品牌主题」TAB（cfpage / cfset 双前缀）；新增会话级浅色模式，浅色调色板
必须覆写 Streamlit 基础变量，否则通用文字/输入面仍是暗色主题的浅色字。
"""

from contextlib import contextmanager
import json
from pathlib import Path
import time
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.models.llm_provider import get_llm_provider
from app.services import chatgpt_oauth, codex_models, codex_oauth, voice
from webui import brand_theme

ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = ROOT / "webui" / "Main.py"
# 设置页 TAB 为键控 st.tabs（值 = 选中标签）：AppTest 需预置选中标签才会
# 打开品牌主题面板（.open 仅对当前选中 TAB 为真）。
_EN_LABELS = json.loads((ROOT / "webui/i18n/en.json").read_text(encoding="utf-8"))["Translation"]
BRAND_TAB_LABEL = _EN_LABELS["Brand Theme Tab"]
MODE_LABELS = ["Dark", "Light"]


@contextmanager
def fake_session(theme=None):
    """brand_theme 直接读写 st.session_state；单测用字典替身隔离运行时。"""

    class _Session(dict):
        pass

    session = _Session()
    if theme is not None:
        session["cf_theme"] = dict(theme)
    with patch.object(brand_theme.st, "session_state", session):
        yield session


def test_default_theme_is_dark_with_brand_accent():
    with fake_session():
        css = brand_theme.variables_css()
    assert "color-scheme:dark" in css
    assert "--cf-bg:#0D0714" in css
    assert "--cf-ink:#F7F2FA" in css
    # 暗色链接/悬停沿用强调浅粉，播放三角保持品牌浅粉。
    assert "--cf-link:#F5D0FE" in css
    assert "--cf-mark-tri:#F5D0FE" in css
    assert "--cf-shadow-strong:0 24px 64px rgba(0, 0, 0, 0.55)" in css
    # 暗色不需要覆写 Streamlit 文字/背景基础变量（服务端 [theme] 已是暗色）。
    assert "--st-text-color" not in css


def test_light_mode_swaps_palette_and_overrides_streamlit_base():
    with fake_session({"mode": "light"}):
        css = brand_theme.variables_css()
    assert "color-scheme:light" in css
    assert "--cf-bg:#F4F1F8" in css
    assert "--cf-surface:#FFFFFF" in css
    assert "--cf-ink:#1D1330" in css
    # 浅色下链接/悬停/选中文字改用强调深色，浅粉在白底不可读。
    assert "--cf-link:#C026D3" in css
    assert "--cf-accent-pale:#C026D3" in css
    assert "--cf-mark-tri:#C026D3" in css
    # Streamlit 基础变量新旧名双写，保证未走 --cf-* 的表面跟随浅色。
    assert "--st-text-color:#1D1330" in css
    assert "--st-background-color:#F4F1F8" in css
    assert "--st-secondary-background-color:#FFFFFF" in css
    assert "--text-color:#1D1330" in css
    # 浅色阴影软化，黑阴影不再压在浅底上。
    assert "--cf-shadow-strong:0 24px 64px rgba(29, 19, 48, 0.22)" in css


def test_invalid_mode_falls_back_to_dark():
    with fake_session({"mode": "sepia"}) as session:
        assert brand_theme.theme()["mode"] == "dark"
        assert "color-scheme:dark" in brand_theme.variables_css()
        assert session["cf_theme"]["mode"] == "dark"


def test_light_background_field_keeps_accent_tints():
    a, b = "#EC4899", "#8B5CF6"
    deep_light = brand_theme._field_bg("deep", a, b, "light")
    assert deep_light.startswith("radial-gradient")
    assert "#EC48991a" in deep_light.replace(a, "#EC4899") or b + "1a" in deep_light
    assert deep_light.endswith("#F4F1F8")
    assert brand_theme._field_bg("black", a, b, "light") == "#FBF9FD"
    assert brand_theme._field_bg("aurora", a, b, "light").endswith("#F4F1F8")
    # 暗色场保持原值：纯黑与深空底色不变。
    assert brand_theme._field_bg("black", a, b, "dark") == "#000000"
    assert brand_theme._field_bg("deep", a, b, "dark").endswith("#0D0714")


def test_source_no_longer_mounts_nav_brand_or_sidebar_deck():
    source = MAIN_PY.read_text(encoding="utf-8")
    assert "render_nav_brand" not in source
    assert 'render_controls("cfnav"' not in source


def test_mode_field_syncs_widget_keys_and_reset_prefixes():
    # mode 是第一个字段：两处控制区与复位逻辑都按 _FIELDS 顺序对齐控件键。
    assert brand_theme._FIELDS[0] == "mode"
    assert set(brand_theme.MODES) == {"dark", "light"}


@pytest.mark.parametrize(
    "locale", sorted(p.stem for p in (ROOT / "webui/i18n").glob("*.json"))
)
def test_theme_mode_keys_exist_in_every_locale(locale):
    data = json.loads(
        (ROOT / f"webui/i18n/{locale}.json").read_text(encoding="utf-8")
    )["Translation"]
    for key in ("Theme Mode", "Theme Mode Dark", "Theme Mode Light"):
        assert data.get(key), (locale, key)
    hint = data["Theme Dialog Hint"]
    assert "left navigation" not in hint
    assert "左导航" not in hint


@contextmanager
def webui_app(**presets):
    """全量 AppTest 样板：与 test_settings_navigation.settings_app 同一补丁栈。"""
    settings = dict(
        llm_provider="openai_codex",
        openai_codex_model_name="text-model",
        codex_image_model_name="image-model",
        video_source="pexels",
        script_generation_backend="llm",
        pexels_api_keys=["initial-pexels"],
        pixabay_api_keys=["initial-pixabay"],
    )
    catalog = codex_models.Catalog(
        (codex_models.Model("text-model", "Text model"),), time.time()
    )
    with (
        patch.object(config, "app", settings),
        patch.object(config, "ui", dict(config.ui, language="en")),
        patch.object(config, "try_save_config", return_value=True),
        patch.object(config, "save_config"),
        patch("webui.settings_providers.shutil.which", return_value=None),
        patch.object(codex_models, "get_catalog", return_value=catalog),
        patch.object(codex_oauth, "account_status", return_value=False),
        patch.object(chatgpt_oauth, "account_status", return_value=False),
        patch.object(voice, "get_all_azure_voices", return_value=[]),
    ):
        app = AppTest.from_file(str(ROOT / "webui/Main.py"), default_timeout=60)
        app.session_state["ui_language"] = "en"
        for key, value in presets.items():
            app.session_state[key] = value
        yield app


def _run(app):
    app.run()
    assert not app.exception, [str(item.value) for item in app.exception]


def test_default_page_mounts_no_theme_controls():
    """左导航撤场后：默认页不再出现任何主题控制键（旧 cfnav_* 与新前缀皆无）。"""
    with webui_app() as app:
        _run(app)
        theme_keys = [
            str(key)
            for key in app.session_state.keys()
            if str(key).startswith(("cfnav_", "cfset_", "cfpage_"))
        ]
        assert theme_keys == []


def test_settings_page_hosts_brand_theme_tab_with_mode_control():
    """导航 Settings 项对应页：第 5 个 TAB 挂载 cfpage 主题控制区（含明暗模式）。"""
    with webui_app(active_page="settings", settings_page_tabs=BRAND_TAB_LABEL) as app:
        _run(app)
        assert "cfpage_mode" in app.session_state
        mode_select = app.selectbox(key="cfpage_mode")
        assert mode_select.label == "Theme Mode"
        # AppTest 的 options 返回 format_func 后的标签；value 才是原始值。
        assert mode_select.options == MODE_LABELS
        assert mode_select.value == "dark"
        # 其余 8 项工具照常挂载：cfpage 前缀 8 个字段键齐备。
        for field in brand_theme._FIELDS:
            assert f"cfpage_{field}" in app.session_state
        assert not any(
            str(item.key).startswith("cfset_") for item in app.selectbox
        )


def test_settings_page_mode_select_syncs_session_theme():
    """切换浅色：on_change 同步会话主题并整页重跑，主题成为唯一事实源。"""
    with webui_app(
        active_page="settings", settings_page_tabs=BRAND_TAB_LABEL
    ) as app:
        _run(app)
        app.selectbox(key="cfpage_mode").select("light")
        _run(app)
        assert app.session_state["cf_theme"]["mode"] == "light"
        assert app.session_state["cfpage_mode"] == "light"
        # 浅色会话下重渲染：弹窗/页面共用的控制区键随主题对齐，无漂移。
        assert app.session_state["cfpage_accent"] == "magenta"


def test_settings_dialog_brand_tab_keeps_cfset_controls():
    """设置弹窗 brand TAB 仍是 cfset 前缀；设置页让位时不会同时挂载 cfpage。"""
    with webui_app(settings_dialog_open=True, settings_dialog_target_tab="brand") as app:
        _run(app)
        assert "cfset_mode" in app.session_state
        assert app.selectbox(key="cfset_mode").options == MODE_LABELS
        assert app.selectbox(key="cfset_mode").value == "dark"
        assert not any(
            str(item.key).startswith("cfpage_") for item in app.selectbox
        )


def test_reset_returns_both_control_zones_to_defaults():
    """复位按钮覆盖 cfset 与 cfpage 两个前缀；旧 cfnav 不再出现。"""
    with webui_app(
        active_page="settings", settings_page_tabs=BRAND_TAB_LABEL
    ) as app:
        _run(app)
        app.session_state["cf_theme"] = dict(brand_theme.DEFAULTS, mode="light")
        app.session_state["cfpage_mode"] = "light"
        app.button(key="cfpage_reset").click()
        _run(app)
        assert app.session_state["cf_theme"]["mode"] == "dark"
        assert app.session_state["cfpage_mode"] == "dark"

"""WebUI 国内发布设置区：开关解耦、B站分区条件显隐、国外区保留与 i18n 完整性。"""
import json
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.config import config

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
I18N_DIR = ROOT_DIR / "webui" / "i18n"

NEW_KEYS = [
    "Domestic Auto-Publish Intro",
    "Social Auto Upload Setup Guide",
    "Social Auto Upload Setup Steps",
    "Enable Domestic Publishing",
    "Enable Domestic Auto-Publish",
    "Publish Account Name",
    "Publish Account Name Help",
    "Domestic Platforms",
    "Bilibili Partition ID",
    "Bilibili Partition Help",
    "Advanced Publish Settings",
    "SAU CLI Path",
    "SAU CLI Path Help",
    "Check Login Sessions",
    "Checking Login Sessions",
    "Session Check Busy",
    "Overseas Platforms Optional UploadPost",
    "Upload-Post Free Tier Note",
    "Publish Pending",
    "Publish Processing",
    "Publish Complete",
    "Publish Failed",
    "Publish Headed",
    "Publish Headed Help",
    "Publish Queue",
    "Publish Queue Position",
    "Publish Stage Queued",
    "Publish Stage Metadata",
    "Publish Stage Uploading",
    "Publish Log",
    "Publish History Tab",
    "Publish History Empty",
    "Publish Trigger Manual",
    "Publish Trigger Auto",
    "Republish",
]


def _widget_by_key(elements, key):
    return next(
        item
        for item in elements
        if str(getattr(item, "key", "")) == key
        or str(getattr(item, "key", "")).startswith(f"{key}_")
    )


def _open_publish_tab(app):
    app.session_state["settings_dialog_open"] = True
    app.session_state["settings_dialog_target_tab"] = "publish"
    app.run()
    assert not app.exception


def test_domestic_checkboxes_stay_decoupled():
    values = dict(
        config.app,
        social_publish_enabled=True,
        social_publish_auto_upload=False,
    )
    with (
        patch.object(config, "app", values),
        patch.object(config, "try_save_config", return_value=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60).run()
        _open_publish_tab(app)

        enabled_box = _widget_by_key(app.checkbox, "social_publish_enabled_checkbox")
        auto_box = _widget_by_key(app.checkbox, "social_publish_auto_upload_checkbox")
        assert enabled_box.value is True
        assert auto_box.value is False
        # 仅渲染对话框不得改写两键分裂的配置。
        assert values["social_publish_enabled"] is True
        assert values["social_publish_auto_upload"] is False

        auto_box.set_value(True)
        app.run()
        assert not app.exception
        assert values["social_publish_enabled"] is True
        assert values["social_publish_auto_upload"] is True


def test_bilibili_tid_shown_only_when_bilibili_selected():
    values = dict(config.app, social_publish_platforms=["douyin", "tencent"])
    with (
        patch.object(config, "app", values),
        patch.object(config, "try_save_config", return_value=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60).run()
        _open_publish_tab(app)
        assert not any(
            item.key == "social_publish_bilibili_tid_input" for item in app.number_input
        )

    values = dict(
        config.app,
        social_publish_platforms=["bilibili"],
        social_publish_bilibili_tid="abc",
    )
    with (
        patch.object(config, "app", values),
        patch.object(config, "try_save_config", return_value=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60).run()
        _open_publish_tab(app)
        tid_input = _widget_by_key(app.number_input, "social_publish_bilibili_tid_input")
        # 非法 tid 回退默认值而不是崩溃，也不擅自改写已保存配置。
        assert tid_input.value == 21
        assert values["social_publish_bilibili_tid"] == "abc"


def test_overseas_section_keeps_legacy_keys_and_check_button_gates():
    values = dict(config.app, social_publish_enabled=False)
    with (
        patch.object(config, "app", values),
        patch.object(config, "try_save_config", return_value=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60).run()
        _open_publish_tab(app)
        # 国外区控件 key 不变（折叠 expander 内仍完整渲染）。
        assert _widget_by_key(app.checkbox, "upload_post_enabled_checkbox")
        assert _widget_by_key(app.text_input, "upload_post_api_key_input")
        # 未启用国内发布时，登录态体检按钮必须禁用。
        check_button = _widget_by_key(app.button, "social_publish_check_sessions_button")
        assert check_button.disabled is True


def test_headed_toggle_defaults_on_and_persists():
    values = dict(config.app, social_publish_enabled=True)
    values.pop("social_publish_headed", None)
    with (
        patch.object(config, "app", values),
        patch.object(config, "try_save_config", return_value=True),
    ):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60).run()
        _open_publish_tab(app)
        headed = _widget_by_key(app.checkbox, "social_publish_headed_checkbox")
        # 默认有头：未配置时也必须勾选，降低风控拦截概率。
        assert headed.value is True
        headed.uncheck().run()
        assert values["social_publish_headed"] is False


def test_all_locales_carry_new_publish_keys():
    locales = sorted(I18N_DIR.glob("*.json"))
    assert len(locales) == 14
    for locale in locales:
        data = json.loads(locale.read_text(encoding="utf-8"))["Translation"]
        missing = [key for key in NEW_KEYS if key not in data]
        assert not missing, f"{locale.name} missing keys: {missing}"
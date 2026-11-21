"""Settings navigation must preserve real form values and task selections.

服务商体系 v1.8.0：素材来源按能力分组为四个 TAB（三槽来源链，无 Key 输入），
服务商凭证表单集中在服务商配置页的懒加载面板；通用页激活契约保持不变。
"""

from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.models.llm_provider import get_llm_provider
from app.services import chatgpt_oauth, codex_models, codex_oauth, voice

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {
    "pexels": ("stock_video", "pexels_api_keys_input"),
    "pixabay": ("stock_video", "pixabay_api_keys_input"),
    "coverr": ("stock_video", "coverr_api_keys_input"),
    "metaso_minimax": ("ai_video", "metaso_minimax_api_key_input"),
    "ofox": ("ai_video", "ofox_api_key_input"),
    "loomloom": ("ai_video", "loomloom_api_token_input"),
    "volcengine_seedance": ("ai_video", "volcengine_seedance_api_key_input"),
    "infistar": ("ai_video", "infistar_video_api_key_input"),
    "jalapeno": ("ai_video", "jalapeno_video_api_key_input"),
    "wavespeed": ("ai_video", "wavespeed_api_keys_input"),
    "muapi": ("ai_video", "muapi_api_key_input"),
    "openai_image": ("ai_image", "openai_image_base_url_input"),
    "codex_image": ("ai_image", "codex_image_timeout_input"),
}

# 与 webui.Main.VIDEO_SOURCE_GROUPS 一致：能力 TAB 的来源链成员（local 不参与）。
CAPABILITY_GROUPS = {
    "ai_video": (
        "metaso_minimax",
        "ofox",
        "loomloom",
        "volcengine_seedance",
        "infistar",
        "jalapeno",
        "wavespeed",
        "muapi",
    ),
    "ai_image": ("openai_image", "codex_image"),
    "stock_video": ("pexels", "pixabay", "coverr"),
    "stock_image": ("pexels_image", "pixabay_image"),
}

PROVIDER_LABELS = {
    "pexels": "Pexels",
    "pixabay": "Pixabay",
    "coverr": "Coverr",
    "pexels_image": "Pexels Images",
    "pixabay_image": "Pixabay Images",
    "metaso_minimax": "Metaso MiniMax H3",
    "ofox": "OFox AI Video",
    "loomloom": "Shengsuan Cloud AI Video",
    "volcengine_seedance": "Volcano Engine Seedance",
    "infistar": "Infistar AI Video",
    "jalapeno": "Jalapeno Cloud AI Video",
    "wavespeed": "WaveSpeed AI Video",
    "muapi": "MuAPI AI Video",
    "openai_image": "OpenAI Compatible Text-to-Image",
    "codex_image": "codex.image.label",
}

# 服务商配置页懒加载面板（能力 → webui.Main.PROVIDER_TAB_LABEL_KEYS 稳定键）。
PROVIDER_PANEL_GROUPS = {
    "Provider Video Tab": ("ai_video",),
    "Provider Image Tab": ("ai_image",),
    "Provider Stock Search Tab": ("stock_video",),
}

_TRANSLATIONS = {}


def translate(locale, key):
    if locale not in _TRANSLATIONS:
        english = json.loads(
            (ROOT / "webui/i18n/en.json").read_text(encoding="utf-8")
        )["Translation"]
        local = json.loads(
            (ROOT / f"webui/i18n/{locale}.json").read_text(encoding="utf-8")
        )["Translation"]
        _TRANSLATIONS[locale] = (english, local)
    english, local = _TRANSLATIONS[locale]
    return local.get(key, english.get(key, key))


@contextmanager
def settings_app(
    target=None,
    *,
    locale="en",
    codex_connected=True,
    claude_available=False,
    **overrides,
):
    settings = dict(
        llm_provider="openai_codex",
        openai_codex_model_name="text-model",
        codex_image_model_name="image-model",
        video_source="pexels",
        script_generation_backend="llm",
        pexels_api_keys=["initial-pexels"],
        pixabay_api_keys=["initial-pixabay"],
        loomloom_api_token="synthetic-loomloom",
    )
    settings.update(overrides)
    catalog = codex_models.Catalog(
        (codex_models.Model("text-model", "Text model"),), time.time()
    )
    with (
        patch.object(config, "app", settings),
        patch.object(config, "ui", dict(config.ui, language=locale)),
        patch.object(config, "try_save_config", return_value=True),
        patch.object(config, "save_config"),
        patch(
            "webui.settings_providers.shutil.which",
            return_value="synthetic-claude" if claude_available else None,
        ),
        patch.object(codex_models, "get_catalog", return_value=catalog) as models,
        patch.object(codex_oauth, "account_status", return_value=codex_connected),
        patch.object(chatgpt_oauth, "account_status", return_value=False),
        patch.object(codex_oauth, "request_device_code") as login,
        patch.object(
            voice, "get_all_azure_voices", return_value=["en-US-JennyNeural-Female"]
        ),
    ):
        app = AppTest.from_file(str(ROOT / "webui/Main.py"), default_timeout=60)
        app.session_state["ui_language"] = locale
        app.session_state["settings_dialog_open"] = True
        if target:
            app.session_state["settings_dialog_target_tab"] = target
        yield app, settings, models, login


def run(app):
    app.run()
    assert not app.exception, [str(item.value) for item in app.exception]


def open_provider_panel(app, provider_tab):
    """服务商配置页为懒加载 TAB：通过目标键直达指定能力面板。"""
    app.session_state["settings_dialog_target_tab"] = "llm"
    app.session_state["service_provider_target_tab"] = provider_tab


def assert_capability_tab(app, locale, group, expected_primary):
    """素材能力 TAB 契约：三槽来源链 + 源状态 + Key 集中提示，无任何 Key 输入。"""
    providers = CAPABILITY_GROUPS[group]
    primary = app.selectbox(key=f"material_primary_{group}_select_{locale}")
    assert primary.label == translate(locale, "Priority Source")
    assert primary.options == [
        translate(locale, PROVIDER_LABELS[provider]) for provider in providers
    ]
    # 第一优先槽与唯一主源键双向同步：始终跟随当前 video_source。
    assert primary.value == expected_primary
    for slot in (1, 2):
        backup = app.selectbox(key=f"material_backup{slot}_{group}_select_{locale}")
        assert backup.label == translate(locale, f"Backup Source {slot}")
        assert backup.options == [translate(locale, "Backup Slot Disabled")] + [
            translate(locale, PROVIDER_LABELS[provider]) for provider in providers
        ]
        assert backup.value == ""
    captions = [str(item.value) for item in app.caption]
    assert translate(locale, "Material Primary Source Help") in captions
    assert translate(locale, "Material Chain Help") in captions
    assert translate(locale, "Material Keys In Provider Page Hint") in captions
    status = "\n".join(str(item.value) for item in app.get("markdown"))
    assert f"**{translate(locale, 'Source Status Section')}**" in status
    for provider in providers:
        assert translate(locale, PROVIDER_LABELS[provider]) in status
    assert any(
        str(item.key) == f"material_open_providers_{group}" for item in app.button
    )
    # 素材 TAB 只决定“用哪个来源”，绝不挂载任何 Key 输入或旧分组选择器。
    assert not set(field for _, field in FIELDS.values()) & {
        str(item.key) for item in app.text_input
    }
    assert not any(
        str(item.key).startswith("settings_material_provider_")
        for item in app.selectbox
    )
    return primary.value


def test_general_can_activate_claude_from_default_cli_on_path():
    with settings_app(claude_available=True) as (app, settings, _, login):
        run(app)
        app.selectbox(key="settings_general_llm_provider_select_en").select(
            "claude_code"
        )
        app.button(key="settings_general_use_llm").click()
        run(app)
        assert settings["llm_provider"] == "claude_code"
        login.assert_not_called()


def test_general_render_does_not_activate_or_mount_provider_forms_or_catalogs():
    with settings_app() as (app, settings, models, login):
        run(app)
        assert app.session_state["settings_dialog_tabs_en"] == "General"
        assert [
            item.key
            for item in app.selectbox
            if str(item.key).startswith("settings_general_")
        ] == [
            f"settings_general_{section}_provider_select_en"
            for section in ("llm", "ai_video", "ai_image", "stock_video")
        ]
        assert not set(FIELDS[p][1] for p in FIELDS) & {x.key for x in app.text_input}
        assert not any(
            str(x.key).startswith("llm_provider_select") for x in app.selectbox
        )
        assert settings["llm_provider"] == "openai_codex"
        assert settings["video_source"] == "pexels"
        models.assert_not_called()
        login.assert_not_called()


@pytest.mark.parametrize("provider_tab", sorted(PROVIDER_PANEL_GROUPS))
def test_provider_panel_renders_its_capability_forms_and_lazily_hides_others(
    provider_tab,
):
    """服务商配置页按能力懒加载：面板内 render-all 能力表单，其他能力不挂载。"""
    groups = PROVIDER_PANEL_GROUPS[provider_tab]
    with settings_app() as (app, settings, models, login):
        open_provider_panel(app, provider_tab)
        run(app)
        present = {str(item.key) for item in app.text_input}
        for provider, (group, field) in FIELDS.items():
            if group in groups:
                assert field in present, provider
            else:
                assert field not in present, provider
        # 服务商配置页不挂载素材来源链与通用页选择器。
        assert not any(
            str(item.key).startswith(("material_primary_", "material_backup"))
            for item in app.selectbox
        )
        assert not any(
            str(item.key).startswith("settings_general_") for item in app.selectbox
        )
        assert settings["video_source"] == "pexels"
        assert settings["llm_provider"] == "openai_codex"
        login.assert_not_called()
        # 仅图片生成面板包含 codex_image 表单（模型选择器读取 codex 目录）。
        if provider_tab != "Provider Image Tab":
            models.assert_not_called()


@pytest.mark.parametrize(
    "target,group,primary",
    [
        ("stock", "stock_video", "pexels"),
        ("video", "ai_video", "metaso_minimax"),
        ("image", "ai_image", "openai_image"),
    ],
)
def test_general_opens_selected_section_without_activating_a_material_provider(
    target, group, primary
):
    with settings_app() as (app, settings, _, _):
        run(app)
        app.button(key=f"settings_general_configure_{group}").click()
        run(app)
        assert app.session_state["settings_material_group"] == group
        assert_capability_tab(app, "en", group, primary)
        assert settings["video_source"] == "pexels"
        assert settings["llm_provider"] == "openai_codex"


def test_final_password_edit_is_saved_before_same_event_unmounts_panel():
    with settings_app() as (app, settings, _, _):
        open_provider_panel(app, "Provider Stock Search Tab")
        run(app)
        app.text_input(key="pexels_api_keys_input").set_value(" final key ")
        # 同一事件内切走懒加载面板（素材搜索表单卸载），最终编辑仍先落盘。
        app.session_state["service_provider_target_tab"] = "Provider Text Tab"
        run(app)
        assert settings["pexels_api_keys"] == ["finalkey"]
        app.session_state["service_provider_target_tab"] = "Provider Stock Search Tab"
        run(app)
        assert app.text_input(key="pexels_api_keys_input").value == "finalkey"


def test_final_image_url_edit_is_saved_before_switching_panel():
    with settings_app() as (app, settings, _, _):
        open_provider_panel(app, "Provider Image Tab")
        run(app)
        app.text_input(key="openai_image_base_url_input").set_value(
            " https://images.example/v1 "
        )
        app.session_state["service_provider_target_tab"] = "Provider Text Tab"
        run(app)
        assert settings["openai_image_base_url"] == "https://images.example/v1"
        app.session_state["service_provider_target_tab"] = "Provider Image Tab"
        run(app)
        assert (
            app.text_input(key="openai_image_base_url_input").value
            == "https://images.example/v1"
        )


def test_final_material_edit_survives_general_and_reopening():
    with settings_app() as (app, settings, _, _):
        open_provider_panel(app, "Provider Stock Search Tab")
        run(app)
        app.text_input(key="pexels_api_keys_input").set_value("final-before-general")
        app.session_state["settings_dialog_target_tab"] = "general"
        run(app)
        assert settings["pexels_api_keys"] == ["final-before-general"]
        assert not {field for _, field in FIELDS.values()} & {
            item.key for item in app.text_input
        }
        open_provider_panel(app, "Provider Stock Search Tab")
        run(app)
        assert (
            app.text_input(key="pexels_api_keys_input").value == "final-before-general"
        )
        assert settings["video_source"] == "pexels"


def test_switching_provider_panels_preserves_final_edits():
    with settings_app() as (app, settings, _, _):
        open_provider_panel(app, "Provider Video Tab")
        run(app)
        app.text_input(key="metaso_minimax_api_key_input").set_value("final-video-key")
        app.session_state["service_provider_target_tab"] = "Provider Stock Search Tab"
        run(app)
        assert settings["metaso_minimax_api_key"] == "final-video-key"
        app.text_input(key="pexels_api_keys_input").set_value("final-stock-key")
        app.session_state["service_provider_target_tab"] = "Provider Image Tab"
        run(app)
        assert settings["pexels_api_keys"] == ["final-stock-key"]
        app.text_input(key="openai_image_base_url_input").set_value(
            " https://images.example/v1 "
        )
        run(app)
        assert settings["openai_image_base_url"] == "https://images.example/v1"
        # 回访各面板：跨面板切换不回滚任何最终编辑。
        app.session_state["service_provider_target_tab"] = "Provider Video Tab"
        run(app)
        assert (
            app.text_input(key="metaso_minimax_api_key_input").value
            == "final-video-key"
        )
        app.session_state["service_provider_target_tab"] = "Provider Stock Search Tab"
        run(app)
        assert app.text_input(key="pexels_api_keys_input").value == "final-stock-key"
        app.session_state["service_provider_target_tab"] = "Provider Image Tab"
        run(app)
        assert (
            app.text_input(key="openai_image_base_url_input").value
            == "https://images.example/v1"
        )


def test_final_manual_model_edit_survives_navigation_away_from_llm():
    with settings_app("llm") as (app, settings, models, _):
        models.side_effect = codex_models.CatalogError()
        app.session_state["service_provider_target_tab"] = "Provider Text Tab"
        run(app)
        app.text_input(key="openai_codex_model_name_input").set_value(
            "custom-responses-model"
        )
        app.session_state["settings_dialog_target_tab"] = "general"
        run(app)
        assert settings["openai_codex_model_name"] == "custom-responses-model"
        open_provider_panel(app, "Provider Text Tab")
        run(app)
        assert (
            app.text_input(key="openai_codex_model_name_input").value
            == "custom-responses-model"
        )


def test_material_capability_tabs_survive_tabs_and_language_changes():
    with settings_app("material") as (app, settings, _, _):
        run(app)
        assert app.session_state["settings_material_group"] == "stock_video"
        assert_capability_tab(app, "en", "stock_video", "pexels")
        # 弹窗内切换到通用页再回素材页：能力 TAB 记忆保持。
        app.session_state["settings_dialog_target_tab"] = "general"
        run(app)
        app.session_state["settings_dialog_target_tab"] = "material"
        run(app)
        assert app.session_state["settings_material_group"] == "stock_video"
        assert_capability_tab(app, "en", "stock_video", "pexels")
        # 语言切换重建控件（key 带 locale 后缀），分组与主源选择保持。
        app.selectbox(key="top_language_code_selector").select("es")
        run(app)
        assert app.session_state["settings_material_group"] == "stock_video"
        assert_capability_tab(app, "es", "stock_video", "pexels")
        assert settings["video_source"] == "pexels"
        assert app.session_state["video_source_select_es"] == "pexels"
        assert settings["llm_provider"] == "openai_codex"


def test_contextual_material_access_uses_active_source_instead_of_old_navigation():
    with settings_app("material", video_source="codex_image") as (
        app,
        _,
        _,
        _,
    ):
        run(app)
        assert app.session_state["settings_material_group"] == "ai_image"
        assert_capability_tab(app, "en", "ai_image", "codex_image")


def test_pending_values_survive_hidden_widgets_while_task_holds_configuration():
    with settings_app() as (app, settings, _, _):
        open_provider_panel(app, "Provider Stock Search Tab")
        run(app)
        entered, release = threading.Event(), threading.Event()

        def worker():
            with config.runtime_config_lock():
                entered.set()
                release.wait(30)

        thread = threading.Thread(target=worker)
        thread.start()
        assert entered.wait(5)
        try:
            app.text_input(key="pexels_api_keys_input").set_value("pending-key")
            app.session_state["service_provider_target_tab"] = "Provider Text Tab"
            run(app)
            assert settings["pexels_api_keys"] == ["initial-pexels"]
            assert config.snapshot_config_with_pending(settings)["pexels_api_keys"] == [
                "pending-key"
            ]
            app.session_state["service_provider_target_tab"] = (
                "Provider Stock Search Tab"
            )
            run(app)
            assert app.text_input(key="pexels_api_keys_input").value == "pending-key"
        finally:
            release.set()
            thread.join(5)
            with config.runtime_config_lock():
                config._flush_pending_config_locked(suppress_save_errors=False)
        assert settings["pexels_api_keys"] == ["pending-key"]


GENERAL_CONFIGURATION = {
    "openai_api_key": "synthetic-openai",
    "anthropic_api_key": "synthetic-anthropic",
    "metaso_minimax_api_key": "synthetic-video",
    "ofox_api_key": "synthetic-ofox",
    "openai_image_base_url": "https://images.example/v1",
    "openai_image_model": "local-image",
}


def active_captions(app, locale="en"):
    translations = json.loads(
        (ROOT / f"webui/i18n/{locale}.json").read_text(encoding="utf-8")
    )["Translation"]
    template = translations["Active Provider"]
    prefix = template.split("{provider}")[0]
    return [item.value for item in app.caption if item.value.startswith(prefix)]


def assert_active_providers(app, llm_provider, material_source, locale="en"):
    local = json.loads(
        (ROOT / f"webui/i18n/{locale}.json").read_text(encoding="utf-8")
    )["Translation"]
    english = json.loads((ROOT / "webui/i18n/en.json").read_text(encoding="utf-8"))[
        "Translation"
    ]
    llm = get_llm_provider(llm_provider)
    llm_label = local.get(llm.label_key, english.get(llm.label_key, llm.default_label))
    source_key = PROVIDER_LABELS[material_source]
    source_label = local.get(source_key, english.get(source_key, source_key))
    template = local["Active Provider"]
    assert active_captions(app, locale) == [
        template.format(provider=llm_label),
        template.format(provider=source_label),
    ]


@pytest.mark.parametrize(
    "section,provider",
    [
        ("llm", "openai"),
        ("ai_video", "ofox"),
        ("ai_image", "openai_image"),
        ("stock_video", "pixabay"),
    ],
)
def test_general_selection_alone_never_activates_provider(section, provider):
    with settings_app(**GENERAL_CONFIGURATION) as (app, settings, models, login):
        run(app)
        initial_badges = active_captions(app)
        assert_active_providers(app, "openai_codex", "pexels")
        app.selectbox(key=f"settings_general_{section}_provider_select_en").select(
            provider
        )
        run(app)
        assert settings["llm_provider"] == "openai_codex"
        assert settings["video_source"] == "pexels"
        assert active_captions(app) == initial_badges
        models.assert_not_called()
        login.assert_not_called()


@pytest.mark.parametrize(
    "section,provider",
    [
        ("llm", "openai"),
        ("llm", "anthropic"),
        ("ai_video", "ofox"),
        ("ai_image", "openai_image"),
        ("stock_video", "pixabay"),
    ],
)
def test_general_use_reads_new_selection_in_same_event(section, provider):
    with settings_app(**GENERAL_CONFIGURATION) as (app, settings, models, login):
        run(app)
        app.selectbox(key=f"settings_general_{section}_provider_select_en").select(
            provider
        )
        app.button(key=f"settings_general_use_{section}").click()
        run(app)
        if section == "llm":
            assert settings["llm_provider"] == provider
            assert settings["video_source"] == "pexels"
            assert app.session_state["llm_provider_select_en"] == provider
        else:
            assert settings["video_source"] == provider
            assert settings["llm_provider"] == "openai_codex"
            assert app.session_state["video_source_select_en"] == provider
        assert_active_providers(
            app,
            provider if section == "llm" else "openai_codex",
            "pexels" if section == "llm" else provider,
        )
        models.assert_not_called()
        login.assert_not_called()


def test_general_use_roundtrip_main_language_and_configuration_tabs_does_not_revert():
    with settings_app("stock", **GENERAL_CONFIGURATION) as (app, settings, _, _):
        run(app)
        assert assert_capability_tab(app, "en", "stock_video", "pexels") == "pexels"
        app.session_state["settings_dialog_target_tab"] = "llm"
        app.session_state["service_provider_target_tab"] = "Provider Text Tab"
        run(app)
        assert app.selectbox(key="llm_provider_select_en").value == "openai_codex"
        app.session_state["settings_dialog_target_tab"] = "general"
        run(app)
        app.selectbox(key="settings_general_llm_provider_select_en").select("openai")
        app.button(key="settings_general_use_llm").click()
        run(app)
        app.selectbox(key="settings_general_stock_video_provider_select_en").select(
            "pixabay"
        )
        app.button(key="settings_general_use_stock_video").click()
        run(app)
        app.selectbox(key="top_language_code_selector").select("es")
        run(app)
        assert app.session_state["video_source_select_es"] == "pixabay"
        assert_active_providers(app, "openai", "pixabay", "es")
        app.button(key="settings_general_configure_llm").click()
        app.session_state["service_provider_target_tab"] = "Provider Text Tab"
        run(app)
        assert app.selectbox(key="llm_provider_select_es").value == "openai"
        app.session_state["settings_dialog_target_tab"] = "stock"
        run(app)
        assert app.session_state["settings_material_group"] == "stock_video"
        assert assert_capability_tab(app, "es", "stock_video", "pixabay") == "pixabay"
        app.session_state["settings_dialog_target_tab"] = "general"
        run(app)
        assert settings["llm_provider"] == "openai"
        assert settings["video_source"] == "pixabay"
        assert app.session_state["video_source_select_es"] == "pixabay"


def test_general_empty_categories_offer_configuration_without_activation():
    with settings_app(
        codex_connected=False,
        loomloom_api_token="",
        pexels_api_keys=[],
        pixabay_api_keys=[],
    ) as (app, settings, models, login):
        run(app)
        selector_keys = {item.key for item in app.selectbox}
        button_keys = {item.key for item in app.button}
        for section in ("llm", "ai_video", "ai_image", "stock_video"):
            assert f"settings_general_{section}_provider_select_en" not in selector_keys
            assert f"settings_general_use_{section}" not in button_keys
            assert not app.button(key=f"settings_general_configure_{section}").disabled
        translations = json.loads(
            (ROOT / "webui/i18n/en.json").read_text(encoding="utf-8")
        )["Translation"]
        assert [item.value for item in app.info].count(
            translations["No Configured Providers"]
        ) == 4
        assert settings["llm_provider"] == "openai_codex"
        assert settings["video_source"] == "pexels"
        models.assert_not_called()
        login.assert_not_called()


def test_general_revalidates_configuration_when_using_previously_listed_provider():
    with settings_app() as (app, settings, _, _):
        run(app)
        app.selectbox(key="settings_general_stock_video_provider_select_en").select(
            "pixabay"
        )
        settings["pixabay_api_keys"] = []
        app.button(key="settings_general_use_stock_video").click()
        run(app)
        assert settings["video_source"] == "pexels"
        assert app.session_state["video_source_select_en"] == "pexels"


def test_general_activation_survives_pending_configuration_lock():
    with settings_app() as (app, settings, _, _):
        run(app)
        entered, release = threading.Event(), threading.Event()

        def worker():
            with config.runtime_config_lock():
                entered.set()
                release.wait(30)

        thread = threading.Thread(target=worker)
        thread.start()
        assert entered.wait(5)
        try:
            app.selectbox(key="settings_general_stock_video_provider_select_en").select(
                "pixabay"
            )
            app.button(key="settings_general_use_stock_video").click()
            run(app)
            assert settings["video_source"] == "pexels"
            assert (
                config.snapshot_config_with_pending(settings)["video_source"]
                == "pixabay"
            )
            assert app.session_state["video_source_select_en"] == "pixabay"
            app.selectbox(key="top_language_code_selector").select("es")
            run(app)
            assert app.session_state["video_source_select_es"] == "pixabay"
            assert (
                config.snapshot_config_with_pending(settings)["video_source"]
                == "pixabay"
            )
            app.session_state["settings_dialog_open"] = False
            run(app)
            assert app.session_state["video_source_select_es"] == "pixabay"
            assert settings["video_source"] == "pexels"
            assert (
                config.snapshot_config_with_pending(settings)["video_source"]
                == "pixabay"
            )
            app.session_state["settings_dialog_open"] = True
            app.session_state["settings_dialog_target_tab"] = "stock"
            run(app)
            assert app.session_state["settings_material_group"] == "stock_video"
            # 素材能力 TAB 读取含 pending 的快照：主源槽展示待生效选择。
            assert (
                app.selectbox(key="material_primary_stock_video_select_es").value
                == "pixabay"
            )
        finally:
            release.set()
            thread.join(5)
            with config.runtime_config_lock():
                config._flush_pending_config_locked(suppress_save_errors=False)
        run(app)
        assert settings["video_source"] == "pixabay"


@pytest.mark.parametrize(
    "locale", sorted(p.stem for p in (ROOT / "webui/i18n").glob("*.json"))
)
def test_new_navigation_translations_are_present(locale):
    translations = json.loads(
        (ROOT / f"webui/i18n/{locale}.json").read_text(encoding="utf-8")
    )["Translation"]
    for key in (
        "General Settings Tab",
        "General Providers Title",
        "General Providers Help",
        "Configured Providers",
        "Use Provider",
        "Configure Providers",
        "Active Provider",
        "No Configured Providers",
        "Provider Configuration Changed",
        # 服务商体系 v1.8.0：服务商配置页与素材能力 TAB。
        "Service Providers Tab",
        "Material API Tab",
        "Provider Overview Tab",
        "Provider Text Tab",
        "Provider Video Tab",
        "Provider Image Tab",
        "Provider Voiceover Tab",
        "Provider Music Tab",
        "Provider Stock Search Tab",
        "Capability Group AI Video",
        "Capability Group AI Image",
        "Capability Group Stock Video",
        "Capability Group Stock Image",
        "Priority Source",
        "Material Primary Source Help",
        "Backup Source 1",
        "Backup Source 2",
        "Backup Slot Disabled",
        "Material Chain Help",
        "Material Keys In Provider Page Hint",
        "Source Status Section",
        "Open Provider Settings",
        "Provider Configured Badge",
        "Provider Not Configured Badge",
        "LLM Chain Help",
        "TTS Chain Help",
    ):
        assert translations[key].strip()

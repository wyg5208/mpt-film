# -*- coding: utf-8 -*-
"""服务商配置页契约：七个能力 TAB、总览矩阵与无 Key 外泄。

服务商体系 v1.8.0 把全部 API 凭证集中到服务商配置页（原"大模型设置"）。
本文件锁定页面级契约：
1. TAB 结构固定为 总览/文本生成/视频生成/图片生成/配音/音乐/素材搜索，
   显式目标键（service_provider_target_tab）在页面与设置弹窗都能中途定向。
2. 总览矩阵按 国内→本地→国际→聚合 分组展示平台、能力与就绪徽标。
3. 各能力 TAB 惰性渲染且只承载自己的表单：文本 TAB 是 LLM 三槽链，
   配音 TAB 是 TTS 三槽链 + 各服务凭证，音乐/素材搜索集中对应 Key，
   素材能力下拉与素材页 Key 表单不出现在本页。
"""
import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config  # noqa: E402
from app.services import material as _material  # noqa: E402,F401  平台解析需先行
from app.services import publish_history, version_checker  # noqa: E402
from app.services import state as sm  # noqa: E402
from app.utils import utils  # noqa: E402

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
TREE = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))
ZH = json.loads(
    (ROOT_DIR / "webui" / "i18n" / "zh.json").read_text(encoding="utf-8")
)["Translation"]


def _module_constant(name):
    node = next(
        n for n in TREE.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    )
    return ast.literal_eval(node.value)


PROVIDER_TAB_LABEL_KEYS = _module_constant("PROVIDER_TAB_LABEL_KEYS")
VIDEO_SOURCE_GROUPS = _module_constant("VIDEO_SOURCE_GROUPS")
TTS_SERVER_OPTIONS = _module_constant("TTS_SERVER_OPTIONS")


def translate(key):
    return ZH[key]


PROVIDER_TABS_ZH = [translate(key) for key in PROVIDER_TAB_LABEL_KEYS]


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


def _provider_tabs(app):
    return [tab for tab in app.tabs if tab.label in PROVIDER_TABS_ZH]


def _selectbox_by_key(app, widget_key):
    return next(
        (box for box in app.selectbox if str(box.key) == widget_key), None
    )


def test_provider_page_mounts_seven_capability_tabs(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.run()
    assert not app.exception
    tabs = _provider_tabs(app)
    assert [tab.label for tab in tabs] == PROVIDER_TABS_ZH
    # 首次挂载预置首个 TAB，并把稳定 key 写入记忆。
    assert app.session_state["service_provider_active_tab"] == "Provider Overview Tab"


def test_overview_matrix_groups_platforms_with_badges(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.run()
    group_subheaders = [
        translate(key)
        for key in (
            "Platform Group Domestic",
            "Platform Group Local",
            "Platform Group International",
            "Platform Group Aggregator",
        )
    ]
    subheaders = [sh.value for sh in app.subheader]
    positions = [subheaders.index(label) for label in group_subheaders]
    assert positions == sorted(positions), "矩阵分组顺序必须为国内→本地→国际→聚合"
    # 平台标签与就绪徽标出现：免费 Edge TTS 平台已配置，密塔平台未配置。
    markdowns = [md.value for md in app.markdown]
    assert f"**{translate('platform_label.metaso')}**" in markdowns
    assert f"**{translate('platform_label.edge')}**" in markdowns
    assert translate("Provider Configured Badge") in "".join(markdowns)
    assert translate("Provider Not Configured Badge") in "".join(markdowns)


def test_text_tab_shows_llm_chain_and_current_provider_form(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Text Tab"
    app.run()
    assert not app.exception
    primary = _selectbox_by_key(app, "llm_provider_select_zh")
    assert primary is not None
    assert len(primary.options) == 45
    assert primary.value == "moonshot"
    for slot in (1, 2):
        backup = _selectbox_by_key(app, f"llm_provider_backup{slot}_select_zh")
        assert backup is not None
        # AppTest options 为渲染后的标签；空槽显示为“不启用”。
        assert len(backup.options) == 46
        assert backup.options[0] == translate("Backup Slot Disabled")
        assert backup.value == ""
    captions = [c.value for c in app.caption]
    assert translate("LLM Chain Help") in captions
    # 服务商页不承载素材链与素材源 Key 表单（LLM Provider 自身的 Key 表单除外）。
    assert not any(
        str(box.key).startswith("material_primary_") for box in app.selectbox
    )
    material_key_inputs = {
        f"{provider}_api_keys_input"
        for providers in VIDEO_SOURCE_GROUPS.values()
        for provider in providers
    }
    material_key_inputs.add("metaso_minimax_api_key_input")
    assert not any(
        str(item.key) in material_key_inputs for item in app.text_input
    )


def test_text_tab_backup_selection_saves_provider_id(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Text Tab"
    app.run()
    backup1 = _selectbox_by_key(app, "llm_provider_backup1_select_zh")
    backup1.set_value("deepseek").run()
    assert not app.exception
    assert app.session_state["llm_provider_backup1_select_zh"] == "deepseek"


def test_voiceover_tab_shows_tts_chain_and_eleven_credential_expanders(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Voiceover Tab"
    app.run()
    assert not app.exception
    primary = _selectbox_by_key(app, "tts_server_primary_select_zh")
    assert primary is not None
    server_ids = [server_id for server_id, _ in TTS_SERVER_OPTIONS]
    server_labels = [label for _, label in TTS_SERVER_OPTIONS]
    assert list(primary.options) == server_labels
    assert primary.value in server_ids
    for slot in (1, 2):
        backup = _selectbox_by_key(app, f"tts_server_backup{slot}_select_zh")
        assert backup is not None
        assert backup.value == ""
    captions = [c.value for c in app.caption]
    assert translate("TTS Chain Help") in captions
    # 11 个配音服务的凭证 expander 全部惰性渲染在此 TAB。
    expander_labels = [e.label for e in app.expander]
    for server_id, label in TTS_SERVER_OPTIONS:
        matching = [label_text for label_text in expander_labels if label in label_text]
        assert matching, f"missing credential expander for {server_id}"


def test_music_tab_concentrates_music_keys(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Music Tab"
    app.run()
    assert not app.exception
    input_keys = [str(item.key) for item in app.text_input]
    assert "sonilo_api_key_input" in input_keys
    assert any("elevenlabs" in key for key in input_keys)
    captions = [c.value for c in app.caption]
    assert translate("Provider Music Tab Help") in captions
    # 音乐 TAB 不承载配音/库存表单（惰性渲染互斥）。
    assert "pexels_api_keys_input" not in input_keys
    assert not any(str(box.key).startswith("tts_server_") for box in app.selectbox)


def test_stock_tab_lists_stock_video_keys_with_shared_hint(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Stock Search Tab"
    app.run()
    assert not app.exception
    input_keys = [str(item.key) for item in app.text_input]
    for provider in VIDEO_SOURCE_GROUPS["stock_video"]:
        assert f"{provider}_api_keys_input" in input_keys
    captions = [c.value for c in app.caption]
    assert translate("Stock Image Keys Shared Hint") in captions
    # AI 视频的密钥表单在视频生成 TAB，不在素材搜索 TAB。
    assert "ofox_api_key_input" not in input_keys


def test_video_and_image_tabs_render_their_own_provider_forms(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Video Tab"
    app.run()
    assert not app.exception
    captions = [c.value for c in app.caption]
    assert translate("Provider Video Tab Help") in captions
    input_keys = [str(item.key) for item in app.text_input]
    assert "sonilo_api_key_input" not in input_keys
    assert not any(str(box.key).startswith("llm_provider_") for box in app.selectbox)

    app.session_state["service_provider_target_tab"] = "Provider Image Tab"
    app.run()
    assert not app.exception
    captions = [c.value for c in app.caption]
    assert translate("Provider Image Tab Help") in captions
    expander_labels = [e.label for e in app.expander]
    assert any(
        translate("OpenAI Compatible Text-to-Image") in label
        for label in expander_labels
    )
    assert "pexels_api_keys_input" not in [
        str(item.key) for item in app.text_input
    ]


def test_settings_dialog_reuses_provider_body_with_target(isolated_app):
    """设置弹窗素材/服务商 TAB 复用同一 body：定向键在弹窗内同样生效。"""
    app = isolated_app
    app.session_state["settings_dialog_open"] = True
    app.session_state["settings_dialog_target_tab"] = "llm"
    app.session_state["service_provider_target_tab"] = "Provider Voiceover Tab"
    app.run()
    assert not app.exception
    assert _selectbox_by_key(app, "tts_server_primary_select_zh") is not None

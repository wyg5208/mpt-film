# -*- coding: utf-8 -*-
"""素材来源设置契约：能力 TAB、三槽链与主源双向同步。

素材体系 v1.8.0 把素材来源按能力分组为四个 TAB（AI 视频/AI 图片/
库存视频/库存图片）。本文件锁定页面级契约：
1. 每个 TAB = 三槽来源链：第一优先写唯一主源键 config.app.video_source
   并与创作页下拉双向同步；备用 1/2 按能力分组存储
   （video_source_backups_<group>_<slot>）。
2. 能力 TAB 惰性渲染，且素材体不承载任何 Key 输入（Key 全部集中在
   服务商配置页）。
3. "前往服务商配置"按钮按能力分组定向到对应服务商 TAB 并打开设置弹窗。
4. 页面与设置弹窗共用同一记忆键，互切后能力分组不丢失。
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


VIDEO_SOURCE_GROUPS = _module_constant("VIDEO_SOURCE_GROUPS")
CAPABILITY_TAB_LABEL_KEYS = (
    "Capability Group AI Video",
    "Capability Group AI Image",
    "Capability Group Stock Video",
    "Capability Group Stock Image",
)
CAPABILITY_TABS_ZH = [ZH[key] for key in CAPABILITY_TAB_LABEL_KEYS]
CAPABILITY_GROUPS = {
    "Capability Group AI Video": "ai_video",
    "Capability Group AI Image": "ai_image",
    "Capability Group Stock Video": "stock_video",
    "Capability Group Stock Image": "stock_image",
}
GROUP_PROVIDER_TAB = {
    "ai_video": "Provider Video Tab",
    "ai_image": "Provider Image Tab",
    "stock_video": "Provider Stock Search Tab",
    "stock_image": "Provider Stock Search Tab",
}


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


def _capability_tabs(app):
    return [tab for tab in app.tabs if tab.label in CAPABILITY_TABS_ZH]


def _selectbox_by_key(app, widget_key):
    return next(
        (box for box in app.selectbox if str(box.key) == widget_key), None
    )


def _open_material_group(app, group):
    app.session_state["settings_material_group"] = group
    app.session_state["active_page"] = "material"
    app.run()
    assert not app.exception


def test_material_page_mounts_four_capability_tabs(isolated_app):
    app = isolated_app
    _open_material_group(app, "ai_video")
    tabs = _capability_tabs(app)
    assert [tab.label for tab in tabs] == CAPABILITY_TABS_ZH
    # 首次挂载记忆键落在首个能力分组（stable key = 分组 id）。
    assert app.session_state["settings_material_group"] == "ai_video"


def test_capability_tab_renders_three_slot_chain_without_key_inputs(isolated_app):
    app = isolated_app
    _open_material_group(app, "ai_video")
    providers = list(VIDEO_SOURCE_GROUPS["ai_video"])
    primary = _selectbox_by_key(app, "material_primary_ai_video_select_zh")
    assert primary is not None
    # options 为渲染后的标签；数量与能力分组的来源数一致。
    assert len(primary.options) == len(providers)
    assert primary.value in providers
    for slot in (1, 2):
        backup = _selectbox_by_key(app, f"material_backup{slot}_ai_video_select_zh")
        assert backup is not None
        assert len(backup.options) == len(providers) + 1
        assert backup.options[0] == ZH["Backup Slot Disabled"]
        assert backup.value == ""
    captions = [c.value for c in app.caption]
    for key in (
        "Material Primary Source Help",
        "Material Chain Help",
        "Material Keys In Provider Page Hint",
    ):
        assert ZH[key] in captions
    # 源状态区：分隔徽标行逐源列出（展示用能力标签，非原始 id）。
    markdowns = [md.value for md in app.markdown]
    assert f"**{ZH['Source Status Section']}**" in markdowns
    badge_lines = [
        md for md in markdowns
        if md.startswith(":material/") and "·" in md
    ]
    assert len(badge_lines) == len(providers)
    assert any(ZH["Metaso MiniMax H3"] in md for md in badge_lines)
    assert any(ZH["OFox AI Video"] in md for md in badge_lines)
    assert "material_open_providers_ai_video" in [
        str(btn.key) for btn in app.button
    ]
    # 素材体不承载任何 Key 输入。
    assert not any("api_key" in str(item.key) for item in app.text_input)


def test_seed_group_targets_lazy_capability_tab(isolated_app):
    app = isolated_app
    _open_material_group(app, "ai_image")
    assert (
        _selectbox_by_key(app, "material_primary_ai_image_select_zh") is not None
    )
    # 惰性渲染：非当前能力分组的第一优先下拉不存在。
    assert _selectbox_by_key(app, "material_primary_ai_video_select_zh") is None


def test_primary_select_writes_unique_source_key(isolated_app):
    """第一优先下拉写唯一主源键，并同步创作页与通用页的来源控件。"""
    app = isolated_app
    _open_material_group(app, "ai_video")
    primary = _selectbox_by_key(app, "material_primary_ai_video_select_zh")
    primary.set_value("ofox").run()
    assert not app.exception
    assert config.app["video_source"] == "ofox"
    # 双向同步：创作页/通用页的来源选择控件跟随更新。
    assert app.session_state["video_source_select_zh"] == "ofox"
    # 能力分组记忆保持。
    assert app.session_state["settings_material_group"] == "ai_video"


def test_backup_slots_write_capability_scoped_keys(isolated_app):
    app = isolated_app
    _open_material_group(app, "ai_image")
    backup1 = _selectbox_by_key(app, "material_backup1_ai_image_select_zh")
    backup1.set_value("codex_image").run()
    assert not app.exception
    assert config.app["video_source_backups_ai_image_1"] == "codex_image"
    backup2 = _selectbox_by_key(app, "material_backup2_ai_image_select_zh")
    backup2.set_value("openai_image").run()
    assert not app.exception
    assert config.app["video_source_backups_ai_image_2"] == "openai_image"
    # 第一优先不受备用槽影响。
    assert config.app["video_source"] != "codex_image"


def test_stock_image_group_lists_shared_key_sources(isolated_app):
    app = isolated_app
    _open_material_group(app, "stock_image")
    providers = list(VIDEO_SOURCE_GROUPS["stock_image"])
    primary = _selectbox_by_key(app, "material_primary_stock_image_select_zh")
    assert primary is not None
    assert len(primary.options) == len(providers)
    captions = [c.value for c in app.caption]
    assert ZH["Material Keys In Provider Page Hint"] in captions


def test_open_provider_button_targets_group_tab(isolated_app):
    app = isolated_app
    _open_material_group(app, "ai_video")
    button = next(
        btn for btn in app.button
        if str(btn.key) == "material_open_providers_ai_video"
    )
    button.click().run()
    assert not app.exception
    # 目标键被本次挂载消费；记忆键落在对应服务商 TAB。
    assert "service_provider_target_tab" not in app.session_state
    assert app.session_state["service_provider_active_tab"] == "Provider Video Tab"
    # 弹窗目标键同样被消费，弹窗 TAB 记忆落在 llm。
    assert "settings_dialog_target_tab" not in app.session_state
    assert app.session_state["settings_active_tab"] == "llm"
    assert app.session_state["settings_dialog_open"] is True
    # 服务商配置页惰性渲染了对应能力分组的 Key 表单（视频生成 TAB）。
    captions = [c.value for c in app.caption]
    assert ZH["Provider Video Tab Help"] in captions


def test_group_memory_survives_page_and_dialog_switch(isolated_app):
    """页面 ↔ 设置弹窗互切后能力分组保持（记忆键是唯一事实来源）。"""
    app = isolated_app
    _open_material_group(app, "ai_image")
    app.session_state["active_page"] = "quick"
    app.session_state["settings_dialog_open"] = True
    app.session_state["settings_active_tab"] = "material"
    app.run()
    assert not app.exception
    assert app.session_state["settings_material_group"] == "ai_image"
    assert _selectbox_by_key(app, "material_primary_ai_image_select_zh") is not None
    # 回到一级素材页，分组仍在。
    app.session_state["settings_dialog_open"] = False
    app.session_state["active_page"] = "material"
    app.run()
    assert not app.exception
    assert app.session_state["settings_material_group"] == "ai_image"
    assert _selectbox_by_key(app, "material_primary_ai_image_select_zh") is not None

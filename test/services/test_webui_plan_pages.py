# -*- coding: utf-8 -*-
"""B7 生产 WebUI 契约测试：三页渲染 + 14 locale 完整性 + llamacpp Registry。

- locale 完整性：AST 提取三页渲染器实际使用的 tr() 键（含条件表达式与
  标签常量），断言 14 个语言文件全部收录且非空。
- AppTest 冒烟：render-all 壳下三页同跑，引擎探针/草稿库/系列库全部
  patch 到临时目录与离线状态，不触碰真实 storage 与网络引擎。
"""

import ast
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.models.llm_provider import get_llm_provider
from app.models.schema import Series
from app.services import comfy_local, plan_store, series_store

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
I18N_DIR = ROOT_DIR / "webui" / "i18n"
LOCALES = ("az", "ca", "de", "en", "es", "fr", "id", "it", "ko", "pt", "ru", "tr", "vi", "zh")

B7_RENDERERS = {
    "_render_wizard_page", "_render_plan_page", "_render_series_page",
    "_render_local_engine_dashboard", "_plan_draft_picked",
    "_plan_scene_field_changed", "_plan_setting_changed",
    "_series_character_appearance_changed", "_series_reference_lock_changed",
}
LABEL_CONSTANTS = (
    "PLAN_ENGINE_LABELS", "PLAN_TRANSITION_LABELS",
    "EPISODE_STATUS_LABELS", "WIZARD_GENRES",
)
OFFLINE_ENGINES = {
    "comfyui": {"online": False},
    "acestep": {"online": False},
    "ollama": {"online": False},
}


def _load_translation(locale: str) -> dict:
    data = json.loads((I18N_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    return data["Translation"]


def _used_b7_keys() -> set:
    """与 .tmp-ui-impl/b7-key-check.py 同源的键提取，测试内自包含。"""
    tree = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))
    used = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in B7_RENDERERS:
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "tr"
                    and sub.args
                ):
                    # 只取键参数本身：常量或 tr("A" if cond else "B")
                    # 条件键；不.walk 整个调用，避免误收比较常量。
                    arg = sub.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        used.add(arg.value)
                    elif isinstance(arg, ast.IfExp):
                        for branch in (arg.body, arg.orelse):
                            if isinstance(branch, ast.Constant) and isinstance(branch.value, str):
                                used.add(branch.value)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") in LABEL_CONSTANTS for t in node.targets
        ):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if re.match(r"^(Plan Engine|Transition|Episode Status|Genre) ", sub.value):
                        used.add(sub.value)
    # 生成钩子里的方案校验失败提示。
    used.add("Plan Execute Invalid")
    return used


def make_plan_payload(**overrides) -> dict:
    payload = {
        "title": "冒烟影片",
        "target_duration": 60,
        "scenes": [
            {"id": "s1", "order": 1, "narration": "开场旁白", "est_duration": 5.0}
        ],
    }
    payload.update(overrides)
    return payload


def make_series(**overrides) -> Series:
    payload = {
        "id": "sr-smoke01",
        "title": "冒烟短剧",
        "characters": [
            {"id": "c1", "name": "林晚", "voice_name": "zh-CN-XiaoxiaoNeural"}
        ],
        "episodes": [
            {"id": "ep1", "seq": 1, "title": "开局"},
            {"id": "ep2", "seq": 2, "title": "反转"},
        ],
    }
    payload.update(overrides)
    return Series.model_validate(payload)


def _widget_by_key(elements, key: str):
    return next(
        item
        for item in elements
        if str(getattr(item, "key", "")) == key
        or str(getattr(item, "key", "")).startswith(f"{key}_")
    )


@pytest.fixture()
def isolated_stores(tmp_path):
    plans = tmp_path / "plans"
    series = tmp_path / "series"
    plans.mkdir()
    series.mkdir()
    with (
        patch.object(plan_store, "plans_root", return_value=plans),
        patch.object(series_store, "series_root", return_value=series),
        patch.object(comfy_local, "local_engines_status", return_value=OFFLINE_ENGINES),
        patch.object(config, "save_config"),
        patch.object(config, "try_save_config", return_value=True),
    ):
        yield plans, series


def test_b7_keys_translated_in_all_14_locales():
    used = _used_b7_keys()
    # 提取器 sanity：三页 + 仪表盘 + 标签常量的键规模。
    assert len(used) >= 110, f"key extraction suspiciously small: {len(used)}"
    for locale in LOCALES:
        translations = _load_translation(locale)
        for key in sorted(used):
            assert key in translations, f"{locale}: missing {key}"
            assert str(translations[key]).strip(), f"{locale}: empty {key}"


def test_llamacpp_tips_follow_zh_en_convention():
    for locale in ("en", "zh"):
        tips = _load_translation(locale)["llm_provider_tips.llamacpp"]
        assert "{default_base_url}" in tips
        assert "{default_model}" in tips
        assert "llama-server" in tips


def test_llamacpp_registry_spec():
    spec = get_llm_provider("llamacpp")
    assert spec is not None
    assert spec.provider_id == "llamacpp"
    assert spec.default_label == "llama.cpp (llama-server)"
    assert spec.default_model == "local-model"
    assert spec.default_base_url == "http://127.0.0.1:8080/v1"
    assert spec.requires_api_key is False
    assert spec.adapter == "openai_compatible"


def test_plan_pages_smoke_empty_state(isolated_stores):
    translations = _load_translation("zh")
    app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60)
    app.session_state["ui_language"] = "zh"
    # 激活向导页：仪表盘只在所属页活动时探针（已 patch 离线）。
    app.session_state["active_page"] = "wizard"
    app.run()

    assert [str(item.value) for item in app.exception] == []
    # 向导页：想法输入 + 题材 + 生成按钮（标签走 zh 翻译）。
    assert _widget_by_key(app.text_area, "wizard_story_idea") is not None
    assert _widget_by_key(app.selectbox, "wizard_genre") is not None
    generate = _widget_by_key(app.button, "wizard_generate_button")
    assert generate.label == translations["Wizard Generate"]
    # 方案页空态：主题输入 + 生成入口。
    assert _widget_by_key(app.text_input, "plan_new_subject") is not None
    assert _widget_by_key(app.button, "plan_generate_button") is not None
    # 系列页空态：新建入口。
    assert _widget_by_key(app.button, "series_create_button") is not None
    # 导航契约（IA 重构后）：创作组收敛为快速成片/专业短剧两个一级页，
    # 向导/方案/系列作为专业页 TAB 存在（旧 id 经 LEGACY 映射仍可导航）。
    for page in ("quick", "pro"):
        assert _widget_by_key(app.button, f"nav_page_{page}") is not None


def test_plan_page_edit_and_confirm_contract(isolated_stores):
    plans_root, series_root = isolated_stores
    plan_id = plan_store.save_plan(make_plan_payload(), plan_id="pl-smoke01")
    series_store.save_series(make_series())
    series_store.bind_episode_plan("sr-smoke01", "ep1", plan_id)

    app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60)
    app.session_state["ui_language"] = "zh"
    app.session_state["script_plan_current_id"] = plan_id
    app.run()
    assert [str(item.value) for item in app.exception] == []

    # 草稿选择器 + 场景卡 + 执行入口 + 系列剧集绑定全部渲染。
    assert _widget_by_key(app.selectbox, "plan_draft_picker") is not None
    narration = _widget_by_key(app.text_area, "plan_scene_narration_s1")
    assert narration.value == "开场旁白"
    assert _widget_by_key(app.button, "plan_execute_button") is not None
    assert _widget_by_key(app.selectbox, "series_picker") is not None
    assert _widget_by_key(app.button, "series_open_plan_ep1") is not None

    # 确认：status→confirmed，修订号不变（付费门禁重新生效的入口）。
    _widget_by_key(app.button, "plan_confirm_button").click().run()
    assert [str(item.value) for item in app.exception] == []
    stored = plan_store.load_plan(plan_id)
    assert stored["status"] == "confirmed"
    assert stored["revision"] == 1

    # 编辑旁白：回退 draft + revision++，预估时长按字数重算。
    new_narration = "她推开门，看见桌上那份被否决的方案，忽然笑了。"
    _widget_by_key(app.text_area, "plan_scene_narration_s1").set_value(
        new_narration
    ).run()
    assert [str(item.value) for item in app.exception] == []
    stored = plan_store.load_plan(plan_id)
    assert stored["status"] == "draft"
    assert stored["revision"] == 2
    assert stored["scenes"][0]["narration"] == new_narration
    assert stored["scenes"][0]["est_duration"] > 5.0
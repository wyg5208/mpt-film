"""方案编辑回调的重置产物契约：None 控件值不得写入模型。

背景（2026-11-21 用户实测）：脚本方案页 AI 重生成后报
“方案编辑被拒绝: script plan validation failed: … quality_tier …
input_value=None”。根因链：_plan_reset_widgets 删除会话键 → Streamlit
重建控件时以 None 重放 on_change → _plan_setting_changed 把 None setattr
进模型（pydantic 默认不校验赋值）→ model_dump 出 null → save_plan
fail-closed 拒绝。磁盘草稿本身干净，属误拒绝。本文件在回调接缝处钉死：
None（控件重置产物）跳过；真实编辑值照常落盘。
"""
import ast
import types
from pathlib import Path

import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from app.models.schema import ScriptPlan
from app.services import llm, plan_store
from app.services import material as _material  # noqa: F401  (平台解析顺序)
from app.services.llm import estimate_scene_duration

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
TREE = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))

SEAM_FUNCTIONS = (
    "_plan_mutate",
    "_plan_setting_changed",
    "_plan_scene_field_changed",
)


def _seam_namespace():
    """只抽取三个回调接缝函数源码执行，不导入 Streamlit 脚本本体。"""
    text = WEBUI_MAIN.read_text(encoding="utf-8")
    source = [
        ast.get_source_segment(text, node)
        for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name in SEAM_FUNCTIONS
    ]
    assert len(source) == len(SEAM_FUNCTIONS)
    fake_st = types.SimpleNamespace(session_state={})
    namespace = {
        "st": fake_st,
        "plan_store": plan_store,
        "ScriptPlan": ScriptPlan,
        "ValidationError": ValidationError,
        "estimate_scene_duration": estimate_scene_duration,
    }
    exec("\n\n".join(source), namespace)
    return namespace, fake_st


def _sample_payload():
    plan = ScriptPlan.model_validate(
        {
            "title": "重置产物契约",
            "scenes": [
                {"id": "s1", "order": 1, "narration": "第一幕旁白。", "est_duration": 3.0},
                {"id": "s2", "order": 2, "narration": "第二幕旁白。", "est_duration": 3.0},
            ],
        }
    )
    return plan.model_dump(mode="json", by_alias=True)


@pytest.fixture
def tmp_plans(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_store, "plans_root", lambda: tmp_path / "plans")
    plan_id = plan_store.save_plan(_sample_payload())
    return plan_id


def test_reset_artifact_none_does_not_reject_edit(tmp_plans):
    namespace, fake_st = _seam_namespace()
    # 会话键缺失（_plan_reset_widgets 删除后的重置产物）→ 回调不得突变。
    namespace["_plan_setting_changed"](tmp_plans, "quality_tier", "plan_quality_tier")
    assert "plan_edit_error" not in fake_st.session_state
    namespace["_plan_scene_field_changed"](
        tmp_plans, "s1", "narration", "plan_scene_s1_narration"
    )
    assert "plan_edit_error" not in fake_st.session_state
    saved = plan_store.load_plan(tmp_plans)
    assert saved["quality_tier"] == "draft"
    assert saved["revision"] == 1
    assert saved["scenes"][0]["narration"] == "第一幕旁白。"


def test_real_edit_values_still_land(tmp_plans):
    namespace, fake_st = _seam_namespace()
    fake_st.session_state["plan_quality_tier"] = "final"
    namespace["_plan_setting_changed"](tmp_plans, "quality_tier", "plan_quality_tier")
    assert "plan_edit_error" not in fake_st.session_state
    saved = plan_store.load_plan(tmp_plans)
    assert saved["quality_tier"] == "final"
    assert saved["revision"] == 2
    assert saved["status"] == "draft"

    fake_st.session_state["plan_scene_s1_narration"] = "改后的旁白。"
    namespace["_plan_scene_field_changed"](
        tmp_plans, "s1", "narration", "plan_scene_s1_narration"
    )
    assert "plan_edit_error" not in fake_st.session_state
    saved = plan_store.load_plan(tmp_plans)
    assert saved["scenes"][0]["narration"] == "改后的旁白。"
    assert saved["revision"] == 3


def test_app_ai_regenerate_leaves_no_edit_error(tmp_plans, monkeypatch):
    regenerated = ScriptPlan.model_validate(
        {
            "title": "AI 重生成产物",
            "scenes": [
                {"id": "s1", "order": 1, "narration": "新第一幕。", "est_duration": 3.0},
                {"id": "s2", "order": 2, "narration": "新第二幕。", "est_duration": 3.0},
            ],
        }
    ).model_dump(mode="json", by_alias=True)
    monkeypatch.setattr(llm, "generate_script_plan", lambda *_a, **_k: regenerated)
    app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60)
    app.session_state["script_plan_current_id"] = tmp_plans
    app.session_state["active_page"] = "plan"
    app.run()
    assert not app.exception
    app.button(key="plan_regenerate_button").click()
    app.run()
    assert not app.exception
    assert "plan_edit_error" not in app.session_state
    saved = plan_store.load_plan(tmp_plans)
    assert saved["revision"] == 2
    assert saved["title"] == "AI 重生成产物"
    assert saved["quality_tier"] == "draft"
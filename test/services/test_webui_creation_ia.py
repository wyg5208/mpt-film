"""创作区 IA 契约：快速成片 / 专业短剧 两路线 + 全 TAB 化 + 项目级设置。

背景（2026-11-21 用户反馈“创作菜单思路混乱”）：七个一级创作页收敛为
两个一级路线页，其余全部 TAB 化；四个设置 TAB（图片/视频/音频/字幕）
在两条路线页都出现；render-all 契约保持（每次 rerun 七个渲染器恰好
各渲染一次，params 组装不漂移）；项目切换恢复覆盖图片设置参数。
"""
import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.config import config
from app.services import publish_history, version_checker
from app.services import state as sm
from app.utils import utils

# 与 test_webui_idle_polling 相同：moviepy/numpy 的平台解析必须先于
# 任何 monkeypatch 完成。
from app.services import material as _material  # noqa: F401

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
TREE = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))
ZH = json.loads(
    (ROOT_DIR / "webui" / "i18n" / "zh.json").read_text(encoding="utf-8")
)["Translation"]

IA_KEYS = [
    "Nav Quick Film",
    "Nav Pro Drama",
    "Image Settings",
    "Tab Script",
    "Tab Video",
    "Tab Audio",
    "Tab Subtitle",
    "Image Motion Section",
    "Image Motion Section Help",
    "Image Provider Elsewhere Hint",
    "Local Keyframe Engine Section",
    "Local Keyframe Engine Help",
    "Local Engine Probe",
    "Local Engine Online",
    "Local Engine Offline",
    "Local Engine Unknown",
]
LOCALES = [
    "az", "ca", "de", "en", "es", "fr", "id",
    "it", "ko", "pt", "ru", "tr", "vi", "zh",
]


def _module_constant(name):
    node = next(
        n for n in TREE.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    )
    return ast.literal_eval(node.value)


def test_nav_creation_group_is_exactly_two_routes():
    pages = _module_constant("NAV_PAGES")
    creation = [page for page, _label, _icon, group in pages if group == "creation"]
    assert creation == ["quick", "pro"]
    # 其余分组保持原一级页，不受本次 IA 收敛影响。
    assert [p for p, _l, _i, g in pages if g == "publish"] == [
        "tasks", "publish_history"
    ]


def test_legacy_creation_ids_all_map_into_route_tabs():
    legacy = _module_constant("LEGACY_CREATION_PAGES")
    quick_keys = _module_constant("QUICK_TAB_LABEL_KEYS")
    pro_keys = _module_constant("PRO_TAB_LABEL_KEYS")
    assert set(legacy) == {
        "script", "video", "audio", "subtitle", "wizard", "plan", "series"
    }
    for route, index in legacy.values():
        labels = quick_keys if route == "quick" else pro_keys
        assert route in {"quick", "pro"}
        assert 0 <= index < len(labels)
    # 四个设置 TAB 在两条路线页都出现（用户显式要求）。
    for key in ("Image Settings", "Tab Video", "Tab Audio", "Tab Subtitle"):
        assert key in quick_keys and key in pro_keys


def test_ia_keys_translated_and_non_empty_in_all_locales():
    for locale in LOCALES:
        data = json.loads(
            (ROOT_DIR / "webui" / "i18n" / f"{locale}.json").read_text(encoding="utf-8")
        )["Translation"]
        for key in IA_KEYS:
            assert key in data, f"{locale} missing {key}"
            assert data[key].strip(), f"{locale} has empty {key}"


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


def _tab_labels(app):
    # app.tabs 收集全应用所有 TAB（含系列页/设置弹窗内嵌 TAB）；
    # 只保留创作区一级 TAB 标签，保持渲染顺序。
    wanted = set(ZH[key] for key in _module_constant("QUICK_TAB_LABEL_KEYS"))
    wanted |= set(ZH[key] for key in _module_constant("PRO_TAB_LABEL_KEYS"))
    return [tab.label for tab in app.tabs if tab.label in wanted]


def _params_snapshot(app):
    return app.session_state["project_params_last_full"]


def test_quick_page_tabs_and_render_all_params(isolated_app):
    app = isolated_app
    app.run()
    assert not app.exception
    assert _tab_labels(app) == [
        ZH[key] for key in _module_constant("QUICK_TAB_LABEL_KEYS")
    ]
    snapshot = _params_snapshot(app)
    # 图片/视频/音频/字幕渲染器都在本次 run 组装了 params。
    for field in ("image_motion", "video_aspect", "voice_name", "subtitle_enabled"):
        assert field in snapshot, field
    # render-all：专业路线渲染器在隐藏 fallback 中仍产出控件。
    assert any(str(b.key) == "wizard_generate_button" for b in app.button)
    # 页级路线横幅在 TAB 栏之上，任何 TAB 下可达。
    assert any(str(b.key) == "route_quick_to_plan" for b in app.button)


def test_pro_page_tabs_include_settings_and_params(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "pro"
    app.run()
    assert not app.exception
    assert _tab_labels(app) == [
        ZH[key] for key in _module_constant("PRO_TAB_LABEL_KEYS")
    ]
    snapshot = _params_snapshot(app)
    for field in ("image_motion", "video_aspect", "voice_name", "subtitle_enabled"):
        assert field in snapshot, field
    # 文案渲染器让位到 fallback，但控件与页级路线横幅仍在。
    assert any(str(b.key) == "route_pro_to_quick" for b in app.button)
    assert any(str(b.key) == "image_local_engine_probe" for b in app.button)


def test_non_creation_page_still_assembles_params(isolated_app):
    app = isolated_app
    app.session_state["active_page"] = "tasks"
    app.run()
    assert not app.exception
    # 非创作页：TAB 不渲染，但 fallback 承载全部渲染器，params 不漂移。
    assert _tab_labels(app) == []
    snapshot = _params_snapshot(app)
    for field in ("image_motion", "video_aspect", "voice_name", "subtitle_enabled"):
        assert field in snapshot, field
    assert any(str(b.key) == "wizard_generate_button" for b in app.button)


def test_legacy_active_page_aliases_normalize_to_route_tab(isolated_app):
    app = isolated_app
    for alias, route, label_key in (
        ("plan", "pro", "Script Plan"),
        ("video", "quick", "Tab Video"),
        ("wizard", "pro", "Creation Wizard"),
    ):
        app.session_state["active_page"] = alias
        app.run()
        assert not app.exception
        assert app.session_state["active_page"] == route
        tabs_key = "quick_tabs" if route == "quick" else "pro_tabs"
        assert app.session_state[tabs_key] == ZH[label_key]


def test_project_restore_carries_image_settings_per_project(isolated_app):
    app = isolated_app
    app.run()
    assert not app.exception
    # 项目 A：静态图动效；恢复后控件与参数快照都应是 static。
    # 动效仅对本地/AI 图像源挂载，恢复参数需带 video_source。
    app.session_state["task_restore_payload"] = {
        "task_id": "proj-a",
        "params": {"video_subject": "A", "video_source": "local", "image_motion": "static"},
    }
    app.run()
    assert not app.exception
    motion_keys = [
        k for k in app.session_state.keys() if k.startswith("image_motion_select")
    ]
    assert motion_keys, "image motion widget state missing"
    assert app.session_state[motion_keys[0]] == "static"
    assert _params_snapshot(app)["image_motion"] == "static"
    # 项目 B：缓慢缩放；切换后独立生效，不串项目。
    app.session_state["task_restore_payload"] = {
        "task_id": "proj-b",
        "params": {"video_subject": "B", "video_source": "local", "image_motion": "zoom"},
    }
    app.run()
    assert not app.exception
    assert app.session_state[motion_keys[0]] == "zoom"
    assert _params_snapshot(app)["image_motion"] == "zoom"


def test_in_app_legacy_jump_lands_on_route_tab(isolated_app):
    # 系列页“新建系列”按钮仍用旧 id（wizard）跳转：必须归一到
    # 专业页 + 创作向导 TAB，而不是被 NAV_PAGE_IDS 守卫静默丢弃。
    app = isolated_app
    app.session_state["active_page"] = "pro"
    app.run()
    assert not app.exception
    button = next(
        b for b in app.button if str(b.key) == "series_create_button"
    )
    button.click().run()
    assert not app.exception
    assert app.session_state["active_page"] == "pro"
    assert app.session_state["pro_tabs"] == ZH["Creation Wizard"]


def test_route_entry_seeds_tab_selection_and_keeps_memory(isolated_app):
    # 进路线页前预置 TAB 选中值：避免 st.tabs 挂载补发选中事件
    # 触发额外整轮 rerun；影子键保留用户上次选中，跨页不丢。
    app = isolated_app
    app.session_state["pro_tabs_last"] = ZH["Series Library"]
    app.run()
    assert not app.exception
    nav_pro = next(b for b in app.button if str(b.key) == "nav_page_pro")
    nav_pro.click().run()
    assert not app.exception
    # 无显式目标 TAB：恢复影子键里的上次选中，而非首 TAB。
    assert app.session_state["pro_tabs"] == ZH["Series Library"]
    assert app.session_state["pro_tabs_last"] == ZH["Series Library"]
    nav_quick = next(b for b in app.button if str(b.key) == "nav_page_quick")
    nav_quick.click().run()
    assert not app.exception
    # 首次进快速页：预置首 TAB，挂载即稳定。
    assert app.session_state["quick_tabs"] == ZH["Tab Script"]
    nav_pro = next(b for b in app.button if str(b.key) == "nav_page_pro")
    nav_pro.click().run()
    assert not app.exception
    # 离开再回来：TAB 记忆仍在。
    assert app.session_state["pro_tabs"] == ZH["Series Library"]


def test_material_primary_select_renders_only_in_material_body(isolated_app):
    # 创作面板已参数化：图片能力的第一优先下拉只存在于素材来源体
    # （一级页 / 设置弹窗素材 TAB），快速成片页不再渲染任何来源选择器。
    app = isolated_app
    prefix = "material_primary_ai_image_select"

    def count():
        return sum(1 for b in app.selectbox if str(b.key).startswith(prefix))

    app.run()
    assert not app.exception
    assert count() == 0  # 快速成片页的图片 TAB 只保留参数
    # 能力 TAB 惰性渲染：显式定位到图片能力分组再统计。
    app.session_state["settings_material_group"] = "ai_image"
    app.session_state["active_page"] = "material"
    app.run()
    assert not app.exception
    assert count() == 1  # 素材来源页能力 TAB 本体
    app.session_state["active_page"] = "quick"
    app.session_state["settings_dialog_open"] = True
    app.session_state["settings_active_tab"] = "material"
    app.run()
    assert not app.exception
    assert count() == 1  # 设置弹窗素材 TAB 本体
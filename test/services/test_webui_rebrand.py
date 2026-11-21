"""ChangoFilm 品牌升级契约：UI 零旧品牌、旧导出文件兼容、元数据一致。

背景（2026-11-21 用户要求“正式改名为 ChangoFilm，UI 中不再体现任何
MoneyPrinterTurbo 说明，仅 README 保留参考项目致谢”）：
- 页面配置、品牌区与 14 个语言文件的可见文案不得再出现旧品牌；
  功能性 URL（赞助追踪参数等）按既定决策原样保留，校验时先剥离 URL。
- 品牌升级前导出的设置预设 / 密钥备份 / 项目参数快照（旧 schema）必须
  仍可导入读取，新导出一律写新 schema。
"""
import ast
import json
import os
from pathlib import Path
import re
import tomllib
from unittest.mock import patch

import pytest
from loguru import logger
from streamlit.testing.v1 import AppTest

from app.config import config
from app.models.schema import VideoParams
from app.services import publish_history, version_checker
from app.services import state as sm
from app.utils import utils

# moviepy/numpy 的平台解析必须先于任何 monkeypatch 完成。
from app.services import material as _material  # noqa: F401

ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"
I18N_DIR = ROOT_DIR / "webui" / "i18n"

# 与 rebrand-sweep 相同的 URL 掩码：功能性链接（含 aff=moneyprinterturbo、
# ?s=MPT 等历史追踪参数）不参与品牌文案校验。
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]\\]+")
_LEGACY_BRAND_RES = (
    re.compile(r"moneyprint", re.IGNORECASE),
    re.compile(r"\bMPT\b"),
    re.compile(r"\bmpt\b"),
)


def _visible_text(value: str) -> str:
    return _URL_RE.sub("", value)


def _assert_brand_free(value: str, where: str):
    stripped = _visible_text(value)
    for pattern in _LEGACY_BRAND_RES:
        assert not pattern.search(stripped), f"{where} 仍含旧品牌: {value!r}"


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


def test_page_config_uses_changofilm_brand():
    """页面标题、图标与 About 菜单均为 ChangoFilm，且不再指向上游仓库。"""
    source = WEBUI_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    page_config = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_page_config"
        ):
            page_config = ast.get_source_segment(source, node)
            break
    assert page_config is not None
    assert 'page_title="ChangoFilm"' in page_config
    assert "# ChangoFilm" in page_config
    assert "Report a bug" not in page_config
    assert "harry0703" not in page_config
    assert "MoneyPrinter" not in page_config


def test_rendered_ui_shows_changofilm_and_no_legacy_brand(isolated_app):
    """真实渲染：品牌区为 ChangoFilm，可见文案（剥离 URL 后）零旧品牌。"""
    app = isolated_app
    app.run()
    assert not app.exception
    markdown_values = [str(element.value) for element in app.markdown]
    assert any(
        'changofilm-brand__name">ChangoFilm' in value
        for value in markdown_values
    ), "品牌区必须渲染 ChangoFilm 名称"
    for value in markdown_values:
        _assert_brand_free(value, "st.markdown")
    for button in app.button:
        _assert_brand_free(str(button.label), f"button[{button.key}].label")
        _assert_brand_free(str(button.help or ""), f"button[{button.key}].help")


def test_i18n_all_locales_are_brand_free():
    """14 个语言文件的键值剥离 URL 后不得出现旧品牌词。"""
    locale_files = sorted(I18N_DIR.glob("*.json"))
    assert len(locale_files) == 14

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                _assert_brand_free(str(key), f"{where} key")
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str):
            _assert_brand_free(node, where)

    for locale_file in locale_files:
        translations = json.loads(locale_file.read_text(encoding="utf-8"))
        walk(translations, locale_file.stem)


# ---- 旧 schema 兼容：与 test_webui_settings_transfer 相同的 AST 隔离加载 ----

_REBRAND_CONSTANTS = {
    "MAX_SETTINGS_TRANSFER_BYTES",
    "SETTINGS_PRESET_SCHEMA",
    "SETTINGS_PRESET_VERSION",
    "KEY_BACKUP_SCHEMA",
    "KEY_BACKUP_VERSION",
    "PROJECT_PARAMS_SCHEMA",
    "PROJECT_PARAMS_VERSION",
    "LEGACY_SETTINGS_PRESET_SCHEMA",
    "LEGACY_KEY_BACKUP_SCHEMA",
    "LEGACY_PROJECT_PARAMS_SCHEMA",
    "_LEGACY_SCHEMA_ALIASES",
}
_REBRAND_HELPERS = {"_load_transfer_payload", "_read_project_params"}


def _load_rebrand_helpers():
    tree = ast.parse(WEBUI_MAIN.read_text(encoding="utf-8"))
    selected_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in _REBRAND_CONSTANTS
            for target in node.targets
        ):
            selected_nodes.append(node)
        elif (
            isinstance(node, ast.FunctionDef) and node.name in _REBRAND_HELPERS
        ):
            selected_nodes.append(node)
    namespace = {
        "json": json,
        "os": os,
        "VideoParams": VideoParams,
        "logger": logger,
        # 项目快照路径由测试指定，避免依赖真实 storage 目录。
        "_project_params_path": lambda task_id: namespace["_params_path"],
        "_params_path": None,
    }
    module = ast.fix_missing_locations(ast.Module(body=selected_nodes, type_ignores=[]))
    exec(compile(module, str(WEBUI_MAIN), "exec"), namespace)
    return namespace


NAMESPACE = _load_rebrand_helpers()


@pytest.mark.parametrize(
    "schema_key,legacy_key",
    [
        ("SETTINGS_PRESET_SCHEMA", "LEGACY_SETTINGS_PRESET_SCHEMA"),
        ("KEY_BACKUP_SCHEMA", "LEGACY_KEY_BACKUP_SCHEMA"),
    ],
)
def test_legacy_export_schemas_still_importable(schema_key, legacy_key):
    """新旧 schema 的导出文件都能通过导入校验，未知 schema 仍被拒绝。"""
    load = NAMESPACE["_load_transfer_payload"]
    schema = NAMESPACE[schema_key]
    legacy = NAMESPACE[legacy_key]
    assert schema.startswith("changofilm.")
    assert legacy.startswith("moneyprinterturbo.")
    for accepted in (schema, legacy):
        raw = json.dumps({"schema": accepted, "version": 1}).encode("utf-8")
        payload = load(raw, schema, 1)
        assert payload["schema"] == accepted
    rejected = json.dumps({"schema": "other.tool", "version": 1}).encode("utf-8")
    with pytest.raises(ValueError):
        load(rejected, schema, 1)


@pytest.mark.parametrize(
    "schema_key", ["PROJECT_PARAMS_SCHEMA", "LEGACY_PROJECT_PARAMS_SCHEMA"]
)
def test_legacy_project_params_still_readable(tmp_path, schema_key):
    """旧品牌项目快照（params.json）无需转换即可读取。"""
    params = VideoParams(video_subject="品牌升级").model_dump(mode="json")
    params_file = tmp_path / "params.json"
    params_file.write_text(
        json.dumps(
            {
                "schema": NAMESPACE[schema_key],
                "version": NAMESPACE["PROJECT_PARAMS_VERSION"],
                "params": params,
            }
        ),
        encoding="utf-8",
    )
    NAMESPACE["_params_path"] = params_file
    loaded = NAMESPACE["_read_project_params"]("task-legacy")
    assert loaded is not None
    assert loaded["video_subject"] == "品牌升级"


def test_unknown_project_params_schema_is_rejected(tmp_path):
    params_file = tmp_path / "params.json"
    params_file.write_text(
        json.dumps({"schema": "other.tool", "version": 1, "params": {}}),
        encoding="utf-8",
    )
    NAMESPACE["_params_path"] = params_file
    assert NAMESPACE["_read_project_params"]("task-unknown") is None


def test_config_defaults_and_release_feed_are_changofilm():
    assert config.project_name == "ChangoFilm"
    assert "harry0703" not in config.project_description
    assert "MoneyPrinter" not in config.project_description
    assert version_checker.LATEST_RELEASE_API_URL == (
        "https://api.github.com/repos/wyg5208/changofilm/releases/latest"
    )
    assert version_checker.LATEST_RELEASE_PAGE_URL == (
        "https://github.com/wyg5208/changofilm/releases/latest"
    )


def test_pyproject_metadata_is_changofilm():
    project = tomllib.loads(
        (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    assert project["name"] == "changofilm"
    assert "ChangoFilm" in project["description"]
    assert "harry0703" not in project["description"]
    assert project["scripts"]["changofilm"] == "app.launcher:main"
    assert project["urls"]["Homepage"] == "https://github.com/wyg5208/changofilm"
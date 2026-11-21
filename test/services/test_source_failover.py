# -*- coding: utf-8 -*-
"""备用源链解析契约：三槽链、就绪口径与切换日志。

任务预检的失败转移（app/services/source_failover.py）遵循三条契约：
1. 候选链 = [主源, 备用1, 备用2]，备用槽只在主源所属能力分组内生效，
   local 永远不作为备用目标；切换只改本次任务参数，不写回配置。
2. 就绪检查与 WebUI"已配置"徽标同口径：只验证本地配置齐全，不探测连通性；
   未知来源按可用处理，交给任务自身的逐源预检。
3. 主源不可用时自动切换并写 WARNING 日志；整链不可用返回空结果并写
   ERROR 日志，由调用方把整链缺失项列入失败消息。
"""
import io
import sys
from pathlib import Path

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import source_failover  # noqa: E402


# is_enabled 系列优先读取配置映射，其次回落环境变量；清空相关环境变量
# 保证"未配置"分支不受开发机环境影响。
_FAILOVER_ENV_KEYS = (
    "METASO_MINIMAX_API_KEY",
    "OFOX_API_KEY",
    "INFISTAR_VIDEO_API_KEY",
    "JALAPENO_VIDEO_API_KEY",
    "MUAPI_API_KEY",
    "VOLCENGINE_ARK_API_KEY",
    "OPENAI_API_KEY",
)


@pytest.fixture
def clean_env(monkeypatch):
    for name in _FAILOVER_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


def _capture_warnings():
    sink = io.StringIO()
    handler_id = logger.add(sink, level="WARNING")
    return sink, handler_id


def _section_getter(sections):
    def getter(name):
        return dict(sections.get(name, {}) or {})

    return getter


# ---------------------------------------------------------------------------
# 素材来源链
# ---------------------------------------------------------------------------


def test_video_primary_available_keeps_primary(clean_env):
    config_map = {"video_source": "pexels", "pexels_api_keys": "key-1, key-2"}
    result = source_failover.resolve_video_source(config_map)
    assert result.source == "pexels"
    assert result.primary == "pexels"
    assert result.switched is False
    assert result.attempts == (("pexels", True),)


def test_video_unavailable_primary_switches_to_backup_and_logs(clean_env):
    config_map = {
        "video_source": "pexels",
        "video_source_backups_stock_video_1": "ofox",
        "ofox_api_key": "ofox-key",
    }
    sink, handler_id = _capture_warnings()
    try:
        result = source_failover.resolve_video_source(config_map)
    finally:
        logger.remove(handler_id)
    assert result.source == "ofox"
    assert result.switched is True
    assert result.attempts == (("pexels", False), ("ofox", True))
    assert "switched to backup source 'ofox'" in sink.getvalue()
    assert "'pexels'" in sink.getvalue()


def test_video_chain_tries_backup_two_after_unavailable_backup_one(clean_env):
    config_map = {
        "video_source": "pexels",
        "video_source_backups_stock_video_1": "pixabay",
        "video_source_backups_stock_video_2": "coverr",
        "coverr_api_keys": "coverr-key",
    }
    result = source_failover.resolve_video_source(config_map)
    assert result.source == "coverr"
    assert result.attempts == (
        ("pexels", False),
        ("pixabay", False),
        ("coverr", True),
    )


def test_video_backup_duplicate_of_primary_is_skipped(clean_env):
    config_map = {
        "video_source": "ofox",
        "ofox_api_key": "key",
        "video_source_backups_ai_video_1": "ofox",
    }
    result = source_failover.resolve_video_source(config_map)
    assert result.source == "ofox"
    assert result.attempts == (("ofox", True),)


def test_video_backups_do_not_cross_capability(clean_env):
    """库存视频主源不得切到 AI 视频备用槽；跨能力键不进链。"""
    config_map = {
        "video_source": "pexels",
        "video_source_backups_ai_video_1": "ofox",
        "ofox_api_key": "key",
    }
    result = source_failover.resolve_video_source(config_map)
    assert result.source == ""
    assert result.attempts == (("pexels", False),)


def test_video_local_never_enters_fallback_chain(clean_env):
    config_map = {
        "video_source": "pexels",
        "video_source_backups_stock_video_1": "local",
    }
    result = source_failover.resolve_video_source(config_map)
    assert result.source == ""
    assert result.attempts == (("pexels", False),)


def test_video_empty_chain_returns_empty_source(clean_env):
    config_map = {"video_source": "metaso_minimax"}
    sink, handler_id = _capture_warnings()
    try:
        result = source_failover.resolve_video_source(config_map)
    finally:
        logger.remove(handler_id)
    assert result.source == ""
    assert result.switched is False
    assert result.attempts == (("metaso_minimax", False),)
    assert "no usable video source" in sink.getvalue()


def test_video_unknown_source_treated_available(clean_env):
    """未知来源按可用处理，交给任务逐源预检给出明确错误。"""
    config_map = {"video_source": "future_source_xyz"}
    result = source_failover.resolve_video_source(config_map)
    assert result.source == "future_source_xyz"


def test_video_codex_image_switches_to_openai_image(clean_env):
    config_map = {
        "video_source": "codex_image",
        "video_source_backups_ai_image_1": "openai_image",
        "openai_image_base_url": "https://gw.example/v1",
        "openai_image_model": "gpt-image-1",
    }
    result = source_failover.resolve_video_source(config_map, codex_connected=False)
    assert result.source == "openai_image"
    assert result.switched is True
    connected = source_failover.resolve_video_source(config_map, codex_connected=True)
    assert connected.source == "codex_image"
    assert connected.switched is False


@pytest.mark.parametrize(
    "source_id, config_map, expected",
    [
        ("pexels", {"pexels_api_keys": "k1"}, True),
        ("pexels", {"pexels_api_keys": " , "}, False),
        ("pexels", {"pexels_api_keys": ["k1", ""]}, True),
        ("pexels", {"pexels_api_keys": []}, False),
        ("pexels", {}, False),
        ("wavespeed", {"wavespeed_api_keys": "ws"}, True),
        ("wavespeed", {}, False),
        ("volcengine_seedance", {"volcengine_seedance_api_key": "ark"}, True),
        ("volcengine_seedance", {"volcengine_api_key": "shared"}, True),
        ("volcengine_seedance", {}, False),
    ],
)
def test_video_source_available_key_semantics(monkeypatch, source_id, config_map, expected):
    monkeypatch.delenv("VOLCENGINE_ARK_API_KEY", raising=False)
    assert (
        source_failover.video_source_available(source_id, config_map) is expected
    )


def test_video_source_available_local_and_unknown_always_ready():
    assert source_failover.video_source_available("local", {}) is True
    assert source_failover.video_source_available("not_a_source", {}) is True


def test_video_source_available_metaso_follows_settings(clean_env):
    assert source_failover.video_source_available("metaso_minimax", {}) is False
    assert (
        source_failover.video_source_available(
            "metaso_minimax", {"metaso_minimax_api_key": "k"}
        )
        is True
    )


# ---------------------------------------------------------------------------
# 配音链
# ---------------------------------------------------------------------------


def test_tts_free_primary_needs_no_switch():
    ui_config = {"tts_server": "azure-tts-v1"}
    result = source_failover.resolve_tts_server(ui_config)
    assert result.server == "azure-tts-v1"
    assert result.primary_server == "azure-tts-v1"
    assert result.switched is False
    assert result.voice_name == ""
    assert result.attempts == (("azure-tts-v1", True),)


def test_tts_switches_to_configured_backup_with_voice(monkeypatch):
    monkeypatch.setattr(
        source_failover, "_pick_fallback_voice", lambda server, language: "VOICE-A"
    )
    ui_config = {
        "tts_server": "azure-tts-v2",
        "tts_server_backup1": "siliconflow",
    }
    sections = {"siliconflow": {"api_key": "sk"}, "azure": {"speech_key": ""}}
    sink, handler_id = _capture_warnings()
    try:
        result = source_failover.resolve_tts_server(
            ui_config, language="zh", section_getter=_section_getter(sections)
        )
    finally:
        logger.remove(handler_id)
    assert result.server == "siliconflow"
    assert result.switched is True
    assert result.voice_name == "VOICE-A"
    assert result.attempts == (("azure-tts-v2", False), ("siliconflow", True))
    assert "switched to backup 'siliconflow'" in sink.getvalue()


def test_tts_online_voice_backup_is_skipped(monkeypatch):
    """在线拉取音色的服务（如 MiniMax TTS）不参与自动切换，顺延到下一家。"""
    monkeypatch.setattr(
        source_failover, "_pick_fallback_voice", lambda server, language: "VOICE-B"
    )
    ui_config = {
        "tts_server": "azure-tts-v2",
        "tts_server_backup1": "minimax-tts",
        "tts_server_backup2": "azure-tts-v1",
    }
    sections = {"minimax_tts": {"api_key": "mk"}}
    result = source_failover.resolve_tts_server(
        ui_config, language="zh", section_getter=_section_getter(sections)
    )
    assert result.server == "azure-tts-v1"
    assert result.attempts == (
        ("azure-tts-v2", False),
        ("minimax-tts", False),
        ("azure-tts-v1", True),
    )


def test_tts_voice_pick_failure_falls_through(monkeypatch):
    """挑不到可用音色等同不可用，继续尝试下一家。"""
    monkeypatch.setattr(
        source_failover,
        "_pick_fallback_voice",
        lambda server, language: "" if server == "siliconflow" else "VOICE-B",
    )
    ui_config = {
        "tts_server": "azure-tts-v2",
        "tts_server_backup1": "siliconflow",
        "tts_server_backup2": "azure-tts-v1",
    }
    sections = {"siliconflow": {"api_key": "sk"}}
    result = source_failover.resolve_tts_server(
        ui_config, language="zh", section_getter=_section_getter(sections)
    )
    assert result.server == "azure-tts-v1"
    assert result.switched is True
    assert result.voice_name == "VOICE-B"
    # attempts 记录的是音色挑选前的就绪态；音色挑选失败在链上表现为顺延。
    assert result.attempts == (
        ("azure-tts-v2", False),
        ("siliconflow", True),
        ("azure-tts-v1", True),
    )


def test_tts_empty_chain_returns_empty_server():
    ui_config = {"tts_server": "azure-tts-v2", "tts_server_backup1": "fish_audio"}
    result = source_failover.resolve_tts_server(ui_config)
    assert result.server == ""
    assert result.attempts == (("azure-tts-v2", False), ("fish_audio", False))


def test_tts_backup_duplicate_of_primary_is_skipped():
    ui_config = {"tts_server": "azure-tts-v1", "tts_server_backup1": "azure-tts-v1"}
    result = source_failover.resolve_tts_server(ui_config)
    assert result.attempts == (("azure-tts-v1", True),)


@pytest.mark.parametrize(
    "server_id, sections, expected",
    [
        ("azure-tts-v1", {}, True),
        ("chatterbox", {}, True),
        ("kokoro", {}, True),
        ("not_a_server", {"any": {"x": "y"}}, False),
        ("azure-tts-v2", {"azure": {"speech_key": ""}}, False),
        ("azure-tts-v2", {"azure": {"speech_key": "sk"}}, True),
        ("elevenlabs", {"elevenlabs": {"api_key": "el"}}, True),
        ("voxcpm", {"voxcpm": {"api_key": ""}}, False),
        ("voxcpm", {"voxcpm": {"api_key": "v"}}, True),
        # MiniMax TTS 多候选凭证：独立 Key 或复用 LLM Key 任一非空即可。
        ("minimax-tts", {}, False),
        ("minimax-tts", {"minimax_tts": {"api_key": "a"}}, True),
        ("minimax-tts", {"app": {"minimax_api_key": "b"}}, True),
        ("minimax-tts", {"minimax_tts": {"api_key": " "}}, False),
    ],
)
def test_tts_server_available_semantics(server_id, sections, expected):
    assert (
        source_failover.tts_server_available(
            server_id, section_getter=_section_getter(sections)
        )
        is expected
    )


# ---------------------------------------------------------------------------
# LLM 备用链
# ---------------------------------------------------------------------------


def test_llm_chain_order_and_normalization():
    config_map = {
        "llm_provider": " Moonshot ",
        "llm_provider_backup1": "DEEPSEEK",
        "llm_provider_backup2": "moonshot",
    }
    result = source_failover.resolve_llm_chain(config_map)
    assert result.chain == ("moonshot", "deepseek")
    assert result.primary == "moonshot"


def test_llm_chain_without_backups_is_single_element():
    result = source_failover.resolve_llm_chain({"llm_provider": "qwen"})
    assert result.chain == ("qwen",)


def test_llm_chain_blank_primary_keeps_empty_head():
    result = source_failover.resolve_llm_chain({"llm_provider": ""})
    assert result.chain == ("",)
    assert result.primary == ""

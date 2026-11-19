"""国内平台文案规格：SOCIAL_PLATFORMS 纯数据表扩展的行为锁定。"""
import json

import pytest

from app.services import llm


CN_PLATFORMS = ["douyin", "tencent", "xiaohongshu", "bilibili", "kuaishou", "weibo", "baijiahao"]


@pytest.mark.parametrize("platform", CN_PLATFORMS)
def test_cn_platform_prompt_uses_its_own_limits(platform):
    spec = llm.SOCIAL_PLATFORMS[platform]
    prompt = llm.build_social_metadata_prompt("美食主题", "脚本", platform=platform)
    assert llm.SOCIAL_PLATFORM_LABELS[platform] in prompt
    assert str(spec["caption_max"]) in prompt
    assert str(spec["hashtag_count"]) in prompt


@pytest.mark.parametrize("platform", CN_PLATFORMS)
def test_cn_platform_metadata_is_clamped_to_spec(platform):
    spec = llm.SOCIAL_PLATFORMS[platform]
    response = json.dumps(
        {
            "title": "长" * (spec["title_max"] + 50),
            "caption": "文" * (spec["caption_max"] + 500),
            "hashtags": [f"#美食{i}" for i in range(spec["hashtag_count"] + 5)],
        },
        ensure_ascii=False,
    )
    metadata = llm._parse_social_metadata(response, platform)
    assert len(metadata["title"]) <= spec["title_max"]
    assert len(metadata["caption"]) <= spec["caption_max"]
    assert len(metadata["hashtags"]) == spec["hashtag_count"]


def test_tencent_prompt_enforces_title_minimum():
    prompt = llm.build_social_metadata_prompt("美食主题", platform="tencent")
    assert "between 6 and 16 characters" in prompt


def test_other_platform_prompts_keep_original_title_rule():
    prompt = llm.build_social_metadata_prompt("美食主题", platform="douyin")
    assert "at most 30 characters" in prompt
    assert "between" not in prompt


def test_unknown_platform_still_falls_back_to_tiktok():
    assert llm._resolve_social_platform("xigua") == llm.DEFAULT_SOCIAL_PLATFORM
    assert llm._resolve_social_platform(None) == llm.DEFAULT_SOCIAL_PLATFORM


def test_cn_fallback_metadata_uses_subject():
    metadata = llm._fallback_social_metadata("家常红烧肉做法", "第一步焯水。第二步炒糖色。", "douyin")
    assert metadata["title"] == "家常红烧肉做法"
    assert len(metadata["title"]) <= llm.SOCIAL_PLATFORMS["douyin"]["title_max"]
    assert metadata["hashtags"]
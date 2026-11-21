# -*- coding: utf-8 -*-
"""服务能力目录契约：平台分组、能力映射与注册表交叉一致性。

服务商体系 v1.8.0 把"平台是什么、有哪些真实接线能力"集中到
app/models/service_catalog.py。这里锁定三条不变量：
1. 平台分组顺序即产品口径：国内厂商 → 本地与免费引擎 → 国际主流 →
   聚合/推广平台（聚合平台只允许出现在注册表尾部，不删除任何服务商）。
2. 能力只声明真实已接线的能力，未接线能力（图片识别/图片编辑/视频编辑）
   不进入 capabilities。
3. 目录与 LLM Provider 注册表、配音服务目录严格互覆盖：新增 Provider
   漏登目录时在导入期即失败（duplicate 检查）之外的遗漏由此处拦截。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import llm_provider  # noqa: E402
from app.models import service_catalog as catalog  # noqa: E402
from app.services.source_failover import TTS_SERVER_REQUIREMENTS  # noqa: E402

KNOWN_CAPABILITIES = {
    catalog.CAP_TEXT,
    catalog.CAP_IMAGE_GEN,
    catalog.CAP_T2V,
    catalog.CAP_I2V,
    catalog.CAP_TTS,
    catalog.CAP_MUSIC,
    catalog.CAP_STOCK_VIDEO,
    catalog.CAP_STOCK_IMAGE,
}

# 明确未接线的能力绝不允许出现在任何平台上（矩阵不虚标）。
UNWIRED_CAPABILITIES = {"image_understanding", "image_edit", "video_edit"}


def _catalog_llm_ids():
    return [
        service_id
        for platform in catalog.SERVICE_PLATFORMS
        for service_id in platform.llm_ids
    ]


def test_platform_groups_follow_product_order():
    """分组顺序锁定：国内 → 本地 → 国际 → 聚合，目录条目单调不回退。"""
    assert catalog.PLATFORM_GROUP_ORDER == (
        catalog.GROUP_DOMESTIC,
        catalog.GROUP_LOCAL,
        catalog.GROUP_INTERNATIONAL,
        catalog.GROUP_AGGREGATOR,
    )
    group_index = {g: i for i, g in enumerate(catalog.PLATFORM_GROUP_ORDER)}
    indices = [group_index[p.group] for p in catalog.SERVICE_PLATFORMS]
    assert indices == sorted(indices), "platform entries must be grouped in order"
    # 每个分组都至少有一个平台，防止分组被清空后矩阵失真。
    seen = {p.group for p in catalog.SERVICE_PLATFORMS}
    assert seen == set(catalog.PLATFORM_GROUP_ORDER)


def test_platform_ids_and_service_ids_are_unique():
    """平台 id 与 (kind, service_id) 不允许重复；导入期已自检，这里复核集合。"""
    platform_ids = [p.platform_id for p in catalog.SERVICE_PLATFORMS]
    assert len(platform_ids) == len(set(platform_ids))
    all_service_keys = []
    for platform in catalog.SERVICE_PLATFORMS:
        for kind in ("llm", "material", "tts", "music"):
            for service_id in getattr(platform, f"{kind}_ids"):
                all_service_keys.append((kind, service_id))
    assert len(all_service_keys) == len(set(all_service_keys))


def test_capabilities_are_real_wired_capabilities_only():
    """能力矩阵只允许出现已接线能力，且每个平台至少声明一个能力。"""
    for platform in catalog.SERVICE_PLATFORMS:
        assert platform.capabilities, f"{platform.platform_id} has no capabilities"
        unknown = set(platform.capabilities) - KNOWN_CAPABILITIES
        assert not unknown, f"{platform.platform_id} declares unknown {unknown}"
        unwired = set(platform.capabilities) & UNWIRED_CAPABILITIES
        assert not unwired, f"{platform.platform_id} overstates {unwired}"
        # 能力 i18n key 必须覆盖所有已声明能力。
        for capability in platform.capabilities:
            assert capability in catalog.CAPABILITY_LABEL_KEYS
        assert platform.group in catalog.GROUP_LABEL_KEYS


def test_capabilities_for_service_by_namespace():
    """(kind, service_id) 决定能力集合；LLM/TTS/音乐按命名空间取子集。"""
    assert catalog.capabilities_for_service("volcengine", "llm") == (
        catalog.CAP_TEXT,
    )
    assert catalog.capabilities_for_service("volcengine_seedance", "material") == (
        catalog.CAP_T2V,
        catalog.CAP_I2V,
    )
    assert catalog.capabilities_for_service("pexels", "material") == (
        catalog.CAP_STOCK_VIDEO,
        catalog.CAP_STOCK_IMAGE,
    )
    assert catalog.capabilities_for_service("coverr", "material") == (
        catalog.CAP_STOCK_VIDEO,
    )
    assert catalog.capabilities_for_service("openai_image", "material") == (
        catalog.CAP_IMAGE_GEN,
    )
    assert catalog.capabilities_for_service("elevenlabs_music", "music") == (
        catalog.CAP_MUSIC,
    )
    assert catalog.capabilities_for_service("azure-tts-v1", "tts") == (
        catalog.CAP_TTS,
    )
    assert catalog.capabilities_for_service("nope", "material") == ()


def test_platform_for_service_namespaces_and_local():
    """同名聚合服务按命名空间区分；local 归属本地关键帧引擎平台。"""
    assert catalog.platform_for_service("infistar", "llm").platform_id == "infistar"
    assert (
        catalog.platform_for_service("infistar", "material").platform_id == "infistar"
    )
    assert catalog.platform_for_service("local", "material").platform_id == "comfyui"
    assert catalog.platform_for_service("kimi_code", "llm").platform_id == "kimi"
    assert catalog.platform_for_service("nope", "llm") is None


def test_material_capability_groups_partition_sources():
    """能力分组互斥、全覆盖素材来源，local 不参与任何备用能力分组。"""
    all_sources = [
        source
        for sources in catalog.MATERIAL_CAPABILITY_GROUPS.values()
        for source in sources
    ]
    assert len(all_sources) == len(set(all_sources)), "source in multiple groups"
    assert "local" not in all_sources
    for source in all_sources:
        group = catalog.material_capability_of_source(source)
        assert group in catalog.MATERIAL_CAPABILITY_GROUPS
        assert source in catalog.MATERIAL_CAPABILITY_GROUPS[group]
    assert catalog.material_capability_of_source("local") is None
    assert catalog.material_capability_of_source("nope") is None


def test_catalog_covers_llm_provider_registry_exactly():
    """目录 llm_ids 与 LLM Provider 注册表互覆盖且各只出现一次。"""
    registry_ids = [p.provider_id for p in llm_provider.LLM_PROVIDER_REGISTRY]
    catalog_ids = _catalog_llm_ids()
    assert sorted(registry_ids) == sorted(catalog_ids)
    assert len(catalog_ids) == len(set(catalog_ids)), "llm id mapped twice"


def test_tts_catalog_matches_failover_requirements():
    """配音目录与备用链就绪检查表互覆盖。"""
    tts_ids = {
        service_id
        for platform in catalog.SERVICE_PLATFORMS
        for service_id in platform.tts_ids
    }
    assert tts_ids == set(TTS_SERVER_REQUIREMENTS)


def test_llm_provider_registry_orders_aggregators_to_tail():
    """注册表顺序：国内 → 本地/订阅 → 国际 → 聚合（尾部），默认 Provider 不变。"""
    group_index = {g: i for i, g in enumerate(catalog.PLATFORM_GROUP_ORDER)}
    order = [p.provider_id for p in llm_provider.LLM_PROVIDER_REGISTRY]
    groups = []
    for provider_id in order:
        platform = catalog.platform_for_service(provider_id, "llm")
        assert platform is not None, f"{provider_id} missing from catalog"
        groups.append(group_index[platform.group])
    assert groups == sorted(groups), "aggregators must stay at the registry tail"
    assert llm_provider.DEFAULT_LLM_PROVIDER_ID == "moonshot"
    assert order[0] == "moonshot"
    # 分组锚点：聚合平台整体位于国际主流之后。
    first_aggregator = next(
        i
        for i, provider_id in enumerate(order)
        if catalog.platform_for_service(provider_id, "llm").group
        == catalog.GROUP_AGGREGATOR
    )
    last_international = max(
        i
        for i, provider_id in enumerate(order)
        if catalog.platform_for_service(provider_id, "llm").group
        == catalog.GROUP_INTERNATIONAL
    )
    assert last_international < first_aggregator


@pytest.mark.parametrize(
    "platform_id",
    ["metaso", "volcengine", "minimax", "kimi", "deepseek", "openai", "anthropic",
     "google", "pexels", "pixabay", "coverr", "elevenlabs", "sonilo", "ollama",
     "comfyui", "infistar", "jalapeno", "ofox"],
)
def test_representative_platforms_keep_capabilities(platform_id):
    """代表性平台的能力映射不被无声改动（含国内/本地/国际/聚合代表）。"""
    platform = catalog.SERVICE_PLATFORMS_BY_ID[platform_id]
    for service_id in platform.llm_ids:
        assert catalog.CAP_TEXT in catalog.capabilities_for_service(service_id, "llm")
    for service_id in platform.material_ids:
        assert catalog.capabilities_for_service(service_id, "material")

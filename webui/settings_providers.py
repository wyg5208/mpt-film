"""Local configuration eligibility for the General settings shortcuts.

迁移方案 1.3：判定逻辑已下沉到 ``app/services/provider_readiness.py``，
Streamlit 与 API 共用同一实现；本模块保留原导入路径，行为不变。

These checks never authenticate, refresh tokens, inspect model catalogs or probe a
provider. Eligibility means configuration is present, not that a remote call works.
"""

# 兼容旧测试导入路径：部分套件 monkeypatch `webui.settings_providers.shutil.which`。
# shutil 是全局共享模块对象，补丁同样作用于下沉后的实现。
import shutil  # noqa: F401

from app.services.provider_readiness import (  # noqa: F401  (兼容旧导入路径)
    VIDEO_SOURCE_GROUPS,
    configured_llm_providers,
    configured_material_providers,
)

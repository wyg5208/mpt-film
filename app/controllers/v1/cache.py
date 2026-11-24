"""缓存管理 API（迁移方案 1.8）。

封装 ``app/services/cache_manager.py``：统计预览与按类型清理。目前只有
视频素材缓存一种，未来新增缓存类型时在 _KINDS 中登记即可。
"""

from dataclasses import asdict

from fastapi import Depends, Query, Request

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import cache_manager
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])


def _cleaner_for(kind: str):
    """请求期动态解析服务属性，便于测试打桩，也避免导入期绑定旧引用。"""
    if kind == "video":
        return cache_manager.clean_video_cache
    return None


@router.get("/cache/stats", summary="Video cache statistics")
def cache_stats(request: Request, max_age_days: int | None = Query(None, ge=0)):
    stats = cache_manager.get_video_cache_stats(max_age_days=max_age_days)
    body = asdict(stats)
    # 设置页缓存管理 TAB 与 Main.py 一致展示缓存目录路径。
    body["dir"] = cache_manager.video_cache_dir()
    return utils.get_response(200, body)


@router.delete("/cache/{kind}", summary="Clean a cache category")
def clean_cache(
    request: Request, kind: str, max_age_days: int | None = Query(None, ge=0)
):
    cleaner = _cleaner_for(kind)
    if cleaner is None:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=f"unknown cache kind: {kind}",
        )
    result = cleaner(max_age_days=max_age_days)
    return utils.get_response(200, asdict(result))

"""Application configuration - root APIRouter

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""

from fastapi import APIRouter

from app.controllers import ping
from app.controllers.v1 import (
    auth,
    catalogs,
    cache,
    llm,
    media,
    oauth,
    plans,
    publish,
    series,
    settings,
    uploads,
    video,
)

root_api_router = APIRouter()
root_api_router.include_router(ping.router)

# v1
# auth 提供短时令牌换发/刷新，其 login/refresh 必须早于其它受保护路由可达，
# 因此先注册；router 组本身不挂统一鉴权依赖（见 auth.py）。
root_api_router.include_router(auth.router)
root_api_router.include_router(video.router)
root_api_router.include_router(llm.router)
# media 为产物短时效签名 URL 签发面（<video src> 无法带自定义头），沿用统一鉴权依赖。
root_api_router.include_router(media.router)
# 迁移方案 Phase 0 补齐的 API 面：设置/OAuth/系列/发布/上传/目录/缓存。
root_api_router.include_router(settings.router)
root_api_router.include_router(oauth.router)
root_api_router.include_router(series.router)
root_api_router.include_router(publish.router)
root_api_router.include_router(uploads.router)
root_api_router.include_router(catalogs.router)
root_api_router.include_router(cache.router)
# 脚本方案草稿库（专业短剧主页面）+ 本地引擎就绪度探针。
root_api_router.include_router(plans.router)

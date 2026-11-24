"""媒体短时效签名 URL 签发（迁移方案 1.10 / 4.A）。

``<video src>`` 无法携带自定义鉴权头，故任务产物的播放/下载链接改走短时效 HMAC
签名查询串。本端点要求有效凭据（主密钥或 Bearer 令牌），批量为落盘产物签发
``?expires=<epoch>&sig=<hex>`` URL，签名对规范路径 + method 逐字绑定，过期或篡改
即由 ``verify_token`` 汇聚点拒绝，主密钥永不出现在 URL/浏览器。

签发校验顺序（对齐 4.A）：① 路径必须落在 ``utils.task_dir()`` 内（复用
``file_security.resolve_path_within_directory``）→ 否则 403；② 文件必须存在 →
否则 404。签名只对白名单前缀（``/tasks/``）生效，挪作他用一律被汇聚点拒绝。
"""

from typing import Annotated

from fastapi import Depends, Query, Request
from pydantic import BaseModel, Field

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import media_sign
from app.utils import file_security, utils

router = new_router(dependencies=[Depends(base.verify_token)])


class MediaSignRequest(BaseModel):
    paths: Annotated[
        list[str],
        Field(description="相对 task_dir 的产物路径，如 '{task_id}/final-1.mp4'"),
    ] = []


def _sign_one(request_id: str, raw_path: str, ttl: int) -> dict:
    """把单个产物路径校验在 task_dir 内且存在，再签发给定的 URL。

    越界抛 403、不存在抛 404，交由统一异常处理封装为信封。
    """

    if not isinstance(raw_path, str) or not raw_path:
        raise HttpException(
            task_id=request_id,
            status_code=403,
            message=f"{request_id}: invalid media path",
        )

    try:
        file_security.resolve_path_within_directory(
            utils.task_dir(), raw_path, require_file=True
        )
    except ValueError as exc:
        missing = "does not exist" in str(exc)
        raise HttpException(
            task_id=request_id,
            status_code=404 if missing else 403,
            message=f"{request_id}: {'file does not exist' if missing else 'path is outside the allowed directory'}",
        ) from exc

    url_path = "/tasks/" + raw_path.lstrip("/")
    sig, expires_at = media_sign.sign_url(url_path, ttl_seconds=ttl, method="GET")
    return {
        "path": raw_path,
        "url": f"{url_path}?expires={expires_at}&sig={sig}",
        "expires_at": expires_at,
    }


@router.post("/media/sign", summary="Sign short-lived media URLs for task artifacts")
def sign_media_batch(request: Request, body: MediaSignRequest):
    """批量为产物路径签发短时效 URL，避免每张卡片一次请求（对齐 4.A）。"""

    request_id = base.get_task_id(request)
    ttl = media_sign.DEFAULT_MEDIA_TTL_SECONDS
    items = [_sign_one(request_id, path, ttl) for path in (body.paths or [])]
    return utils.get_response(200, {"items": items})


@router.get("/media/sign", summary="Sign a single short-lived media URL (debug)")
def sign_media_single(
    request: Request,
    path: Annotated[str, Query(description="相对 task_dir 的产物路径")],
):
    """单条签发（调试用）。校验与批量一致。"""

    request_id = base.get_task_id(request)
    ttl = media_sign.DEFAULT_MEDIA_TTL_SECONDS
    item = _sign_one(request_id, path, ttl)
    return utils.get_response(200, {"item": item})

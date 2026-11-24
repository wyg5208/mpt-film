"""短时令牌鉴权路由（迁移方案 4.B / Phase 0.3）。

Mode B 下主密钥只在 ``/auth/login`` 请求中出现一次，成功后浏览器持有一枚
15 分钟的无状态 Bearer 令牌，之后的 API/媒体请求都带令牌而非主密钥。

路由分两类凭据要求：

- ``login`` / ``refresh``：不能让统一鉴权依赖拦截（否则拿不到令牌就无法登录），
  因此在 plain router 上定义，自行校验凭据。
- ``session`` / ``logout``：复用 ``base.verify_token`` 依赖，要求有效凭据。
"""

import secrets

from fastapi import Request
from pydantic import BaseModel

from app.config import config
from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import token as token_service
from app.utils import utils


class LoginRequest(BaseModel):
    api_key: str = ""

# login/refresh 必须对未认证客户端开放，故路由组本身不挂鉴权依赖；
# session/logout 通过路由级 dependencies 单独要求有效凭据。
router = new_router()


def _auth_disabled_response(request: Request) -> HttpException:
    return HttpException(
        task_id=base.get_task_id(request),
        status_code=400,
        message="authentication is disabled; no token is issued",
    )


def _issue_login_payload(subject: str = "user") -> dict:
    """签发令牌并组装登录响应体。

    响应绝不含主密钥或 session_secret；只回令牌、类型、生命周期与 scope。
    """

    access_token, expires_in, expires_at = token_service.issue_token(subject=subject)
    return {
        "access_token": access_token,
        "token_type": token_service.TOKEN_TYPE,
        "expires_in": expires_in,
        "expires_at": expires_at,
        "scope": ["*"],
    }


@router.post("/auth/login", summary="Exchange the master key for a short-lived token")
def login(request: Request, body: LoginRequest):
    configured_key = config.app.get("api_key", "")
    # 免认证本地模式没有可交换的密钥，也没有可派生的签名密钥，明确拒绝。
    if configured_key in (None, ""):
        raise _auth_disabled_response(request)
    if not isinstance(configured_key, str):
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=500,
            message="API authentication is misconfigured",
        )

    provided = body.api_key if body is not None else ""
    if not isinstance(provided, str) or not secrets.compare_digest(
        provided.encode("utf-8"), configured_key.encode("utf-8")
    ):
        # 与 verify_token 的 API Key 失败语义一致，避免枚举登录尝试。
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=401,
            message="invalid API key",
            data={"code": "invalid_api_key"},
        )

    return utils.get_response(200, _issue_login_payload())


@router.post("/auth/refresh", summary="Refresh a still-valid short-lived token")
def refresh(request: Request):
    configured_key = config.app.get("api_key", "")
    if configured_key in (None, ""):
        raise _auth_disabled_response(request)

    # 复用同一校验逻辑：presented bearer 必须仍有效（未过期、签名正确）才能续期。
    # 校验失败会抛出带 data.code 的 HttpException，透传给前端区分重新登录/刷新。
    payload = base.verify_token(request)
    subject = payload.get("sub", "user") if isinstance(payload, dict) else "user"
    return utils.get_response(200, _issue_login_payload(subject=subject))


@router.get("/auth/session", summary="Inspect the current session / auth requirement")
def session(request: Request):
    """探测当前凭据与鉴权要求（迁移方案 4.B / 4.2）。

    与需要凭据的其它路由不同，本端点必须在**无凭据**下可达，前端才能据此
    决定“直接进应用”还是“显示登录页”。语义：

    - 未配置 ``api_key``（本地免认证）→ ``200 {valid:true, auth_required:false}``；
    - 配置了 ``api_key`` 且凭据有效 → ``200 {valid:true, auth_required:true, expires_at, scope}``；
    - 配置了 ``api_key`` 但无/无效凭据 → 由 ``verify_token`` 抛 401，前端回登录页。

    响应绝不含主密钥原文，只回令牌生命周期内的 ``expires_at`` 与 ``scope``。
    """

    configured_key = config.app.get("api_key", "")
    if configured_key in (None, ""):
        return utils.get_response(200, {"valid": True, "auth_required": False})

    # 已启用鉴权：交由汇聚点校验凭据（缺失/无效会抛 401），有效则透传会话信息。
    payload = base.verify_token(request)
    expires_at = payload.get("exp") if isinstance(payload, dict) else None
    scope = payload.get("scope", ["*"]) if isinstance(payload, dict) else ["*"]
    return utils.get_response(
        200,
        {
            "valid": True,
            "auth_required": True,
            "expires_at": expires_at,
            "scope": scope,
        },
    )


@router.post("/auth/logout", summary="Signal logout (stateless tokens are discarded client-side)")
def logout(request: Request):
    # 登出需要有效凭据（与 session 一致）；无状态令牌无法在服务端撤销，
    # 这里只回 200 确认，实际丢弃令牌由客户端完成。
    base.verify_token(request)
    return utils.get_response(200, {"logged_out": True})


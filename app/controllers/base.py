import secrets
from typing import Annotated
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Header, Request

from app.config import config
from app.models.exception import HttpException
from app.services import media_sign
from app.services import token as token_service

MAX_TASK_ID_LENGTH = 128


def normalize_task_id(value: object) -> str:
    """Return a log-safe request ID, replacing invalid client input with a UUID."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_TASK_ID_LENGTH
        or not value.isprintable()
    ):
        return str(uuid4())
    return value


def get_task_id(request: Request) -> str:
    return normalize_task_id(request.headers.get("x-task-id"))


def get_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    return api_key


def get_api_key_values(request: Request) -> list[str]:
    """返回请求中全部 API Key Header，保留重复值用于安全校验。"""

    # Starlette Headers 提供 getlist()，可以区分代理或客户端发送的重复 Header。
    # 单元测试中的轻量 Request 替身只使用普通 dict，因此保留兼容回退。
    get_list = getattr(request.headers, "getlist", None)
    if callable(get_list):
        return [value for value in get_list("x-api-key") if isinstance(value, str)]

    api_key = get_api_key(request)
    return [api_key] if isinstance(api_key, str) else []


def get_authorization_values(request: Request) -> list[str]:
    """返回请求中全部 Authorization Header，保留重复值用于安全校验。

    与 ``get_api_key_values`` 同样处理重复 Header：代理或客户端可能发送多个
    Authorization，其取值顺序不确定，必须拒绝而不是隐式采用某一个。
    """

    get_list = getattr(request.headers, "getlist", None)
    if callable(get_list):
        return [
            value for value in get_list("authorization") if isinstance(value, str)
        ]

    authorization = request.headers.get("authorization")
    return [authorization] if isinstance(authorization, str) else []


def _request_path(request: Request) -> str:
    """安全取请求路径，兼容轻量 Request 替身（url 可能是字符串或缺失）。"""

    url = getattr(request, "url", None)
    path = getattr(url, "path", None)
    if isinstance(path, str):
        return path
    if isinstance(url, str):
        return urlsplit(url).path
    return ""


def _signature_params(request: Request) -> tuple[str | None, str | None]:
    """取签名查询参数 sig/expires；轻量替身无 query_params 时视为未携带。"""

    query_params = getattr(request, "query_params", None)
    if query_params is None:
        return None, None
    return query_params.get("sig"), query_params.get("expires")


def verify_token(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
):
    """按配置决定是否校验凭据，支持 ``x-api-key`` 与短时 Bearer 令牌。

    空 Key 保留现有的本地免认证模式；管理员显式配置非空 Key 后，API 路由和
    任务产物下载都要求凭据。客户端可用两种凭据：

    - ``x-api-key``：CLI/curl/n8n/服务端 SDK 的既有方式，行为与之前完全一致；
    - ``Authorization: Bearer``：迁移方案 4.B 的短时令牌，登录换发、浏览器持有。

    两者同时出现视为歧义凭据，一律拒绝，避免隐式择一产生认证绕过。Bearer 校验
    通过时返回令牌 payload（供会话端点读取 scope/exp），其余成功路径返回 None，
    与既有以依赖形式忽略返回值的调用方保持兼容。
    """

    configured_key = config.app.get("api_key", "")
    # 免认证短路必须最先执行，保证 test_empty_key_preserves_existing_open_access
    # 与本地升级体验不因新增凭据分支而改变。
    if configured_key in (None, ""):
        return None

    # 配置项必须是字符串。这里拒绝列表、数字等错误类型，避免字符串隐式
    # 转换产生难以发现的认证行为；错误信息也不包含实际 Key。
    if not isinstance(configured_key, str):
        raise HttpException(
            task_id=get_task_id(request),
            status_code=500,
            message="API authentication is misconfigured",
        )

    # 媒体短签名通道（迁移方案 4.A）：仅对白名单前缀路径且携带 sig 参数时生效。
    # 成功放行，篡改/过期按 4.D 拒绝；非白名单路径的 sig 参数一律忽略（继续走凭据
    # 校验），从而让静态 /tasks、/stream、/download 与令牌/x-api-key 三种方式共用本汇聚点。
    request_path = _request_path(request)
    if request_path.startswith(media_sign.MEDIA_SIGN_WHITELIST_PREFIXES):
        signature, expires = _signature_params(request)
        if signature is not None:
            method = getattr(request, "method", "GET") or "GET"
            try:
                media_sign.verify_signature(request_path, expires, signature, method)
            except media_sign.MediaSignError as exc:
                expired = exc.code == "media_signature_expired"
                message = (
                    "media signature expired" if expired else "invalid media signature"
                )
                raise HttpException(
                    task_id=get_task_id(request),
                    status_code=401,
                    message=message,
                    data={"code": exc.code},
                )
            return None

    # FastAPI 参数用于在 OpenAPI 中声明 x-api-key；实际校验始终读取 Request，
    # 才能识别同名 Header 被重复发送的情况。普通客户端和反向代理对重复 Header
    # 的取值顺序可能不同，因此必须拒绝，而不能隐式采用第一个或最后一个值。
    api_key_values = get_api_key_values(request)
    if not api_key_values and isinstance(x_api_key, str):
        api_key_values = [x_api_key]
    authorization_values = get_authorization_values(request)

    # 两种凭据同时携带属于歧义请求：不同代理对 Header 顺序/取值的处理不一致，
    # 隐式择一可能让较弱的凭据被采用。因此无论内容是否正确都直接拒绝。
    if api_key_values and authorization_values:
        raise HttpException(
            task_id=get_task_id(request),
            status_code=401,
            message="ambiguous credentials",
            data={"code": "ambiguous_credentials"},
        )

    if authorization_values:
        # 重复 Authorization 无法确定采用哪一枚，拒绝而不是猜测顺序。
        if len(authorization_values) != 1:
            raise HttpException(
                task_id=get_task_id(request),
                status_code=401,
                message="invalid token",
                data={"code": "invalid_token"},
            )
        authorization = authorization_values[0]
        if not token_service.bearer_scheme_matches(authorization):
            raise HttpException(
                task_id=get_task_id(request),
                status_code=401,
                message="invalid token",
                data={"code": "invalid_token"},
            )
        bearer = token_service.extract_bearer_token(authorization)
        try:
            return token_service.verify_token(bearer)
        except token_service.TokenError as exc:
            # TokenError.code 是稳定语义（invalid_token/token_expired），直接
            # 透传到 data.code，供前端区分“重新登录”与“刷新令牌”。
            raise HttpException(
                task_id=get_task_id(request),
                status_code=401,
                message=exc.code,
                data={"code": exc.code},
            )

    # 以下保持 x-api-key 既有校验语义：数量≠1 拒绝，恒定时间比较，
    # 错误信息仍为 "invalid API key"（既有单测断言该字符串）。
    if len(api_key_values) != 1:
        raise HttpException(
            task_id=get_task_id(request),
            status_code=401,
            message="invalid API key",
            data={"code": "invalid_api_key"},
        )

    # compare_digest 对 str 只支持 ASCII。请求 Header 属于不可信输入，攻击者
    # 可以发送 Latin-1 字符触发 TypeError。统一编码为 UTF-8 bytes 后既保留
    # 恒定时间比较，也支持 TOML 中合法的 Unicode Key。
    api_key_token = api_key_values[0]
    if not secrets.compare_digest(
        api_key_token.encode("utf-8"), configured_key.encode("utf-8")
    ):
        raise HttpException(
            task_id=get_task_id(request),
            status_code=401,
            message="invalid API key",
            data={"code": "invalid_api_key"},
        )

    return None

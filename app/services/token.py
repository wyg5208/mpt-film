"""无状态短时令牌（HS256）实现。

对应迁移方案 4.B：Mode B 下主密钥只在登录请求中出现一次，之后浏览器只
持有 15 分钟令牌。令牌无状态 → 兼容多 worker uvicorn，无需会话存储。

格式：``header.payload.sig``（base64url，无 padding）::

    header  = {"alg":"HS256","typ":"CFT"}
    payload = {"sub","iat","exp","jti","scope","v"}
    sig     = HMAC-SHA256(session_secret, f"{header_b64}.{payload_b64}")

``session_secret`` 取自 ``config.app["session_secret"]``；缺省时用主密钥
派生（``HMAC-SHA256(key=api_key, msg="changofilm/session/v1")``），使主密
钥轮换后旧令牌立即失效。
"""

import base64
import binascii
import hashlib
import hmac
import json
import math
import secrets
import time
from uuid import uuid4

from app.config import config

TOKEN_TYPE = "Bearer"
TOKEN_VERSION = 1
# 令牌默认生命周期（秒）。方案 4.B 使用 900（15 分钟）。
DEFAULT_TOKEN_TTL_SECONDS = 900
# 允许的时钟偏移容忍（秒）。
CLOCK_SKEW_TOLERANCE_SECONDS = 60

_SESSION_SECRET_MSG = b"changofilm/session/v1"
_ALL_SCOPES = ["*"]


class TokenError(Exception):
    """令牌校验失败的稳定错误码。

    由 :func:`app.controllers.base.verify_token` 转成带 ``data.code`` 的
    ``HttpException``，因此这里只携带语义，不直接依赖 HTTP 层。
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _derive_default_secret(api_key: str) -> bytes:
    return hmac.new(api_key.encode("utf-8"), _SESSION_SECRET_MSG, hashlib.sha256).digest()


def get_session_secret() -> bytes:
    """返回令牌签名密钥。

    优先使用显式配置的 ``session_secret``；缺省时由主密钥派生。两者都不存
    在（免认证本地模式）时抛 :class:`TokenError`，由调用方按认证关闭处理。
    """

    configured = config.app.get("session_secret")
    if isinstance(configured, str) and configured:
        return configured.encode("utf-8")

    api_key = config.app.get("api_key", "")
    if isinstance(api_key, str) and api_key:
        return _derive_default_secret(api_key)

    raise TokenError("invalid_token")


def _sign(secret: bytes, signing_input: str) -> str:
    signature = hmac.new(secret, signing_input.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(signature)


def issue_token(
    subject: str = "user",
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    scopes: list[str] | None = None,
) -> tuple[str, int, int]:
    """签发一枚短时令牌。

    返回 ``(token, expires_in, expires_at)``。``expires_at`` 为绝对 epoch
    秒，供前端在生命周期 80% 处主动刷新（方案 4.B 前端会话流程）。
    """

    secret = get_session_secret()
    now = int(time.time())
    # TTL 约束在 [1, 3600]，防止配置错误产生长期令牌或 0 秒令牌。
    ttl = max(1, min(int(ttl_seconds), 3600))
    expires_at = now + ttl

    header = {"alg": "HS256", "typ": "CFT"}
    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
        "scope": scopes or _ALL_SCOPES,
        "v": TOKEN_VERSION,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    token = f"{signing_input}.{_sign(secret, signing_input)}"
    return token, ttl, expires_at


def verify_token(token: str) -> dict:
    """校验令牌并返回其 payload。

    任何失败都抛 :class:`TokenError`，携带稳定错误码：

    - ``invalid_token``：格式非法 / 签名不符 / 版本不匹配 / JSON 损坏
    - ``token_expired``：``exp`` 已过期（含容忍后仍过期）
    """

    if not isinstance(token, str) or not token:
        raise TokenError("invalid_token")

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("invalid_token")

    header_b64, payload_b64, sig_b64 = parts
    secret = get_session_secret()
    expected_sig = _sign(secret, f"{header_b64}.{payload_b64}")

    # 恒定时间比较签名，避免时序侧信道；对 str 需 ASCII，统一转 bytes。
    if not hmac.compare_digest(sig_b64.encode("ascii"), expected_sig.encode("ascii")):
        raise TokenError("invalid_token")

    try:
        payload = json.loads(_b64url_decode(payload_b64))
        header = json.loads(_b64url_decode(header_b64))
    except (ValueError, binascii.Error):
        raise TokenError("invalid_token")

    if header.get("alg") != "HS256":
        raise TokenError("invalid_token")
    if payload.get("v") != TOKEN_VERSION:
        raise TokenError("invalid_token")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, (int, float)) or math.isnan(float(expires_at)):
        raise TokenError("invalid_token")

    now = time.time()
    if now - CLOCK_SKEW_TOLERANCE_SECONDS >= float(expires_at):
        raise TokenError("token_expired")

    return payload


def bearer_scheme_matches(authorization: str) -> bool:
    """判断 Authorization 头是否为 Bearer 方案（大小写敏感于 scheme 词）。"""

    return isinstance(authorization, str) and authorization.startswith("Bearer ")


def extract_bearer_token(authorization: str) -> str:
    return authorization[len("Bearer ") :].strip()


# 保留 secrets 引用以强调本模块依赖恒定时间比较实现（供静态检查与后续轮换）。
__all__ = [
    "TokenError",
    "issue_token",
    "verify_token",
    "get_session_secret",
    "bearer_scheme_matches",
    "extract_bearer_token",
    "TOKEN_TYPE",
    "DEFAULT_TOKEN_TTL_SECONDS",
]

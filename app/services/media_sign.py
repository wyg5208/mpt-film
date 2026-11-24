"""媒体短时签名 URL（迁移方案 4.A / Phase 0.5 / 1.10）。

``<video src>`` 无法携带自定义鉴权头，故 Mode B 下任务产物的下载链接改走短时效
HMAC 签名查询串：``?expires=<epoch>&sig=<hexdigest>``。签名对**规范化后的完整路径
+ 过期时间 + HTTP method** 逐字绑定（scope 到单个文件与单个方法），过期或被篡改即
拒绝，避免把主密钥暴露到 URL/浏览器。

密钥材料：优先 ``config.app["media_signing_key"]``；缺省由主密钥经
``HMAC-SHA256(key=api_key, msg="changofilm/media-signing/v1")`` 派生，主密钥轮换
后旧签名立即失效（TTL 600s 窗口内可接受）。鉴权关闭（未配置 api_key）时回退到
落盘随机密钥 ``storage/auth/media_signing.key``：首次使用时生成，重启保持稳定，
签名链接因此可跨进程有效；落盘失败时退回进程内随机密钥（仅重启后旧链接失效）。

签名算法（对齐 4.A）::

    canonical_path = posixpath.normpath("/" + raw_path.lstrip("/"))   # 消除 . // 歧义
    payload        = f"{canonical_path}\\n{expires_at}\\n{method}"     # method ∈ GET|HEAD
    sig            = HMAC-SHA256(secret, payload).hexdigest()

校验用同一套规范化重算，故 ``..``/`.`/`//`/百分号编码差异都无法绕过；比较用恒定
时间；时钟偏移容忍 ±60s。签名仅对白名单前缀生效。
"""

import hashlib
import hmac
import posixpath
import secrets
import time
from pathlib import Path

from app.config import config
from app.paths import runtime_root

# 媒体链接默认时效（秒），上限 3600（对齐 4.A）。
DEFAULT_MEDIA_TTL_SECONDS = 600
MAX_MEDIA_TTL_SECONDS = 3600
CLOCK_SKEW_TOLERANCE_SECONDS = 60

_MEDIA_SECRET_MSG = b"changofilm/media-signing/v1"

# 签名放行的白名单前缀：其它路径出现 sig 参数一律忽略，不得越权访问别端点。
MEDIA_SIGN_WHITELIST_PREFIXES = ("/tasks/", "/api/v1/stream/", "/api/v1/download/")


class MediaSignError(Exception):
    """签名校验失败的稳定错误码（media_signature_invalid / media_signature_expired）。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def canonicalize_path(raw_path: str) -> str:
    """把请求路径折叠成签名用的规范形式（消除 ``.``/``//``/前导斜杠歧义）。"""

    if not isinstance(raw_path, str):
        raise MediaSignError("media_signature_invalid")
    normalized = posixpath.normpath("/" + raw_path.lstrip("/"))
    return normalized


# 无 api_key（鉴权关闭）部署的兜底密钥文件名与进程内缓存。
_FALLBACK_SECRET_FILENAME = "media_signing.key"
_FALLBACK_SECRET_CACHE: bytes | None = None


def _fallback_secret_path() -> Path:
    return runtime_root() / "storage" / "auth" / _FALLBACK_SECRET_FILENAME


def _load_or_create_fallback_secret() -> bytes:
    """读取落盘兜底密钥；不存在则生成随机密钥并落盘。"""

    path = _fallback_secret_path()
    try:
        stored = path.read_bytes().strip()
    except OSError:
        stored = b""
    if stored:
        return stored
    generated = secrets.token_hex(32).encode("ascii")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(generated)
    except OSError:
        # 只读文件系统等场景退回进程内密钥：签名仍可用，重启后旧链接失效。
        pass
    return generated


def get_media_secret() -> bytes:
    """返回媒体签名密钥；优先配置项，其次主密钥派生，最后落盘随机兜底。"""

    configured = config.app.get("media_signing_key")
    if isinstance(configured, str) and configured:
        return configured.encode("utf-8")

    api_key = config.app.get("api_key", "")
    if isinstance(api_key, str) and api_key:
        return hmac.new(api_key.encode("utf-8"), _MEDIA_SECRET_MSG, hashlib.sha256).digest()

    global _FALLBACK_SECRET_CACHE
    if _FALLBACK_SECRET_CACHE is None:
        _FALLBACK_SECRET_CACHE = _load_or_create_fallback_secret()
    return _FALLBACK_SECRET_CACHE


def _sign(secret: bytes, canonical_path: str, expires_at: int, method: str) -> str:
    signing_input = f"{canonical_path}\n{expires_at}\n{method}".encode("utf-8")
    return hmac.new(secret, signing_input, hashlib.sha256).hexdigest()


def sign_url(
    path: str, ttl_seconds: int = DEFAULT_MEDIA_TTL_SECONDS, method: str = "GET"
) -> tuple[str, int]:
    """为请求路径 + method 签发短时效参数。

    返回 ``(sig, expires_at)``，调用方拼成 ``?expires=<expires_at>&sig=<sig>``。
    """

    secret = get_media_secret()
    ttl = max(1, min(int(ttl_seconds), MAX_MEDIA_TTL_SECONDS))
    expires_at = int(time.time()) + ttl
    canonical = canonicalize_path(path)
    return _sign(secret, canonical, expires_at, method.upper()), expires_at


def verify_signature(
    path: str, expires: object, sig: object, method: str = "GET"
) -> None:
    """校验签名；失败抛 :class:`MediaSignError`。

    顺序：路径规范 + 白名单前缀 → 参数类型 → 过期（含容忍）→ 恒定时间验签。
    """

    canonical = canonicalize_path(path)
    if not canonical.startswith(MEDIA_SIGN_WHITELIST_PREFIXES):
        raise MediaSignError("media_signature_invalid")
    if not isinstance(sig, str) or not sig:
        raise MediaSignError("media_signature_invalid")
    try:
        expires_at = int(expires)
    except (TypeError, ValueError):
        raise MediaSignError("media_signature_invalid")

    now = time.time()
    if now - CLOCK_SKEW_TOLERANCE_SECONDS >= expires_at:
        raise MediaSignError("media_signature_expired")

    secret = get_media_secret()
    expected = _sign(secret, canonical, expires_at, method.upper())
    if not hmac.compare_digest(sig.encode("ascii"), expected.encode("ascii")):
        raise MediaSignError("media_signature_invalid")


__all__ = [
    "MediaSignError",
    "sign_url",
    "verify_signature",
    "get_media_secret",
    "canonicalize_path",
    "MEDIA_SIGN_WHITELIST_PREFIXES",
    "DEFAULT_MEDIA_TTL_SECONDS",
    "MAX_MEDIA_TTL_SECONDS",
]

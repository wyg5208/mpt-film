"""服务商登录 API（迁移方案 1.4）。

把 Streamlit 登录向导（webui/chatgpt_login.py、codex_login.py、kimi_login.py）
背后的编排搬到服务端：start 返回登录链接与 flow 句柄，客户端在用户完成浏览器
授权后调用 complete 轮询收尾。逻辑全部复用既有 ``app/services/*_oauth``，
不改动服务实现；登录句柄由客户端原样回传（chatgpt 的服务端 attempt 表不变）。

注意：本组响应绝不回传任何 token 材料，只回 connected / 账号摘要。
"""

import time

from fastapi import Body, Depends, Request

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import chatgpt_oauth, codex_oauth, kimi_code_oauth
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

PROVIDERS = ("chatgpt", "codex", "kimi")

LOGIN_INSTRUCTIONS = {
    "chatgpt": "Open the login_url in a browser on this machine and finish the "
    "ChatGPT sign-in, then call complete.",
    "codex": "Open the login_url, enter the user code shown in flow, then call "
    "complete.",
    "kimi": "Open the login_url and approve the device code shown in flow, then "
    "call complete.",
}


def _require_provider(request: Request, provider: str) -> str:
    if provider not in PROVIDERS:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=f"unknown oauth provider: {provider}",
        )
    return provider


def _bad_gateway(request: Request, message: str):
    return HttpException(
        task_id=base.get_task_id(request),
        status_code=502,
        message=f"provider error: {message}",
    )


@router.post("/oauth/{provider}/start", summary="Begin a provider login flow")
def oauth_start(request: Request, provider: str):
    _require_provider(request, provider)
    try:
        if provider == "chatgpt":
            flow = chatgpt_oauth.begin_login()
            login_url = flow["authorize_url"]
            handle = {"id": flow["id"]}
        elif provider == "codex":
            flow = codex_oauth.request_device_code()
            login_url = codex_oauth.VERIFY_URL
            handle = {
                "device_auth_id": flow["device_auth_id"],
                "user_code": flow["user_code"],
                "interval": flow["interval"],
                "expires_at": flow["expires_at"],
                "generation": flow["generation"],
                "session_revision": flow["session_revision"],
            }
        else:
            from app.config import config

            region = kimi_code_oauth.resolve_region(
                config.app.get("kimi_code_base_url") or ""
            )
            payload = kimi_code_oauth.request_device_code(region)
            now = time.time()
            login_url = payload["verification_uri_complete"]
            handle = {
                "region": region,
                "device_code": payload["device_code"],
                "user_code": payload["user_code"],
                "interval": max(int(payload.get("interval", 5)), 2),
                "expires_at": now + float(payload.get("expires_in", 600)),
                "generation": kimi_code_oauth.authorization_generation(),
            }
    except (chatgpt_oauth.ChatGPTError, codex_oauth.CodexError, ValueError) as error:
        raise _bad_gateway(request, str(error))

    return utils.get_response(
        200,
        {
            "login_url": login_url,
            "instructions": LOGIN_INSTRUCTIONS[provider],
            "flow": handle,
        },
    )


@router.post("/oauth/{provider}/complete", summary="Poll and commit a started login")
def oauth_complete(request: Request, provider: str, payload: dict = Body(...)):
    _require_provider(request, provider)
    flow = payload.get("flow")
    if not isinstance(flow, dict) or not flow:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message="flow from /oauth/{provider}/start is required",
        )
    try:
        if provider == "chatgpt":
            connected = bool(chatgpt_oauth.poll_login(flow))
        elif provider == "codex":
            connected = bool(codex_oauth.poll_login(flow))
        else:
            if time.time() >= flow.get("expires_at", 0):
                raise ValueError("kimi_code.oauth.expired")
            token = kimi_code_oauth.poll_token(flow["region"], flow["device_code"])
            if token.get("expired"):
                raise ValueError("kimi_code.oauth.expired")
            if token.get("denied"):
                raise ValueError("kimi_code.oauth.denied")
            if token.get("pending"):
                connected = False
            else:
                kimi_code_oauth.store_token_bundle(
                    flow["region"], token, expected_generation=flow.get("generation")
                )
                connected = True
    except (chatgpt_oauth.ChatGPTError, codex_oauth.CodexError, ValueError, KeyError) as error:
        raise _bad_gateway(request, str(error))

    return utils.get_response(200, {"connected": connected})


@router.get("/oauth/{provider}/status", summary="Connected state and account summary")
def oauth_status(request: Request, provider: str):
    _require_provider(request, provider)
    try:
        if provider == "chatgpt":
            details = chatgpt_oauth.account_details() or {}
            connected = bool(details.get("authorized"))
            account = {
                "profiles": [
                    {
                        "email": profile.get("email"),
                        "plan": profile.get("plan_type") or profile.get("plan"),
                    }
                    for profile in (details.get("profiles") or {}).values()
                ]
                if isinstance(details.get("profiles"), dict)
                else [],
                "active": details.get("active"),
            }
        elif provider == "codex":
            connected = bool(codex_oauth.account_status())
            account = {}
        else:
            connected = bool(kimi_code_oauth.is_authorized())
            account = {"region": kimi_code_oauth.authorized_region() if connected else ""}
    except (chatgpt_oauth.ChatGPTError, codex_oauth.CodexError, ValueError) as error:
        # 探测失败按未连接处理，避免登录页因瞬时凭据库异常而不可用。
        return utils.get_response(200, {"connected": False, "account": None, "error": str(error)})

    return utils.get_response(200, {"connected": connected, "account": account})


@router.get("/oauth/{provider}/models", summary="Provider model catalog")
def oauth_models(request: Request, provider: str):
    _require_provider(request, provider)
    models: list = []
    if provider == "chatgpt":
        try:
            models = list(chatgpt_oauth.get_models())
        except (chatgpt_oauth.ChatGPTError, ValueError) as error:
            raise _bad_gateway(request, str(error))
    elif provider == "codex":
        # 与 webui/codex_models.py 共用服务层目录（models.dev + 本地缓存）。
        from app.services import codex_models

        try:
            catalog = codex_models.get_catalog()
        except codex_models.CatalogError as error:
            raise _bad_gateway(request, str(error))
        models = [{"id": model.id, "name": model.name} for model in catalog.models]
    else:
        # kimi 与 webui 保持一致：无远端模型目录，模型名由用户直接填写。
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message="provider has no model catalog: kimi",
        )

    return utils.get_response(200, {"provider": provider, "models": models})

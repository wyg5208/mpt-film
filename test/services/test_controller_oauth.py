"""服务商登录 API 回归（迁移方案 1.4）。

外部网络全部打桩：只验证编排与状态语义，绝不发起真实授权请求。
"""

import unittest
from dataclasses import field
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import chatgpt_oauth, codex_oauth


class TestOAuthEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_unknown_provider_is_404(self):
        response = self.client.post("/api/v1/oauth/deepseek/start")
        self.assertEqual(response.status_code, 404)

    def test_chatgpt_start_returns_login_url_and_flow(self):
        with patch.object(
            chatgpt_oauth,
            "begin_login",
            return_value={
                "id": "attempt-1",
                "authorize_url": "https://auth.openai.com/authorize?x=1",
                "expires_at": 9999999999.0,
            },
        ):
            response = self.client.post("/api/v1/oauth/chatgpt/start")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["login_url"].startswith("https://auth.openai.com/"))
        self.assertEqual(data["flow"], {"id": "attempt-1"})
        self.assertIn("instructions", data)

    def test_chatgpt_complete_reports_pending_then_connected(self):
        with patch.object(chatgpt_oauth, "poll_login", return_value=False):
            pending = self.client.post(
                "/api/v1/oauth/chatgpt/complete", json={"flow": {"id": "a"}}
            )
        self.assertTrue(pending.json()["data"]["connected"] is False)
        with patch.object(chatgpt_oauth, "poll_login", return_value=True):
            done = self.client.post(
                "/api/v1/oauth/chatgpt/complete", json={"flow": {"id": "a"}}
            )
        self.assertTrue(done.json()["data"]["connected"])

    def test_complete_requires_flow(self):
        response = self.client.post("/api/v1/oauth/chatgpt/complete", json={})
        self.assertEqual(response.status_code, 400)

    def test_provider_failure_maps_to_502(self):
        with patch.object(
            chatgpt_oauth,
            "begin_login",
            side_effect=chatgpt_oauth.ChatGPTError("login_failed"),
        ):
            response = self.client.post("/api/v1/oauth/chatgpt/start")
        self.assertEqual(response.status_code, 502)

    def test_codex_device_flow_roundtrip(self):
        with patch.object(
            codex_oauth,
            "request_device_code",
            return_value={
                "device_auth_id": "dev-1",
                "user_code": "ABCD-EFGH",
                "interval": 5,
                "expires_at": 9999999999.0,
                "generation": 1,
                "session_revision": "rev-1",
            },
        ):
            start = self.client.post("/api/v1/oauth/codex/start")
        self.assertEqual(start.status_code, 200)
        flow = start.json()["data"]["flow"]
        with patch.object(codex_oauth, "poll_login", return_value=True):
            complete = self.client.post(
                "/api/v1/oauth/codex/complete", json={"flow": flow}
            )
        self.assertTrue(complete.json()["data"]["connected"])

    def test_status_endpoints_never_leak_tokens(self):
        with patch.object(
            chatgpt_oauth,
            "account_details",
            return_value={
                "authorized": True,
                "active": "profile-1",
                "profiles": {
                    "profile-1": {
                        "email": "user@example.com",
                        "access_token": "super-secret-token",
                    }
                },
            },
        ):
            response = self.client.get("/api/v1/oauth/chatgpt/status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["connected"])
        self.assertNotIn("super-secret-token", response.text)

    def test_kimi_status_and_models(self):
        from app.services import kimi_code_oauth

        with patch.object(kimi_code_oauth, "is_authorized", return_value=True), patch.object(
            kimi_code_oauth, "authorized_region", return_value="china"
        ):
            status = self.client.get("/api/v1/oauth/kimi/status")
        self.assertTrue(status.json()["data"]["connected"])
        self.assertEqual(status.json()["data"]["account"]["region"], "china")

        models = self.client.get("/api/v1/oauth/kimi/models")
        self.assertEqual(models.status_code, 404)

    def test_codex_models_from_service_catalog(self):
        class Item:
            def __init__(self, model_id, name):
                self.id = model_id
                self.name = name

        class Catalog:
            models = [Item("gpt-5.4", "GPT-5.4")]

        from app.services import codex_models

        with patch.object(codex_models, "get_catalog", return_value=Catalog()):
            response = self.client.get("/api/v1/oauth/codex/models")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"]["models"], [{"id": "gpt-5.4", "name": "GPT-5.4"}]
        )

    def test_requires_credentials_when_enabled(self):
        config.app["api_key"] = "oauth-secret"
        anonymous = self.client.get("/api/v1/oauth/chatgpt/status")
        self.assertEqual(anonymous.status_code, 401)


if __name__ == "__main__":
    unittest.main()

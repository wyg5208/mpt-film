import unittest

from fastapi.testclient import TestClient

from app import asgi
from app.config import config


class TestAuthControllerHTTP(unittest.TestCase):
    """Short-lived token exchange flow (migration 4.B / Phase 0.3)."""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "auth-master-secret"
        config.app.pop("session_secret", None)
        config.app.pop("media_signing_key", None)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _login(self, api_key: str):
        return self.client.post("/api/v1/auth/login", json={"api_key": api_key})

    def test_login_issues_token_and_never_leaks_master_key(self):
        response = self._login("auth-master-secret")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], 200)
        data = body["data"]
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertGreater(data["expires_in"], 0)
        self.assertNotIn("auth-master-secret", response.text)

    def test_login_rejects_wrong_key(self):
        response = self._login("nope")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["data"]["code"], "invalid_api_key")

    def test_login_rejected_when_auth_disabled(self):
        config.app["api_key"] = ""
        response = self._login("")
        self.assertEqual(response.status_code, 400)

    def test_session_reports_valid_and_scope(self):
        token = self._login("auth-master-secret").json()["data"]["access_token"]
        response = self.client.get(
            "/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["valid"])
        self.assertTrue(data["auth_required"])
        self.assertEqual(data["scope"], ["*"])

    def test_session_requires_credentials_when_auth_enabled(self):
        response = self.client.get("/api/v1/auth/session")
        self.assertEqual(response.status_code, 401)

    def test_session_reports_auth_not_required_when_disabled(self):
        config.app["api_key"] = ""
        response = self.client.get("/api/v1/auth/session")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["valid"])
        self.assertFalse(data["auth_required"])

    def test_refresh_returns_new_token(self):
        token = self._login("auth-master-secret").json()["data"]["access_token"]
        response = self.client.post(
            "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        new_token = response.json()["data"]["access_token"]
        self.assertNotEqual(new_token, token)
        verify = self.client.get(
            "/api/v1/auth/session", headers={"Authorization": f"Bearer {new_token}"}
        )
        self.assertEqual(verify.status_code, 200)

    def test_refresh_rejects_missing_token(self):
        response = self.client.post("/api/v1/auth/refresh")
        self.assertEqual(response.status_code, 401)

    def test_logout_confirms_without_server_revocation(self):
        token = self._login("auth-master-secret").json()["data"]["access_token"]
        response = self.client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["logged_out"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import token as token_service


class TestTokenService(unittest.TestCase):
    """Stateless short-lived tokens: issue/verify/expiry/scheme (migration 4.B / 4.D)."""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "token-secret"
        config.app.pop("session_secret", None)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_issue_and_verify_roundtrip(self):
        access_token, expires_in, expires_at = token_service.issue_token(
            subject="user"
        )
        self.assertEqual(expires_in, token_service.DEFAULT_TOKEN_TTL_SECONDS)
        payload = token_service.verify_token(access_token)
        self.assertEqual(payload["sub"], "user")
        self.assertEqual(payload["exp"], expires_at)
        self.assertEqual(payload["scope"], ["*"])
        self.assertEqual(payload["v"], token_service.TOKEN_VERSION)

    def test_verify_rejects_tampered_signature(self):
        access_token, _, _ = token_service.issue_token()
        header, payload, sig = access_token.split(".")
        flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
        tampered = f"{header}.{payload}.{flipped}"
        with self.assertRaises(token_service.TokenError) as raised:
            token_service.verify_token(tampered)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_verify_rejects_malformed_token(self):
        for bad in ("", "not-a-token", "a.b"):
            with self.subTest(bad=bad):
                with self.assertRaises(token_service.TokenError) as raised:
                    token_service.verify_token(bad)
                self.assertEqual(raised.exception.code, "invalid_token")

    def test_expired_token_raises_token_expired(self):
        access_token, expires_in, _ = token_service.issue_token()
        future = (expires_in + token_service.CLOCK_SKEW_TOLERANCE_SECONDS + 10)
        with patch("app.services.token.time.time", return_value=_now_plus(future)):
            with self.assertRaises(token_service.TokenError) as raised:
                token_service.verify_token(access_token)
        self.assertEqual(raised.exception.code, "token_expired")

    def test_secret_rotation_invalidates_tokens(self):
        access_token, _, _ = token_service.issue_token()
        config.app["api_key"] = "rotated-secret"
        with self.assertRaises(token_service.TokenError):
            token_service.verify_token(access_token)

    def test_bearer_scheme_detection(self):
        self.assertTrue(token_service.bearer_scheme_matches("Bearer abc"))
        self.assertFalse(token_service.bearer_scheme_matches("bearer abc"))
        self.assertFalse(token_service.bearer_scheme_matches("Basic abc"))
        self.assertEqual(token_service.extract_bearer_token("Bearer abc123"), "abc123")

    def test_missing_secret_raises(self):
        config.app["api_key"] = ""
        config.app.pop("session_secret", None)
        with self.assertRaises(token_service.TokenError):
            token_service.issue_token()


def _now_plus(seconds: int) -> float:
    import time as _time

    return _time.time() + seconds


class TestBearerAuthHTTP(unittest.TestCase):
    """Verify Bearer credential path and ambiguous-credential rejection from the real ASGI entry."""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "http-secret"
        config.app.pop("session_secret", None)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _login_token(self):
        response = self.client.post(
            "/api/v1/auth/login", json={"api_key": "http-secret"}
        )
        return response.json()["data"]["access_token"]

    def test_bearer_token_authorizes_protected_route(self):
        token = self._login_token()
        response = self.client.get(
            "/api/v1/tasks", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)

    def test_ambiguous_credentials_rejected(self):
        token = self._login_token()
        response = self.client.get(
            "/api/v1/tasks",
            headers={
                "Authorization": f"Bearer {token}",
                "x-api-key": "http-secret",
            },
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["data"]["code"], "ambiguous_credentials")

    def test_non_bearer_scheme_rejected(self):
        response = self.client.get(
            "/api/v1/tasks", headers={"Authorization": "Basic abc"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["data"]["code"], "invalid_token")

    def test_x_api_key_still_supported(self):
        response = self.client.get(
            "/api/v1/tasks", headers={"x-api-key": "http-secret"}
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlparse

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import media_sign
from app.utils import utils


class TestMediaSignService(unittest.TestCase):
    """签名算法单元用例（迁移方案 4.A / 4.D）。"""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "media-secret"
        config.app.pop("media_signing_key", None)
        config.app.pop("session_secret", None)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_sign_and_verify_roundtrip(self):
        sig, expires = media_sign.sign_url("/tasks/abc/final-1.mp4")
        media_sign.verify_signature("/tasks/abc/final-1.mp4", expires, sig)

    def test_canonical_path_equivalence(self):
        # ``.``/``//``/多余前导斜杠规范化后签名一致，防止绕过。
        media_sign.verify_signature(
            "/tasks//abc/./final-1.mp4",
            *media_sign.sign_url("/tasks/abc/final-1.mp4")[::-1],
        )

    def test_verify_rejects_tampered_path(self):
        sig, expires = media_sign.sign_url("/tasks/abc/final-1.mp4")
        with self.assertRaises(media_sign.MediaSignError) as raised:
            media_sign.verify_signature("/tasks/other/final-1.mp4", expires, sig)
        self.assertEqual(raised.exception.code, "media_signature_invalid")

    def test_verify_rejects_tampered_method(self):
        sig, expires = media_sign.sign_url("/tasks/abc/v.mp4", method="GET")
        with self.assertRaises(media_sign.MediaSignError) as raised:
            media_sign.verify_signature("/tasks/abc/v.mp4", expires, sig, "HEAD")
        self.assertEqual(raised.exception.code, "media_signature_invalid")

    def test_verify_allows_head_when_signed_head(self):
        sig, expires = media_sign.sign_url("/tasks/abc/v.mp4", method="HEAD")
        media_sign.verify_signature("/tasks/abc/v.mp4", expires, sig, "HEAD")

    def test_verify_rejects_expired(self):
        sig, expires = media_sign.sign_url("/tasks/abc/v.mp4", ttl_seconds=1)
        future = expires + media_sign.CLOCK_SKEW_TOLERANCE_SECONDS + 10
        with patch("app.services.media_sign.time.time", return_value=float(future)):
            with self.assertRaises(media_sign.MediaSignError) as raised:
                media_sign.verify_signature("/tasks/abc/v.mp4", expires, sig)
        self.assertEqual(raised.exception.code, "media_signature_expired")

    def test_verify_rejects_missing_params(self):
        for bad_sig, bad_exp in ((None, "x"), ("abc", "notint"), ("", 0)):
            with self.subTest(sig=bad_sig, exp=bad_exp):
                with self.assertRaises(media_sign.MediaSignError) as raised:
                    media_sign.verify_signature("/tasks/abc/v.mp4", bad_exp, bad_sig)
                self.assertEqual(raised.exception.code, "media_signature_invalid")

    def test_verify_rejects_non_whitelisted_prefix(self):
        # 把 /tasks 的签名挪到非白名单前缀（如 settings）必须被拒（对齐 4.D）。
        sig, expires = media_sign.sign_url("/tasks/abc/v.mp4")
        with self.assertRaises(media_sign.MediaSignError) as raised:
            media_sign.verify_signature("/api/v1/settings/app", expires, sig)
        self.assertEqual(raised.exception.code, "media_signature_invalid")

    def test_ttl_capped_at_max(self):
        _, expires = media_sign.sign_url(
            "/tasks/abc/v.mp4", ttl_seconds=media_sign.MAX_MEDIA_TTL_SECONDS + 9999
        )
        import time

        self.assertLessEqual(expires - int(time.time()), media_sign.MAX_MEDIA_TTL_SECONDS)

    def test_secret_missing_falls_back_to_persisted_secret(self):
        # 鉴权关闭（无 api_key）时自动落盘随机密钥，签名/验签仍可用。
        config.app["api_key"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("app.services.media_sign.runtime_root", return_value=Path(tmp)):
                media_sign._FALLBACK_SECRET_CACHE = None
                try:
                    sig, expires = media_sign.sign_url("/tasks/abc/v.mp4")
                    media_sign.verify_signature("/tasks/abc/v.mp4", expires, sig)
                    secret_file = Path(tmp) / "storage" / "auth" / "media_signing.key"
                    self.assertTrue(secret_file.is_file())
                    stored = secret_file.read_bytes().strip()
                    # 落盘密钥在重启（进程内缓存清空）后继续生效。
                    media_sign._FALLBACK_SECRET_CACHE = None
                    self.assertEqual(media_sign.get_media_secret(), stored)
                finally:
                    media_sign._FALLBACK_SECRET_CACHE = None

    def test_secret_fallback_survives_unwritable_path(self):
        # 落盘失败（storage 不是目录）时回退进程内密钥：签名仍可用。
        config.app["api_key"] = ""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "storage").write_text("not a dir", encoding="utf-8")
            with patch("app.services.media_sign.runtime_root", return_value=Path(tmp)):
                media_sign._FALLBACK_SECRET_CACHE = None
                try:
                    sig, expires = media_sign.sign_url("/tasks/abc/v.mp4")
                    media_sign.verify_signature("/tasks/abc/v.mp4", expires, sig)
                finally:
                    media_sign._FALLBACK_SECRET_CACHE = None


class TestMediaSignStaticHTTP(unittest.TestCase):
    """签名链接对 <video src> 放行，且保留 Range 行为（迁移方案 4.A / 4.D）。"""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "media-http-secret"
        config.app.pop("media_signing_key", None)
        config.app.pop("session_secret", None)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _artifact(self):
        directory = tempfile.TemporaryDirectory(
            prefix="media-sign-", dir=utils.task_dir()
        )
        self.addCleanup(directory.cleanup)
        task_path = Path(directory.name)
        artifact = task_path / "artifact.txt"
        artifact.write_text("protected task artifact", encoding="utf-8")
        return task_path.name, artifact.name

    def _signed(self, url, ttl=60, method="GET"):
        sig, expires = media_sign.sign_url(url, ttl_seconds=ttl, method=method)
        return f"{url}?expires={expires}&sig={quote(sig, safe='')}"

    def test_unsigned_rejected_signed_allowed(self):
        task_name, artifact_name = self._artifact()
        url = f"/tasks/{task_name}/{artifact_name}"
        self.assertEqual(self.client.get(url).status_code, 401)
        signed = self.client.get(self._signed(url))
        self.assertEqual(signed.status_code, 200)
        self.assertEqual(signed.text, "protected task artifact")

    def test_range_still_served_for_signed_url(self):
        task_name, artifact_name = self._artifact()
        url = f"/tasks/{task_name}/{artifact_name}"
        signed = self.client.get(
            self._signed(url), headers={"Range": "bytes=0-4"}
        )
        self.assertIn(signed.status_code, (200, 206))

    def test_tampered_signature_rejected(self):
        task_name, artifact_name = self._artifact()
        url = f"/tasks/{task_name}/{artifact_name}"
        sig, expires = media_sign.sign_url(url, ttl_seconds=60)
        flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
        response = self.client.get(f"{url}?expires={expires}&sig={quote(flipped, safe='')}")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["data"]["code"], "media_signature_invalid")

    def test_cross_path_signature_reuse_rejected(self):
        # 用 A 文件签发的签名去访问同目录下的 B 文件必须被拒（签名逐字绑定路径）。
        directory = tempfile.TemporaryDirectory(
            prefix="media-sign-x-", dir=utils.task_dir()
        )
        self.addCleanup(directory.cleanup)
        task_path = Path(directory.name)
        (task_path / "a.txt").write_text("aaa", encoding="utf-8")
        (task_path / "b.txt").write_text("bbb", encoding="utf-8")
        task_name = task_path.name
        url_a = f"/tasks/{task_name}/a.txt"
        parsed = urlparse(self._signed(url_a))
        qs = parse_qs(parsed.query)
        url_b = f"/tasks/{task_name}/b.txt"
        response = self.client.get(
            f"{url_b}?expires={qs['expires'][0]}&sig={qs['sig'][0]}"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["data"]["code"], "media_signature_invalid")

    def test_head_signature_rejected_for_get(self):
        task_name, artifact_name = self._artifact()
        url = f"/tasks/{task_name}/{artifact_name}"
        # 以 HEAD 方法签发，用 GET 访问应被拒（method 绑定）。
        response = self.client.get(self._signed(url, method="HEAD"))
        self.assertEqual(response.status_code, 401)


class TestMediaSignEndpoint(unittest.TestCase):
    """POST/GET /media/sign 签发端点（迁移方案 1.10 / 4.A）。"""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = "endpoint-secret"
        config.app.pop("media_signing_key", None)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _artifact(self):
        directory = tempfile.TemporaryDirectory(
            prefix="media-ep-", dir=utils.task_dir()
        )
        self.addCleanup(directory.cleanup)
        task_path = Path(directory.name)
        artifact = task_path / "final-1.mp4"
        artifact.write_bytes(b"fake video bytes")
        return f"{task_path.name}/final-1.mp4"

    def test_batch_sign_returns_urls_that_pass_static_guard(self):
        rel = self._artifact()
        response = self.client.post(
            "/api/v1/media/sign",
            json={"paths": [rel]},
            headers={"x-api-key": "endpoint-secret"},
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["path"], rel)
        self.assertIn("expires=", items[0]["url"])
        self.assertIn("sig=", items[0]["url"])
        # 换发的 URL 能被静态中间件放行。
        played = self.client.get(items[0]["url"])
        self.assertEqual(played.status_code, 200)

    def test_single_sign_debug_endpoint(self):
        rel = self._artifact()
        response = self.client.get(
            "/api/v1/media/sign",
            params={"path": rel},
            headers={"x-api-key": "endpoint-secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sig=", response.json()["data"]["item"]["url"])

    def test_sign_rejects_path_outside_task_dir(self):
        response = self.client.post(
            "/api/v1/media/sign",
            json={"paths": ["../../etc/passwd"]},
            headers={"x-api-key": "endpoint-secret"},
        )
        # 越界路径整体被拒：HttpException 403/404 经异常处理器映射为 HTTP 状态码。
        self.assertIn(response.status_code, (403, 404))

    def test_sign_rejects_missing_file(self):
        # 存在白名单目录前缀但文件不存在 → 404。
        response = self.client.post(
            "/api/v1/media/sign",
            json={"paths": ["no-such-task/no-such-file.mp4"]},
            headers={"x-api-key": "endpoint-secret"},
        )
        self.assertEqual(response.status_code, 404)

    def test_sign_requires_credentials(self):
        rel = self._artifact()
        anonymous = self.client.post("/api/v1/media/sign", json={"paths": [rel]})
        self.assertEqual(anonymous.status_code, 401)


if __name__ == "__main__":
    unittest.main()

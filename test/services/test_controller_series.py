"""系列管理 API 回归（迁移方案 1.5）。

覆盖：CRUD、角色、参考图上传/下发/人工锁定（409）、剧集状态机
（非法迁移 409）、bind-plan，以及图片路径必须严格限定在系列目录内。
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import series_store

# 1x1 透明 PNG。
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d47414d4100000000000000000000000000dbb2945f0000000a4944"
    "4154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class TestSeriesEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.root = tempfile.mkdtemp(prefix="series-api-")
        patcher = patch.object(
            series_store, "series_root", return_value=Path(self.root)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _create_series(self, title="My Series") -> str:
        response = self.client.post(
            "/api/v1/series", json={"title": title, "genre_template": "suspense"}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["id"]

    def _create_character(self, sid: str, name="Hero") -> str:
        response = self.client.post(
            f"/api/v1/series/{sid}/characters",
            json={"name": name, "role": "protagonist", "appearance_prompt": "tall"},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["id"]

    def test_crud_roundtrip(self):
        sid = self._create_series()
        listing = self.client.get("/api/v1/series").json()["data"]["series"]
        self.assertIn(sid, {item["id"] for item in listing})

        fetched = self.client.get(f"/api/v1/series/{sid}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["data"]["title"], "My Series")

        missing = self.client.get("/api/v1/series/sr-does-not-exist")
        self.assertEqual(missing.status_code, 404)

        updated = self.client.put(f"/api/v1/series/{sid}", json={"title": "Renamed"})
        self.assertEqual(updated.json()["data"]["title"], "Renamed")

        deleted = self.client.delete(f"/api/v1/series/{sid}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/series/{sid}").status_code, 404)

    def test_create_rejects_unknown_genre(self):
        response = self.client.post(
            "/api/v1/series", json={"title": "x", "genre_template": "western_horror"}
        )
        self.assertEqual(response.status_code, 400)

    def test_reference_image_lifecycle_and_lock(self):
        sid = self._create_series()
        cid = self._create_character(sid)

        upload = self.client.post(
            f"/api/v1/series/{sid}/characters/{cid}/images",
            files={"file": ("ref.png", PNG_BYTES, "image/png")},
        )
        self.assertEqual(upload.status_code, 200)
        relative = upload.json()["data"]["path"]
        name = relative.split("/")[-1]

        served = self.client.get(f"/api/v1/series/{sid}/characters/{cid}/images/{name}")
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.content, PNG_BYTES)

        # 人工锁定后删除必须 409（AI 不得覆盖人工选择）。
        self.assertEqual(
            self.client.put(
                f"/api/v1/series/{sid}/characters/{cid}/images/{name}/lock"
            ).status_code,
            200,
        )
        locked = self.client.delete(
            f"/api/v1/series/{sid}/characters/{cid}/images/{name}"
        )
        self.assertEqual(locked.status_code, 409)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/series/{sid}/characters/{cid}/images/{name}/lock"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/v1/series/{sid}/characters/{cid}/images/{name}"
            ).status_code,
            200,
        )

    def test_reference_image_rejects_bad_suffix_and_traversal(self):
        sid = self._create_series()
        cid = self._create_character(sid)
        bad = self.client.post(
            f"/api/v1/series/{sid}/characters/{cid}/images",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        self.assertEqual(bad.status_code, 400)
        traversal = self.client.get(
            f"/api/v1/series/{sid}/characters/{cid}/images/..%2Fseries.json"
        )
        self.assertIn(traversal.status_code, (400, 404))

    def test_episode_state_machine_is_forward_only(self):
        sid = self._create_series()
        created = self.client.post(
            f"/api/v1/series/{sid}/episodes",
            json={"title": "Pilot", "logline": "hook line", "hook": "cold open"},
        )
        self.assertEqual(created.status_code, 200)
        episode = created.json()["data"]
        self.assertEqual(episode["status"], "draft")
        self.assertEqual(episode["seq"], 1)

        forward = self.client.patch(
            f"/api/v1/series/{sid}/episodes/{episode['id']}/status",
            json={"status": "confirmed"},
        )
        self.assertEqual(forward.status_code, 200)

        backward = self.client.patch(
            f"/api/v1/series/{sid}/episodes/{episode['id']}/status",
            json={"status": "draft"},
        )
        self.assertEqual(backward.status_code, 409)

        bound = self.client.post(
            f"/api/v1/series/{sid}/bind-plan",
            json={"episode_id": episode["id"], "plan_id": "plan-123"},
        )
        self.assertEqual(bound.status_code, 200)
        self.assertEqual(bound.json()["data"]["plan_id"], "plan-123")

        unknown = self.client.post(
            f"/api/v1/series/{sid}/bind-plan",
            json={"episode_id": "ep-missing", "plan_id": "plan-123"},
        )
        self.assertEqual(unknown.status_code, 404)

    def test_requires_credentials_when_enabled(self):
        config.app["api_key"] = "series-secret"
        anonymous = self.client.get("/api/v1/series")
        self.assertEqual(anonymous.status_code, 401)
        authorized = self.client.get(
            "/api/v1/series", headers={"x-api-key": "series-secret"}
        )
        self.assertEqual(authorized.status_code, 200)


if __name__ == "__main__":
    unittest.main()

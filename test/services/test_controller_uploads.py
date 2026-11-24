"""文件上传 API 回归（迁移方案 1.7）。"""

import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.controllers.v1 import uploads as uploads_controller


class TestUploadEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.root = tempfile.mkdtemp(prefix="uploads-api-")
        patcher = patch.object(
            uploads_controller,
            "_voice_reference_dir",
            return_value=self.root,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_voice_reference_persists_server_token(self):
        response = self.client.post(
            "/api/v1/uploads/voice-reference",
            files={"file": ("prompt.mp3", b"ID3-fake-audio", "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["file"].endswith(".mp3"))
        self.assertTrue(os.path.isfile(data["path"]))
        with open(data["path"], "rb") as handle:
            self.assertEqual(handle.read(), b"ID3-fake-audio")

    def test_voice_reference_rejects_non_audio_suffix(self):
        response = self.client.post(
            "/api/v1/uploads/voice-reference",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_voice_reference_size_cap(self):
        original = uploads_controller.MAX_VOICE_REFERENCE_BYTES
        uploads_controller.MAX_VOICE_REFERENCE_BYTES = 4
        self.addCleanup(
            setattr, uploads_controller, "MAX_VOICE_REFERENCE_BYTES", original
        )
        response = self.client.post(
            "/api/v1/uploads/voice-reference",
            files={"file": ("long.mp3", b"0123456789", "audio/mpeg")},
        )
        self.assertEqual(response.status_code, 413)

    def test_material_delegates_to_material_service(self):
        with patch(
            "app.services.material_upload.save_material_upload",
            return_value=os.path.join(self.root, "stored-uuid.mp4"),
        ) as mock_save:
            response = self.client.post(
                "/api/v1/uploads/material",
                files={"file": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["name"], "stored-uuid.mp4")
        filename, source = mock_save.call_args[0]
        self.assertEqual(filename, "clip.mp4")
        self.assertIsInstance(source, io.BytesIO)

    def test_material_upload_error_maps_to_400(self):
        from app.services import material_upload as material_upload_service

        with patch(
            "app.services.material_upload.save_material_upload",
            side_effect=material_upload_service.MaterialUploadError("unsupported"),
        ):
            response = self.client.post(
                "/api/v1/uploads/material",
                files={"file": ("clip.xyz", b"1234", "application/octet-stream")},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unsupported", response.json()["message"])

    def test_requires_credentials_when_enabled(self):
        config.app["api_key"] = "uploads-secret"
        anonymous = self.client.post(
            "/api/v1/uploads/voice-reference",
            files={"file": ("a.mp3", b"x", "audio/mpeg")},
        )
        self.assertEqual(anonymous.status_code, 401)


if __name__ == "__main__":
    unittest.main()

"""素材库文件管理 API 回归：公共素材空间的 TXT/MD 与文件夹 CRUD + 安全边界。

作用域根目录经 ``material_docs.public_docs_dir`` 打桩到临时目录，逐条验证
HTTP 状态码与落盘事实，重点覆盖越界/非法名/非文本/非空目录/删除根等拒绝路径。
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import material_docs


class TestMaterialDocsApi(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.root = tempfile.mkdtemp(prefix="material-docs-")
        patcher = patch.object(
            material_docs, "public_docs_dir", return_value=self.root
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    # ---- helpers ----
    def _tree(self):
        response = self.client.get("/api/v1/materials/tree?scope=public")
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def _create_file(self, name, content="", parent=""):
        return self.client.post(
            "/api/v1/materials/file",
            json={"scope": "public", "name": name, "content": content, "parent": parent},
        )

    # ---- CRUD happy paths ----
    def test_create_read_update_delete_file(self):
        created = self._create_file("notes.txt", "hello 世界")
        self.assertEqual(created.status_code, 200)
        data = created.json()["data"]
        self.assertEqual(data["name"], "notes.txt")
        self.assertTrue(data["created"])
        # 落盘事实：内容按 UTF-8 原样写入。
        with open(os.path.join(self.root, "notes.txt"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "hello 世界")

        read = self.client.get("/api/v1/materials/file?scope=public&path=notes.txt")
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json()["data"]["content"], "hello 世界")

        updated = self.client.put(
            "/api/v1/materials/file",
            json={"scope": "public", "path": "notes.txt", "content": "v2"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["data"]["created"])

        deleted = self.client.delete("/api/v1/materials/file?scope=public&path=notes.txt")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(os.path.exists(os.path.join(self.root, "notes.txt")))

    def test_name_without_extension_becomes_txt(self):
        response = self._create_file("readme", "x")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["name"], "readme.txt")

    def test_markdown_allowed(self):
        response = self._create_file("plan.md", "# 标题")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["name"], "plan.md")

    def test_folder_create_list_and_nested_file(self):
        folder = self.client.post(
            "/api/v1/materials/folder", json={"scope": "public", "name": "scripts"}
        )
        self.assertEqual(folder.status_code, 200)
        self.assertTrue(os.path.isdir(os.path.join(self.root, "scripts")))

        nested = self._create_file("a.txt", "inner", parent="scripts")
        self.assertEqual(nested.status_code, 200)
        self.assertEqual(nested.json()["data"]["path"], "scripts/a.txt")

        tree = self._tree()
        paths = {item["path"]: item for item in tree["items"]}
        self.assertEqual(paths["scripts"]["type"], "dir")
        self.assertTrue(paths["scripts/a.txt"]["editable"])

    def test_delete_folder_only_when_empty(self):
        self.client.post(
            "/api/v1/materials/folder", json={"scope": "public", "name": "tmp"}
        )
        empty = self.client.delete("/api/v1/materials/folder?scope=public&path=tmp")
        self.assertEqual(empty.status_code, 200)

        self.client.post(
            "/api/v1/materials/folder", json={"scope": "public", "name": "full"}
        )
        self._create_file("x.txt", "", parent="full")
        busy = self.client.delete("/api/v1/materials/folder?scope=public&path=full")
        self.assertEqual(busy.status_code, 409)

    def test_delete_root_folder_rejected(self):
        response = self.client.delete("/api/v1/materials/folder?scope=public&path=")
        self.assertEqual(response.status_code, 409)

    # ---- security / validation rejections ----
    def test_reject_traversal_in_name(self):
        for bad in ("../evil", "a/b", "..", "CON.txt"):
            with self.subTest(name=bad):
                response = self._create_file(bad, "x")
                self.assertEqual(response.status_code, 400)

    def test_reject_non_text_extension(self):
        response = self._create_file("movie.mp4", "x")
        self.assertEqual(response.status_code, 400)

    def test_reject_traversal_in_read_path(self):
        # 读取路径里的 .. 会被逐级清洗拒绝。
        response = self.client.get(
            "/api/v1/materials/file?scope=public&path=../secret.txt"
        )
        self.assertEqual(response.status_code, 400)

    def test_read_missing_file_404(self):
        response = self.client.get("/api/v1/materials/file?scope=public&path=nope.txt")
        self.assertEqual(response.status_code, 404)

    def test_create_duplicate_conflict_updates(self):
        # 同名再写走更新语义（created=False），不产生 409。
        self._create_file("dup.txt", "one")
        again = self._create_file("dup.txt", "two")
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.json()["data"]["created"])

    def test_oversized_content_rejected(self):
        original = material_docs.MAX_TEXT_FILE_BYTES
        material_docs.MAX_TEXT_FILE_BYTES = 4
        self.addCleanup(setattr, material_docs, "MAX_TEXT_FILE_BYTES", original)
        response = self._create_file("big.txt", "0123456789")
        self.assertEqual(response.status_code, 400)

    def test_requires_credentials_when_enabled(self):
        config.app["api_key"] = "material-secret"
        anonymous = self.client.get("/api/v1/materials/tree?scope=public")
        self.assertIn(anonymous.status_code, (401, 403))

    # ---- task scope ----
    def test_task_scope_crud_and_unknown_task(self):
        self.task_root = tempfile.mkdtemp(prefix="material-tasks-")
        os.makedirs(os.path.join(self.task_root, "t1"))
        self.addCleanup(shutil.rmtree, self.task_root, True)
        with patch.object(material_docs.utils, "task_dir", return_value=self.task_root):
            created = self.client.post(
                "/api/v1/materials/file",
                json={
                    "scope": "task",
                    "task_id": "t1",
                    "name": "draft.md",
                    "content": "body",
                },
            )
            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["data"]["path"], "draft.md")
            self.assertTrue(
                os.path.isfile(os.path.join(self.task_root, "t1", "draft.md"))
            )

            tree = self.client.get(
                "/api/v1/materials/tree?scope=task&task_id=t1"
            )
            self.assertEqual(tree.status_code, 200)
            self.assertEqual(tree.json()["data"]["items"][0]["name"], "draft.md")

            missing = self.client.get(
                "/api/v1/materials/tree?scope=task&task_id=nope"
            )
            self.assertEqual(missing.status_code, 404)

    def test_task_scope_rejects_traversal_task_id(self):
        # task_id 越出 tasks 根目录必须被拒（400/403/404 任一，不得 200）。
        response = self.client.get("/api/v1/materials/tree?scope=task&task_id=../../etc")
        self.assertNotEqual(response.status_code, 200)

    # ---- reference (copy public -> task) ----
    def test_reference_copies_public_file_into_task(self):
        self._create_file("tpl.md", "# 公共模板")
        self.task_root = tempfile.mkdtemp(prefix="material-ref-")
        os.makedirs(os.path.join(self.task_root, "t9"))
        self.addCleanup(shutil.rmtree, self.task_root, True)
        with patch.object(material_docs.utils, "task_dir", return_value=self.task_root):
            response = self.client.post(
                "/api/v1/materials/reference",
                json={"path": "tpl.md", "task_id": "t9"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()["data"]
            self.assertEqual(data["path"], "tpl.md")
            self.assertTrue(data["created"])
            self.assertEqual(data["source"], "tpl.md")
            with open(
                os.path.join(self.task_root, "t9", "tpl.md"), encoding="utf-8"
            ) as handle:
                self.assertEqual(handle.read(), "# 公共模板")
            # 幂等：再引用一次为更新，不报错。
            again = self.client.post(
                "/api/v1/materials/reference",
                json={"path": "tpl.md", "task_id": "t9"},
            )
            self.assertEqual(again.status_code, 200)
            self.assertFalse(again.json()["data"]["created"])

    def test_reference_missing_source_404(self):
        response = self.client.post(
            "/api/v1/materials/reference",
            json={"path": "ghost.txt", "task_id": "t9"},
        )
        self.assertEqual(response.status_code, 404)

    def test_reference_rejects_non_text_source(self):
        self._create_file("keep.txt", "x")
        # 源名直接为非文本扩展名，在 read_text 阶段即被拒。
        response = self.client.post(
            "/api/v1/materials/reference",
            json={"path": "movie.mp4", "task_id": "t9"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

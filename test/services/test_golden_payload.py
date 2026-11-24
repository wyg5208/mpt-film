"""黄金载荷回归（迁移方案 第七部分）。

用 esbuild 打包真实的前端组装器（frontend/src/stores/params.ts），
把 assembleVideoParams 的默认载荷与全量样例载荷交给后端 pydantic
VideoParams 做字段级 diff，守住约 44 个参数的组装一致性。
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from app.models.schema import VideoParams

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def _norm(value):
    """把 pydantic 模型/枚举归一化为可比较的纯 JSON，并丢弃 None 字段
    （未发出的可选字段与显式 None 在语义上等价）。"""

    def default(o):
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "value"):
            return o.value
        raise TypeError(type(o))

    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if x is not None}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v

    return strip(json.loads(json.dumps(value, default=default)))


def _schema_default(field):
    if field.default_factory is not None:
        return field.default_factory()
    return field.default


def _find_node() -> str | None:
    node = shutil.which("node")
    if node:
        return node
    fallback = Path(r"D:\Program Files\nodejs\node.exe")
    return str(fallback) if fallback.exists() else None


class TestGoldenPayload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = _find_node()
        if cls.node is None or not FRONTEND_DIR.is_dir():
            raise unittest.SkipTest("node or frontend/ unavailable")
        result = subprocess.run(
            [cls.node, str(FRONTEND_DIR / "scripts" / "golden-payload.mjs")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(FRONTEND_DIR),
        )
        if result.returncode != 0:
            raise AssertionError(f"golden-payload.mjs failed: {result.stderr}")
        cls.payload = json.loads(result.stdout)

    def test_field_names_match_schema_minus_script_plan(self):
        schema_fields = set(VideoParams.model_fields.keys())
        frontend_fields = set(self.payload["field_names"])
        # script_plan 为流水线内部字段，前端手工组装刻意排除。
        self.assertEqual(schema_fields - frontend_fields, {"script_plan"})
        self.assertFalse(frontend_fields - schema_fields)

    def test_default_payload_validates_and_matches_schema_defaults(self):
        body = self.payload["default_payload"]
        params = VideoParams.model_validate(body)
        for key, value in body.items():
            self.assertEqual(
                getattr(params, key),
                value,
                msg=f"{key} round-trip mismatch",
            )
        # 前端默认值必须等于 schema 默认值（null 字段被丢弃后由 pydantic 填充）。
        emitted = set(body.keys())
        for name, field in VideoParams.model_fields.items():
            if name == "script_plan":
                continue
            default = field.default
            if field.is_required():
                # 必填字段（video_subject）由前端显式发出，不等 pydantic 报错。
                self.assertIn(
                    name, emitted, msg=f"{name} is required, must be emitted"
                )
            elif default is None:
                self.assertNotIn(
                    name, emitted, msg=f"{name} default is None, must be dropped"
                )
            else:
                self.assertIn(name, emitted, msg=f"{name} missing from payload")
                # 前端默认值必须等于 schema 声明的字段默认值。
                self.assertEqual(
                    _norm(_schema_default(field)),
                    _norm(body[name]),
                    msg=f"{name} frontend default diverges from schema",
                )

    def test_sample_payload_round_trips_field_for_field(self):
        body = self.payload["sample_payload"]
        params = VideoParams.model_validate(body)
        dumped = _norm(params.model_dump())
        for key, value in body.items():
            self.assertEqual(
                dumped[key],
                _norm(value),
                msg=f"field {key} diverges between React assembly and pydantic",
            )


if __name__ == "__main__":
    unittest.main()

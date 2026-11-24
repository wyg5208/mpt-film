"""离线导出 FastAPI OpenAPI schema，供前端 codegen（迁移方案 Phase 0.7）。

用法：
    python scripts/export_openapi.py [输出路径]

默认写到 ``frontend/openapi.json``（若该目录不存在则回退到仓库根 openapi.json）。
前端用 ``openapi-typescript`` 从该文件生成 TS 类型，保证契约唯一来源为后端。

只调用 ``app.openapi()`` 构建静态 schema，不启动服务、不触碰外部模型/存储。
"""

import json
import os
import sys

# 允许从仓库根以外的当前工作目录运行脚本。
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app import asgi  # noqa: E402


def _default_output_path() -> str:
    frontend_dir = os.path.join(REPO_ROOT, "frontend")
    if os.path.isdir(frontend_dir):
        return os.path.join(frontend_dir, "openapi.json")
    return os.path.join(REPO_ROOT, "openapi.json")


def main(argv: list[str]) -> int:
    output_path = argv[1] if len(argv) > 1 else _default_output_path()
    schema = asgi.app.openapi()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"exported OpenAPI schema ({len(schema.get('paths', {}))} paths) -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""素材库文档空间服务：公共素材 / 任务素材两作用域内的 TXT/MD 文件与文件夹管理。

素材库页新增"公共素材"TAB（一个跨项目共享的文档空间 ``storage/material_docs``，
与媒体池 ``storage/local_videos`` 平级），并在两作用域内提供 UI 侧的文件管理能力：
创建/编辑/删除 TXT 或 MD 文件、创建/删除空文件夹。作用域根目录：

- ``public``：``storage/material_docs``（跨项目共享，所有任务均可引用）；
- ``task``：``storage/tasks/{task_id}``（与素材库现有任务产物同一目录）。

安全边界与 ``material_upload`` / ``file_security`` 保持同一套纪律：

- 每一级相对路径段都必须通过名称清洗（拒绝路径分隔符、``.``/``..``、控制符与
  双向文本字符、Windows 非法字符与保留设备名、点前缀隐藏名）；
- 组装后的路径再经 ``file_security.resolve_path_within_directory`` 真实路径校验，
  阻断符号链接逃逸与盘符穿越；
- 读写只允许普通文件/真实目录，拒绝链接与特殊文件；
- 文本写入上限 :data:`MAX_TEXT_FILE_BYTES`，临时文件 + ``os.replace`` 原子落盘；
- 文本文件仅接受 ``.txt``/``.md`` 扩展名，读取按 UTF-8 + replace 容错解码。
"""

import os
import tempfile
from typing import Literal

from loguru import logger

from app.utils import file_security, utils
from app.services.material_upload import (
    _UNSAFE_FILENAME_CHARACTERS,
    _WINDOWS_INVALID_FILENAME_CHARS,
    _WINDOWS_RESERVED_FILENAMES,
    MaterialUploadError,
)

# 公共文档空间的根目录名（storage 下），与媒体池 local_videos 平级。
PUBLIC_DOCS_DIR = "material_docs"
TEXT_EXTENSIONS = (".txt", ".md")
# UI 手写的剧本/说明类文本，1 MiB 足够且防止内存与磁盘被大文件滥用。
MAX_TEXT_FILE_BYTES = 1 * 1024 * 1024
# 目录浏览防护：层级深度与单目录条目数上限，避免病态目录拖垮请求。
MAX_TREE_DEPTH = 8
MAX_LISTING_ENTRIES = 2000

Scope = Literal["public", "task"]


class MaterialDocError(ValueError):
    """请求的文件/文件夹名称或路径不满足安全与格式要求。"""

    status_code = 400


class MaterialDocNotFound(MaterialDocError):
    """目标文件或文件夹不存在。"""

    status_code = 404


class MaterialDocConflict(MaterialDocError):
    """目标位置已被占用（重名创建、非空或删除根目录）。"""

    status_code = 409


def public_docs_dir(create: bool = True) -> str:
    """公共文档空间根目录；请求期动态解析，便于测试打桩。"""
    return utils.storage_dir(PUBLIC_DOCS_DIR, create=create)


def scope_root(scope: str, task_id: str = "") -> str:
    """把作用域解析为已校验的根目录真实路径。

    task 作用域的 task_id 必须先落在 tasks 根目录内且真实存在，防止借文档
    接口探测或写入任意目录。
    """
    if scope == "public":
        return public_docs_dir(create=True)
    if scope == "task":
        tasks_root = utils.task_dir()
        try:
            root = file_security.resolve_path_within_directory(
                tasks_root, task_id, require_file=False
            )
        except ValueError as exc:
            raise MaterialDocError(f"invalid task scope: {exc}") from exc
        if not os.path.isdir(root) or os.path.islink(root):
            raise MaterialDocNotFound("task directory does not exist")
        return root
    raise MaterialDocError(f"unknown scope: {scope}")


def _validate_name(name: str) -> str:
    """清洗单级文件/文件夹名，复用素材上传的字符级黑名单。"""
    safe_name = (name or "").strip()
    if (
        not safe_name
        or safe_name in {".", ".."}
        or len(safe_name) > 127
        or "/" in safe_name
        or "\\" in safe_name
        or safe_name.startswith(".")
        or any(character in _UNSAFE_FILENAME_CHARACTERS for character in safe_name)
        or any(character in _WINDOWS_INVALID_FILENAME_CHARS for character in safe_name)
    ):
        raise MaterialDocError("invalid file or folder name")
    # Windows 把扩展名之前的段当作设备名：CON.txt、LPT1.md 无法作为普通文件创建。
    windows_basename = safe_name.split(".", 1)[0].rstrip(" .").upper()
    if windows_basename in _WINDOWS_RESERVED_FILENAMES:
        raise MaterialDocError("invalid file or folder name")
    return safe_name


def normalize_text_name(name: str) -> str:
    """校验文本文件名并补齐扩展名：无后缀补 .txt，仅允许 .txt/.md。"""
    safe_name = _validate_name(name)
    stem, suffix = os.path.splitext(safe_name)
    suffix = suffix.lower()
    if not suffix:
        return f"{safe_name}.txt"
    if suffix not in TEXT_EXTENSIONS:
        raise MaterialDocError("only .txt and .md files are supported")
    return f"{stem}{suffix}"


def resolve_rel(scope: str, task_id: str, rel_path: str) -> str:
    """把作用域 + 相对路径解析为安全真实路径（不要求存在）。

    逐段清洗后拼接，再整体过真实路径校验；既拒绝 ``../`` 穿越，也拒绝段内
    夹带的非法字符。空相对路径表示作用域根目录。
    """
    root = scope_root(scope, task_id)
    segments = (rel_path or "").replace("\\", "/").split("/")
    cleaned: list[str] = []
    for segment in segments:
        if not segment:
            continue
        cleaned.append(_validate_name(segment))
    candidate = os.path.join(root, *cleaned) if cleaned else root
    try:
        return file_security.resolve_path_within_directory(
            root, candidate, require_file=False
        )
    except ValueError as exc:
        raise MaterialDocError(f"path is outside the allowed directory: {exc}") from exc


def _require_type(path: str, *, directory: bool) -> None:
    """确认目标是真实文件/目录，拒绝符号链接与其它特殊类型。"""
    if os.path.islink(path):
        raise MaterialDocError("symbolic links are not allowed")
    if directory:
        if not os.path.isdir(path):
            raise MaterialDocNotFound("folder does not exist")
    elif not os.path.isfile(path):
        raise MaterialDocNotFound("file does not exist")


def _entry_item(root: str, entry: os.DirEntry, *, depth: int) -> dict:
    is_dir = entry.is_dir(follow_symlinks=False)
    stat = entry.stat(follow_symlinks=False)
    return {
        "name": entry.name,
        "path": os.path.relpath(entry.path, root).replace(os.sep, "/"),
        "type": "dir" if is_dir else "file",
        "size": 0 if is_dir else stat.st_size,
        "mtime": int(stat.st_mtime),
        "editable": (not is_dir)
        and os.path.splitext(entry.name)[1].lower() in TEXT_EXTENSIONS,
        "depth": depth,
    }


def list_tree(scope: str, task_id: str = "") -> dict:
    """递归列出作用域内全部文件与文件夹（跳过隐藏项与链接，含防护上限）。"""
    root = scope_root(scope, task_id)
    items: list[dict] = []
    overflow = False
    stack = [(root, 0)]
    while stack:
        current_dir, depth = stack.pop()
        try:
            entries = sorted(
                os.scandir(current_dir),
                key=lambda item: (item.name.casefold(), item.name),
            )
        except OSError as exc:
            logger.warning(f"skip unreadable material doc dir: {current_dir}, error={exc}")
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            if is_dir and os.path.islink(entry.path):
                continue
            if len(items) >= MAX_LISTING_ENTRIES:
                overflow = True
                break
            items.append(_entry_item(root, entry, depth=depth))
            if is_dir and depth + 1 < MAX_TREE_DEPTH:
                stack.append((entry.path, depth + 1))
        if overflow:
            break
    items.sort(key=lambda item: (item["depth"], item["type"] != "dir", item["name"].casefold(), item["name"]))
    return {"root": root, "items": items, "truncated": overflow}


def create_folder(scope: str, task_id: str, name: str, parent_rel: str = "") -> dict:
    """在 parent_rel 下创建空文件夹，重名 409。"""
    safe_name = _validate_name(name)
    root = scope_root(scope, task_id)
    parent = resolve_rel(scope, task_id, parent_rel)
    _require_type(parent, directory=True)
    target = os.path.join(parent, safe_name)
    if os.path.lexists(target):
        raise MaterialDocConflict("folder already exists")
    try:
        os.mkdir(target)
    except OSError as exc:
        raise MaterialDocConflict(f"failed to create folder: {exc}") from exc
    return {"name": safe_name, "path": _rel(target, root)}


def read_text(scope: str, task_id: str, rel_path: str) -> dict:
    """读取 TXT/MD 内容（UTF-8 + replace 容错解码）。"""
    resolved = resolve_rel(scope, task_id, rel_path)
    _check_text_file(rel_path, resolved)
    _require_type(resolved, directory=False)
    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(MAX_TEXT_FILE_BYTES + 1)
    except OSError as exc:
        raise MaterialDocNotFound(f"failed to read file: {exc}") from exc
    return {"path": rel_path, "content": content}


def write_text(
    scope: str, task_id: str, name: str, content: str, parent_rel: str = ""
) -> dict:
    """创建（parent+name 不存在）或更新（同路径已存在为文件）TXT/MD 文件。

    原子落盘：同目录临时文件 + fsync + os.replace；同名已存在则更新（created=False），
    目标为目录/特殊类型时 409。返回的 path 相对作用域根，与树列表一致。
    """
    safe_name = normalize_text_name(name)
    payload = (content or "").encode("utf-8")
    if len(payload) > MAX_TEXT_FILE_BYTES:
        raise MaterialDocError("text file exceeds the size limit")
    root = scope_root(scope, task_id)
    parent = resolve_rel(scope, task_id, parent_rel)
    _require_type(parent, directory=True)
    target = os.path.join(parent, safe_name)
    if os.path.islink(target):
        raise MaterialDocError("symbolic links are not allowed")
    if os.path.isdir(target):
        raise MaterialDocConflict("a folder with the same name exists")
    if os.path.lexists(target) and not os.path.isfile(target):
        # 已存在但既非文件也非目录（链接/特殊类型）：拒绝覆盖。
        raise MaterialDocConflict("target exists and is not a file")
    temp_path = ""
    try:
        descriptor, temp_path = tempfile.mkstemp(
            prefix=".material-doc-", suffix=".part", dir=parent
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        created = not os.path.exists(target)
        os.replace(temp_path, target)
        temp_path = ""
    except OSError as exc:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise MaterialDocConflict(f"failed to write file: {exc}") from exc
    if created:
        logger.info(f"material doc created: scope={scope}, path={_rel(target, root)}")
    else:
        logger.info(f"material doc updated: scope={scope}, path={_rel(target, root)}")
    return {"name": safe_name, "path": _rel(target, root), "created": created}


def reference_file(
    source_path: str,
    task_id: str,
    dest_parent: str = "",
    dest_name: str = "",
    source_scope: str = "public",
    source_task_id: str = "",
) -> dict:
    """把源作用域内的 TXT/MD 文件复制（引用）到目标任务空间。

    复用 read_text + write_text 的全部安全校验：源文件必须存在且为文本，目标经
    任务作用域根校验。目标同名文件已存在则更新（幂等引用）。默认保留源文件名。
    """
    data = read_text(source_scope, source_task_id, source_path)
    name = dest_name or source_path.replace("\\", "/").rstrip("/").split("/")[-1]
    result = write_text("task", task_id, name, data["content"], dest_parent)
    logger.info(
        f"material referenced: source={source_path} (scope={source_scope}) "
        f"-> task={task_id} dest={result['path']}"
    )
    return {"source": source_path, **result}


def delete_file(scope: str, task_id: str, rel_path: str) -> dict:
    """删除作用域内的 TXT/MD 文件（媒体等其它类型不经本接口删除）。"""
    resolved = resolve_rel(scope, task_id, rel_path)
    if not resolved:
        raise MaterialDocError("empty path is not allowed")
    _check_text_file(rel_path, resolved)
    _require_type(resolved, directory=False)
    try:
        os.remove(resolved)
    except OSError as exc:
        raise MaterialDocNotFound(f"failed to delete file: {exc}") from exc
    logger.info(f"material doc deleted: scope={scope}, path={rel_path}")
    return {"path": rel_path, "deleted": True}


def delete_folder(scope: str, task_id: str, rel_path: str) -> dict:
    """删除空文件夹；根目录与含内容目录一律拒绝。"""
    segments = [s for s in (rel_path or "").replace("\\", "/").split("/") if s]
    if not segments:
        raise MaterialDocConflict("cannot delete the scope root")
    resolved = resolve_rel(scope, task_id, rel_path)
    _require_type(resolved, directory=True)
    try:
        os.rmdir(resolved)
    except OSError as exc:
        raise MaterialDocConflict(f"folder is not empty: {exc}") from exc
    logger.info(f"material folder deleted: scope={scope}, path={rel_path}")
    return {"path": rel_path, "deleted": True}


def _check_text_file(rel_path: str, resolved: str) -> None:
    suffix = os.path.splitext(resolved)[1].lower()
    if suffix not in TEXT_EXTENSIONS:
        raise MaterialDocError("only .txt and .md files are supported")
    _ = rel_path


def _rel(target: str, parent: str) -> str:
    return os.path.relpath(target, parent).replace(os.sep, "/")

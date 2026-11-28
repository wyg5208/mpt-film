"""素材库文件管理 API：公共素材共享空间 + 任务/公共两作用域的 TXT/MD 与文件夹 CRUD。

前端素材库页新增"公共素材"TAB（跨项目共享的文档空间，所有任务均可浏览引用），
并在两个 TAB 内提供通过 UI 直接进行的文件与文件夹操作：新建/编辑/删除 TXT 或 MD
文件、新建/删除空文件夹。全部落到 :mod:`app.services.material_docs`，作用域由
``scope``（``public`` / ``task``）+ 可选 ``task_id`` 决定，安全边界见该服务文档。

HTTP 语义：
- 400 名称/路径/扩展名/大小非法（含 ``../`` 穿越，逐级名称清洗先拦截，真实路径
  校验作为二道防线同样回 400）；
- 404 作用域、文件或文件夹不存在；
- 409 重名、非空目录、删除根目录等冲突。
"""

from typing import Literal

from fastapi import Depends, Query, Request
from pydantic import BaseModel, Field
from loguru import logger

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import material_docs
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

Scope = Literal["public", "task"]


class FolderCreateRequest(BaseModel):
    scope: Scope = "public"
    task_id: str = ""
    name: str = Field(default="", description="新文件夹名（单级，无路径分隔符）")
    parent: str = Field(default="", description="父文件夹相对路径，空为作用域根")


class FileCreateRequest(BaseModel):
    scope: Scope = "public"
    task_id: str = ""
    name: str = Field(default="", description="文件名，缺扩展名时补 .txt，仅允许 .txt/.md")
    content: str = Field(default="", description="文件文本内容")
    parent: str = Field(default="", description="父文件夹相对路径，空为作用域根")


class FileUpdateRequest(BaseModel):
    scope: Scope = "public"
    task_id: str = ""
    path: str = Field(default="", description="相对作用域根的文件路径（含扩展名）")
    content: str = Field(default="", description="新的完整文本内容")


class FileReferenceRequest(BaseModel):
    path: str = Field(default="", description="公共素材（源）相对路径")
    task_id: str = Field(default="", description="目标任务 ID（引用目标）")
    source_scope: Scope = Field(
        default="public", description="源作用域，默认从公共素材引用"
    )
    source_task_id: str = Field(default="", description="源为 task 作用域时的任务 ID")
    parent: str = Field(default="", description="目标任务内的目标文件夹相对路径")
    name: str = Field(default="", description="引用后的文件名，留空保留源名")


def _fail(request: Request, exc: Exception) -> HttpException:
    """把服务层异常翻译成带 request_id 与稳定状态码的 HttpException。"""
    request_id = base.get_task_id(request)
    status = getattr(exc, "status_code", 400)
    logger.warning(
        f"material doc operation rejected: request_id={request_id}, error={exc}"
    )
    return HttpException(
        task_id=request_id, status_code=status, message=f"{request_id}: {exc}"
    )


def _split_parent(path: str) -> tuple[str, str]:
    """把作用域内相对路径拆成 (父目录相对路径, 末段名)。"""
    normalized = (path or "").replace("\\", "/").strip("/")
    if "/" in normalized:
        parent, name = normalized.rsplit("/", 1)
        return parent, name
    return "", normalized


@router.get("/materials/tree", summary="List a material scope file tree")
def get_material_tree(
    request: Request,
    scope: Scope = Query("public", description="作用域：public 公共素材 / task 任务素材"),
    task_id: str = Query("", description="scope=task 时必填的任务 ID"),
):
    try:
        data = material_docs.list_tree(scope, task_id)
    except ValueError as exc:
        raise _fail(request, exc)
    # 不把服务器绝对路径（root）返回给客户端，只回相对项。
    return utils.get_response(
        200,
        {"scope": scope, "items": data["items"], "truncated": data["truncated"]},
    )


@router.get("/materials/file", summary="Read a material TXT/MD file")
def get_material_file(
    request: Request,
    path: str = Query(..., description="相对作用域根的文件路径"),
    scope: Scope = Query("public"),
    task_id: str = Query(""),
):
    try:
        data = material_docs.read_text(scope, task_id, path)
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": scope, **data})


@router.post("/materials/folder", summary="Create an empty folder in a material scope")
def post_material_folder(request: Request, body: FolderCreateRequest):
    try:
        data = material_docs.create_folder(
            body.scope, body.task_id, body.name, body.parent
        )
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": body.scope, **data})


@router.post("/materials/file", summary="Create a TXT/MD file in a material scope")
def post_material_file(request: Request, body: FileCreateRequest):
    try:
        data = material_docs.write_text(
            body.scope, body.task_id, body.name, body.content, body.parent
        )
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": body.scope, **data})


@router.put("/materials/file", summary="Update a TXT/MD file in a material scope")
def put_material_file(request: Request, body: FileUpdateRequest):
    parent, name = _split_parent(body.path)
    if not name:
        raise _fail(request, material_docs.MaterialDocError("empty file path"))
    try:
        # 更新走同一路径写入：name 已含扩展名，normalize_text_name 原样保留。
        data = material_docs.write_text(
            body.scope, body.task_id, name, body.content, parent
        )
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": body.scope, **data})


@router.post("/materials/reference", summary="Reference (copy) a material file into a task")
def post_material_reference(request: Request, body: FileReferenceRequest):
    """把公共（或另一任务）内的 TXT/MD 文件复制引用到指定任务空间。

    目标同名文件已存在时覆盖（幂等引用）；返回的 path 为相对目标任务根的路径。
    """
    try:
        data = material_docs.reference_file(
            body.path,
            body.task_id,
            dest_parent=body.parent,
            dest_name=body.name,
            source_scope=body.source_scope,
            source_task_id=body.source_task_id,
        )
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, data)


@router.delete("/materials/file", summary="Delete a TXT/MD file in a material scope")
def delete_material_file(
    request: Request,
    path: str = Query(..., description="相对作用根的文件路径"),
    scope: Scope = Query("public"),
    task_id: str = Query(""),
):
    try:
        data = material_docs.delete_file(scope, task_id, path)
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": scope, **data})


@router.delete("/materials/folder", summary="Delete an empty folder in a material scope")
def delete_material_folder(
    request: Request,
    path: str = Query(..., description="相对作用域根的文件夹路径"),
    scope: Scope = Query("public"),
    task_id: str = Query(""),
):
    try:
        data = material_docs.delete_folder(scope, task_id, path)
    except ValueError as exc:
        raise _fail(request, exc)
    return utils.get_response(200, {"scope": scope, **data})

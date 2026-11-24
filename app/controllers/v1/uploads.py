"""文件上传 API（迁移方案 1.7）。

只接受 multipart 文件并返回可写入 ``VideoParams`` 的服务端存储标识 ——
绝不接受客户端原始路径；API 创建的任务继续保持
``allow_server_file_input=False``。素材通道复用现成的
``material_upload`` 服务（文件名清洗、媒体校验、原子落盘）。
"""

import io
import os
from uuid import uuid4

from fastapi import Depends, File, Request, UploadFile
from loguru import logger

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.services import material_upload as material_upload_service
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

# 配音参考音频：VoxCPM 参考/提示音只需常见无损/有损音频容器。
VOICE_REFERENCE_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
MAX_VOICE_REFERENCE_BYTES = 50 * 1024 * 1024
# 素材上传沿用 material_upload 的内部上限，这里只挡明显的超大请求体，
# 避免把整段视频读进内存（方案 1.7：体积上限双层防线之一）。
MAX_MATERIAL_BYTES = 500 * 1024 * 1024


def _voice_reference_dir() -> str:
    return utils.storage_dir("voice_reference", create=True)


def _read_capped(upload: UploadFile, limit: int, request: Request, label: str) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=413,
            message=f"{label} exceeds the size limit",
        )
    return data


@router.post(
    "/uploads/voice-reference",
    summary="Upload a voice reference/prompt audio for custom dubbing",
)
def upload_voice_reference(request: Request, file: UploadFile = File(...)):
    request_id = base.get_task_id(request)
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in VOICE_REFERENCE_SUFFIXES:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"unsupported audio suffix: {suffix or '(none)'}",
        )
    data = _read_capped(file, MAX_VOICE_REFERENCE_BYTES, request, "voice reference")
    if not data:
        raise HttpException(
            task_id=request_id, status_code=400, message="voice reference is empty"
        )
    stored_name = f"{uuid4().hex}{suffix}"
    destination = os.path.join(_voice_reference_dir(), stored_name)
    temp_path = f"{destination}.part"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    except OSError as exc:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        logger.error(f"voice reference upload failed: request_id={request_id}, error={exc}")
        raise HttpException(
            task_id=request_id, status_code=500, message="voice reference upload failed"
        )
    # 返回服务端存储标识（绝对路径），供 VideoParams 自定义配音字段引用。
    return utils.get_response(200, {"file": stored_name, "path": destination})


@router.post(
    "/uploads/material", summary="Upload a local video/image material"
)
def upload_material(request: Request, file: UploadFile = File(...)):
    request_id = base.get_task_id(request)
    data = _read_capped(file, MAX_MATERIAL_BYTES, request, "material")
    if not data:
        raise HttpException(
            task_id=request_id, status_code=400, message="material file is empty"
        )

    try:
        stored_path = material_upload_service.save_material_upload(
            file.filename or "upload", io.BytesIO(data)
        )
    except material_upload_service.MaterialUploadError as exc:
        logger.warning(
            f"uploads/material rejected: request_id={request_id}, error={exc}"
        )
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: {exc}"
        )
    except material_upload_service.MaterialServiceError as exc:
        logger.error(
            f"uploads/material failed: request_id={request_id}, error={exc}"
        )
        raise HttpException(
            task_id=request_id, status_code=500, message="material upload failed"
        )
    return utils.get_response(
        200,
        {
            "path": stored_path,
            "name": os.path.basename(stored_path),
        },
    )

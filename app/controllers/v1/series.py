"""系列/剧集管理 API（迁移方案 1.5）。

对 ``app/services/series_store.py`` 的薄封装：系列 CRUD、角色、参考图
（含人工锁定）与剧集状态机。服务层规则原样透传：
- 人工锁定的参考图删除 → 409（AI 不得覆盖人工选择）；
- 剧集状态仅允许前向迁移，非法迁移 → 409；
- 参考图文件下发路径必须经 ``file_security.resolve_path_within_directory``
  严格限定在系列目录内，越界 → 404/403。
"""

import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import Series, SeriesCharacter, SeriesEpisode
from app.services import series_store
from app.utils import file_security, utils

router = new_router(dependencies=[Depends(base.verify_token)])

# 参考图上传体积上限：只收图片，拒绝超大文件打满后端内存（方案 1.7 同源策略）。
MAX_REFERENCE_IMAGE_BYTES = 20 * 1024 * 1024
_ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class SeriesCreateRequest(BaseModel):
    title: str = ""
    genre_template: str = "custom"


class SeriesUpdateRequest(BaseModel):
    title: str | None = None
    genre_template: str | None = None
    style_bible: dict | None = None


class CharacterCreateRequest(BaseModel):
    name: str = ""
    role: str = "support"
    appearance_prompt: str = ""
    seed: int = Field(default=0, ge=0, le=0xFFFFFFFF)
    voice_name: str = ""
    personality: str = ""


class EpisodeCreateRequest(BaseModel):
    title: str = ""
    logline: str = ""
    hook: str = ""


class EpisodeStatusRequest(BaseModel):
    status: str


class BindPlanRequest(BaseModel):
    episode_id: str
    plan_id: str


def _series_or_404(request: Request, sid: str):
    try:
        series = series_store.load_series(sid)
    except series_store.SeriesStoreError as error:
        # fail-closed：损坏档案不透传细节，只报系列不可用。
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=500,
            message=f"series档案不可用: {error}",
        )
    if series is None:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=f"series not found: {sid}",
        )
    return series


def _conflict(request: Request, error: Exception) -> HttpException:
    return HttpException(
        task_id=base.get_task_id(request),
        status_code=409,
        message=str(error),
    )


def _store_error_to_http(request: Request, error: series_store.SeriesStoreError):
    message = str(error)
    if "not found" in message.lower():
        return HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message=message,
        )
    if "locked" in message.lower() or "cannot move" in message.lower():
        # 人工锁定删除与非法状态迁移都是冲突语义（方案 1.5）。
        return _conflict(request, error)
    return HttpException(
        task_id=base.get_task_id(request),
        status_code=400,
        message=message,
    )


@router.get("/series", summary="List saved series (manifest summaries)")
def list_series(request: Request):
    return utils.get_response(200, {"series": series_store.list_series()})


@router.post("/series", summary="Create a series")
def create_series(request: Request, body: SeriesCreateRequest):
    try:
        series = Series(
            id=series_store.new_series_id(),
            title=body.title,
            genre_template=body.genre_template,
        )
    except ValidationError as error:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message=f"invalid series payload: {error.errors()[0].get('loc')}",
        )
    series_store.save_series(series)
    return utils.get_response(200, series.model_dump())


@router.get("/series/{sid}", summary="Get one series")
def get_series(request: Request, sid: str):
    return utils.get_response(200, _series_or_404(request, sid).model_dump())


@router.put("/series/{sid}", summary="Partially update series fields")
def update_series_endpoint(request: Request, sid: str, body: SeriesUpdateRequest):
    def mutate(series: Series) -> None:
        if body.title is not None:
            series.title = body.title
        if body.genre_template is not None:
            series.genre_template = body.genre_template
        if body.style_bible is not None:
            series.style_bible = series.style_bible.__class__(**body.style_bible)

    try:
        series = series_store.update_series(sid, mutate)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    return utils.get_response(200, series.model_dump())


@router.delete("/series/{sid}", summary="Delete a series directory")
def delete_series(request: Request, sid: str):
    _series_or_404(request, sid)
    shutil.rmtree(series_store.series_dir(sid))
    return utils.get_response(200, {"deleted": sid})


@router.get("/series/{sid}/characters", summary="List characters")
def list_characters(request: Request, sid: str):
    series = _series_or_404(request, sid)
    return utils.get_response(
        200, {"characters": [c.model_dump() for c in series.characters]}
    )


@router.post("/series/{sid}/characters", summary="Add a character")
def add_character(request: Request, sid: str, body: CharacterCreateRequest):
    character = SeriesCharacter(
        id=f"ch-{uuid4().hex[:12]}",
        name=body.name,
        role=body.role,
        appearance_prompt=body.appearance_prompt,
        seed=body.seed,
        voice_name=body.voice_name,
        personality=body.personality,
    )

    def mutate(series: Series) -> None:
        if any(c.id == character.id for c in series.characters):
            raise series_store.SeriesStoreError(
                f"character id collision: {character.id}"
            )
        series.characters.append(character)

    try:
        series = series_store.update_series(sid, mutate)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    return utils.get_response(200, character.model_dump())


@router.post(
    "/series/{sid}/characters/{cid}/images", summary="Upload a reference image"
)
def upload_reference_image(
    request: Request, sid: str, cid: str, file: UploadFile = File(...)
):
    data = file.file.read(MAX_REFERENCE_IMAGE_BYTES + 1)
    if len(data) > MAX_REFERENCE_IMAGE_BYTES:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=413,
            message="reference image exceeds the size limit",
        )
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_IMAGE_SUFFIXES:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message=f"unsupported image suffix: {suffix or '(none)'}",
        )
    try:
        relative = series_store.add_reference_image(sid, cid, data, suffix=suffix)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    return utils.get_response(200, {"path": relative})


@router.delete(
    "/series/{sid}/characters/{cid}/images/{name}",
    summary="Remove a reference image (locked images rejected)",
)
def remove_reference_image(request: Request, sid: str, cid: str, name: str):
    try:
        series_store.remove_reference_image(sid, cid, name)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    return utils.get_response(200, {"removed": name})


@router.put(
    "/series/{sid}/characters/{cid}/images/{name}/lock",
    summary="Human-lock a reference image",
)
def lock_reference_image(request: Request, sid: str, cid: str, name: str):
    _series_or_404(request, sid)
    series_store.lock_reference_image(sid, cid, name)
    return utils.get_response(200, {"locked": name})


@router.delete(
    "/series/{sid}/characters/{cid}/images/{name}/lock",
    summary="Remove the human lock from a reference image",
)
def unlock_reference_image(request: Request, sid: str, cid: str, name: str):
    _series_or_404(request, sid)
    series_store.unlock_reference_image(sid, cid, name)
    return utils.get_response(200, {"locked": None})


@router.get(
    "/series/{sid}/characters/{cid}/images/{name}",
    summary="Serve a reference image (strictly within series dir)",
)
def get_reference_image(request: Request, sid: str, cid: str, name: str):
    root = series_store.series_dir(sid)
    try:
        resolved = file_security.resolve_path_within_directory(
            str(root), f"characters/{cid}/{name}", require_file=True
        )
    except ValueError:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=404,
            message="reference image not found",
        )
    return FileResponse(resolved)


@router.post("/series/{sid}/episodes", summary="Append an episode (next seq)")
def add_episode(request: Request, sid: str, body: EpisodeCreateRequest):
    def mutate(series: Series) -> None:
        next_seq = max((e.seq for e in series.episodes), default=0) + 1
        series.episodes.append(
            SeriesEpisode(
                id=f"ep-{uuid4().hex[:12]}",
                seq=next_seq,
                title=body.title,
                logline=body.logline,
                hook=body.hook,
            )
        )

    try:
        series = series_store.update_series(sid, mutate)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    return utils.get_response(200, series.episodes[-1].model_dump())


@router.patch(
    "/series/{sid}/episodes/{eid}/status", summary="Forward-only status transition"
)
def set_episode_status(request: Request, sid: str, eid: str, body: EpisodeStatusRequest):
    try:
        series = series_store.set_episode_status(sid, eid, body.status)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    episode = next(e for e in series.episodes if e.id == eid)
    return utils.get_response(200, episode.model_dump())


@router.post("/series/{sid}/bind-plan", summary="Bind an episode to a plan")
def bind_plan(request: Request, sid: str, body: BindPlanRequest):
    try:
        series = series_store.bind_episode_plan(sid, body.episode_id, body.plan_id)
    except series_store.SeriesStoreError as error:
        raise _store_error_to_http(request, error)
    episode = next(e for e in series.episodes if e.id == body.episode_id)
    return utils.get_response(200, episode.model_dump())

"""脚本方案草稿库 REST 层（专业短剧「脚本方案」页的 SPA 后端）。

与 webui/Main.py `_render_plan_page` 对齐的草稿 CRUD/编辑语义：
- 编辑（设置项/镜头字段/调序/增删镜头）一律回退 draft 并 revision++；
- confirm 只置 confirmed（付费门禁重新生效的入口），revision 不变；
- 调序/删镜头后共享边界帧约束解除（shared_with_prev=False，relation 重置）；
- execute：至少一个镜头有旁白 → 确认 → 按 Main.py 的对齐规则组装
  TaskVideoRequest（标题/画幅/音色/目标时长随方案，本地引擎镜头全选时
  video_source=local）→ 复用 video.create_task 的排队链路。
草稿落盘由 app/services/plan_store 负责（storage/plans/{plan_id}.json）。
"""

from typing import List, Optional

from fastapi import Depends, Request
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from app.config import config
from app.controllers import base
from app.controllers.v1.base import new_router
from app.controllers.v1 import video as video_controller
from app.models.exception import HttpException
from app.models.schema import (
    Series,
    SeriesCharacter,
    SeriesEpisode,
    ScriptPlan,
    ScriptScene,
    TaskVideoRequest,
    estimate_scene_duration,
)
from app.services import llm, plan_store, series_store
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

# 与 Main.py PLAN_ENGINE_OPTIONS / PLAN_TRANSITION_OPTIONS 一致；模型层
# Literal 也会拒绝越界值，这里显式白名单以便 400 而不是 500。
PLAN_ENGINE_OPTIONS = ("stock", "local_fl2v", "local_i2v")
PLAN_TRANSITION_OPTIONS = ("none", "fade", "slide", "zoom", "match_cut")
SCENE_PATCH_FIELDS = frozenset(
    {
        "locked",
        "narration",
        "est_duration",
        "visual",
        "keywords",
        "engine",
        "transition_to_next",
    }
)
SETTING_PATHS = frozenset(
    {
        "title",
        "logline",
        "quality_tier",
        "voice.name",
        "voice.rate",
        "style.tone",
        "style.palette",
        "style.camera",
    }
)
_STOCK_VIDEO_SOURCES = ("pexels", "pixabay", "coverr")


def _task_id(request: Request) -> str:
    return base.get_task_id(request)


def _bad(request: Request, message: str, status_code: int = 400):
    raise HttpException(
        task_id=_task_id(request), status_code=status_code, message=message
    )


def _load_or_404(request: Request, plan_id: str) -> dict:
    try:
        payload = plan_store.load_plan(plan_id)
    except plan_store.PlanStoreError as exc:
        _bad(request, f"plan draft {plan_id} unreadable: {exc}", 400)
    if payload is None:
        _bad(request, f"plan draft not found: {plan_id}", 404)
    return payload


def _plan_detail(payload: dict) -> dict:
    """草稿 payload + 服务端计算的派生值（estimated/warnings），UI 免复制。"""
    plan = ScriptPlan.model_validate(payload)
    return {
        "plan": payload,
        "estimated_duration": plan.estimated_total_duration(),
        "duration_warnings": plan.duration_warnings(),
    }


def _validate(request: Request, payload: dict) -> ScriptPlan:
    try:
        return ScriptPlan.model_validate(payload)
    except ValidationError as exc:
        _bad(request, f"script plan validation failed: {exc}")


def _apply_edit_semantics(plan: ScriptPlan, current_revision: int) -> None:
    """编辑一律回退 draft 并 revision++（confirm 走 confirm 语义，不经这里）。"""
    plan.status = "draft"
    plan.revision = current_revision + 1


def _save(plan: ScriptPlan, plan_id: str) -> dict:
    saved_id = plan_store.save_plan(
        plan.model_dump(mode="json", by_alias=True), plan_id=plan_id
    )
    return plan_store.load_plan(saved_id)


class PlanGenerateRequest(BaseModel):
    """空态「AI 生成方案」请求；同步调用 llm.generate_script_plan。"""

    video_subject: str = Field(min_length=1, max_length=2000)
    language: str = ""
    target_duration: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    scene_count: Optional[int] = Field(default=None, ge=1, le=30)


class PlanImportRequest(BaseModel):
    """JSON 导入：强制 draft + revision++（与 Main.py 导入语义一致）。"""

    plan: dict = Field(min_length=1)


class PlanReplaceRequest(BaseModel):
    """整份草稿替换（导入/外部编辑器回写）；confirm=True 仅置确认。"""

    plan: dict = Field(min_length=1)
    confirm: bool = False


class PlanSettingPatchRequest(BaseModel):
    """方案设置项单字段修改；path 白名单见 SETTING_PATHS。"""

    path: str
    value: object = None


class PlanScenePatchRequest(BaseModel):
    """镜头单字段修改；field 白名单见 SCENE_PATCH_FIELDS。"""

    field: str
    value: object = None


class PlanSceneMoveRequest(BaseModel):
    delta: int = Field(ge=-1, le=1)


class LocalBundleRequest(BaseModel):
    pass


@router.get("/plans", summary="List script plan drafts")
def list_plans(request: Request):
    return utils.get_response(200, {"plans": plan_store.list_plans()})


@router.get("/plans/{plan_id}", summary="Load one script plan draft")
def get_plan(request: Request, plan_id: str):
    payload = _load_or_404(request, plan_id)
    return utils.get_response(200, _plan_detail(payload))


@router.post("/plans/generate", summary="Generate a new script plan draft with AI")
def generate_plan(request: Request, body: PlanGenerateRequest):
    subject = body.video_subject.strip()
    if not subject:
        _bad(request, "video_subject is required")
    generated = llm.generate_script_plan(
        video_subject=subject,
        language=str(config.app.get("video_language", "") or ""),
        target_duration=body.target_duration,
        scene_count=body.scene_count,
    )
    if generated is None:
        _bad(request, "script plan generation failed", 502)
    try:
        plan_id = plan_store.save_plan(generated)
    except plan_store.PlanStoreError as exc:
        _bad(request, f"script plan validation failed: {exc}")
    return utils.get_response(
        200, {"plan_id": plan_id, **_plan_detail(plan_store.load_plan(plan_id))}
    )


@router.post("/plans", summary="Import a script plan draft from JSON")
def import_plan(request: Request, body: PlanImportRequest):
    plan = _validate(request, body.plan)
    # 与 Main.py 一致：导入即回草稿并 revision++，避免覆盖已确认版本号。
    plan.status = "draft"
    plan.revision = plan.revision + 1
    try:
        plan_id = plan_store.save_plan(plan.model_dump(mode="json", by_alias=True))
    except plan_store.PlanStoreError as exc:
        _bad(request, f"script plan validation failed: {exc}")
    return utils.get_response(
        200, {"plan_id": plan_id, **_plan_detail(plan_store.load_plan(plan_id))}
    )


@router.put("/plans/{plan_id}", summary="Replace a script plan draft")
def replace_plan(request: Request, plan_id: str, body: PlanReplaceRequest):
    current = _load_or_404(request, plan_id)
    plan = _validate(request, body.plan)
    if body.confirm:
        plan.status = "confirmed"
    else:
        _apply_edit_semantics(plan, int(current.get("revision", 1)))
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


@router.patch("/plans/{plan_id}/settings", summary="Patch one plan setting field")
def patch_plan_setting(request: Request, plan_id: str, body: PlanSettingPatchRequest):
    if body.path not in SETTING_PATHS:
        _bad(request, f"unknown plan setting path: {body.path}")
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    target = plan
    parts = body.path.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    value = body.value
    if parts[-1] == "rate":
        try:
            value = float(value)
        except (TypeError, ValueError):
            _bad(request, f"invalid value for {body.path}: {value!r}")
    else:
        value = str(value or "")
    setattr(target, parts[-1], value)
    _apply_edit_semantics(plan, int(payload.get("revision", 1)))
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


def _patch_scene_value(request: Request, scene: ScriptScene, field: str, value):
    if field == "locked":
        scene.locked = bool(value)
    elif field == "keywords":
        scene.keywords = [
            term.strip() for term in str(value or "").split(",") if term.strip()
        ]
    elif field == "est_duration":
        try:
            scene.est_duration = float(value)
        except (TypeError, ValueError):
            _bad(request, f"invalid value for est_duration: {value!r}")
    elif field == "engine":
        if value not in PLAN_ENGINE_OPTIONS:
            _bad(request, f"invalid scene engine: {value!r}")
        scene.engine = value
    elif field == "transition_to_next":
        if value not in PLAN_TRANSITION_OPTIONS:
            _bad(request, f"invalid scene transition: {value!r}")
        scene.transition_to_next = value
    else:  # narration / visual
        setattr(scene, field, str(value or ""))
        if field == "narration":
            # 与 Main.py `_plan_scene_field_changed` 一致：旁白编辑后按
            # 语速经验值回填预估时长（估不出 >0 时保留原值）。
            estimated = estimate_scene_duration(scene.narration)
            if estimated > 0:
                scene.est_duration = estimated


@router.patch(
    "/plans/{plan_id}/scenes/{scene_id}", summary="Patch one scene field"
)
def patch_plan_scene(
    request: Request, plan_id: str, scene_id: str, body: PlanScenePatchRequest
):
    if body.field not in SCENE_PATCH_FIELDS:
        _bad(request, f"unknown scene field: {body.field}")
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    scene = next((s for s in plan.scenes if s.id == scene_id), None)
    if scene is None:
        _bad(request, f"scene not found: {scene_id}", 404)
    _patch_scene_value(request, scene, body.field, body.value)
    _apply_edit_semantics(plan, int(payload.get("revision", 1)))
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


def _renumber_after_structure_change(plan: ScriptPlan) -> None:
    """调序/删除后重编号，并解除共享边界帧约束（关键帧链后续重建）。"""
    for order, scene in enumerate(plan.scenes, start=1):
        scene.order = order
        scene.keyframe.shared_with_prev = False
        scene.relation_to_prev = "establish" if order == 1 else "unknown"


@router.post(
    "/plans/{plan_id}/scenes/{scene_id}/move", summary="Reorder a scene"
)
def move_plan_scene(
    request: Request, plan_id: str, scene_id: str, body: PlanSceneMoveRequest
):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    index = next((i for i, s in enumerate(plan.scenes) if s.id == scene_id), None)
    if index is None:
        _bad(request, f"scene not found: {scene_id}", 404)
    target = index + body.delta
    if 0 <= target < len(plan.scenes):
        scenes = plan.scenes
        scenes[index], scenes[target] = scenes[target], scenes[index]
        _renumber_after_structure_change(plan)
        _apply_edit_semantics(plan, int(payload.get("revision", 1)))
        return utils.get_response(
            200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))}
        )
    # 越界移动视作无操作：返回当前草稿，不产生 revision 噪音。
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(payload)})


@router.post("/plans/{plan_id}/scenes", summary="Append a new scene")
def add_plan_scene(request: Request, plan_id: str):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    used = {s.id for s in plan.scenes}
    index = len(plan.scenes) + 1
    while f"s{index}" in used:
        index += 1
    plan.scenes.append(
        ScriptScene(id=f"s{index}", order=len(plan.scenes) + 1, est_duration=5.0)
    )
    _renumber_after_structure_change(plan)
    _apply_edit_semantics(plan, int(payload.get("revision", 1)))
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


@router.delete(
    "/plans/{plan_id}/scenes/{scene_id}", summary="Delete a scene"
)
def delete_plan_scene(request: Request, plan_id: str, scene_id: str):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    if len(plan.scenes) <= 1:
        _bad(request, "a plan must keep at least one scene")
    plan.scenes = [s for s in plan.scenes if s.id != scene_id]
    _renumber_after_structure_change(plan)
    _apply_edit_semantics(plan, int(payload.get("revision", 1)))
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


@router.post("/plans/{plan_id}/regenerate", summary="Regenerate the plan with AI")
def regenerate_plan(request: Request, plan_id: str):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    generated = llm.generate_script_plan(
        video_subject=plan.title or plan.logline,
        language=str(config.app.get("video_language", "") or ""),
        target_duration=plan.target_duration,
        aspect=plan.aspect,
        voice_name=plan.voice.name,
        series_id=plan.series_id,
        episode_id=plan.episode_id,
    )
    if generated is None:
        _bad(request, "script plan generation failed", 502)
    new_plan = _validate(request, generated)
    # 锁定镜头按 order 原位保留（与 Main.py 重生成语义一致）。
    locked_old = [s for s in plan.scenes if s.locked]
    for old_scene in locked_old:
        index = old_scene.order - 1
        if index < len(new_plan.scenes):
            target = new_plan.scenes[index]
            target.narration = old_scene.narration
            target.visual = old_scene.visual
            target.keywords = list(old_scene.keywords)
            target.est_duration = old_scene.est_duration
            target.locked = True
    _apply_edit_semantics(new_plan, plan.revision)
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(new_plan, plan_id))})


@router.post("/plans/{plan_id}/confirm", summary="Confirm a script plan draft")
def confirm_plan(request: Request, plan_id: str):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    plan.status = "confirmed"
    return utils.get_response(200, {"plan_id": plan_id, **_plan_detail(_save(plan, plan_id))})


@router.delete("/plans/{plan_id}", summary="Delete a script plan draft")
def delete_plan(request: Request, plan_id: str):
    deleted = plan_store.delete_plan(plan_id)
    return utils.get_response(200, {"deleted": bool(deleted)})


@router.post("/plans/{plan_id}/execute", summary="Confirm and generate video from plan")
def execute_plan(request: Request, plan_id: str):
    payload = _load_or_404(request, plan_id)
    plan = _validate(request, payload)
    # 与 Main.py 相同的门禁：旁白是一次整篇 TTS，必须至少一个镜头可读。
    if not any(scene.narration.strip() for scene in plan.scenes):
        _bad(request, "plan requires at least one scene with narration")
    plan.status = "confirmed"
    plan_store.save_plan(plan.model_dump(mode="json", by_alias=True), plan_id=plan_id)

    body = TaskVideoRequest(
        video_subject=plan.title or plan.logline or plan_id,
        video_aspect=plan.aspect,
        plan_target_duration=plan.target_duration,
        voice_name=plan.voice.name,
        voice_rate=plan.voice.rate,
        script_plan=plan,
    )
    # 素材源对齐 Main.py：本地引擎镜头全选 → local；否则只放行 stock 源。
    if all(scene.engine in {"local_fl2v", "local_i2v"} for scene in plan.scenes):
        body.video_source = "local"
    elif body.video_source not in _STOCK_VIDEO_SOURCES:
        body.video_source = "pexels"
    return video_controller.create_task(request, body, stop_at="video")


# ---------------------------------------------------------------------------
# 创作向导（Main.py `_render_wizard_page` 的联动后端）：一个故事创意 →
# 同步生成分镜方案草稿 + 建系列（N 集剧集 + 角色档案）+ 绑定 ep1 → plan。
# 与脚本方案页共用同一草稿库，向导产物直接出现在「脚本方案」页的选择器里。
# ---------------------------------------------------------------------------

# 与 Main.py WIZARD_GENRES 一致；值域同时受 Series.genre_template Literal 约束。
WIZARD_GENRES = (
    "urban_revenge",
    "period_romance",
    "suspense",
    "healing",
    "scifi",
    "custom",
)


class WizardCharacterInput(BaseModel):
    name: str = ""
    voice_name: str = ""
    appearance_prompt: str = ""


class WizardGenerateRequest(BaseModel):
    story_idea: str = ""
    genre: str = "urban_revenge"
    episode_duration: float = Field(default=60.0, ge=30, le=300, allow_inf_nan=False)
    episode_count: int = Field(default=3, ge=1, le=12)
    characters: List[WizardCharacterInput] = Field(default_factory=list)


@router.post(
    "/wizard/generate",
    summary="Generate the first-episode plan draft plus its series",
)
def wizard_generate(request: Request, body: WizardGenerateRequest):
    idea = body.story_idea.strip()
    if not idea:
        _bad(request, "wizard story idea is required")
    if body.genre not in WIZARD_GENRES:
        _bad(request, f"unknown wizard genre: {body.genre}")
    generated = llm.generate_script_plan(
        video_subject=idea,
        language=str(config.app.get("video_language", "") or ""),
        target_duration=body.episode_duration,
        aspect="9:16",
    )
    if generated is None:
        _bad(request, "script plan generation failed", 502)
    # 与 Main.py 相同：空名角色剔除；第一集标题用创意前 40 字。
    characters = [
        character for character in body.characters if character.name.strip()
    ]
    try:
        series = Series(
            id=series_store.new_series_id(),
            title=idea[:60],
            genre_template=body.genre,
            characters=[
                SeriesCharacter(
                    id=f"c{index}",
                    name=character.name.strip(),
                    voice_name=character.voice_name.strip(),
                    appearance_prompt=character.appearance_prompt.strip(),
                )
                for index, character in enumerate(characters, start=1)
            ],
            episodes=[
                SeriesEpisode(
                    id=f"ep{index}",
                    seq=index,
                    title=idea[:40] if index == 1 else "",
                )
                for index in range(1, body.episode_count + 1)
            ],
        )
        series_store.save_series(series)
        plan_id = plan_store.save_plan(generated)
        series_store.bind_episode_plan(series.id, "ep1", plan_id)
    except (
        series_store.SeriesStoreError,
        plan_store.PlanStoreError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.error(f"wizard series creation failed: {exc}")
        _bad(request, f"wizard series creation failed: {exc}")
    return utils.get_response(
        200,
        {
            "series_id": series.id,
            "plan_id": plan_id,
            **_plan_detail(plan_store.load_plan(plan_id)),
        },
    )


@router.get("/engines/status", summary="Probe local engine readiness")
def engines_status(request: Request):
    from app.services import comfy_local

    try:
        status = comfy_local.local_engines_status()
    except Exception as exc:  # noqa: BLE001 - 探针离线不抛，置灰即可
        logger.warning(f"local engines status probe failed: {exc}")
        status = {
            "comfyui": {"online": False},
            "acestep": {"online": False},
            "ollama": {"online": False},
        }
    return utils.get_response(200, {"engines": status})


@router.post("/engines/local-bundle", summary="Switch writer engine to local ollama")
def apply_local_bundle(request: Request):
    # 与 Main.py 本地全家桶一致：编剧引擎切 ollama，模型为空时补推荐默认；
    # 画面/音乐引擎由方案逐场景选择，不在这里改全局素材源。
    changes = {"llm_provider": "ollama"}
    if not str(config.app.get("ollama_model_name", "") or "").strip():
        changes["ollama_model_name"] = "gemma4:26b"
    applied = config.update_config_values_nonblocking(config.app, changes)
    return utils.get_response(
        200,
        {
            "applied": bool(applied),
            "updated_keys": sorted(changes),
            "pending": not applied,
        },
    )

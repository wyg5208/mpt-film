"""发布面板 API（迁移方案 1.6）。

历史读取 ``publish_history``，手动/重新发布走 task.py 现成的跨平台发布调度器
（``publish_task_now`` → ``_schedule_cross_post``，通道与 YouTube 隐私设置由
调度器按当前配置解析），队列视图从 ``state.py`` 的 cross_post_* 字段投影并
附带 ``publish_zombies`` 的僵尸进程告警。
"""

from fastapi import Depends, Query, Request
from pydantic import BaseModel

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models import const
from app.models.exception import HttpException
from app.services import (
    publish_history,
    publish_zombies,
    social_auto_upload,
)
from app.services import state as sm
from app.services import task as task_service
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])

ACTIVE_STATES = (
    const.CROSS_POST_STATE_PENDING,
    const.CROSS_POST_STATE_PROCESSING,
)


class PublishRequest(BaseModel):
    task_id: str
    # 通道由调度器按已配置渠道解析；保留字段以对齐发布面板的勾选语义。
    platforms: list[str] = []
    youtube_privacy_status: str | None = None
    youtube_made_for_kids: bool | None = None


@router.get("/publish/history", summary="List cross-platform publish attempts")
def get_publish_history(request: Request, limit: int = Query(200, ge=1, le=1000)):
    return utils.get_response(
        200, {"history": publish_history.list_publish_history(limit=limit)}
    )


@router.post("/publish", summary="Manually publish a finished task")
def publish_now(request: Request, body: PublishRequest):
    error = task_service.publish_task_now(body.task_id)
    if error:
        raise HttpException(
            task_id=base.get_task_id(request),
            status_code=400,
            message=error,
        )
    return utils.get_response(200, {"scheduled": True, "task_id": body.task_id})


@router.get("/publish/queue", summary="Active cross-post jobs + zombie warnings")
def publish_queue(request: Request):
    tasks, _total = sm.state.get_all_tasks(1, 1000)
    jobs = []
    for task in tasks or []:
        cross_state = task.get("cross_post_state")
        if cross_state not in ACTIVE_STATES:
            continue
        jobs.append(
            {
                "task_id": task.get("task_id"),
                "state": cross_state,
                "stage": task.get("cross_post_stage"),
                "progress": task.get("cross_post_progress"),
                "platform": task.get("cross_post_platform"),
                "platforms": task.get("cross_post_platforms"),
                "log": task.get("cross_post_log") or [],
                "video_subject": task.get("video_subject"),
            }
        )
    return utils.get_response(
        200,
        {
            "jobs": jobs,
            "zombies": publish_zombies.detect_zombies(),
        },
    )


class SessionCheckRequest(BaseModel):
    # 与 Streamlit 设置体一致的登录态体检：逐平台调用 sau check 子进程。
    platforms: list[str]
    account: str = "default"


@router.post(
    "/publish/sessions/check", summary="Check social-auto-upload login sessions"
)
def check_publish_sessions(request: Request, body: SessionCheckRequest):
    report = social_auto_upload.social_auto_upload_service.check_sessions(
        body.platforms, body.account
    )
    if report is None:
        # 已有体检在运行：与 Streamlit 的 toast 提示对齐，由前端提示稍后再试。
        return utils.get_response(200, {"busy": True, "report": {}})
    return utils.get_response(200, {"busy": False, "report": report})

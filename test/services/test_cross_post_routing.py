"""task.py 跨平台发布的通道路由测试：状态机与队列语义必须保持不变。"""
import json
from unittest.mock import Mock, PropertyMock, patch

import pytest

from app.models import const
from app.services import state as state_service
from app.services import task


METADATA = {"title": "标题", "caption": "简介", "hashtags": ["#美食"]}


@pytest.fixture(autouse=True)
def history_mock(monkeypatch):
    """发布历史写盘隔离：路由测试不应触碰真实 storage，也不残留运行元数据。"""
    mock = Mock()
    monkeypatch.setattr(task.publish_history, "record_publish", mock)
    task._cross_post_run_meta.clear()
    yield mock
    task._cross_post_run_meta.clear()


def _run(platforms, videos=("v1.mp4",), social_result=None, upload_result=None, trigger="auto"):
    social_mock = Mock(
        return_value=social_result
        if social_result is not None
        else {"success": True, "results": {}}
    )
    upload_mock = Mock(
        return_value=upload_result if upload_result is not None else {"success": True}
    )
    with (
        patch.object(task, "_patch_cross_post_state", return_value=True) as state_mock,
        patch.object(task.llm, "generate_social_metadata", return_value=dict(METADATA)) as meta_mock,
        patch.object(task.social_auto_upload, "cross_post_video", social_mock),
        patch.object(task.upload_post, "cross_post_video", upload_mock),
    ):
        task._run_cross_post(
            "task-1",
            tuple(videos),
            "美食主题",
            "脚本正文",
            "zh-CN",
            tuple(platforms),
            "public",
            False,
            {"upload_post_api_key": "k"},
            {"social_publish_account": "queued"},
            trigger=trigger,
        )
    return state_mock, meta_mock, social_mock, upload_mock


def _final_state(state_mock):
    kwargs = state_mock.call_args_list[-1].kwargs
    return kwargs


def test_cn_only_routes_to_sau_and_skips_upload_post():
    state_mock, meta_mock, social_mock, upload_mock = _run(["douyin", "bilibili"])
    upload_mock.assert_not_called()
    assert social_mock.call_count == 2
    # 每个平台各自生成一次文案（字数上限不同）。
    assert [c.kwargs["platform"] for c in meta_mock.call_args_list] == ["douyin", "bilibili"]
    for call in social_mock.call_args_list:
        assert call.kwargs["title"] == "标题"
        assert call.kwargs["desc"] == "简介"
        assert call.kwargs["tags"] == ["#美食"]
        assert call.kwargs["account_snapshot"] == {"social_publish_account": "queued"}
    final = _final_state(state_mock)
    assert final["cross_post_state"] == const.CROSS_POST_STATE_COMPLETE
    assert [entry["platform"] for entry in final["cross_post_results"]] == ["douyin", "bilibili"]
    assert all(entry["video_index"] == 1 for entry in final["cross_post_results"])


def test_overseas_only_keeps_legacy_upload_post_path():
    state_mock, meta_mock, social_mock, upload_mock = _run(["tiktok", "instagram"])
    social_mock.assert_not_called()
    upload_mock.assert_called_once()
    assert upload_mock.call_args.kwargs["platforms"] == ["tiktok", "instagram"]
    # 旧链路元数据仍按首个国外平台生成一次。
    assert meta_mock.call_count == 1
    assert meta_mock.call_args.kwargs["platform"] == "tiktok"
    final = _final_state(state_mock)
    assert final["cross_post_state"] == const.CROSS_POST_STATE_COMPLETE


def test_mixed_channels_merge_results_into_one_state():
    state_mock, _, social_mock, upload_mock = _run(["douyin", "youtube"])
    social_mock.assert_called_once()
    upload_mock.assert_called_once()
    assert upload_mock.call_args.kwargs["platforms"] == ["youtube"]
    final = _final_state(state_mock)
    assert final["cross_post_state"] == const.CROSS_POST_STATE_COMPLETE
    assert len(final["cross_post_results"]) == 2
    assert final["cross_post_results"][0]["platform"] == "douyin"


def test_cn_failure_marks_publish_failed_without_touching_videos():
    state_mock, _, _, _ = _run(
        ["douyin"],
        social_result={"success": False, "error": "sau douyin exited with code 1"},
    )
    final = _final_state(state_mock)
    assert final["cross_post_state"] == const.CROSS_POST_STATE_FAILED
    assert "sau douyin" in final["cross_post_error"]
    assert final["cross_post_owner"] is None


def test_cn_multiple_videos_publish_serially_per_platform():
    _, _, social_mock, _ = _run(["tencent"], videos=("v1.mp4", "v2.mp4"))
    assert social_mock.call_count == 2
    assert [c.kwargs["video_path"] for c in social_mock.call_args_list] == ["v1.mp4", "v2.mp4"]


def test_schedule_passes_both_account_snapshots():
    params = Mock(video_subject="主题", video_language="zh-CN")
    future = Mock()
    with (
        patch.object(task._cross_post_slots, "acquire", return_value=True),
        patch.object(task._cross_post_executor, "submit", return_value=future) as submit,
        patch.object(task, "_register_cross_post_future"),
        patch.object(
            task.upload_post.upload_post_service, "snapshot_account", return_value={"up": 1}
        ),
        patch.object(
            task.social_auto_upload.social_auto_upload_service,
            "snapshot_account",
            return_value={"soc": 2},
        ),
    ):
        error = task._schedule_cross_post(
            task_id="task-1",
            video_paths=["v1.mp4"],
            params=params,
            video_script="脚本",
            platforms=["douyin"],
            youtube_privacy_status="public",
        )
    assert error is None
    args = submit.call_args.args
    assert args[-2:] == ({"up": 1}, {"soc": 2})
    future.add_done_callback.assert_called_once()


def test_queue_full_still_degrades_to_queryable_failure():
    params = Mock(video_subject="主题", video_language="zh-CN")
    with (
        patch.object(task._cross_post_slots, "acquire", return_value=False),
        patch.object(task, "_patch_cross_post_state", return_value=True) as state_mock,
    ):
        error = task._schedule_cross_post(
            task_id="task-1",
            video_paths=["v1.mp4"],
            params=params,
            video_script="脚本",
            platforms=["douyin"],
            youtube_privacy_status="public",
        )
    assert "queue is full" in error
    kwargs = state_mock.call_args.kwargs
    assert kwargs["cross_post_state"] == const.CROSS_POST_STATE_FAILED
    assert kwargs["cross_post_error"] == error


def _manual_publish(
    tmp_path,
    task_state=None,
    social_configured=True,
    upload_configured=False,
    video_exists=True,
    write_manifest=True,
):
    """驱动 publish_task_now，返回 (错误, 状态补丁 mock, 调度 mock)。"""
    if task_state is None:
        task_state = {
            "state": const.TASK_STATE_COMPLETE,
            "videos": ["v1.mp4"],
            "script": "脚本正文",
            "video_subject": "美食主题",
            "video_language": "zh-CN",
        }
    if write_manifest:
        (tmp_path / "script.json").write_text(
            json.dumps(
                {
                    "params": {
                        "video_subject": "美食主题",
                        "video_language": "zh-CN",
                    },
                    "script": "清单里的脚本",
                }
            ),
            encoding="utf-8",
        )
    social_service = task.social_auto_upload.social_auto_upload_service
    upload_service = task.upload_post.upload_post_service
    with (
        patch.object(task.sm.state, "get_task", return_value=task_state),
        patch.object(task.path, "isfile", return_value=video_exists),
        patch.object(task.utils, "task_dir", return_value=str(tmp_path)),
        patch.object(
            social_service, "is_configured", return_value=social_configured
        ),
        patch.object(
            type(social_service),
            "platforms",
            new_callable=PropertyMock,
            return_value=["douyin", "bilibili"],
        ),
        patch.object(
            upload_service, "is_configured", return_value=upload_configured
        ),
        patch.object(
            type(upload_service),
            "platforms",
            new_callable=PropertyMock,
            return_value=["youtube"],
        ),
        patch.object(task, "_patch_cross_post_state", return_value=True) as state_mock,
        patch.object(task, "_schedule_cross_post", return_value=None) as schedule_mock,
    ):
        error = task.publish_task_now("task-1")
    return error, state_mock, schedule_mock


def test_manual_publish_queues_without_auto_upload_toggle(tmp_path):
    error, state_mock, schedule_mock = _manual_publish(tmp_path)
    assert error is None
    # 排队窗口内先写 pending，再交给与自动发布共用的调度函数。
    assert state_mock.call_args.kwargs["cross_post_state"] == const.CROSS_POST_STATE_PENDING
    kwargs = schedule_mock.call_args.kwargs
    assert kwargs["platforms"] == ["douyin", "bilibili"]
    assert kwargs["video_paths"] == ["v1.mp4"]
    assert kwargs["params"].video_subject == "美食主题"
    assert kwargs["video_script"] == "清单里的脚本"


def test_manual_publish_merges_both_configured_channels(tmp_path):
    error, _, schedule_mock = _manual_publish(tmp_path, upload_configured=True)
    assert error is None
    assert schedule_mock.call_args.kwargs["platforms"] == ["douyin", "bilibili", "youtube"]


def test_manual_publish_rejects_unfinished_task(tmp_path):
    error, _, schedule_mock = _manual_publish(
        tmp_path, task_state={"state": const.TASK_STATE_PROCESSING, "videos": []}
    )
    assert "not complete" in error
    schedule_mock.assert_not_called()


def test_manual_publish_rejects_when_already_queued(tmp_path):
    error, _, schedule_mock = _manual_publish(
        tmp_path,
        task_state={
            "state": const.TASK_STATE_COMPLETE,
            "cross_post_state": const.CROSS_POST_STATE_PENDING,
            "videos": ["v1.mp4"],
        },
    )
    assert "already queued" in error
    schedule_mock.assert_not_called()


def test_manual_publish_requires_a_configured_channel(tmp_path):
    error, _, schedule_mock = _manual_publish(
        tmp_path, social_configured=False, upload_configured=False
    )
    assert "no publishing channel" in error
    schedule_mock.assert_not_called()


def test_manual_publish_rejects_missing_video_files(tmp_path):
    error, _, schedule_mock = _manual_publish(tmp_path, video_exists=False)
    assert "no finished video files" in error
    schedule_mock.assert_not_called()


def test_manual_publish_falls_back_when_manifest_missing(tmp_path):
    error, _, schedule_mock = _manual_publish(tmp_path, write_manifest=False)
    assert error is None
    kwargs = schedule_mock.call_args.kwargs
    # 旧任务没有 script.json 时用状态里的最小信息兜底，不阻断发布。
    assert kwargs["params"].video_subject == "美食主题"
    assert kwargs["video_script"] == "脚本正文"


def test_manual_publish_restores_state_from_disk_after_restart(tmp_path):
    # 重启后内存状态为空，但任务目录里仍有成片和清单。
    task_dir = tmp_path / "task-1"
    task_dir.mkdir()
    (task_dir / "final-1.mp4").write_bytes(b"video")
    (task_dir / "combined-1.mp4").write_bytes(b"intermediate")
    (task_dir / "script.json").write_text(
        json.dumps(
            {
                "params": {"video_subject": "美食主题", "video_language": "zh-CN"},
                "script": "清单里的脚本",
            }
        ),
        encoding="utf-8",
    )
    fresh_state = state_service.MemoryState()
    social_service = task.social_auto_upload.social_auto_upload_service
    with (
        patch.object(task.sm, "state", fresh_state),
        patch.object(task.utils, "task_dir", return_value=str(task_dir)),
        patch.object(social_service, "is_configured", return_value=True),
        patch.object(
            type(social_service),
            "platforms",
            new_callable=PropertyMock,
            return_value=["douyin"],
        ),
        patch.object(
            task.upload_post.upload_post_service, "is_configured", return_value=False
        ),
        patch.object(task, "_schedule_cross_post", return_value=None) as schedule_mock,
    ):
        error = task.publish_task_now("task-1")
    assert error is None
    kwargs = schedule_mock.call_args.kwargs
    # 只接受 final 成片，combined 中间文件不得被发布。
    assert kwargs["video_paths"] == [str(task_dir / "final-1.mp4")]
    assert kwargs["params"].video_subject == "美食主题"
    # 状态记录已重建，后续发布状态补丁才能写入并在任务卡上可见。
    restored = fresh_state.get_task("task-1")
    assert restored["state"] == const.TASK_STATE_COMPLETE
    assert restored["cross_post_state"] == const.CROSS_POST_STATE_PENDING


def test_manual_publish_missing_state_and_disk_still_fails(tmp_path):
    with (
        patch.object(task.sm.state, "get_task", return_value=None),
        patch.object(task.utils, "task_dir", return_value=str(tmp_path / "missing")),
    ):
        error = task.publish_task_now("task-1")
    assert "task state not found" in error


def test_cross_post_reports_progress_stages_and_live_log():
    def social_side_effect(**kwargs):
        # 模拟 sau 子进程逐行输出，验证日志尾写入任务状态。
        kwargs["on_output"]("uploading line")
        return {"success": True, "results": {}}

    social_mock = Mock(side_effect=social_side_effect)
    with (
        patch.object(task, "_patch_cross_post_state", return_value=True) as state_mock,
        patch.object(task.llm, "generate_social_metadata", return_value=dict(METADATA)),
        patch.object(task.social_auto_upload, "cross_post_video", social_mock),
        patch.object(task.upload_post, "cross_post_video", Mock(return_value={"success": True})),
        patch.object(task, "_CROSS_POST_LOG_WRITE_INTERVAL_SECONDS", 0.0),
    ):
        task._run_cross_post(
            "task-1",
            ("v1.mp4",),
            "美食主题",
            "脚本正文",
            "zh-CN",
            ("douyin",),
            "public",
            False,
            None,
            {"social_publish_account": "queued"},
        )
    patches = [call.kwargs for call in state_mock.call_args_list]
    stages = [p["cross_post_stage"] for p in patches if "cross_post_stage" in p]
    assert stages[0] == "queued"
    assert "metadata" in stages
    assert "uploading" in stages
    assert stages[-1] == "done"
    progress_values = [
        p["cross_post_progress"] for p in patches if "cross_post_progress" in p
    ]
    assert progress_values == sorted(progress_values)
    assert progress_values[-1] == 100
    logs = [p["cross_post_log"] for p in patches if p.get("cross_post_log")]
    assert any("[douyin] uploading line" in line for log in logs for line in log)
    assert callable(social_mock.call_args.kwargs["on_output"])


def test_schedule_records_target_platforms_for_queue_panel():
    params = Mock(video_subject="主题", video_language="zh-CN")
    future = Mock()
    with (
        patch.object(task._cross_post_slots, "acquire", return_value=True),
        patch.object(task._cross_post_executor, "submit", return_value=future),
        patch.object(task, "_register_cross_post_future"),
        patch.object(task, "_patch_cross_post_state", return_value=True) as state_mock,
        patch.object(
            task.upload_post.upload_post_service, "snapshot_account", return_value={}
        ),
        patch.object(
            task.social_auto_upload.social_auto_upload_service,
            "snapshot_account",
            return_value={},
        ),
    ):
        error = task._schedule_cross_post(
            task_id="task-1",
            video_paths=["v1.mp4"],
            params=params,
            video_script="脚本",
            platforms=["douyin", "bilibili"],
            youtube_privacy_status="public",
        )
    assert error is None
    assert state_mock.call_args.kwargs["cross_post_platforms"] == ["douyin", "bilibili"]


def test_history_records_auto_trigger_with_duration(history_mock):
    _run(["douyin", "bilibili"])
    history_mock.assert_called_once()
    entry = history_mock.call_args.args[0]
    assert entry["task_id"] == "task-1"
    assert entry["trigger"] == "auto"
    assert entry["state"] == const.CROSS_POST_STATE_COMPLETE
    assert entry["video_subject"] == "美食主题"
    assert entry["videos"] == ["v1.mp4"]
    assert entry["account"] == "queued"
    assert entry["duration_seconds"] >= 0
    assert entry["error"] is None
    assert [r["platform"] for r in entry["results"]] == ["douyin", "bilibili"]
    # 终态后运行元数据必须被消费，不能泄漏到下一次发布。
    assert task._cross_post_run_meta == {}


def test_history_records_manual_trigger(history_mock):
    _run(["douyin"], trigger="manual")
    entry = history_mock.call_args.args[0]
    assert entry["trigger"] == "manual"
    assert entry["state"] == const.CROSS_POST_STATE_COMPLETE


def test_history_records_failure_with_error(history_mock):
    _run(["douyin"], social_result={"success": False, "error": "sau douyin exited 1"})
    entry = history_mock.call_args.args[0]
    assert entry["state"] == const.CROSS_POST_STATE_FAILED
    assert "sau douyin" in entry["error"]
    assert entry["results"][0]["success"] is False


def test_manual_publish_passes_manual_trigger(tmp_path):
    error, _, schedule_mock = _manual_publish(tmp_path)
    assert error is None
    assert schedule_mock.call_args.kwargs["trigger"] == "manual"


def test_queue_full_records_manual_history(history_mock):
    params = Mock(video_subject="主题", video_language="zh-CN")
    with (
        patch.object(task._cross_post_slots, "acquire", return_value=False),
        patch.object(task, "_patch_cross_post_state", return_value=True),
        patch.object(
            task.social_auto_upload.social_auto_upload_service,
            "snapshot_account",
            return_value={"social_publish_account": "default"},
        ),
    ):
        error = task._schedule_cross_post(
            task_id="task-1",
            video_paths=["v1.mp4"],
            params=params,
            video_script="脚本",
            platforms=["douyin"],
            youtube_privacy_status="public",
            trigger="manual",
        )
    assert "queue is full" in error
    history_mock.assert_called_once()
    entry = history_mock.call_args.args[0]
    assert entry["trigger"] == "manual"
    assert entry["state"] == const.CROSS_POST_STATE_FAILED
    assert entry["account"] == "default"
    assert "queue is full" in entry["error"]
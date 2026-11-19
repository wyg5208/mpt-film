"""publish_history 存储测试：追加、倒序、损坏行容忍与写失败降级。"""
import json

from app.services import publish_history


def _use_tmp_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(
        publish_history.utils, "storage_dir", lambda create=False: str(tmp_path)
    )


def test_record_and_list_roundtrip_newest_first(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    publish_history.record_publish({"task_id": "old", "finished_at": 100})
    publish_history.record_publish({"task_id": "new", "finished_at": 200})
    entries = publish_history.list_publish_history()
    assert [e["task_id"] for e in entries] == ["new", "old"]
    # recorded_at 自动补齐，中文主题不转义。
    assert entries[0]["recorded_at"] > 0
    publish_history.record_publish({"task_id": "zh", "video_subject": "美食"})
    raw = (tmp_path / "publish_history.jsonl").read_text(encoding="utf-8")
    assert "美食" in raw


def test_list_skips_corrupt_lines_and_limits(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    lines = [
        json.dumps({"task_id": "a", "finished_at": 1}),
        "{not json",
        "",
        json.dumps(["not", "a", "dict"]),
        json.dumps({"no_task_id": True}),
        json.dumps({"task_id": "b", "finished_at": 2}),
        json.dumps({"task_id": "c", "finished_at": 3}),
    ]
    (tmp_path / "publish_history.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    entries = publish_history.list_publish_history(limit=2)
    assert [e["task_id"] for e in entries] == ["c", "b"]


def test_list_missing_file_returns_empty(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    assert publish_history.list_publish_history() == []


def test_record_failure_never_raises(monkeypatch, tmp_path):
    # 路径指向目录：open 必然失败，但记录接口只能降级记日志。
    monkeypatch.setattr(publish_history, "history_file", lambda: str(tmp_path))
    publish_history.record_publish({"task_id": "x"})


def test_entries_without_finished_at_sort_by_recorded_at(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    publish_history.record_publish({"task_id": "a", "recorded_at": 10})
    publish_history.record_publish({"task_id": "b", "recorded_at": 20})
    entries = publish_history.list_publish_history()
    assert [e["task_id"] for e in entries] == ["b", "a"]
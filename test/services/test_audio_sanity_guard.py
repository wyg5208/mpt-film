import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from app.models.schema import VideoParams
from app.services import task as tm


# 8 次重复 15 字句 = 120 个 CJK 字符，稳定越过守卫的 50 字阈值。
_LONG_CJK_SCRIPT = "个人智能代理正在重塑教育的未来。" * 8
# 短文案：无论音频多短都应放行，守卫只针对长文案。
_SHORT_CJK_SCRIPT = "个人 Agent 正在改变学习。"


def _run_generate_audio(script, measured_duration):
    """Drive task.generate_audio with a stubbed TTS backend.

    Storage and failure reporting are faked following the conventions used by
    test_task.py, so the test never touches real task directories or the
    global task state.
    """
    sub_maker = SimpleNamespace(cues=[])
    with (
        tempfile.TemporaryDirectory() as temp_dir,
        patch.object(tm.utils, "task_dir", return_value=temp_dir),
        patch.object(tm.voice, "tts", return_value=sub_maker) as synthesize,
        patch.object(
            tm.voice, "get_audio_duration", return_value=measured_duration
        ),
        patch.object(tm, "_mark_task_failed") as mark_task_failed,
    ):
        params = VideoParams(
            video_subject="个人Agent如何改变教育",
            voice_name="af-ZA-AdriNeural-Female",
            voice_rate=0.8,
        )
        audio_file, audio_duration, result_maker = tm.generate_audio(
            "sanity-guard", params, script
        )
        return (
            audio_file,
            audio_duration,
            result_maker,
            synthesize,
            mark_task_failed,
        )


def test_long_cjk_script_with_near_empty_audio_fails_at_audio_stage():
    # 复刻真实事故：Afrikaans 声音读中文脚本只会念出夹杂的英文单词（Agent），
    # 合成出 1.94 秒音频，任务却"成功"产出近 2 秒的空视频。守卫必须在音频
    # 阶段拦截，并点名声音、指向语言不匹配。
    audio_file, audio_duration, sub_maker, synthesize, mark_task_failed = (
        _run_generate_audio(_LONG_CJK_SCRIPT, 1.94)
    )
    assert audio_file is None
    assert audio_duration is None
    assert sub_maker is None
    synthesize.assert_called_once()
    assert mark_task_failed.call_count == 1
    assert mark_task_failed.call_args.args[1] == "audio"
    message = mark_task_failed.call_args.args[2]
    # 失败信息必须点名声音（parse_voice_name 已去掉 -Female 后缀）。
    assert "af-ZA-AdriNeural" in message
    assert "CJK characters" in message
    assert "language" in message


def test_long_cjk_script_with_adequate_audio_passes():
    # 正常配音（25.3 秒 → 取整 26 秒）不应被守卫拦截。
    audio_file, audio_duration, sub_maker, synthesize, mark_task_failed = (
        _run_generate_audio(_LONG_CJK_SCRIPT, 25.3)
    )
    assert audio_file
    assert audio_duration == 26
    assert sub_maker is not None
    mark_task_failed.assert_not_called()


def test_short_script_keeps_short_audio_allowed():
    # 守卫只针对长文案：短脚本的短音频是合法结果（如一句话口播）。
    audio_file, audio_duration, sub_maker, synthesize, mark_task_failed = (
        _run_generate_audio(_SHORT_CJK_SCRIPT, 1.94)
    )
    assert audio_file
    assert audio_duration == 2
    assert sub_maker is not None
    mark_task_failed.assert_not_called()


def test_boundary_five_seconds_is_not_flagged():
    # 阈值语义是"低于 5 秒"才拦截：恰好 5.0 秒放行。
    audio_file, audio_duration, sub_maker, synthesize, mark_task_failed = (
        _run_generate_audio(_LONG_CJK_SCRIPT, 5.0)
    )
    assert audio_file
    assert audio_duration == 5
    mark_task_failed.assert_not_called()

# -*- coding: utf-8 -*-
"""B6 多音色对白模式：speaker → voice_name 路由 + 逐句 TTS 拼接 + 独立时间轴装配。

独立于旁白驱动主路径（整篇一次 TTS + 单 sub_maker + cues 字符切窗）：
只有 plan 含非 narrator 的 speaker 时才由 task.py 路由进入本模块。
拼接/字幕偏移沿用 voice._tts_with_pauses 已验证的样本级精确契约：
逐句解码 PCM 数样本 → 偏移 cues → 末尾单次统一编码，无 MP3 帧累积漂移。
"""

from __future__ import annotations

import os
import tempfile
import wave
from datetime import timedelta
from pathlib import Path

from edge_tts import SubMaker
from edge_tts.srt_composer import Subtitle
from loguru import logger

from app.models.schema import ScriptPlan, Series, SubtitleCue
from app.services import voice
from app.utils import utils

SAMPLE_RATE = 24000
# 空旁白对白场景（哑剧插拍）的最短静音窗。
_MIN_SILENCE_SECONDS = 0.5


class DialogueError(RuntimeError):
    pass


def has_dialogue(plan: ScriptPlan) -> bool:
    """任一场景 speaker 非 narrator 即进入多音色对白模式。"""
    return any((scene.speaker or "narrator") != "narrator" for scene in plan.scenes)


def resolve_speaker_voice(plan: ScriptPlan, series: Series | None, speaker: str) -> str:
    """narrator → plan.voice.name；角色 id → series.characters[].voice_name。"""
    speaker = (speaker or "narrator").strip() or "narrator"
    if speaker == "narrator":
        name = (plan.voice.name or "").strip()
        if not name:
            raise DialogueError("narrator voice is not set in plan.voice.name")
        return name
    if series is None:
        raise DialogueError(
            f"speaker '{speaker}' needs a persisted series with character "
            "voice_name bindings (dialogue mode)"
        )
    character = next((c for c in series.characters if c.id == speaker), None)
    if character is None:
        raise DialogueError(
            f"speaker '{speaker}' is not a character in series {series.id}"
        )
    name = (character.voice_name or "").strip()
    if not name:
        raise DialogueError(
            f"character '{speaker}' has no voice_name bound; set it in the "
            "series character bible before dialogue rendering"
        )
    return name


def validate_dialogue_routing(plan: ScriptPlan, series: Series | None) -> str | None:
    """preflight 用：返回首个路由错误文案，全部可解析返回 None。"""
    for scene in plan.scenes:
        try:
            resolve_speaker_voice(plan, series, scene.speaker)
        except DialogueError as exc:
            return f"scene {scene.id}: {exc}"
    return None


def _shift_cues(combined: SubMaker, chunk: SubMaker, offset_seconds: float) -> list:
    """迁移一句的 cues 到合并时间轴（edge_tts 7.x + legacy 双契约），
    同时返回本句的绝对秒区间供场景 subtitle_cues 回填。"""
    rows = []
    offset_td = timedelta(seconds=offset_seconds)
    if hasattr(chunk, "cues") and chunk.cues:
        for cue in chunk.cues:
            combined.cues.append(
                Subtitle(
                    index=len(combined.cues) + 1,
                    start=cue.start + offset_td,
                    end=cue.end + offset_td,
                    content=cue.content,
                )
            )
            rows.append(
                SubtitleCue(
                    start=round(cue.start.total_seconds() + offset_seconds, 3),
                    end=round(cue.end.total_seconds() + offset_seconds, 3),
                    text=cue.content,
                )
            )
    if hasattr(chunk, "subs") and chunk.subs:
        combined.subs.extend(chunk.subs)
    if hasattr(chunk, "offset") and chunk.offset:
        offset_100ns = int(offset_seconds * 10000000)
        for start_ns, end_ns in chunk.offset:
            combined.offset.append((start_ns + offset_100ns, end_ns + offset_100ns))
    return rows


def _decode_samples(chunk_audio: str, chunk_wav: str, label: str) -> int:
    """MP3 → 24kHz 单声道 PCM，返回真实样本数（字幕偏移的唯一依据）。"""
    cmd = [
        utils.get_ffmpeg_binary(),
        "-nostdin", "-v", "error", "-y",
        "-i", chunk_audio,
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-codec:a", "pcm_s16le",
        chunk_wav,
    ]
    res = voice._run_tts_ffmpeg(cmd, f"dialogue line decode ({label})")
    if res is None or res.returncode != 0 or not os.path.exists(chunk_wav) or os.path.getsize(chunk_wav) == 0:
        raise DialogueError(f"failed to decode dialogue audio for {label}")
    with wave.open(chunk_wav, "rb") as wf:
        samples = wf.getnframes()
    if samples <= 0:
        raise DialogueError(f"dialogue line has no audio samples: {label}")
    return samples


def assemble_dialogue_audio(
    plan: ScriptPlan,
    series: Series | None,
    out_file: str,
    *,
    tts=None,
    on_progress=None,
) -> tuple[str, float, SubMaker, list[dict]]:
    """逐句 TTS → 样本级拼接 → (audio_file, duration, sub_maker, scene_windows)。

    windows 与 plan_compiler.build_scene_windows 同形（cues 为 SubtitleCue），
    边界直接取累计样本偏移，无需字符插值。tts 可注入以便离线单测。
    """
    routing_error = validate_dialogue_routing(plan, series)
    if routing_error:
        raise DialogueError(routing_error)
    synthesize = tts if tts is not None else voice.tts
    combined = voice.ensure_legacy_submaker_fields(SubMaker())
    chunk_files: list[str] = []
    windows: list[dict] = []
    cumulative_samples = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        for index, scene in enumerate(plan.scenes):
            start_seconds = cumulative_samples / float(SAMPLE_RATE)
            text = (scene.narration or "").strip()
            cues: list[SubtitleCue] = []
            if not text:
                # 哑剧插拍：保留画面窗，用精确静音占位。
                silence_seconds = max(float(scene.est_duration or 0), _MIN_SILENCE_SECONDS)
                chunk_wav = os.path.join(temp_dir, f"silence_{index}.wav")
                if not voice.generate_silent_audio(silence_seconds, chunk_wav):
                    raise DialogueError(f"failed to generate silence for scene {scene.id}")
                with wave.open(chunk_wav, "rb") as wf:
                    samples = wf.getnframes()
                chunk_files.append(chunk_wav)
            else:
                voice_name = resolve_speaker_voice(plan, series, scene.speaker)
                chunk_audio = os.path.join(temp_dir, f"line_{index}.mp3")
                chunk_submaker = synthesize(
                    text=text,
                    voice_name=voice_name,
                    voice_rate=plan.voice.rate,
                    voice_file=chunk_audio,
                )
                if (
                    chunk_submaker is None
                    or not os.path.exists(chunk_audio)
                    or os.path.getsize(chunk_audio) == 0
                ):
                    # NoAudioReceived 几乎都是声音与台词语言不匹配：一次失败
                    # 即报错并给出可操作提示，不做无谓重试。
                    raise DialogueError(
                        f"failed to synthesize scene {scene.id} with voice "
                        f"'{voice_name}'; verify the voice matches the line "
                        "language and TTS connectivity"
                    )
                chunk_wav = os.path.join(temp_dir, f"line_{index}_decoded.wav")
                samples = _decode_samples(chunk_audio, chunk_wav, scene.id)
                cues = _shift_cues(combined, chunk_submaker, start_seconds)
                chunk_files.append(chunk_wav)

            cumulative_samples += samples
            end_seconds = cumulative_samples / float(SAMPLE_RATE)
            windows.append(
                {
                    "scene_id": scene.id,
                    "order": scene.order,
                    "start": round(start_seconds, 3),
                    "end": round(end_seconds, 3),
                    "duration": round(end_seconds - start_seconds, 3),
                    "cues": cues,
                }
            )
            if on_progress is not None:
                on_progress((index + 1) / len(plan.scenes))

        if not voice._concat_audio_files(chunk_files, out_file):
            raise DialogueError("failed to concatenate dialogue lines")

    duration = cumulative_samples / float(SAMPLE_RATE)
    combined.duration = duration
    logger.info(
        f"dialogue audio assembled: scenes={len(plan.scenes)}, "
        f"duration={duration:.2f}s, file={Path(out_file).name}"
    )
    return out_file, duration, combined, windows
"""
成片审查（review）的端到端测试。

用 ffmpeg lavfi 现场合成"带缺陷的成片"，断言每类缺陷恰好触发对应 finding，且
正常内容（淡入淡出、硬切、安静环境噪声）不被误报——这些误报一旦进入生产会
把每个任务都刷满 warning，比漏报更致命。

夹具配方全部经过实测校准（ffmpeg 7.1 essentials，imageio-ffmpeg 同源）：
* lavfi 源参数必须用冒号分隔（``color=c=black:s=128x72``）；``=`` 只兼容首个
  键值对，纯数字色名（testsrc2）碰巧能用，``color=`` 会报 Invalid argument。
* 单帧缺陷不能靠 drawbox enable 注入（本构建不可靠），改用 concat 拼接
  ``-frames:v 1`` 的短片段，帧位精确。
* yuv420p 有限范围下纯黑整帧亮度 16、纯白 235、gray 128，黑/白阈值必须包络
  这组实测值，而不是想当然的 0/255。
* 音频响度夹具：pink noise amplitude=0.5 ≈ -20.8 LUFS（干净基线）；
  acompressor makeup=12 ≈ -3.7 LUFS（too_loud）；volume=-30dB ≈ -50.8（too_quiet）。

涉及真实编码的用例共享一次模块级夹具；单测合成帧的部分不碰磁盘。
"""

import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np

# add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import review

_TMP = None
FFMPEG = None
BASE = None
ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "15"]
FPS = 30


def setUpModule():
    global _TMP, FFMPEG, BASE
    FFMPEG = review._ffmpeg_binary()
    if not FFMPEG or not Path(FFMPEG).exists():
        raise unittest.SkipTest("ffmpeg binary not available")
    _TMP = tempfile.TemporaryDirectory()
    out = Path(_TMP.name)


def tearDownModule():
    if _TMP is not None:
        _TMP.cleanup()


def _run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if result.returncode != 0:
        raise RuntimeError(f"fixture command failed: {result.stderr[-300:]}")


def _clip(name, source, frames):
    """用 lavfi 源生成固定帧数的短片。color 源必须用冒号分隔参数。"""
    path = Path(_TMP.name) / name
    sep = ":" if source.startswith("color") else "="
    args = [
        FFMPEG, "-nostdin", "-v", "error", "-y", "-threads", "1",
        "-f", "lavfi", "-i", f"{source}{sep}s=128x72", "-r", str(FPS),
        "-frames:v", str(frames),
    ]
    _run(args + ENC + [str(path)])
    return path


def _join(parts, name):
    """concat 拼接多个短片——单帧缺陷靠它精确注入。"""
    path = Path(_TMP.name) / name
    inputs, filters = [], []
    for index, part in enumerate(parts):
        inputs += ["-i", str(part)]
        filters.append(f"[{index}:v]scale=128:72,setsar=1[v{index}]")
    chain = "".join(f"[v{index}]" for index in range(len(parts)))
    _run([
        FFMPEG, "-nostdin", "-v", "error", "-y", "-threads", "1", *inputs,
        "-filter_complex",
        ";".join(filters) + f";{chain}concat=n={len(parts)}:v=1:a=0[out]",
        "-map", "[out]", "-r", str(FPS), *ENC, str(path),
    ])
    return path


def _audio(name, af=None, duration=9.0):
    path = Path(_TMP.name) / name
    args = [
        FFMPEG, "-nostdin", "-v", "error", "-y", "-threads", "1",
        "-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.5",
        "-t", str(duration),
    ]
    if af:
        args += ["-af", af]
    _run(args + ["-ar", "44100", str(path)])
    return path


def _mux(video_path, audio_path, name):
    path = Path(_TMP.name) / name
    _run([
        FFMPEG, "-nostdin", "-v", "error", "-y", "-threads", "1",
        "-i", str(video_path), "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(path),
    ])
    return path


def _codes(findings):
    return [finding.code for finding in findings]


class FixtureScope(unittest.TestCase):
    """共享模块级夹具的基类，避免每个用例重复编码。"""

    @classmethod
    def setUpClass(cls):
        motion = _clip("motion.mp4", "testsrc2", 90)
        black1 = _clip("black1.mp4", "color=c=black", 1)
        black8 = _clip("black8.mp4", "color=c=black", 8)
        black15 = _clip("black15.mp4", "color=c=black", 15)
        black45 = _clip("black45.mp4", "color=c=black", 45)
        gray1 = _clip("gray1.mp4", "color=c=gray", 1)
        gray45 = _clip("gray45.mp4", "color=c=gray", 45)
        white1 = _clip("white1.mp4", "color=c=white", 1)
        white8 = _clip("white8.mp4", "color=c=white", 8)

        cls.clean_silent = _join([motion, motion, motion], "clean-v.mp4")
        cls.black_head = _join([black8, motion, motion], "black-head.mp4")
        cls.white_head = _join([white8, motion, motion], "white-head.mp4")
        cls.frozen_head = _join([black15, motion, motion], "frozen.mp4")
        cls.still_gray = _join([gray45, gray45], "still.mp4")
        cls.gap_frame = _join([black45, gray1, black45], "gap.mp4")
        cls.white_in_still = _join([gray45, white1, gray45], "flash.mp4")

        # 淡入淡出：合法的刻意转场，不允许被误报成黑场。
        fade_path = Path(_TMP.name) / "fade-real.mp4"
        _run([
            FFMPEG, "-nostdin", "-v", "error", "-y", "-threads", "1",
            "-f", "lavfi", "-i", "testsrc2=s=128x72:d=2", "-r", str(FPS),
            "-vf", "fade=t=in:st=0:d=0.3,fade=t=out:st=1.7:d=0.3",
            *ENC, str(fade_path),
        ])
        cls.fade = fade_path

        # 音频夹具。
        cls.loud_ok = _audio("a-ok.wav")
        cls.hot = _audio(
            "a-hot.wav",
            af="acompressor=threshold=0.1:ratio=20:attack=5:release=50:makeup=12",
        )
        cls.quiet = _audio("a-quiet.wav", af="volume=-30dB")
        cls.long_narration = _audio("a-long.wav", duration=20.0)

        cls.clean_audio = _mux(cls.clean_silent, cls.loud_ok, "clean-audio.mp4")


class TestCleanIsQuiet(FixtureScope):
    def test_clean_video_with_audio_yields_no_findings(self):
        # 一切正常时必须为空列表——这是所有误报回归的总闸。
        self.assertEqual(review.review_video(str(self.clean_audio), mode="full"), [])

    def test_silent_video_reports_only_audio_missing(self):
        findings = review.review_video(str(self.clean_silent), mode="full")
        self.assertEqual(_codes(findings), ["audio_missing"])

    def test_off_mode_returns_empty(self):
        self.assertEqual(review.review_video(str(self.black_head), mode="off"), [])

    def test_fade_out_in_is_not_flagged(self):
        # 淡入淡出两端都接近全黑，但进入/离开是渐变的：不得报 black_frames。
        findings = review.review_video(str(self.fade), mode="full")
        self.assertNotIn("black_frames", _codes(findings))
        self.assertNotIn("abrupt_gap", _codes(findings))


class TestVisualFindings(FixtureScope):
    def test_sustained_black_head(self):
        findings = review.review_video(str(self.black_head), mode="full")
        codes = _codes(findings)
        self.assertIn("black_frames", codes)
        visual = [f for f in findings if f.code == "black_frames"]
        self.assertGreaterEqual(visual[0].end - visual[0].start, review.BLACK_MIN_SECONDS)

    def test_white_flash_head(self):
        findings = review.review_video(str(self.white_head), mode="full")
        self.assertIn("white_flash", _codes(findings))

    def test_single_frame_white_flash(self):
        # 单帧白闪只有 full 模式（原生帧率解码）才保证可见。
        findings = review.review_video(str(self.white_in_still), mode="full")
        codes = _codes(findings)
        self.assertIn("white_flash", codes)

    def test_frozen_sequence(self):
        findings = review.review_video(str(self.frozen_head), mode="full")
        self.assertIn("frozen_sequence", _codes(findings))

    def test_entirely_still_video_is_frozen(self):
        findings = review.review_video(str(self.still_gray), mode="full")
        self.assertIn("frozen_sequence", _codes(findings))

    def test_abrupt_gap_single_frame(self):
        # OpenFilm `jumping frame` 的等价场景：黑色静止画面中掉入一帧灰帧。
        # 单帧黑/白由 black_frames/white_flash 通道负责，这里必须是非黑非白的
        # 异常帧，且两侧基线平稳。
        findings = review.review_video(str(self.gap_frame), mode="full")
        self.assertIn("abrupt_gap", _codes(findings))

    def test_visual_finding_carries_evidence_image(self):
        findings = review.review_video(str(self.white_head), mode="full")
        visual = next(f for f in findings if f.code == "white_flash")
        self.assertTrue(visual.evidence)
        # 证据图与成片同目录；script.json 里记的是相对 task_dir 的路径，
        # 测试里直接按文件名回捞。
        evidence_path = Path(_TMP.name) / os.path.basename(visual.evidence)
        self.assertTrue(evidence_path.is_file())

    def test_sample_mode_is_lighter_and_still_detects_sustained_defects(self):
        findings = review.review_video(str(self.frozen_head), mode="sample")
        self.assertIn("frozen_sequence", _codes(findings))


class TestAudioFindings(FixtureScope):
    def _codes_for(self, audio_path):
        # 把音频挂到干净画面上测量（mux 后统一走 review_video）。
        muxed = _mux(self.clean_silent, audio_path, f"probe-{audio_path.stem}.mp4")
        return _codes(review.review_video(str(muxed), mode="full"))

    def test_too_loud_and_clipping(self):
        codes = self._codes_for(self.hot)
        self.assertIn("too_loud", codes)
        self.assertIn("clipping", codes)

    def test_too_quiet(self):
        self.assertIn("too_quiet", self._codes_for(self.quiet))


class TestDurationMismatch(FixtureScope):
    def test_short_video_vs_long_narration(self):
        findings = review.review_video(
            str(self.clean_audio), audio_path=str(self.long_narration), mode="full"
        )
        self.assertIn("duration_mismatch", _codes(findings))

    def test_longer_video_than_narration_is_fine(self):
        findings = review.review_video(
            str(self.clean_audio), audio_path=str(self.loud_ok), mode="full"
        )
        self.assertNotIn("duration_mismatch", _codes(findings))


def _motion_frames(count=60):
    # 交替帧：luma 100/220，邻接差 120 > JUMP_DIFF，两侧天然"在运动"。
    values = [np.full((36, 64), 100 if i % 2 else 220, dtype=np.uint8) for i in range(count)]
    return np.stack(values)


class TestSyntheticVisualLogic(unittest.TestCase):
    """不碰磁盘：直接用 numpy 帧序列验证判据边界。"""

    def _codes(self, frames, fps=30):
        return _codes(review._find_visual_findings(frames, fps))

    def test_hard_cut_between_motion_is_not_a_gap(self):
        # 运动内容里插一帧黑：进入/离开跳变都存在，但外侧基线在运动——硬切，
        # 由 black_frames 之外的通道处理，不得报 abrupt_gap。
        frames = np.concatenate([
            _motion_frames(40),
            np.zeros((2, 36, 64), dtype=np.uint8),
            _motion_frames(40),
        ])
        self.assertNotIn("abrupt_gap", self._codes(frames))

    def test_isolated_spike_between_quiet_is_a_gap(self):
        quiet = np.full((45, 36, 64), 120, dtype=np.uint8)
        spike = np.full((1, 36, 64), 25, dtype=np.uint8)
        frames = np.concatenate([quiet, spike, quiet])
        self.assertIn("abrupt_gap", self._codes(frames))

    def test_white_spike_prefers_flash_channel(self):
        quiet = np.full((45, 36, 64), 120, dtype=np.uint8)
        spike = np.full((1, 36, 64), 250, dtype=np.uint8)
        frames = np.concatenate([quiet, spike, quiet])
        codes = self._codes(frames)
        self.assertIn("white_flash", codes)
        self.assertNotIn("abrupt_gap", codes)

    def test_gradual_black_transition_ignored(self):
        ramp_in = np.stack([
            np.full((36, 64), int(120 - 120 * i / 9), dtype=np.uint8) for i in range(10)
        ])
        black = np.zeros((20, 36, 64), dtype=np.uint8)
        ramp_out = np.stack([
            np.full((36, 64), int(20 + 100 * i / 9), dtype=np.uint8) for i in range(10)
        ])
        frames = np.concatenate([ramp_in, black, ramp_out])
        codes = self._codes(frames)
        self.assertNotIn("black_frames", codes)

    def test_sustained_black_after_hard_cut_flagged(self):
        frames = np.concatenate([
            np.full((45, 36, 64), 200, dtype=np.uint8),
            np.zeros((20, 36, 64), dtype=np.uint8),
            np.full((45, 36, 64), 200, dtype=np.uint8),
        ])
        self.assertIn("black_frames", self._codes(frames))


class TestReviewNeverRaises(FixtureScope):
    def test_internal_failure_degrades_to_review_unavailable(self):
        # 审查发生在任务末尾：自身环境问题绝不能把成功任务变成失败任务。
        # 用真实存在的成片 + 内部依赖抛异常，验证的是 except 收口而不是
        # 文件缺失的早退分支。
        with patch.object(review, "_measure_audio", side_effect=OSError("boom")):
            findings = review.review_video(str(self.clean_audio), mode="full")
        self.assertEqual(_codes(findings), ["review_unavailable"])
        self.assertEqual(findings[0].severity, "info")


class TestResolveMode(unittest.TestCase):
    def test_precedence_and_normalization(self):
        with ExitStack() as stack:
            get_patcher = stack.enter_context(patch.object(review.config.app, "get"))
            get_patcher.side_effect = lambda key, default=None: {
                "video_review": "full",
            }.get(key, default)
            self.assertEqual(review.resolve_mode(), "full")
            # 显式参数优先于配置。
            self.assertEqual(review.resolve_mode("sample"), "sample")
            get_patcher.side_effect = lambda key, default=None: default
            # 未配置默认 sample；bool 直觉写法映射 sample/off；未知值回落 sample。
            self.assertEqual(review.resolve_mode(None), "sample")
            self.assertEqual(review.resolve_mode(True), "sample")
            self.assertEqual(review.resolve_mode(False), "off")
            self.assertEqual(review.resolve_mode("nonsense"), "sample")

    def test_to_warning_shape_matches_task_warnings(self):
        finding = review.Finding(
            code="black_frames", severity="error", start=1.0, end=2.0, detail="d"
        )
        warning = finding.to_warning(video_index=3)
        self.assertEqual(warning["code"], "review_black_frames")
        self.assertEqual(warning["video_index"], 3)
        self.assertEqual(warning["severity"], "error")


if __name__ == "__main__":
    unittest.main()

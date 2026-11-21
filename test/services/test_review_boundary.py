# -*- coding: utf-8 -*-
"""scene_boundary_jump 边界审查测试（B5，真实 ffmpeg 夹具）。

阈值依据 calibrate-boundary-b5 实测：连续切点 diff ≤6.12，硬切 ≥103.9。
共享帧哨兵：连续运动切点必须安静；库存硬切必须告警且携带场景 order。
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import review


def render(ffmpeg, source, out):
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-y",
         "-f", "lavfi", "-i", source,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
        check=True, capture_output=True, timeout=120,
    )


def concat(ffmpeg, files, out, list_path):
    Path(list_path).write_text(
        "".join(f"file '{f}'\n" for f in files), encoding="utf-8"
    )
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out],
        check=True, capture_output=True, timeout=120,
    )


class BoundaryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = review._ffmpeg_binary()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = cls._tmp.name
        # 连续运动 6s：中段切点是共享帧哨兵的代理（运动连续，无内容跳）。
        cls.motion = str(Path(cls.tmp) / "motion.mp4")
        render(cls.ffmpeg, "testsrc2=size=320x240:rate=30:duration=6", cls.motion)
        # 红→绿硬切：库存切点的典型告警源。
        red = str(Path(cls.tmp) / "red.mp4")
        green = str(Path(cls.tmp) / "green.mp4")
        render(cls.ffmpeg, "color=c=red:size=320x240:rate=30:duration=2", red)
        render(cls.ffmpeg, "color=c=green:size=320x240:rate=30:duration=2", green)
        cls.hard = str(Path(cls.tmp) / "hard.mp4")
        concat(cls.ffmpeg, [red, green], cls.hard, str(Path(cls.tmp) / "list.txt"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def boundary(self, cut, **overrides):
        entry = {"scene_id": "s1", "order": 1, "cut": cut,
                 "shared": False, "transition": "none"}
        entry.update(overrides)
        return entry


class TestBoundaryFindings(BoundaryTestCase):
    def test_continuous_cut_is_quiet_sentinel(self):
        findings = review._boundary_findings(
            self.motion, [self.boundary(3.0, shared=True)], 6.0
        )
        self.assertEqual(findings, [])

    def test_hard_cut_reports_with_scene_order(self):
        findings = review._boundary_findings(
            self.hard, [self.boundary(2.0, order=2)], 4.0
        )
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.code, "scene_boundary_jump")
        self.assertEqual(finding.severity, "warn")
        self.assertEqual(finding.scene_order, 2)
        self.assertAlmostEqual(finding.start, 2.0)
        self.assertIn("scene 2", finding.detail)
        self.assertIn("frame diff", finding.detail)
        warning = finding.to_warning(video_index=0)
        self.assertEqual(warning["code"], "review_scene_boundary_jump")
        self.assertEqual(warning["scene_order"], 2)
        self.assertEqual(warning["video_index"], 0)

    def test_shared_hard_cut_still_reports(self):
        # 哨兵意义：共享标记不豁免检测，实测跳变照样报（文案额外提示）。
        findings = review._boundary_findings(
            self.hard, [self.boundary(2.0, shared=True)], 4.0
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("shared keyframe", findings[0].detail)

    def test_transition_masked_cut_skipped(self):
        for transition in ("fade", "slide", "zoom"):
            with self.subTest(transition=transition):
                findings = review._boundary_findings(
                    self.hard, [self.boundary(2.0, transition=transition)], 4.0
                )
                self.assertEqual(findings, [])

    def test_match_cut_and_none_are_checked(self):
        for transition in ("none", "match_cut"):
            with self.subTest(transition=transition):
                findings = review._boundary_findings(
                    self.hard, [self.boundary(2.0, transition=transition)], 4.0
                )
                self.assertEqual(len(findings), 1)

    def test_invalid_and_edge_cuts_skipped(self):
        boundaries = [
            self.boundary(0),          # 片头不是切点
            self.boundary(-1),         # 非法
            self.boundary("abc"),      # 非法
            self.boundary(3.99),       # 贴尾（4s 片）取不到后帧
        ]
        findings = review._boundary_findings(self.hard, boundaries, 4.0)
        self.assertEqual(findings, [])


class TestReviewVideoBoundaries(BoundaryTestCase):
    def test_boundaries_flow_through_review_video(self):
        findings = review.review_video(
            self.hard, mode="sample", boundaries=[self.boundary(2.0, order=1)]
        )
        codes = [f.code for f in findings]
        self.assertIn("scene_boundary_jump", codes)

    def test_no_boundaries_keeps_legacy_behavior(self):
        findings = review.review_video(self.hard, mode="sample")
        self.assertNotIn("scene_boundary_jump", [f.code for f in findings])

    def test_off_mode_skips_boundaries(self):
        findings = review.review_video(
            self.hard, mode="off", boundaries=[self.boundary(2.0)]
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
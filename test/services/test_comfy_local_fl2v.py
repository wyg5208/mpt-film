# -*- coding: utf-8 -*-
"""comfy_local FL2V 契约测试（B5）：官方 MiniMax H3 i2v 子图接线 + 视频缓存。

假 transport 不触网；graph 断言对照 video_minimax_h3_i2v.json 原生子图。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services import comfy_local as cl

DRAFT = cl.VIDEO_PRESETS["minimax-draft"]
FINAL = cl.VIDEO_PRESETS["minimax-final"]
ALL_OPTIONS = {
    "UNETLoader": [DRAFT["unet"], FINAL["unet"]],
    "CLIPLoader": [DRAFT["clip"]],
    "VAELoader": [DRAFT["vae"]],
    "LoraLoaderModelOnly": [DRAFT["lora"]],
}
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"v" * 40
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 25
VIDEO_FILE = {"filename": "changofilm/video_00001_.mp4", "subfolder": "", "type": "output"}


class FakeComfy:
    """假 ComfyUI：视频产物同样落在 history 的 images 键下（PreviewVideo）。"""

    def __init__(self, pending=2, options=None):
        self.calls = []
        self.asks = 0
        self.pending = pending
        self.options_map = options if options is not None else ALL_OPTIONS
        self.entry = {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {
                "15": {"images": [dict(VIDEO_FILE, type="temp"), VIDEO_FILE],
                       "animated": [True]}
            },
        }

    def online(self):
        self.calls.append(["online"])
        return True

    def options(self, class_type, field):
        self.calls.append(["options", class_type, field])
        return self.options_map.get(class_type, [])

    def submit(self, graph, prompt_id):
        self.calls.append(["submit", graph, prompt_id])

    def history(self, prompt_id):
        self.calls.append(["history", prompt_id])
        self.asks += 1
        return None if self.asks <= self.pending else self.entry

    def view(self, filename, subfolder, type_):
        self.calls.append(["view", filename, subfolder, type_])
        return MP4

    def upload(self, data, name):
        self.calls.append(["upload", data, name])
        return name

    def queue(self):
        self.calls.append(["queue"])
        return {"running": 0, "pending": 0}

    def order(self):
        return [c[0] for c in self.calls]

    def submitted(self):
        return next(c[1] for c in self.calls if c[0] == "submit")


class Fl2vTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            patch.object(cl, "_poll_interval", return_value=0.01),
            patch.object(cl, "_cache_dir", return_value=Path(self.tmp.name)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(cl.set_transport, None)
        self.addCleanup(cl.set_ws_factory, None)
        self.first = Path(self.tmp.name) / "first.png"
        self.first.write_bytes(PNG)
        self.last = Path(self.tmp.name) / "last.png"
        self.last.write_bytes(PNG)

    def run_video(self, api, **kwargs):
        cl.set_transport(api)
        kwargs.setdefault("out_name", "s1")
        kwargs.setdefault("first_frame", str(self.first))
        return cl.generate_video(kwargs.pop("prompt", "she turns around"), **kwargs)


class TestFl2vLength(unittest.TestCase):
    def test_grid_snap_up(self):
        # 17k+5 网格：124/141/158/…/362；向上贴齐，绝不向下。
        self.assertEqual(cl.fl2v_length(5.0), 124)  # 120 → 124
        self.assertEqual(cl.fl2v_length(6.0), 158)  # 144 → 158
        self.assertEqual(cl.fl2v_length(10.0), 243)  # 240 → 243
        self.assertEqual(cl.fl2v_length(15.0), 362)  # 360 → 362

    def test_clamped_to_trained_range(self):
        self.assertEqual(cl.fl2v_length(0.5), cl.FL2V_MIN_LENGTH)
        self.assertEqual(cl.fl2v_length(2.0), cl.FL2V_MIN_LENGTH)
        self.assertEqual(cl.fl2v_length(60.0), cl.FL2V_MAX_LENGTH)

    def test_all_lengths_on_grid(self):
        for sec in (0.1, 1, 3, 5.2, 7, 9.9, 12, 15, 30):
            length = cl.fl2v_length(sec)
            self.assertEqual((length - 5) % 17, 0, f"{sec}s -> {length}")
            self.assertGreaterEqual(length, cl.FL2V_MIN_LENGTH)
            self.assertLessEqual(length, cl.FL2V_MAX_LENGTH)


class TestFl2vGraph(unittest.TestCase):
    def build(self, preset, **kwargs):
        defaults = dict(prompt="p", width=768, height=1344, length=124,
                        steps=preset["steps"], seed=7,
                        first_frame="first.png", last_frame="last.png")
        defaults.update(kwargs)
        return cl.build_fl2v_graph(preset, **defaults)

    def test_draft_graph_matches_official_wiring(self):
        g = self.build(DRAFT)
        self.assertEqual(json.loads(json.dumps(g)), g)
        self.assertEqual(g["1"]["class_type"], "UNETLoader")
        self.assertEqual(g["1"]["inputs"]["unet_name"], DRAFT["unet"])
        self.assertEqual(g["2"]["class_type"], "LoraLoaderModelOnly")
        self.assertEqual(g["2"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["2"]["inputs"]["lora_name"], DRAFT["lora"])
        self.assertEqual(g["3"]["inputs"]["type"], "minimax")
        self.assertEqual(g["5"]["inputs"]["image"], "first.png")
        self.assertEqual(g["6"]["inputs"]["image"], "last.png")
        cond = g["7"]["inputs"]
        self.assertEqual(g["7"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertEqual(cond["clip"], ["3", 0])
        self.assertEqual(cond["vae"], ["4", 0])
        self.assertEqual(cond["first_frame"], ["5", 0])
        self.assertEqual(cond["last_frame"], ["6", 0])
        self.assertEqual(cond["length"], 124)
        # 蒸馏模型：BasicGuider 无负向条件，全图没有 CFG/负向编码节点。
        self.assertEqual(g["8"]["class_type"], "BasicGuider")
        self.assertEqual(g["8"]["inputs"]["model"], ["2", 0])
        self.assertEqual(g["8"]["inputs"]["conditioning"], ["7", 0])
        self.assertEqual(g["9"]["inputs"]["sampler_name"], "res_multistep")
        self.assertEqual(g["10"]["inputs"]["scheduler"], "simple")
        self.assertEqual(g["10"]["inputs"]["steps"], 4)
        self.assertEqual(g["10"]["inputs"]["denoise"], 1.0)
        self.assertEqual(g["11"]["inputs"]["noise_seed"], 7)
        sampler = g["12"]["inputs"]
        self.assertEqual(g["12"]["class_type"], "SamplerCustomAdvanced")
        self.assertEqual(sampler["latent_image"], ["7", 1])
        self.assertEqual(sampler["sigmas"], ["10", 0])
        self.assertEqual(sampler["guider"], ["8", 0])
        self.assertEqual(g["13"]["inputs"]["samples"], ["12", 0])
        self.assertEqual(g["14"]["inputs"]["fps"], 24)
        self.assertEqual(g["15"]["class_type"], "SaveVideo")
        self.assertEqual(g["15"]["inputs"]["video"], ["14", 0])
        types = {n["class_type"] for n in g.values()}
        self.assertNotIn("CLIPTextEncode", types)
        self.assertNotIn("KSampler", types)
        self.assertNotIn("MiniMaxH3SigmaShift", types)

    def test_final_graph_has_no_lora(self):
        g = self.build(FINAL)
        self.assertNotIn("2", g)
        self.assertEqual(g["8"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["10"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["10"]["inputs"]["steps"], 20)

    def test_last_frame_optional(self):
        g = self.build(DRAFT, last_frame="")
        self.assertNotIn("6", g)
        self.assertNotIn("last_frame", g["7"]["inputs"])
        self.assertIn("first_frame", g["7"]["inputs"])

    def test_weights_use_scheduler_steps(self):
        g = self.build(DRAFT)
        weights = cl._graph_weights(g)
        self.assertEqual(weights["12"], 4 * 10)
        self.assertEqual(weights["7"], 3)
        final_weights = cl._graph_weights(self.build(FINAL))
        self.assertEqual(final_weights["12"], 20 * 10)


class TestGenerateVideo(Fl2vTestCase):
    def test_call_order_and_landing(self):
        api = FakeComfy()
        result = self.run_video(api, aspect="9:16", last_frame=str(self.last))
        self.assertEqual(
            api.order(),
            ["online", "options", "options", "options", "options",
             "upload", "upload", "submit", "queue",
             "history", "history", "history", "view"],
        )
        self.assertEqual(api.calls[1], ["options", "UNETLoader", "unet_name"])
        self.assertEqual(api.calls[2], ["options", "CLIPLoader", "clip_name"])
        self.assertEqual(api.calls[3], ["options", "VAELoader", "vae_name"])
        self.assertEqual(api.calls[4], ["options", "LoraLoaderModelOnly", "lora_name"])
        graph = api.submitted()
        self.assertEqual(graph["7"]["inputs"]["width"], 768)
        self.assertEqual(graph["7"]["inputs"]["height"], 1344)
        self.assertEqual(graph["7"]["inputs"]["length"], 124)
        self.assertEqual(graph["5"]["inputs"]["image"], "first.png")
        self.assertEqual(graph["6"]["inputs"]["image"], "last.png")
        self.assertEqual(api.calls[-1], ["view", VIDEO_FILE["filename"], "", "output"])
        self.assertTrue(result["path"].endswith(".mp4"))
        self.assertEqual(Path(result["path"]).read_bytes(), MP4)
        self.assertEqual(result["seed"], graph["11"]["inputs"]["noise_seed"])
        self.assertEqual(result["receipt"]["workflow"], "fl2v")
        self.assertEqual(result["receipt"]["length"], 124)
        self.assertEqual(result["receipt"]["fps"], 24)
        self.assertFalse(result["cached"])

    def test_final_model_skips_lora_check_and_upload_of_last(self):
        api = FakeComfy()
        self.run_video(api, model="minimax-final")
        self.assertEqual(
            api.order(),
            ["online", "options", "options", "options",
             "upload", "submit", "queue", "history", "history", "history", "view"],
        )
        graph = api.submitted()
        self.assertNotIn("2", graph)
        self.assertNotIn("6", graph)

    def test_cache_hit_and_force(self):
        api = FakeComfy()
        first = self.run_video(api)
        again = self.run_video(FakeComfy())
        self.assertTrue(again["cached"])
        self.assertEqual(again["path"], first["path"])
        self.assertEqual(again["request_key"], first["request_key"])
        forced_api = FakeComfy()
        forced = self.run_video(forced_api, force=True)
        self.assertFalse(forced["cached"])
        self.assertIn("submit", forced_api.order())

    def test_same_grid_duration_reuses_artifact(self):
        # 5.0s 与 5.1s 都落在 124 帧：同指纹同产物，不重复烧 GPU。
        first = self.run_video(FakeComfy(), duration=5.0)
        again = self.run_video(FakeComfy(), duration=5.1)
        self.assertTrue(again["cached"])
        self.assertEqual(again["request_key"], first["request_key"])
        longer = self.run_video(FakeComfy(), duration=8.0)
        self.assertNotEqual(longer["request_key"], first["request_key"])

    def test_deterministic_seed(self):
        a = self.run_video(FakeComfy())
        b = self.run_video(FakeComfy(), force=True)
        self.assertEqual(a["seed"], b["seed"])
        c = self.run_video(FakeComfy(), prompt="different motion")
        self.assertNotEqual(a["seed"], c["seed"])

    def test_missing_model_translated(self):
        api = FakeComfy(options={"UNETLoader": []})
        with self.assertRaises(cl.ComfyLocalError) as ctx:
            self.run_video(api)
        self.assertIn("not registered", str(ctx.exception))

    def test_validation_errors(self):
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), prompt="  ")
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), aspect="21:9")
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), model="wan22")
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), duration=0)
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), first_frame="")
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(FakeComfy(), last_frame=str(Path(self.tmp.name) / "nope.png"))


class FreeVramComfy(FakeComfy):
    """带 /free 能力的假 ComfyUI：可选首次提交 OOM，验证卸载重试契约。"""

    def __init__(self, oom_once=False, oom_always=False, busy=False):
        super().__init__(pending=0)
        self.free_calls = 0
        self.busy = busy
        self.oom_once = oom_once
        self.oom_always = oom_always
        self.first_prompt = None
        self.error_entry = {
            "status": {
                "completed": False,
                "status_str": "error",
                "messages": [["execution_error", {
                    "node_type": "SamplerCustomAdvanced",
                    "exception_message": "CUDA out of memory. Tried to allocate 2 GiB",
                }]],
            },
            "outputs": {},
        }

    def free_memory(self):
        self.free_calls += 1
        self.calls.append(["free"])

    def queue(self):
        self.calls.append(["queue"])
        return {"running": 1 if self.busy else 0, "pending": 0}

    def submit(self, graph, prompt_id):
        super().submit(graph, prompt_id)
        if self.first_prompt is None:
            self.first_prompt = prompt_id

    def history(self, prompt_id):
        self.calls.append(["history", prompt_id])
        if self.oom_always or (self.oom_once and prompt_id == self.first_prompt):
            return self.error_entry
        return self.entry


class TestFl2vVramManagement(Fl2vTestCase):
    def test_proactive_free_before_submit_when_queue_idle(self):
        api = FreeVramComfy()
        self.run_video(api)
        order = api.order()
        self.assertIn("free", order)
        self.assertLess(order.index("free"), order.index("submit"))
        self.assertEqual(api.free_calls, 1)

    def test_free_skipped_when_queue_busy(self):
        # 队列非空时不卸载别人正在用的模型。
        api = FreeVramComfy(busy=True)
        self.run_video(api)
        self.assertEqual(api.free_calls, 0)
        self.assertNotIn("free", api.order())

    def test_oom_retries_once_after_free(self):
        api = FreeVramComfy(oom_once=True)
        result = self.run_video(api)
        self.assertFalse(result["cached"])
        self.assertTrue(Path(result["path"]).is_file())
        submits = [c for c in api.calls if c[0] == "submit"]
        self.assertEqual(len(submits), 2)
        self.assertNotEqual(submits[0][2], submits[1][2])
        # 预防性卸载 + OOM 后卸载，共两次。
        self.assertEqual(api.free_calls, 2)

    def test_oom_twice_raises_translated_error(self):
        api = FreeVramComfy(oom_always=True)
        with self.assertRaises(cl.ComfyLocalError) as ctx:
            self.run_video(api)
        self.assertIn("out of GPU memory", str(ctx.exception))
        self.assertEqual(len([c for c in api.calls if c[0] == "submit"]), 2)

    def test_non_oom_error_not_retried(self):
        api = FreeVramComfy()
        api.error_entry["status"]["messages"][0][1]["exception_message"] = "model not found"
        api.oom_always = True
        with self.assertRaises(cl.ComfyLocalError):
            self.run_video(api)
        self.assertEqual(len([c for c in api.calls if c[0] == "submit"]), 1)


if __name__ == "__main__":
    unittest.main()
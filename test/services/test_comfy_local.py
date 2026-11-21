# -*- coding: utf-8 -*-
"""comfy_local 契约测试（B3，移植 ChangoVideo comfy.test.mjs 语义）。

假 transport 记录调用顺序，不触网；真实客户端用桩 requests 验证错误翻译。
"""

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import acestep_local, comfy_local as cl

CHECKPOINT = "dreamshaperXL_lightningDPMSDE.safetensors"
QUALITY_CKPT = "dreamshaperXL10_alpha2Xl10.safetensors"
ALL_OPTIONS = {
    "CheckpointLoaderSimple": [CHECKPOINT, QUALITY_CKPT],
    "IPAdapterUnifiedLoader": ["PLUS (high strength)", "LIGHT - SD1.5 only (sdxl work)"],
}
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 25
FILE = {"filename": "changofilm/image_00001_.png", "subfolder": "", "type": "output"}


class FakeComfy:
    """假 ComfyUI：只回答本地引擎会回答的内容，calls 按序记录每次调用。"""

    def __init__(self, pending=2, file=None, data=None, options=None, history=None,
                 upload_name=None, queue=None):
        self.calls = []
        self.asks = 0
        self.pending = pending
        self.file = file or dict(FILE)
        self.data = data if data is not None else PNG
        self.options_map = options if options is not None else ALL_OPTIONS
        self.entry = history if history is not None else {
            "status": {"completed": True, "status_str": "success"},
            "outputs": {"7": {"images": [dict(self.file, type="temp"), self.file]}},
        }
        self.upload_name = upload_name
        self.queue_depth = queue or {"running": 0, "pending": 0}

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
        return self.data

    def upload(self, data, name):
        self.calls.append(["upload", data, name])
        return self.upload_name or name

    def queue(self):
        self.calls.append(["queue"])
        return self.queue_depth

    def order(self):
        return [c[0] for c in self.calls]

    def submitted(self):
        return next(c[1] for c in self.calls if c[0] == "submit")


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class ComfyLocalTestCase(unittest.TestCase):
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

    def run_image(self, api, **kwargs):
        cl.set_transport(api)
        kwargs.setdefault("out_name", "hero")
        return cl.generate_image(kwargs.pop("prompt", "a brass key"), **kwargs)


class TestGraphBuilders(ComfyLocalTestCase):
    def test_t2i_graph_is_api_format_json(self):
        g = cl.build_t2i_graph(cl.PRESETS["sdxl-lightning"], prompt="a key",
                               negative="bad", width=1024, height=576, steps=6, seed=7)
        self.assertEqual(json.loads(json.dumps(g)), g)
        self.assertEqual(g["7"]["class_type"], "SaveImage")
        self.assertEqual(g["5"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["6"]["inputs"]["vae"], ["1", 2])
        self.assertEqual(g["4"]["inputs"]["width"], 1024)
        self.assertEqual(g["2"]["inputs"]["clip"], ["1", 1])

    def test_ipadapter_graph_wiring(self):
        g = cl.build_ipadapter_graph(cl.PRESETS["sdxl-lightning"], prompt="p",
                                     negative="n", width=576, height=1024, steps=6,
                                     seed=7, image_name="ref.png", weight=0.7)
        self.assertEqual(json.loads(json.dumps(g)), g)
        self.assertEqual(g["2"]["inputs"]["image"], "ref.png")
        self.assertEqual(g["3"]["inputs"]["model"], ["1", 0])
        self.assertEqual(g["4"]["inputs"]["ipadapter"], ["3", 1])
        self.assertEqual(g["4"]["inputs"]["image"], ["2", 0])
        self.assertEqual(g["4"]["inputs"]["weight"], 0.7)
        self.assertEqual(g["8"]["inputs"]["model"], ["4", 0])
        self.assertEqual(g["9"]["inputs"]["vae"], ["1", 2])
        self.assertEqual(g["10"]["class_type"], "SaveImage")


class TestGenerateImage(ComfyLocalTestCase):
    def test_call_order_graph_and_landing(self):
        api = FakeComfy()
        result = self.run_image(api, aspect="16:9")
        self.assertEqual(api.order(),
                         ["online", "options", "submit", "queue",
                          "history", "history", "history", "view"])
        self.assertEqual(api.calls[1], ["options", "CheckpointLoaderSimple", "ckpt_name"])
        graph = api.submitted()
        self.assertEqual(graph["4"]["inputs"]["width"], 1024)
        self.assertEqual(graph["4"]["inputs"]["height"], 576)
        self.assertEqual(graph["5"]["inputs"]["steps"], 6)
        self.assertEqual(graph["2"]["inputs"]["text"], "a brass key")
        self.assertIn("low quality", graph["3"]["inputs"]["text"])
        self.assertEqual(api.calls[-1], ["view", FILE["filename"], "", "output"])
        self.assertTrue(result["path"].endswith(".png"))
        self.assertEqual(Path(result["path"]).read_bytes(), PNG)
        self.assertEqual(result["seed"], graph["5"]["inputs"]["seed"])
        self.assertEqual(result["receipt"]["workflow"], "t2i")
        self.assertEqual(result["receipt"]["provider"], "comfy_local")
        self.assertFalse(result["cached"])

    def test_same_words_same_seed(self):
        one = FakeComfy()
        self.run_image(one, aspect="16:9")
        again = FakeComfy()
        self.run_image(again, aspect="16:9", force=True)
        self.assertEqual(one.submitted()["5"]["inputs"]["seed"],
                         again.submitted()["5"]["inputs"]["seed"])
        other = FakeComfy()
        self.run_image(other, prompt="a silver key")
        self.assertNotEqual(one.submitted()["5"]["inputs"]["seed"],
                            other.submitted()["5"]["inputs"]["seed"])

    def test_quality_preset_parameter_pack(self):
        api = FakeComfy()
        self.run_image(api, model="sdxl-quality")
        graph = api.submitted()
        self.assertEqual(graph["1"]["inputs"]["ckpt_name"], QUALITY_CKPT)
        self.assertEqual(graph["5"]["inputs"]["steps"], 28)
        self.assertEqual(graph["5"]["inputs"]["cfg"], 1.8)

    def test_invalid_inputs_refused_before_any_call(self):
        api = FakeComfy()
        cl.set_transport(api)
        with self.assertRaisesRegex(cl.ComfyLocalError, "aspect is one of"):
            cl.generate_image("y", aspect="21:9")
        with self.assertRaisesRegex(cl.ComfyLocalError, "prompt is required"):
            cl.generate_image("  ")
        with self.assertRaisesRegex(cl.ComfyLocalError, "model is one of"):
            cl.generate_image("y", model="nope")
        self.assertEqual(api.calls, [])

    def test_reference_image_uploads_before_submit(self):
        ref = Path(self.tmp.name) / "ref.png"
        ref.write_bytes(PNG)
        api = FakeComfy(upload_name="ref (1).png")
        result = self.run_image(api, reference_image=str(ref), reference_weight=0.6)
        order = api.order()
        self.assertLess(order.index("upload"), order.index("submit"))
        self.assertIn(["options", "IPAdapterUnifiedLoader", "preset"], api.calls)
        graph = api.submitted()
        self.assertEqual(graph["2"]["inputs"]["image"], "ref (1).png")
        self.assertEqual(graph["4"]["inputs"]["weight"], 0.6)
        self.assertEqual(result["receipt"]["workflow"], "t2i-ipadapter")


class TestModelPreflight(ComfyLocalTestCase):
    def test_unregistered_folder_said_before_submit(self):
        api = FakeComfy(options={"CheckpointLoaderSimple": []})
        with self.assertRaisesRegex(cl.ComfyLocalError,
                                    r"lists no checkpoint files at all.*extra_model_paths\.yaml"):
            self.run_image(api)
        self.assertNotIn("submit", api.order())

    def test_missing_file_named(self):
        api = FakeComfy(options={"CheckpointLoaderSimple": ["another.safetensors"]})
        with self.assertRaisesRegex(cl.ComfyLocalError,
                                    f'does not know the checkpoint "{CHECKPOINT}"'):
            self.run_image(api)
        self.assertNotIn("submit", api.order())


class TestHistoryFailures(ComfyLocalTestCase):
    @staticmethod
    def failure(message):
        return {"status": {"completed": True, "status_str": "error",
                           "messages": [["execution_error",
                                         {"node_type": "KSampler",
                                          "exception_message": message}]]},
                "outputs": {}}

    def test_failure_translations(self):
        cases = [
            ("CUDA out of memory. Tried to allocate 2 GiB", r"ran out of GPU memory \(node KSampler\)"),
            ("No such file or directory: model.safetensors", r"could not find a model or file \(node KSampler\)"),
            ("something broke", r"node KSampler failed: something broke"),
        ]
        for message, expected in cases:
            api = FakeComfy(pending=0, history=self.failure(message))
            with self.assertRaisesRegex(cl.ComfyLocalError, expected):
                self.run_image(api)

    def test_completed_without_output(self):
        api = FakeComfy(pending=0, history={"status": {"completed": True}, "outputs": {}})
        with self.assertRaisesRegex(cl.ComfyLocalError, "finished without a file to hand back"):
            self.run_image(api)


class TestCancellation(ComfyLocalTestCase):
    def test_cancel_stops_asking(self):
        stop = threading.Event()
        api = FakeComfy(pending=100)
        original = api.history

        def history_then_stop(prompt_id):
            entry = original(prompt_id)
            stop.set()
            return entry

        api.history = history_then_stop
        cl.set_transport(api)
        with self.assertRaisesRegex(cl.ComfyLocalError, "cancelled"):
            cl.generate_image("y", stop_event=stop)
        self.assertEqual(api.order().count("history"), 1)


class TestProgress(ComfyLocalTestCase):
    def test_coarse_phases_without_socket(self):
        coarse = []
        self.run_image(FakeComfy(), on_progress=coarse.append)
        self.assertEqual([p["phase"] for p in coarse], ["load", "queue", "sample", "decode"])
        self.assertTrue(all("value" not in p and "max" not in p for p in coarse))

    def test_ws_weighted_percent_and_close(self):
        ws = {"url": "", "on_message": None, "closed": False}

        def make(url, on_message):
            ws["url"] = url
            ws["on_message"] = on_message
            return lambda: ws.update(closed=True)

        cl.set_ws_factory(make)
        fine = []
        api = FakeComfy(pending=1)
        original = api.history

        def history_with_progress(prompt_id):
            entry = original(prompt_id)
            if api.asks == 1:
                # 只有采样器（节点 5，6 步→权重 60）上报，完成一半：30/60 → 50%
                ws["on_message"](json.dumps({
                    "type": "progress_state",
                    "data": {"prompt_id": prompt_id, "nodes": {"5": {"value": 3, "max": 6}}},
                }))
                # 别的任务的进度必须被忽略
                ws["on_message"](json.dumps({
                    "type": "progress_state",
                    "data": {"prompt_id": "other", "nodes": {"5": {"value": 6, "max": 6}}},
                }))
            return entry

        api.history = history_with_progress
        self.run_image(api, on_progress=fine.append)
        weighted = [p for p in fine if p.get("max") == 100]
        self.assertTrue(weighted)
        self.assertEqual(weighted[0]["phase"], "sample")
        self.assertEqual(weighted[0]["value"], 50)
        self.assertTrue(ws["url"].endswith("/ws?clientId=changofilm-local-engines"))
        self.assertTrue(ws["closed"])

    def test_ws_factory_failure_degrades_silently(self):
        def broken(url, on_message):
            raise OSError("no socket")

        cl.set_ws_factory(broken)
        coarse = []
        result = self.run_image(FakeComfy(), on_progress=coarse.append)
        self.assertFalse(result["cached"])
        self.assertEqual([p["phase"] for p in coarse], ["load", "queue", "sample", "decode"])


class TestQueueReporting(ComfyLocalTestCase):
    def test_jobs_ahead_said_and_kept(self):
        api = FakeComfy(queue={"running": 1, "pending": 2})
        result = self.run_image(api)
        notes = result["receipt"]["notes"]
        self.assertTrue(any("2 jobs ahead" in n for n in notes))
        order = api.order()
        self.assertGreater(order.index("queue"), order.index("submit"))

    def test_quiet_queue_says_nothing(self):
        result = self.run_image(FakeComfy())
        self.assertNotIn("notes", result["receipt"])


class TestRequestKeyCache(ComfyLocalTestCase):
    def test_cache_hit_skips_engine(self):
        first = self.run_image(FakeComfy())
        self.assertFalse(first["cached"])
        silent = FakeComfy()
        second = self.run_image(silent)
        self.assertTrue(second["cached"])
        self.assertEqual(second["path"], first["path"])
        self.assertEqual(second["seed"], first["seed"])
        self.assertEqual(silent.calls, [])

    def test_force_regenerates(self):
        self.run_image(FakeComfy())
        again = FakeComfy()
        result = self.run_image(again, force=True)
        self.assertFalse(result["cached"])
        self.assertIn("submit", again.order())

    def test_sidecar_mismatch_regenerates(self):
        first = self.run_image(FakeComfy())
        key_file = Path(first["path"] + ".key")
        stored = json.loads(key_file.read_text(encoding="utf-8"))
        stored["key"] = "stale"
        key_file.write_text(json.dumps(stored), encoding="utf-8")
        again = FakeComfy()
        result = self.run_image(again)
        self.assertFalse(result["cached"])
        self.assertIn("submit", again.order())

    def test_missing_artifact_regenerates(self):
        first = self.run_image(FakeComfy())
        Path(first["path"]).unlink()
        result = self.run_image(FakeComfy())
        self.assertFalse(result["cached"])

    def test_key_stableAcross_arg_order(self):
        k1 = cl.request_key("image", "sdxl-lightning", {"b": 2, "a": 1})
        k2 = cl.request_key("image", "sdxl-lightning", {"a": 1, "b": 2})
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, cl.request_key("image", "sdxl-quality", {"a": 1, "b": 2}))
        self.assertNotEqual(k1, cl.request_key("music", "sdxl-lightning", {"a": 1, "b": 2}))


class TestRealClient(unittest.TestCase):
    """真实 _HttpTransport 对桩 requests：不触网验证错误翻译与两种 COMBO 形状。"""

    def setUp(self):
        self.addCleanup(cl.set_transport, None)
        cfg = patch.dict(config.app, {"comfyui_base_url": "http://127.0.0.1:9"})
        cfg.start()
        self.addCleanup(cfg.stop)
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        p = patch.object(cl, "_cache_dir", return_value=Path(cache.name))
        p.start()
        self.addCleanup(p.stop)

    def test_not_running_said_plainly(self):
        with patch.object(cl.requests, "request", side_effect=cl.requests.ConnectionError("refused")):
            with self.assertRaisesRegex(cl.ComfyLocalError,
                                        r"ComfyUI is not running at http://127\.0\.0\.1:9\. Start it first"):
                cl.generate_image("y")
        self.assertFalse(cl.is_online())

    def test_timeout_said_plainly(self):
        with patch.object(cl.requests, "request", side_effect=cl.requests.Timeout("slow")):
            with self.assertRaisesRegex(cl.ComfyLocalError, "did not answer within"):
                cl.generate_image("y")

    def test_400_translated_old_combo_shape(self):
        rejected = {"node_errors": {"1": {
            "class_type": "CheckpointLoaderSimple",
            "errors": [{"message": "Value not in list",
                        "details": f"ckpt_name: '{CHECKPOINT}' not in ['other.safetensors']"}]}}}

        def stub(method, url, **kwargs):
            if url.endswith("/system_stats"):
                return FakeResponse(payload={})
            if url.endswith("/object_info/CheckpointLoaderSimple"):
                return FakeResponse(payload={
                    "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [[CHECKPOINT]]}}}})
            if url.endswith("/prompt"):
                return FakeResponse(status_code=400, payload=rejected)
            return FakeResponse(status_code=404, payload={})

        with patch.object(cl.requests, "request", side_effect=stub):
            with self.assertRaisesRegex(cl.ComfyLocalError,
                                        "rejected the workflow → model name does not exist"):
                cl.generate_image("y")

    def test_403_names_origin_middleware_new_combo_shape(self):
        seen = []

        def stub(method, url, **kwargs):
            if url.endswith("/system_stats"):
                return FakeResponse(payload={})
            if url.endswith("/object_info/CheckpointLoaderSimple"):
                seen.append(url)
                return FakeResponse(payload={
                    "CheckpointLoaderSimple": {"input": {"required": {
                        "ckpt_name": ["COMBO", {"options": [CHECKPOINT]}]}}}})
            if url.endswith("/prompt"):
                return FakeResponse(status_code=403)
            return FakeResponse(status_code=404, payload={})

        with patch.object(cl.requests, "request", side_effect=stub):
            with self.assertRaisesRegex(cl.ComfyLocalError,
                                        "origin middleware accepts local server-side calls only"):
                cl.generate_image("y")
        self.assertTrue(seen)


class TestLocalEnginesStatus(unittest.TestCase):
    def setUp(self):
        self.addCleanup(cl.set_transport, None)
        self.addCleanup(acestep_local.set_transport, None)

    def test_all_offline_degrades_without_raising(self):
        class Dead:
            def online(self):
                raise RuntimeError("offline")

        cl.set_transport(Dead())
        acestep_local.set_transport(Dead())
        with patch.object(cl.requests, "get", side_effect=cl.requests.ConnectionError("refused")):
            status = cl.local_engines_status()
        self.assertEqual(set(status), {"comfyui", "acestep", "ollama"})
        for engine in status.values():
            self.assertFalse(engine["online"])
            self.assertTrue(engine["base_url"])

    def test_all_online_and_v1_stripped_for_tags(self):
        class Alive:
            def online(self):
                return True

        cl.set_transport(Alive())
        acestep_local.set_transport(Alive())
        urls = []

        def stub_get(url, **kwargs):
            urls.append(url)
            return FakeResponse(payload={"models": []})

        with patch.dict(config.app, {"ollama_base_url": "http://127.0.0.1:11434/v1"}):
            with patch.object(cl.requests, "get", side_effect=stub_get):
                status = cl.local_engines_status()
        self.assertTrue(all(e["online"] for e in status.values()))
        self.assertEqual(urls, ["http://127.0.0.1:11434/api/tags"])
        self.assertEqual(status["ollama"]["base_url"], "http://127.0.0.1:11434")


if __name__ == "__main__":
    unittest.main()
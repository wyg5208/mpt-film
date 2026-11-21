# -*- coding: utf-8 -*-
"""acestep_local 契约测试（B3，移植 ChangoVideo acestep.test.mjs 语义）。

假 transport 记录调用顺序，不触网；300 s 预热契约、keep-alive 重试、
urlencoded Windows 路径与扩展名白名单逐条验证。
"""

import json
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.services import acestep_local as al


def mp3(seconds):
    """定码率 128 kbps 的 MP3 体积（服务器就是这么存的）。"""
    return b"\x00" * round(seconds * 16000)


def make_wav(pcm, sample_rate=16000, channels=1, bits=16):
    byte_rate = sample_rate * channels * bits // 8
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate,
                      channels * bits // 8, bits)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


WAV = make_wav(b"\x00" * 64000)  # 16-bit 单声道 16 kHz：两秒
FILE = "/v1/audio?path=" + quote("D:\\ace-step\\tmp\\api_audio\\track-1.mp3", safe="")


def result_json(**over):
    item = {"file": FILE, "status": 1, "metas": {"duration": 30},
            "seed_value": "7", "dit_model": "acestep-v15-turbo"}
    item.update(over)
    return json.dumps([item])


class FakeAce:
    """假 ACE-Step：只回答本地 API 服务器会回答的内容，calls 按序记录。"""

    def __init__(self, pending=1, status=None, result=None, data=None,
                 drop=(), fail=False, task_id="task-1"):
        self.calls = []
        self.asks = 0
        self.pending = pending
        self.status = status
        self.result = result
        self.data = data if data is not None else mp3(30)
        self.drop = set(drop)
        self.fail = fail
        self.task_id = task_id

    def online(self):
        self.calls.append(["online"])
        return True

    def submit(self, body):
        self.calls.append(["submit", body])
        return self.task_id

    def query(self, task_id):
        self.calls.append(["query", task_id])
        self.asks += 1
        if self.fail or self.asks in self.drop:
            raise al.AceStepLocalError("the server closed a keep-alive connection")
        if self.asks <= self.pending:
            return {"task_id": task_id, "status": 0, "result": ""}
        return {"task_id": task_id, "status": self.status if self.status is not None else 1,
                "result": self.result if self.result is not None else result_json()}

    def audio(self, file):
        self.calls.append(["audio", file])
        return self.data

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


class AceStepLocalTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            patch.object(al, "_poll_interval", return_value=0.01),
            patch.object(al, "_cache_dir", return_value=Path(self.tmp.name)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(al.set_transport, None)

    def run_music(self, api, **kwargs):
        al.set_transport(api)
        kwargs.setdefault("out_name", "bed")
        return al.generate_music(kwargs.pop("prompt", "calm pad"), **kwargs)


class TestGenerateMusic(AceStepLocalTestCase):
    def test_call_order_and_pure_dit_defaults(self):
        api = FakeAce()
        made = self.run_music(api)
        self.assertEqual(api.order(), ["online", "submit", "query", "query", "audio"])
        body = api.submitted()
        self.assertEqual(body["prompt"], "calm pad")
        self.assertEqual(body["lyrics"], "[instrumental]")
        self.assertEqual(body["task_type"], "text2music")
        self.assertFalse(body["thinking"])
        self.assertFalse(body["use_cot_caption"])
        self.assertFalse(body["use_cot_language"])
        self.assertEqual(body["audio_duration"], 30)
        self.assertEqual(body["audio_format"], "mp3")
        self.assertEqual(body["batch_size"], 1)
        self.assertEqual(body["model"], "acestep-v15-turbo")
        self.assertEqual(body["inference_steps"], 8)
        self.assertFalse(body["use_random_seed"])
        self.assertNotIn("vocal_language", body)
        self.assertEqual(api.calls[-1], ["audio", FILE])
        self.assertTrue(made["path"].endswith(".mp3"))
        self.assertEqual(Path(made["path"]).read_bytes(), mp3(30))
        self.assertEqual(made["dur"], 30)
        self.assertEqual(made["receipt"]["provider"], "acestep_local")
        self.assertEqual(made["receipt"]["seed"], body["seed"])
        self.assertNotIn("notes", made["receipt"])
        self.assertNotIn("vocals", made["receipt"])
        self.assertNotIn("think", made["receipt"])
        self.assertFalse(made["cached"])

    def test_length_clamped_and_said(self):
        api = FakeAce()
        asked = self.run_music(api, duration=45)
        self.assertEqual(api.submitted()["audio_duration"], 45)
        self.assertNotIn("notes", asked["receipt"])
        short = FakeAce()
        five = self.run_music(short, duration=5)
        self.assertEqual(short.submitted()["audio_duration"], 10)
        self.assertIn("10–600 s tracks: 10 s", five["receipt"]["notes"][0])
        long = FakeAce()
        seven = self.run_music(long, duration=700)
        self.assertEqual(long.submitted()["audio_duration"], 600)
        self.assertIn("10–600 s tracks: 600 s", seven["receipt"]["notes"][0])

    def test_same_words_same_seed(self):
        one = FakeAce()
        self.run_music(one)
        again = FakeAce()
        self.run_music(again, force=True)
        self.assertEqual(one.submitted()["seed"], again.submitted()["seed"])
        other = FakeAce()
        self.run_music(other, prompt="bright synths")
        self.assertNotEqual(one.submitted()["seed"], other.submitted()["seed"])

    def test_lyrics_lang_think_ride_along(self):
        words = "[Verse]\nSunlight through the window\n\n[Chorus]\nWe are the dreamers"
        api = FakeAce()
        made = self.run_music(api, prompt="warm pop ballad, female vocal",
                              lyrics=words, lang="en", think=True)
        body = api.submitted()
        self.assertEqual(body["lyrics"], words)
        self.assertEqual(body["vocal_language"], "en")
        self.assertTrue(body["thinking"])
        self.assertFalse(body["use_cot_caption"])
        self.assertEqual(made["receipt"]["vocals"], "en")
        self.assertTrue(made["receipt"]["think"])
        # 歌词参与 seed：同词同曲，换词换曲
        again = FakeAce()
        self.run_music(again, prompt="warm pop ballad, female vocal",
                       lyrics=words, lang="en", think=True, force=True)
        self.assertEqual(again.submitted()["seed"], body["seed"])
        changed = FakeAce()
        self.run_music(changed, prompt="warm pop ballad, female vocal",
                       lyrics="[Verse]\nDifferent words", lang="en", think=True)
        self.assertNotEqual(changed.submitted()["seed"], body["seed"])

    def test_prompt_required(self):
        api = FakeAce()
        al.set_transport(api)
        with self.assertRaisesRegex(al.AceStepLocalError, "prompt is required"):
            al.generate_music("   ")
        self.assertEqual(api.calls, [])


class TestResultPaths(AceStepLocalTestCase):
    @staticmethod
    def file_of(path):
        return "/v1/audio?path=" + quote(path, safe="")

    def test_wav_length_from_header(self):
        api = FakeAce(data=WAV, result=result_json(file=self.file_of("D:\\tmp\\my track.wav")))
        made = self.run_music(api)
        self.assertTrue(made["path"].endswith(".wav"))
        self.assertEqual(made["dur"], 2)

    def test_flac_length_from_metas(self):
        api = FakeAce(result=result_json(file=self.file_of("D:\\tmp\\track.flac"),
                                         metas={"duration": 45}))
        made = self.run_music(api)
        self.assertTrue(made["path"].endswith(".flac"))
        self.assertEqual(made["dur"], 45)

    def test_non_whitelisted_extension_lands_as_mp3(self):
        api = FakeAce(result=result_json(file=self.file_of("D:\\tmp\\track.bin")))
        made = self.run_music(api)
        self.assertTrue(made["path"].endswith(".mp3"))

    def test_plain_path_own_extension(self):
        api = FakeAce(result=result_json(file="/v1/audio/track.ogg", metas={"duration": 12}))
        made = self.run_music(api)
        self.assertTrue(made["path"].endswith(".ogg"))
        self.assertEqual(made["dur"], 12)

    def test_ext_of_path_decodes_windows_path(self):
        self.assertEqual(al.ext_of_path(self.file_of("D:\\x\\a.wav")), "wav")
        self.assertEqual(al.ext_of_path(self.file_of("D:\\x\\a.bin")), "mp3")
        self.assertEqual(al.ext_of_path("/v1/audio/a.flac"), "flac")
        self.assertEqual(al.ext_of_path("no-extension"), "mp3")


class TestResilience(AceStepLocalTestCase):
    def test_keep_alive_drop_asked_again(self):
        api = FakeAce(drop=[1, 2])
        made = self.run_music(api)
        self.assertTrue(made["path"].endswith(".mp3"))
        self.assertEqual(api.order().count("query"), 3)

    def test_dead_server_given_up_on_after_ten(self):
        api = FakeAce(fail=True)
        with self.assertRaisesRegex(al.AceStepLocalError, "stopped answering after 10 tries"):
            self.run_music(api)
        self.assertEqual(api.order().count("query"), 10)

    def test_warmup_deadline_is_retryable(self):
        api = FakeAce(pending=10000)
        with patch.object(al, "RUN_TIMEOUT_SECONDS", 0.05):
            with self.assertRaisesRegex(al.AceStepLocalError,
                                        "wait a moment, then run the same request again"):
                self.run_music(api)

    def test_cancel_stops_asking(self):
        stop = threading.Event()
        api = FakeAce(pending=100)
        original = api.query

        def query_then_stop(task_id):
            item = original(task_id)
            stop.set()
            return item

        api.query = query_then_stop
        al.set_transport(api)
        with self.assertRaisesRegex(al.AceStepLocalError, "cancelled"):
            al.generate_music("y", stop_event=stop)
        self.assertEqual(api.order().count("query"), 1)


class TestFailedTasks(AceStepLocalTestCase):
    def test_json_error_reason(self):
        api = FakeAce(pending=0, status=2,
                      result=json.dumps([{"status": 2, "error": "CUDA out of memory"}]))
        with self.assertRaisesRegex(al.AceStepLocalError,
                                    "could not make the music: CUDA out of memory"):
            self.run_music(api)

    def test_plain_text_reason(self):
        api = FakeAce(pending=0, status=2, result="model file missing")
        with self.assertRaisesRegex(al.AceStepLocalError,
                                    "could not make the music: model file missing"):
            self.run_music(api)

    def test_result_without_file_refused(self):
        api = FakeAce(pending=0, result=json.dumps([{"status": 1}]))
        with self.assertRaisesRegex(al.AceStepLocalError, "finished without a file to hand back"):
            self.run_music(api)

    def test_broken_result_refused(self):
        api = FakeAce(pending=0, result="not json")
        with self.assertRaisesRegex(al.AceStepLocalError, "finished without a file to hand back"):
            self.run_music(api)


class TestProgressAndCache(AceStepLocalTestCase):
    def test_coarse_phases_in_order(self):
        phases = []
        self.run_music(FakeAce(), on_progress=phases.append)
        self.assertEqual([p["phase"] for p in phases], ["queue", "sample", "decode"])
        self.assertTrue(all("value" not in p and "max" not in p for p in phases))

    def test_cache_hit_skips_engine(self):
        first = self.run_music(FakeAce())
        silent = FakeAce()
        second = self.run_music(silent)
        self.assertTrue(second["cached"])
        self.assertEqual(second["path"], first["path"])
        self.assertEqual(second["dur"], first["dur"])
        self.assertEqual(silent.calls, [])

    def test_force_regenerates(self):
        self.run_music(FakeAce())
        again = FakeAce()
        made = self.run_music(again, force=True)
        self.assertFalse(made["cached"])
        self.assertIn("submit", again.order())

    def test_sidecar_mismatch_regenerates(self):
        first = self.run_music(FakeAce())
        key_file = Path(self.tmp.name) / f"{first['request_key']}.key"
        stored = json.loads(key_file.read_text(encoding="utf-8"))
        stored["key"] = "stale"
        key_file.write_text(json.dumps(stored), encoding="utf-8")
        made = self.run_music(FakeAce())
        self.assertFalse(made["cached"])

    def test_missing_artifact_regenerates(self):
        first = self.run_music(FakeAce())
        Path(first["path"]).unlink()
        made = self.run_music(FakeAce())
        self.assertFalse(made["cached"])


class TestRealClient(unittest.TestCase):
    """真实 _HttpTransport 对桩 requests：编码路径原样保留，不触网。"""

    def setUp(self):
        self.addCleanup(al.set_transport, None)
        cfg = patch.dict(config.app, {"acestep_base_url": "http://127.0.0.1:9"})
        cfg.start()
        self.addCleanup(cfg.stop)
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        p = patch.object(al, "_cache_dir", return_value=Path(cache.name))
        p.start()
        self.addCleanup(p.stop)
        poll = patch.object(al, "_poll_interval", return_value=0.01)
        poll.start()
        self.addCleanup(poll.stop)

    def test_not_running_said_plainly(self):
        with patch.object(al.requests, "request", side_effect=al.requests.ConnectionError("refused")):
            with self.assertRaisesRegex(al.AceStepLocalError,
                                        r"ACE-Step is not running at http://127\.0\.0\.1:9\. "
                                        r"Start it first \(start_api_server\.bat\)"):
                al.generate_music("y")
        self.assertFalse(al.is_online())

    def test_full_flow_encoded_path_untouched(self):
        urls = []
        bodies = {}

        def stub(method, url, **kwargs):
            urls.append(url)
            if url.endswith("/health"):
                return FakeResponse(payload={"data": {"status": "ok"}, "code": 200})
            if url.endswith("/release_task"):
                bodies["submit"] = kwargs.get("json")
                return FakeResponse(payload={"data": {"task_id": "t-9"}, "code": 200})
            if url.endswith("/query_result"):
                bodies["query"] = kwargs.get("json")
                return FakeResponse(payload={"data": [
                    {"task_id": "t-9", "status": 1, "result": result_json()}], "code": 200})
            if "/v1/audio" in url:
                return FakeResponse(content=mp3(30))
            return FakeResponse(status_code=404, payload={})

        with patch.object(al.requests, "request", side_effect=stub):
            made = al.generate_music("calm pad", duration=30)
        self.assertEqual(bodies["query"], {"task_id_list": ["t-9"]})
        self.assertEqual(bodies["submit"]["lyrics"], "[instrumental]")
        self.assertFalse(bodies["submit"]["thinking"])
        self.assertEqual(urls[0], "http://127.0.0.1:9/health")
        self.assertEqual(urls[-1], "http://127.0.0.1:9" + FILE)
        self.assertTrue(made["path"].endswith(".mp3"))
        self.assertEqual(made["dur"], 30)

    def test_submit_without_id_says_server_reason(self):
        def stub(method, url, **kwargs):
            if url.endswith("/health"):
                return FakeResponse(payload={"data": {"status": "ok"}})
            if url.endswith("/release_task"):
                return FakeResponse(payload={"data": None, "code": 500, "error": "no GPU here"})
            return FakeResponse(status_code=404, payload={})

        with patch.object(al.requests, "request", side_effect=stub):
            with self.assertRaisesRegex(al.AceStepLocalError,
                                        "took the task but gave no id: no GPU here"):
                al.generate_music("y")


if __name__ == "__main__":
    unittest.main()
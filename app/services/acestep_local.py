"""ACE-Step 本地音乐引擎（脚本方案专业模式，B3）。

移植 ChangoVideo acestep.mjs 已验证契约：裸 origin http://127.0.0.1:8001
（config 可覆盖）；POST /release_task 提交 → POST /query_result 轮询
（status 0 运行/1 完成/2 失败）→ 按结果自带的地址取音频
（/v1/audio?path=<urlencoded Windows 路径>，编码原样保留）。
'[instrumental]' 是纯伴奏开关，真歌词出人声；turbo 蒸馏模型锁 8 步。
FNV-1a 确定性 seed（model|out|prompt|lyrics|lang|think），同词同曲。

预热契约：刚启动的服务器要花几分钟加载模型，等待上限 300 s，超时给出
可重试的白话提示；偶发 keep-alive 断连重试，连续 10 次失败才放弃。
免费免 Key：用户自己的 GPU。绝不对 ACE-Step 环境跑 uv sync（会卸掉
文件源安装的 torch）。
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from loguru import logger

from app.config import config
from app.services.comfy_local import request_key, seed_of
from app.utils import utils
from app.utils.request_logging import trace_http_call

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
PROVIDER_ID = "acestep_local"

# turbo 是蒸馏模型：8 步、无 CFG，步数锁死不开放。
MUSIC_MODEL = "acestep-v15-turbo"
STEPS = 8
# API 的时长范围；不指定时来半分钟背景音乐。
LENGTH_MIN = 10
LENGTH_MAX = 600
LENGTH_DEFAULT = 30
# 结果路径可能携带的扩展名；其余一律按 mp3 落地（提交时要求的就是 mp3）。
AUDIO_EXTS = ("mp3", "wav", "flac", "ogg")
# 连续失败多少次才放弃：keep-alive 偶断算一次，死服务器算很多次。
MAX_FAILED_ASKS = 10
# 预热契约：懒加载模型是长的那段，音乐本身只要几秒。
RUN_TIMEOUT_SECONDS = 300.0

DEFAULT_POLL_INTERVAL_SECONDS = 2.0
_HEALTH_TIMEOUT_SECONDS = 5.0


class AceStepLocalError(RuntimeError):
    """表示 ACE-Step 请求、响应协议或生成失败。"""


def _base_url() -> str:
    return str(
        config.app.get("acestep_base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    ).rstrip("/")


def _poll_interval() -> float:
    raw = config.app.get("acestep_poll_interval", DEFAULT_POLL_INTERVAL_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_POLL_INTERVAL_SECONDS
    if value <= 0:
        return DEFAULT_POLL_INTERVAL_SECONDS
    return min(value, 30.0)


# ---------------------------------------------------------------------------
# 测试缝：注入假 transport，契约测试不触网（对齐 acestep.test.mjs）。
# ---------------------------------------------------------------------------

_injected_transport = None


def set_transport(fake):
    """测试专用：注入假 transport；传 None 恢复真实 HTTP 客户端。"""
    global _injected_transport
    _injected_transport = fake


def _api():
    return _injected_transport if _injected_transport is not None else _HttpTransport(_base_url())


class _HttpTransport:
    """真实 transport：requests 直连本地 origin，逐调用超时。

    连接从未落地=API 服务器没启动；落地后沉默=正在加载模型。每个响应都
    包着 {data, code, error}；音频地址是任务结果自己的，只在本 origin 取。
    """

    def __init__(self, base: str):
        self.base = base

    def _ask(self, method: str, path: str, timeout: float, **kwargs):
        url = f"{self.base}{path}"
        try:
            return trace_http_call(
                method, requests.request, method, url, timeout=timeout, **kwargs
            )
        except requests.Timeout:
            raise AceStepLocalError(
                f"ACE-Step did not answer within {timeout:.0f} s "
                "(it may be loading a model). Try again in a moment."
            ) from None
        except requests.RequestException:
            raise AceStepLocalError(
                f"ACE-Step is not running at {self.base}. "
                "Start it first (start_api_server.bat), then try again."
            ) from None

    def online(self) -> bool:
        res = self._ask("GET", "/health", _HEALTH_TIMEOUT_SECONDS)
        if res.status_code != 200:
            raise AceStepLocalError(
                f"ACE-Step answered {res.status_code} on /health; "
                "see its console window."
            )
        return True

    def submit(self, body: dict) -> str:
        res = self._ask("POST", "/release_task", 30.0, json=body)
        if res.status_code != 200:
            raise AceStepLocalError(
                f"ACE-Step answered {res.status_code} on submit; see its console window."
            )
        try:
            data = res.json()
        except ValueError:
            data = None
        task_id = str(((data or {}).get("data") or {}).get("task_id") or "").strip()
        if not task_id:
            err = str((data or {}).get("error") or "").strip()
            raise AceStepLocalError(
                f"ACE-Step took the task but gave no id{f': {err}' if err else ''}."
            )
        return task_id

    def query(self, task_id: str):
        res = self._ask("POST", "/query_result", 30.0, json={"task_id_list": [task_id]})
        if res.status_code != 200:
            return None
        try:
            data = res.json()
        except ValueError:
            return None
        items = (data or {}).get("data")
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("task_id") == task_id:
                return item
        return None

    def audio(self, file: str) -> bytes:
        # file 是结果自带的相对地址（/v1/audio?path=...），编码原样保留。
        res = self._ask("GET", file, 120.0)
        if res.status_code != 200:
            raise AceStepLocalError(
                f"ACE-Step could not hand back the track ({res.status_code})."
            )
        return res.content


# ---------------------------------------------------------------------------
# 时长与结果解析（移植 common.mjs wavSeconds / mp3Seconds）
# ---------------------------------------------------------------------------


def _round3(value: float) -> float:
    return round(value * 1000) / 1000


def wav_seconds(data: bytes):
    """WAV 时长从头部算：走 RIFF chunk 找 fmt 采样率与 data 字节数。"""
    if len(data) < 44 or data[:4] != b"RIFF":
        return None
    rate = 0
    at = 12
    while at + 8 <= len(data):
        chunk_id = data[at : at + 4]
        size = int.from_bytes(data[at + 4 : at + 8], "little")
        if chunk_id == b"fmt " and at + 20 <= len(data):
            rate = int.from_bytes(data[at + 16 : at + 20], "little")
        if chunk_id == b"data":
            there = len(data) - at - 8
            used = size if 0 < size < there else there
            return _round3(used / rate) if rate else None
        at += 8 + size + (size & 1)
    return None


def mp3_seconds(data: bytes, kbps: int = 128) -> float:
    """定码率 MP3 的时长由体积可知（服务器按 128 kbps 存）。"""
    return _round3(len(data) * 8 / (kbps * 1000))


def ext_of_path(file: str) -> str:
    """结果路径的扩展名。真实路径 URL 编码在 path 查询参数里
    （/v1/audio?path=D%3A%5C...%5Ctrack.mp3），先解码再看扩展名；
    白名单之外一律按 mp3 落地。"""
    path = file
    try:
        qs = parse_qs(urlsplit(file).query)
        values = qs.get("path")
        if values:
            path = values[0]
    except ValueError:
        pass
    name = re.split(r"[\\/]", path)[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return ext if ext in AUDIO_EXTS else "mp3"


def first_result(result):
    """result 是 JSON 字符串，一批一条；batch_size=1 取第一条。
    解析不了的是失败纯文本，不是做好的曲子。"""
    try:
        items = json.loads(str(result or ""))
    except ValueError:
        items = None
    item = items[0] if isinstance(items, list) and items else None
    if not isinstance(item, dict):
        raise AceStepLocalError(
            "ACE-Step finished without a file to hand back; see its console window."
        )
    return item


def fail_reason(result) -> str:
    """失败任务的白话原因：result 要么是首条带 error 的 JSON 字符串，
    要么就是错误文本本身。绝不超过一句话的量。"""
    raw = str(result or "")
    try:
        items = json.loads(raw)
        first = items[0] if isinstance(items, list) and items else items
        if isinstance(first, dict):
            why = str(first.get("error") or first.get("message") or "").strip()
            if why:
                return why[:300]
    except ValueError:
        pass
    return raw[:300] or "see its console window."


# ---------------------------------------------------------------------------
# 提交与等待
# ---------------------------------------------------------------------------


def _wait_done(api, task_id: str, stop_event):
    """轮询直到完成/失败/超时（300 s 预热契约）。偶发断连重试，
    连续 MAX_FAILED_ASKS 次失败才放弃；成功一次即清零。"""
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    interval = _poll_interval()
    failed = 0
    while True:
        if stop_event is not None and stop_event.is_set():
            raise AceStepLocalError("ACE-Step run cancelled.")
        try:
            item = api.query(task_id)
            failed = 0
        except Exception:
            failed += 1
            if failed >= MAX_FAILED_ASKS:
                raise AceStepLocalError(
                    f"ACE-Step stopped answering after {failed} tries; "
                    "see its console window."
                ) from None
            item = None
        if isinstance(item, dict) and item.get("status") == 2:
            raise AceStepLocalError(
                f"ACE-Step could not make the music: {fail_reason(item.get('result'))}"
            )
        if isinstance(item, dict) and item.get("status") == 1:
            made = first_result(item.get("result"))
            if not str(made.get("file") or "").strip():
                raise AceStepLocalError(
                    "ACE-Step finished without a file to hand back; see its console window."
                )
            return made
        if time.monotonic() > deadline:
            raise AceStepLocalError(
                "ACE-Step did not finish within 5 minutes. A server just started "
                "spends minutes loading its models: wait a moment, then run the "
                "same request again. If it keeps timing out, try a shorter track "
                "and watch its console window."
            )
        if stop_event is not None:
            stop_event.wait(interval)
        else:
            time.sleep(interval)


def _cache_dir() -> Path:
    return Path(utils.storage_dir("local_acestep_cache", create=True))


def _read_kept(key_file: Path, key: str):
    """旁车携带本次请求 key 且产物仍在时返回回执；否则 None。"""
    try:
        stored = json.loads(key_file.read_text(encoding="utf-8"))
        if (
            isinstance(stored, dict)
            and stored.get("key") == key
            and isinstance(stored.get("receipt"), dict)
        ):
            return stored["receipt"]
    except (OSError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


def is_online() -> bool:
    """健康探测：GET /health。离线返回 False，不抛异常。"""
    try:
        return bool(_api().online())
    except Exception:
        return False


def generate_music(
    prompt: str,
    *,
    lyrics: str = "[instrumental]",
    lang: str = "",
    think: bool = False,
    duration=LENGTH_DEFAULT,
    out_name: str = "",
    force: bool = False,
    on_progress=None,
    stop_event=None,
) -> dict:
    """生成一段配乐/歌曲，返回 {path, seed, dur, request_key, cached, receipt}。

    '[instrumental]' 出纯伴奏，真歌词出人声（lang 指定歌词语言）；think=True
    让服务器的 5Hz LM 规划音频码（需 ACESTEP_INIT_LLM=true）。时长钳制在
    10–600 s 并如实播报。同请求命中 requestKey 缓存直接返回（force 跳过）。
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise AceStepLocalError("prompt is required.")
    lyrics = (lyrics or "").strip() or "[instrumental]"
    lang = (lang or "").strip()
    think = think is True
    asked = None
    if duration is not None:
        try:
            asked = float(duration)
        except (TypeError, ValueError):
            asked = None
    sec = min(max(asked if asked is not None else LENGTH_DEFAULT, LENGTH_MIN), LENGTH_MAX)
    notes = []
    if asked is not None and asked != sec:
        notes.append(f"ACE-Step makes {LENGTH_MIN}–{LENGTH_MAX} s tracks: {sec:g} s")

    model = MUSIC_MODEL
    args = {
        "prompt": prompt,
        "lyrics": lyrics,
        "lang": lang,
        "think": think,
        "duration": sec,
        "out": out_name,
    }
    key = request_key("music", model, args, provider=PROVIDER_ID)
    cache_dir = _cache_dir()
    key_file = cache_dir / f"{key}.key"
    if not force:
        kept = _read_kept(key_file, key)
        if kept is not None and Path(str(kept.get("src") or "")).exists():
            logger.info(f"acestep_local requestKey cache hit: {key}")
            return {
                "path": str(kept.get("src")),
                "seed": kept.get("seed"),
                "dur": kept.get("dur"),
                "request_key": key,
                "cached": True,
                "receipt": kept,
            }

    # JS 模板里布尔是小写 true/false；seed 输入保持同一形状。
    seed = seed_of(model, out_name, prompt, lyrics, lang, "true" if think else "false")
    api = _api()
    api.online()
    if on_progress is not None:
        on_progress({"phase": "queue"})
    body = {
        "prompt": prompt,
        "lyrics": lyrics,
        "task_type": "text2music",
        "audio_duration": sec,
        "audio_format": "mp3",
        "batch_size": 1,
        "thinking": think,
        "use_cot_caption": False,
        "use_cot_language": False,
        "model": model,
        "inference_steps": STEPS,
        "use_random_seed": False,
        "seed": seed,
    }
    if lang:
        body["vocal_language"] = lang
    task_id = api.submit(body)
    if on_progress is not None:
        on_progress({"phase": "sample"})
    made = _wait_done(api, task_id, stop_event)
    if on_progress is not None:
        on_progress({"phase": "decode"})
    file = str(made.get("file") or "")
    data = api.audio(file)
    ext = ext_of_path(file)
    target = cache_dir / f"{key}.{ext}"
    target.write_bytes(data)
    # mp3 由体积可知（128 kbps）、wav 由头部可知；否则 metas；再否则按请求值。
    dur = wav_seconds(data) if ext == "wav" else mp3_seconds(data) if ext == "mp3" else None
    if dur is None:
        try:
            dur = float((made.get("metas") or {}).get("duration"))
        except (TypeError, ValueError):
            dur = None
    if dur is None:
        dur = sec
    sung = lyrics != "[instrumental]"
    receipt = {
        "provider": PROVIDER_ID,
        "model": model,
        "src": str(target),
        "dur": dur,
        "seed": seed,
        "request_key": key,
    }
    if sung:
        receipt["vocals"] = lang or "en"
    if think:
        receipt["think"] = True
    if notes:
        receipt["notes"] = notes
    try:
        key_file.write_text(
            json.dumps({"key": key, "receipt": receipt}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"acestep_local could not write cache sidecar: {exc}")
    return {
        "path": str(target),
        "seed": seed,
        "dur": dur,
        "request_key": key,
        "cached": False,
        "receipt": receipt,
    }
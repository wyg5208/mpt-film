"""ComfyUI 本地画面引擎（脚本方案专业模式，B3）。

移植 ChangoVideo comfy.mjs 已验证契约：裸 origin http://127.0.0.1:8188
（config 可覆盖，兼容 comfy-mini 8190 代理）；模型=成套参数包（checkpoint +
sampler + steps + cfg，小白不碰节点）；FNV-1a 确定性 seed；/prompt 提交 +
/history 轮询 + WS progress_state×节点权重折算 0–100%（KSampler=steps×10，
断线静默降级轮询）；提交后 GET /queue 播报排队深度；sha1 requestKey 内容
寻址复用（同 prompt+参数+模型包→直接返回已有产物，跨任务共享缓存目录，
.key 旁车存指纹与回执）。免费免 Key：用户自己的 GPU，单卡串行。

graph 构建器逐字段移植 comfy-mini app.py 的 build_t2i_graph；IPAdapter
角色参考 graph 为新增（ComfyUI_IPAdapter_plus）。B5 新增 MiniMax H3 FL2V
首尾帧动画化 graph：接线逐字段对照官方模板 video_minimax_h3_i2v.json 的
原生子图（BasicGuider 无 CFG，蒸馏模型不吃负向词），不依赖 T8 自定义节点。
"""

import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

import requests
from loguru import logger

from app.config import config
from app.utils import utils
from app.utils.request_logging import trace_http_call

DEFAULT_BASE_URL = "http://127.0.0.1:8188"
PROVIDER_ID = "comfy_local"
# 每次提交携带的 client_id：ComfyUI 只把进度事件路由给这个 id（WS 同样使用）。
CLIENT_ID = "changofilm-local-engines"

DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_RUN_TIMEOUT_SECONDS = 1200.0
_HEALTH_TIMEOUT_SECONDS = 5.0

# 模型=成套参数包：checkpoint 与采样参数属于同一整体，错配只会渲出糊图
# 而不报错（comfy-mini 的教训）。默认快速档在前。
PRESETS = {
    "sdxl-lightning": {
        "checkpoint": "dreamshaperXL_lightningDPMSDE.safetensors",
        "steps": 6,
        "cfg": 1.0,
        "sampler": "dpmpp_sde",
        "scheduler": "karras",
    },
    "sdxl-quality": {
        "checkpoint": "dreamshaperXL10_alpha2Xl10.safetensors",
        "steps": 28,
        "cfg": 1.8,
        "sampler": "euler",
        "scheduler": "karras",
    },
}
IMAGE_MODELS = tuple(PRESETS)

# MiniMax H3 FL2V（B5）：首尾帧→视频，同样"模型=成套参数包"。草稿档=
# pruned 权重 + turbo 4-step LoRA（768p 训练档）；成片档=完整权重 20 步无
# LoRA（官方模板默认）。两档共用 768p 画布与原生采样链，升分辨率是后续
# 可选项（UltimateSDUpscale），不在 v1 承诺内。
VIDEO_PRESETS = {
    "minimax-draft": {
        "unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        "lora": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
        "lora_strength": 1.0,
        "steps": 4,
        "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_fp16.safetensors",
        "sampler": "res_multistep",
        "scheduler": "simple",
        "fps": 24,
    },
    "minimax-final": {
        "unet": "minimax_h3_fl2va_int8_convrot.safetensors",
        "lora": None,
        "lora_strength": 1.0,
        "steps": 20,
        "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_fp16.safetensors",
        "sampler": "res_multistep",
        "scheduler": "simple",
        "fps": 24,
    },
}
VIDEO_MODELS = tuple(VIDEO_PRESETS)

# 768p 画布（约 1.03MP，边长 32 的倍数——MiniMax H3 的硬约束）。
VIDEO_SIZE = {
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "1:1": (1024, 1024),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
}
VIDEO_FPS = 24
# 帧数落在 17k+5 网格上；训练区间约 124–362 帧（~5.2s–15.1s），区间外未验证。
FL2V_MIN_LENGTH = 124
FL2V_MAX_LENGTH = 362


def fl2v_length(seconds: float) -> int:
    """秒→帧数：向上贴齐 17k+5 网格，再夹到训练区间。短场景也生成最短
    124 帧，多余部分由 timeline 裁窗消化；长场景封顶 362 帧。"""
    base = max(5, round(float(seconds) * VIDEO_FPS))
    length = base + (5 - base % 17) % 17
    return max(FL2V_MIN_LENGTH, min(FL2V_MAX_LENGTH, length))

# 各画幅的 SDXL 画布：约一百万像素，边长为 8 的倍数（1024 档模型的训练尺寸）。
IMAGE_SIZE = {
    "16:9": (1024, 576),
    "9:16": (576, 1024),
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
}

NEGATIVE_STANDARD = (
    "low quality, worst quality, text, watermark, bad anatomy, bad hands"
)

# 各节点占整份工作的权重（移植 comfy-mini _WEIGHT）；KSampler=steps×10。
_NODE_WEIGHT = {
    "VAEDecode": 8,
    "CheckpointLoaderSimple": 6,
    "ImageOnlyCheckpointLoader": 6,
    "UNETLoader": 6,
    "CLIPLoader": 4,
    "VAELoader": 3,
    "CLIPTextEncode": 2,
    "SVD_img2vid_Conditioning": 3,
    "Wan22ImageToVideoLatent": 3,
    "CreateVideo": 3,
    "SaveVideo": 2,
    "SaveImage": 2,
    "EmptyLatentImage": 1,
    "LoadImage": 1,
    "ModelSamplingSD3": 1,
    "VideoLinearCFGGuidance": 1,
    "FreeU_V2": 1,
    "IPAdapterUnifiedLoader": 4,
    "IPAdapter": 3,
    "MiniMaxH3ImageToVideo": 3,
    "LoraLoaderModelOnly": 2,
}


class ComfyLocalError(RuntimeError):
    """表示 ComfyUI 请求、响应协议或生成失败。"""


def _base_url() -> str:
    return str(
        config.app.get("comfyui_base_url", DEFAULT_BASE_URL) or DEFAULT_BASE_URL
    ).rstrip("/")


def _poll_interval() -> float:
    raw = config.app.get("comfyui_poll_interval", DEFAULT_POLL_INTERVAL_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_POLL_INTERVAL_SECONDS
    if value <= 0:
        return DEFAULT_POLL_INTERVAL_SECONDS
    return min(value, 30.0)


def _run_timeout() -> float:
    raw = config.app.get("comfyui_run_timeout", DEFAULT_RUN_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_RUN_TIMEOUT_SECONDS
    if value <= 0:
        return DEFAULT_RUN_TIMEOUT_SECONDS
    return min(value, 7200.0)


# ---------------------------------------------------------------------------
# 测试缝：注入假 transport / 假 WS 工厂，契约测试不触网（对齐 comfy.test.mjs）。
# ---------------------------------------------------------------------------

_injected_transport = None
_ws_factory = None


def set_transport(fake):
    """测试专用：注入假 transport；传 None 恢复真实 HTTP 客户端。"""
    global _injected_transport
    _injected_transport = fake


def set_ws_factory(fake):
    """测试专用：注入假 WS 工厂；传 None 恢复默认（注入 transport 时无 WS）。"""
    global _ws_factory
    _ws_factory = fake


def _api():
    return _injected_transport if _injected_transport is not None else _HttpTransport(_base_url())


class _HttpTransport:
    """真实 transport：requests 直连本地 origin，逐调用超时。

    连接从未落地=ComfyUI 没启动；落地后沉默=正在加载模型。服务端调用不带
    Origin/Sec-Fetch-Site 头，ComfyUI 的 origin_only_middleware 会放行。
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
            raise ComfyLocalError(
                f"ComfyUI did not answer within {timeout:.0f} s "
                "(it may be loading a model). Try again in a moment."
            ) from None
        except requests.RequestException:
            raise ComfyLocalError(
                f"ComfyUI is not running at {self.base}. "
                "Start it first (绘世启动器, one-click start), then try again."
            ) from None

    def online(self) -> bool:
        res = self._ask("GET", "/system_stats", _HEALTH_TIMEOUT_SECONDS)
        if res.status_code != 200:
            raise ComfyLocalError(
                f"ComfyUI answered {res.status_code} on /system_stats; "
                "see its console window."
            )
        return True

    def options(self, class_type: str, field: str) -> list:
        res = self._ask("GET", f"/object_info/{class_type}", _HEALTH_TIMEOUT_SECONDS)
        if res.status_code == 404:
            raise ComfyLocalError(
                f"ComfyUI has no {class_type} node: the custom nodes it comes "
                "from may not be installed."
            )
        if res.status_code != 200:
            raise ComfyLocalError(
                f"ComfyUI answered {res.status_code} reading {class_type}'s options."
            )
        try:
            info = res.json()
        except ValueError:
            return []
        inputs = (info.get(class_type) or {}).get("input") or {}
        for group in ("required", "optional"):
            entry = (inputs.get(group) or {}).get(field)
            if not entry:
                continue
            # 两种形状并存：旧 ["a.safetensors", ...] 与新 ["COMBO", {options:[...]}]
            opts = entry[0] if isinstance(entry, list) and entry else None
            if isinstance(opts, str) and len(entry) > 1 and isinstance(entry[1], dict):
                opts = entry[1].get("options")
            if isinstance(opts, list) and opts:
                return [str(o) for o in opts]
        return []

    def submit(self, graph: dict, prompt_id: str) -> None:
        res = self._ask(
            "POST",
            "/prompt",
            30.0,
            json={"prompt": graph, "client_id": CLIENT_ID, "prompt_id": prompt_id},
        )
        if res.status_code == 403:
            raise ComfyLocalError(
                "ComfyUI refused the request (403): its origin middleware accepts "
                "local server-side calls only. Keep comfyui_base_url on 127.0.0.1 "
                "and ComfyUI's security settings as they are."
            )
        if res.status_code == 400:
            try:
                payload = res.json()
            except ValueError:
                payload = None
            raise ComfyLocalError(_explain_prompt_error(payload))
        if res.status_code != 200:
            raise ComfyLocalError(
                f"ComfyUI answered {res.status_code} on submit; see its console window."
            )

    def history(self, prompt_id: str):
        res = self._ask("GET", f"/history/{prompt_id}", 15.0)
        if res.status_code != 200:
            return None
        try:
            data = res.json()
        except ValueError:
            return None
        return (data or {}).get(prompt_id)

    def view(self, filename: str, subfolder: str, type_: str) -> bytes:
        res = self._ask(
            "GET",
            "/view",
            120.0,
            params={"filename": filename, "subfolder": subfolder, "type": type_},
        )
        if res.status_code != 200:
            raise ComfyLocalError(
                f"ComfyUI could not hand back {filename} ({res.status_code})."
            )
        return res.content

    def upload(self, data: bytes, name: str) -> str:
        res = self._ask(
            "POST",
            "/upload/image",
            30.0,
            files={"image": (name, data, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        if res.status_code != 200:
            raise ComfyLocalError(
                f"ComfyUI could not take the picture ({res.status_code})."
            )
        try:
            body = res.json()
        except ValueError:
            body = {}
        return str((body or {}).get("name") or name)

    def queue(self) -> dict:
        res = self._ask("GET", "/queue", _HEALTH_TIMEOUT_SECONDS)
        if res.status_code != 200:
            return {"running": 0, "pending": 0}
        try:
            body = res.json()
        except ValueError:
            body = {}
        return {
            "running": len((body or {}).get("queue_running") or []),
            "pending": len((body or {}).get("queue_pending") or []),
        }

    def free_memory(self) -> None:
        """POST /free：卸载驻留模型并清空显存缓存。 best-effort，失败不阻断主流程。"""
        self._ask(
            "POST",
            "/free",
            30.0,
            json={"unload_models": True, "free_memory": True},
        )


# ---------------------------------------------------------------------------
# graph 构建器（纯函数，API 格式；逐字段移植 comfy-mini build_t2i_graph）
# ---------------------------------------------------------------------------


def build_t2i_graph(
    preset: dict,
    *,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
) -> dict:
    """SDXL 文生图。CheckpointLoaderSimple 槽位 MODEL=0/CLIP=1/VAE=2；
    SaveImage 是必需的 OUTPUT_NODE——validate_prompt 拒绝没有输出节点的图。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": preset["checkpoint"]}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": preset.get("cfg", 1.8),
                "sampler_name": preset.get("sampler", "dpmpp_sde"),
                "scheduler": preset.get("scheduler", "karras"),
                "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "changofilm/image"}},
    }


def build_ipadapter_graph(
    preset: dict,
    *,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
    image_name: str,
    weight: float = 0.8,
    ipadapter_preset: str = "PLUS (high strength)",
) -> dict:
    """IPAdapter 角色参考文生图（ComfyUI_IPAdapter_plus）。

    参考图经 IPAdapterUnifiedLoader/IPAdapter 注入模型，保证角色外貌跨场景
    一致；参考图必须先 upload，LoadImage 按 ComfyUI 返回的名字引用。
    真机节点参数校准在 B5。
    """
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": preset["checkpoint"]}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["1", 0], "preset": ipadapter_preset}},
        "4": {
            "class_type": "IPAdapter",
            "inputs": {
                "model": ["3", 0],
                "ipadapter": ["3", 1],
                "image": ["2", 0],
                "weight": weight,
                "weight_type": "linear",
                "start_at": 0.0,
                "end_at": 1.0,
            },
        },
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "7": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "seed": seed,
                "steps": steps,
                "cfg": preset.get("cfg", 1.8),
                "sampler_name": preset.get("sampler", "dpmpp_sde"),
                "scheduler": preset.get("scheduler", "karras"),
                "denoise": 1.0,
            },
        },
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "changofilm/image"}},
    }


def build_fl2v_graph(
    preset: dict,
    *,
    prompt: str,
    width: int,
    height: int,
    length: int,
    steps: int,
    seed: int,
    first_frame: str = "",
    last_frame: str = "",
) -> dict:
    """MiniMax H3 首尾帧动画化（官方 video_minimax_h3_i2v 子图的原生接线）。

    MiniMaxH3ImageToVideo 槽位 CONDITIONING=0/LATENT=1；蒸馏模型走
    BasicGuider（无负向条件、无 CFG）+ SamplerCustomAdvanced；首/尾帧
    先 upload，LoadImage 按 ComfyUI 返回的名字引用。SaveVideo 是 OUTPUT_NODE，
    产物同样落在 history 的 images 键下（PreviewVideo.as_dict）。
    """
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": preset["unet"], "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": preset["clip"], "type": "minimax"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": preset["vae"]}},
    }
    model_ref = ["1", 0]
    if preset.get("lora"):
        graph["2"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": preset["lora"],
                "strength_model": preset.get("lora_strength", 1.0),
            },
        }
        model_ref = ["2", 0]
    cond_inputs = {
        "clip": ["3", 0],
        "vae": ["4", 0],
        "prompt": prompt,
        "width": width,
        "height": height,
        "length": length,
    }
    if first_frame:
        graph["5"] = {"class_type": "LoadImage", "inputs": {"image": first_frame}}
        cond_inputs["first_frame"] = ["5", 0]
    if last_frame:
        graph["6"] = {"class_type": "LoadImage", "inputs": {"image": last_frame}}
        cond_inputs["last_frame"] = ["6", 0]
    graph["7"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": cond_inputs}
    graph["8"] = {"class_type": "BasicGuider", "inputs": {"model": model_ref, "conditioning": ["7", 0]}}
    graph["9"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": preset.get("sampler", "res_multistep")}}
    graph["10"] = {
        "class_type": "BasicScheduler",
        "inputs": {
            "model": model_ref,
            "scheduler": preset.get("scheduler", "simple"),
            "steps": steps,
            "denoise": 1.0,
        },
    }
    graph["11"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    graph["12"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["11", 0],
            "guider": ["8", 0],
            "sampler": ["9", 0],
            "sigmas": ["10", 0],
            "latent_image": ["7", 1],
        },
    }
    graph["13"] = {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["4", 0]}}
    graph["14"] = {"class_type": "CreateVideo", "inputs": {"images": ["13", 0], "fps": preset.get("fps", VIDEO_FPS)}}
    graph["15"] = {
        "class_type": "SaveVideo",
        "inputs": {"video": ["14", 0], "filename_prefix": "changofilm/video", "format": "auto", "codec": "auto"},
    }
    return graph


# ---------------------------------------------------------------------------
# 确定性 seed 与 requestKey 内容寻址缓存
# ---------------------------------------------------------------------------


def seed_of(*parts) -> int:
    """FNV-1a（32 位）：同样的输入落在同样的 seed，重跑即同一张图。"""
    h = 0x811C9DC5
    for b in "|".join(str(p) for p in parts).encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def request_key(verb: str, model: str, args: dict, *, provider: str = PROVIDER_ID) -> str:
    """请求指纹：sha1({verb, provider, model, args 按键排序})。任一输入
    变化→新 key→重新生成（ComfyUI 输入签名缓存的纪律）。"""
    payload = {
        "verb": verb,
        "provider": provider,
        "model": model or None,
        "args": {k: args[k] for k in sorted(args)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_dir() -> Path:
    return Path(utils.storage_dir("local_comfy_cache", create=True))


def _read_kept(key_file: Path, key: str):
    """旁车携带本次请求 key 时返回回执；key 不同或损坏返回 None。"""
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
# 提交与等待（粗粒度阶段 + WS 细粒度百分比 + 队列播报）
# ---------------------------------------------------------------------------


def _ensure_model(api, class_type: str, field: str, name: str, kind: str) -> None:
    """提交前确认 ComfyUI 认识模型文件：空列表=模型目录未注册；缺名=文件不在。"""
    options = api.options(class_type, field)
    if not options:
        raise ComfyLocalError(
            f"ComfyUI lists no {kind} files at all: that model folder is not "
            "registered in extra_model_paths.yaml, or ComfyUI was not restarted "
            "after registering it."
        )
    if name not in options:
        raise ComfyLocalError(
            f'ComfyUI does not know the {kind} "{name}". Put the file where '
            "ComfyUI looks (or register its folder in extra_model_paths.yaml), "
            "then restart ComfyUI."
        )


def _report_queue(api, notes: list) -> None:
    """本任务前面还有几个任务：GPU 串行，诚实播报。读不到队列绝不阻塞任务。"""
    try:
        depth = api.queue()
    except Exception:
        return
    ahead = max(0, int(depth.get("running", 0)) + int(depth.get("pending", 0)) - 1)
    if not ahead:
        return
    jobs = f"{ahead} job{'s' if ahead != 1 else ''}"
    line = (
        f"ComfyUI queue: {jobs} ahead of this one — the GPU runs them one at a time"
    )
    logger.info(line)
    notes.append(line)


def _graph_weights(graph: dict) -> dict:
    # FL2V 的步数在 BasicScheduler 上，采样本体是 SamplerCustomAdvanced。
    custom_steps = 1
    for node in graph.values():
        if (node or {}).get("class_type") == "BasicScheduler":
            custom_steps = (node.get("inputs") or {}).get("steps") or 1
    weights = {}
    for node_id, node in graph.items():
        class_type = (node or {}).get("class_type")
        if class_type == "KSampler":
            steps = (node.get("inputs") or {}).get("steps") or 1
            weights[node_id] = max(1, int(steps)) * 10
        elif class_type == "SamplerCustomAdvanced":
            weights[node_id] = max(1, int(custom_steps)) * 10
        else:
            weights[node_id] = _NODE_WEIGHT.get(class_type, 1)
    return weights


def _real_ws(url: str, on_message):
    """真实进度 WS（websocket-client，dashscope 已带入）。连接失败静默——
    粗粒度阶段照常，进度绝不阻塞任务本体。返回 close 函数。"""
    try:
        import websocket
    except ImportError:
        return lambda: None
    try:
        ws = websocket.WebSocket()
        ws.settimeout(5.0)
        ws.connect(url)
    except Exception:
        return lambda: None
    closed = threading.Event()

    def pump():
        while not closed.is_set():
            try:
                raw = ws.recv()
            except Exception:
                return
            if not raw:
                return
            try:
                on_message(raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))
            except Exception:
                continue

    thread = threading.Thread(target=pump, name="comfy-progress-ws", daemon=True)
    thread.start()

    def close():
        if closed.is_set():
            return
        closed.set()
        try:
            ws.close()
        except Exception:
            pass

    return close


def _open_progress(prompt_id: str, graph: dict, on_progress):
    """为本次运行打开细粒度进度：progress_state×节点权重折算 0–100%。
    无 WS（注入 transport 或连接失败）时为 no-op，粗粒度阶段照常。"""
    make = _ws_factory
    if make is None:
        if _injected_transport is not None or on_progress is None:
            return lambda: None
        make = _real_ws
    weights = _graph_weights(graph)
    nodes = {}

    def report():
        done = total = 0.0
        for n in nodes.values():
            total += n["weight"]
            frac = min(1.0, n["value"] / n["max"]) if n["max"] > 0 else 0.0
            done += n["weight"] * frac
        if total > 0 and on_progress is not None:
            on_progress({"phase": "sample", "value": round(done / total * 100), "max": 100})

    def on_message(raw):
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return
        if not isinstance(msg, dict) or msg.get("type") != "progress_state":
            return
        data = msg.get("data") or {}
        if data.get("prompt_id") != prompt_id:
            return
        for node_id, n in (data.get("nodes") or {}).items():
            weight = weights.get(node_id) or weights.get(str((n or {}).get("real_node_id"))) or 1
            try:
                value = float((n or {}).get("value") or 0)
                max_ = float((n or {}).get("max") or 0)
            except (TypeError, ValueError):
                value, max_ = 0.0, 0.0
            nodes[node_id] = {"value": value, "max": max_, "weight": weight}
        report()

    ws_url = _base_url().replace("http", "ws", 1) + f"/ws?clientId={CLIENT_ID}"
    try:
        close = make(ws_url, on_message)
    except Exception:
        return lambda: None
    return close if callable(close) else (lambda: None)


def _wait_done(api, prompt_id: str, stop_event):
    """轮询直到完成/失败/超时。history 中的执行错误翻译后抛出。"""
    deadline = time.monotonic() + _run_timeout()
    interval = _poll_interval()
    while True:
        if stop_event is not None and stop_event.is_set():
            raise ComfyLocalError("ComfyUI run cancelled.")
        entry = api.history(prompt_id)
        status = (entry or {}).get("status") or {}
        if status.get("completed") or status.get("status_str") == "error":
            why = _explain_history_error(entry)
            if why:
                raise ComfyLocalError(why)
            if status.get("status_str") == "error":
                raise ComfyLocalError(
                    "ComfyUI could not make it; see its console window."
                )
            return entry
        if time.monotonic() > deadline:
            raise ComfyLocalError(
                f"ComfyUI did not finish within {_run_timeout():.0f} s. Try fewer "
                "frames or steps, and watch its console window."
            )
        if stop_event is not None:
            stop_event.wait(interval)
        else:
            time.sleep(interval)


def _release_vram(api) -> None:
    """FL2V 是重型 graph（32B 文本编码器 + 视频 UNet + 视频 VAE 共享一张卡）。
    队列空闲时卸载驻留模型，给 ComfyUI 显存管理一个干净起点，避免上一轮
    t2i/视频模型残留导致采样 OOM；队列非空时不动别人正在用的模型。"""
    free = getattr(api, "free_memory", None)
    if free is None:
        return
    try:
        depth = api.queue()
        if depth.get("running") or depth.get("pending"):
            return
        free()
    except Exception:
        pass


def _submit_and_wait(api, graph: dict, on_progress, stop_event, notes: list):
    prompt_id = str(uuid.uuid4())
    if on_progress is not None:
        on_progress({"phase": "queue"})
    close_ws = _open_progress(prompt_id, graph, on_progress)
    try:
        api.submit(graph, prompt_id)
        _report_queue(api, notes)
        if on_progress is not None:
            on_progress({"phase": "sample"})
        entry = _wait_done(api, prompt_id, stop_event)
        if on_progress is not None:
            on_progress({"phase": "decode"})
        return entry
    finally:
        close_ws()


def _first_output(entry: dict) -> dict:
    """完成任务交回的第一个文件。视频也在 images 键下（PreviewVideo.as_dict），
    没有 videos 键；temp 预览跳过。filename 只用于取字节，不是本地路径。"""
    for node in ((entry or {}).get("outputs") or {}).values():
        for item in (node or {}).get("images") or []:
            if (item or {}).get("filename") and item.get("type") != "temp":
                return item
    raise ComfyLocalError(
        "ComfyUI finished without a file to hand back; see its console window."
    )


def _explain_prompt_error(payload) -> str:
    """ComfyUI 400 校验错误的白话翻译（移植 comfy-mini _explain_prompt_error）。"""
    if not payload:
        return (
            "ComfyUI rejected the workflow (400) without a readable reason; "
            "see its console window."
        )
    parts = []
    for node_id, detail in (payload.get("node_errors") or {}).items():
        class_type = str((detail or {}).get("class_type") or "?")
        for reason in (detail or {}).get("errors") or []:
            msg = str((reason or {}).get("message") or "")
            det = str((reason or {}).get("details") or "")
            if det.rstrip().endswith("not in []"):
                parts.append(
                    f"{class_type} lists no files at all: that kind of model folder "
                    "is not registered in extra_model_paths.yaml, or ComfyUI was "
                    "not restarted after registering it"
                )
            elif "ckpt_name" in det or "not in ['" in det:
                parts.append(f"model name does not exist: {det[:200]}")
            else:
                parts.append(f"[{class_type} #{node_id}] {msg}: {det}"[:300])
    if not parts:
        err = payload.get("error") or {}
        parts.append(
            f"{err.get('message') or 'the workflow did not validate'}: "
            f"{err.get('details') or ''}"[:300]
        )
    return "ComfyUI rejected the workflow → " + " | ".join(parts[:3])


def _explain_history_error(entry):
    """history 执行失败的白话翻译：显存不足/缺文件/节点失败。无错误返回 None。"""
    for message in ((entry or {}).get("status") or {}).get("messages") or []:
        if not isinstance(message, list) or len(message) < 2 or message[0] != "execution_error":
            continue
        data = message[1] or {}
        node_type = str(data.get("node_type") or "?")
        raw = str(data.get("exception_message") or "")
        # ComfyUI 在消息后追加英文 TIPS；只有第一行是给用户看的。
        first_line = raw.split("\n", 1)[0][:300]
        low = raw.lower()
        if "out of memory" in low or "oom" in low:
            return (
                f"ComfyUI ran out of GPU memory (node {node_type}). Close other "
                "programs using the GPU, then try again."
            )
        if "no such file" in low or "not found" in low:
            return (
                f"ComfyUI could not find a model or file (node {node_type}): {first_line}"
            )
        return f"ComfyUI node {node_type} failed: {first_line}"
    return None


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


def is_online() -> bool:
    """健康探测：GET /system_stats。离线返回 False，不抛异常。"""
    try:
        return bool(_api().online())
    except Exception:
        return False


def generate_image(
    prompt: str,
    *,
    model: str = "sdxl-lightning",
    aspect: str = "9:16",
    out_name: str = "",
    negative: str = "",
    reference_image: str = "",
    reference_weight: float = 0.8,
    force: bool = False,
    on_progress=None,
    stop_event=None,
) -> dict:
    """生成一张关键帧/角色图，返回 {path, seed, request_key, cached, receipt}。

    同 prompt+参数+模型包命中 requestKey 缓存时直接返回已有产物（force=True
    跳过）。reference_image 非空时走 IPAdapter 角色参考 graph（先 upload）。
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ComfyLocalError("prompt is required.")
    if aspect not in IMAGE_SIZE:
        raise ComfyLocalError(f"aspect is one of {', '.join(IMAGE_SIZE)}.")
    if model not in PRESETS:
        raise ComfyLocalError(f"model is one of {', '.join(IMAGE_MODELS)}.")
    preset = PRESETS[model]
    negative = (negative or "").strip() or NEGATIVE_STANDARD
    width, height = IMAGE_SIZE[aspect]

    args = {
        "prompt": prompt,
        "aspect": aspect,
        "out": out_name,
        "negative": negative,
        "reference_image": reference_image,
        "reference_weight": reference_weight,
    }
    key = request_key("image", model, args)
    cache_dir = _cache_dir()
    target = cache_dir / f"{key}.png"
    key_file = cache_dir / f"{key}.png.key"
    if not force and target.exists():
        kept = _read_kept(key_file, key)
        if kept is not None:
            logger.info(f"comfy_local requestKey cache hit: {key}")
            return {
                "path": str(target),
                "seed": kept.get("seed"),
                "request_key": key,
                "cached": True,
                "receipt": kept,
            }

    api = _api()
    api.online()
    if on_progress is not None:
        on_progress({"phase": "load"})
    _ensure_model(api, "CheckpointLoaderSimple", "ckpt_name", preset["checkpoint"], "checkpoint")

    seed = seed_of(model, out_name, prompt, reference_image)
    notes = []
    if reference_image:
        _ensure_model(api, "IPAdapterUnifiedLoader", "preset", "PLUS (high strength)", "IPAdapter preset")
        data = Path(reference_image).read_bytes()
        image_name = api.upload(data, Path(reference_image).name)
        graph = build_ipadapter_graph(
            preset,
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            steps=preset["steps"],
            seed=seed,
            image_name=image_name,
            weight=reference_weight,
        )
        workflow = "t2i-ipadapter"
    else:
        graph = build_t2i_graph(
            preset,
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            steps=preset["steps"],
            seed=seed,
        )
        workflow = "t2i"

    entry = _submit_and_wait(api, graph, on_progress, stop_event, notes)
    item = _first_output(entry)
    data = api.view(item["filename"], str(item.get("subfolder") or ""), str(item.get("type") or "output"))
    target.write_bytes(data)
    receipt = {
        "provider": PROVIDER_ID,
        "model": model,
        "src": str(target),
        "seed": seed,
        "workflow": workflow,
        "width": width,
        "height": height,
        "request_key": key,
    }
    if notes:
        receipt["notes"] = notes
    try:
        key_file.write_text(
            json.dumps({"key": key, "receipt": receipt}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"comfy_local could not write cache sidecar: {exc}")
    return {
        "path": str(target),
        "seed": seed,
        "request_key": key,
        "cached": False,
        "receipt": receipt,
    }


def generate_video(
    prompt: str,
    *,
    model: str = "minimax-draft",
    aspect: str = "9:16",
    duration: float = 5.0,
    out_name: str = "",
    first_frame: str = "",
    last_frame: str = "",
    force: bool = False,
    on_progress=None,
    stop_event=None,
) -> dict:
    """首尾帧动画化一段场景视频，返回 {path, seed, request_key, cached, receipt}。

    FL2V 必须有首帧（i2v 范式）；尾帧可选，缺省由模型自由收尾。duration
    贴齐帧网格后作为缓存指纹的一部分（同网格时长复用同一产物）。首/尾帧
    通常是 generate_image 的缓存产物（{key}.png，内容寻址路径稳定）。
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ComfyLocalError("prompt is required.")
    if aspect not in VIDEO_SIZE:
        raise ComfyLocalError(f"aspect is one of {', '.join(VIDEO_SIZE)}.")
    if model not in VIDEO_PRESETS:
        raise ComfyLocalError(f"model is one of {', '.join(VIDEO_MODELS)}.")
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        raise ComfyLocalError("duration must be a positive number of seconds.") from None
    if duration <= 0:
        raise ComfyLocalError("duration must be a positive number of seconds.")
    if not first_frame or not Path(first_frame).is_file():
        raise ComfyLocalError(
            "first_frame is required for FL2V: generate the keyframe first "
            "(generate_image), then pass its path."
        )
    if last_frame and not Path(last_frame).is_file():
        raise ComfyLocalError(f"last_frame file does not exist: {last_frame}")
    preset = VIDEO_PRESETS[model]
    width, height = VIDEO_SIZE[aspect]
    length = fl2v_length(duration)

    args = {
        "prompt": prompt,
        "aspect": aspect,
        "length": length,
        "out": out_name,
        "first_frame": first_frame,
        "last_frame": last_frame,
    }
    key = request_key("video", model, args)
    cache_dir = _cache_dir()
    target = cache_dir / f"{key}.mp4"
    key_file = cache_dir / f"{key}.mp4.key"
    if not force and target.exists():
        kept = _read_kept(key_file, key)
        if kept is not None:
            logger.info(f"comfy_local requestKey cache hit: {key}")
            return {
                "path": str(target),
                "seed": kept.get("seed"),
                "request_key": key,
                "cached": True,
                "receipt": kept,
            }

    api = _api()
    api.online()
    if on_progress is not None:
        on_progress({"phase": "load"})
    _ensure_model(api, "UNETLoader", "unet_name", preset["unet"], "diffusion model")
    _ensure_model(api, "CLIPLoader", "clip_name", preset["clip"], "text encoder")
    _ensure_model(api, "VAELoader", "vae_name", preset["vae"], "video VAE")
    if preset.get("lora"):
        _ensure_model(api, "LoraLoaderModelOnly", "lora_name", preset["lora"], "LoRA")

    seed = seed_of(model, out_name, prompt, first_frame, last_frame)
    notes = []
    first_name = api.upload(Path(first_frame).read_bytes(), Path(first_frame).name)
    last_name = ""
    if last_frame:
        last_name = api.upload(Path(last_frame).read_bytes(), Path(last_frame).name)
    graph = build_fl2v_graph(
        preset,
        prompt=prompt,
        width=width,
        height=height,
        length=length,
        steps=preset["steps"],
        seed=seed,
        first_frame=first_name,
        last_frame=last_name,
    )

    _release_vram(api)
    try:
        entry = _submit_and_wait(api, graph, on_progress, stop_event, notes)
    except ComfyLocalError as exc:
        if "out of GPU memory" not in str(exc):
            raise
        # 显存不足多半是其它程序/残留模型占卡：卸载后重试一次，仍失败才报错。
        logger.warning(
            "comfy_local FL2V ran out of GPU memory; unloading models and retrying once"
        )
        _release_vram(api)
        entry = _submit_and_wait(api, graph, on_progress, stop_event, notes)
    item = _first_output(entry)
    data = api.view(item["filename"], str(item.get("subfolder") or ""), str(item.get("type") or "output"))
    target.write_bytes(data)
    receipt = {
        "provider": PROVIDER_ID,
        "model": model,
        "src": str(target),
        "seed": seed,
        "workflow": "fl2v",
        "width": width,
        "height": height,
        "length": length,
        "fps": preset.get("fps", VIDEO_FPS),
        "request_key": key,
    }
    if notes:
        receipt["notes"] = notes
    try:
        key_file.write_text(
            json.dumps({"key": key, "receipt": receipt}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"comfy_local could not write cache sidecar: {exc}")
    return {
        "path": str(target),
        "seed": seed,
        "request_key": key,
        "cached": False,
        "receipt": receipt,
    }


def local_engines_status() -> dict:
    """三引擎就绪度（UI 仪表盘与 preflight 复用）：ComfyUI /system_stats、
    ACE-Step /health、Ollama /api/tags。任一离线只置灰对应引擎，不抛异常。"""
    from app.services import acestep_local

    status = {
        "comfyui": {"online": is_online(), "base_url": _base_url()},
        "acestep": {
            "online": acestep_local.is_online(),
            "base_url": acestep_local._base_url(),
        },
    }
    ollama_base = str(config.app.get("ollama_base_url", "") or "").strip().rstrip("/")
    if not ollama_base:
        ollama_base = config.get_default_ollama_base_url().rstrip("/")
    # /api/tags 是 Ollama 原生端点，不在 OpenAI-compatible 的 /v1 之下。
    if ollama_base.endswith("/v1"):
        ollama_base = ollama_base[: -len("/v1")]
    ollama_online = False
    try:
        res = requests.get(f"{ollama_base}/api/tags", timeout=_HEALTH_TIMEOUT_SECONDS)
        ollama_online = res.status_code == 200
    except requests.RequestException:
        pass
    status["ollama"] = {"online": ollama_online, "base_url": ollama_base}
    return status
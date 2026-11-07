"""
任务级确定性工具。

MoneyPrinterTurbo 历史上的随机决策直接使用进程级 ``random`` 模块。该模块被所有
线程共享，而 CPython 会为每个首次使用它的线程自动重新播种，因此片段并发数
（``app.video_clip_concurrency``）、批次划分、甚至某个片段处理失败与否，都会改变
后续片段拿到的随机序列，最终改变成片画面。仅在执行入口调用一次 ``random.seed()``
无法修掉这个问题：线程池仍会各自播种，主线程与 worker 的消耗顺序也不受调用方控制。

本模块把"随机决策"降级成纯函数：一个决策只取决于
``(base_seed, role, role_index)`` 三元组，与执行顺序彻底解耦。

角色约定（role）：
    material  素材下载队列的打乱，决定下载哪些素材
    order     片段编排序列的打乱，按成片序号区分（``video_count``）
    clip      单个片段自身的转场决策，按编排序号区分
    bgm       随机背景音乐选曲

角色之间、以及同角色的不同序号之间互不影响：改一个片段的转场不会重排其他片段，
批量生成多条视频也不会让每条片子拿到相同的编排。
"""

import hashlib
import random

_MAX_SEED = 0xFFFFFFFF


def derive_seed(base_seed: int, role: str, role_index: int = 0) -> int:
    """
    由基础种子派生子种子。

    使用 sha256 而不是 ``base_seed + role_index``：相邻整数种子在 Mersenne
    Twister 上仍高度相关，直接相加会让不同角色或相邻片段序号产出相关的随机序列，
    表现为"转场方向看起来在重复"。哈希把相关性打散到整个 32 位空间。
    """
    key = f"{base_seed}\0{role}\0{role_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def rng_for(base_seed: int | None, role: str, role_index: int = 0) -> random.Random:
    """
    返回该决策专属的 RNG。

    ``base_seed is None`` 表示"未指定种子"，此时返回进程级 ``random`` 模块本身。
    这不是偷懒：未传种子的调用方必须拿到与今天完全一致的分布，而给每个决策各建
    一个未播种的 ``random.Random()`` 会让行为变成"按创建时刻熵源分布"，属于
    没有承诺过的变化。
    """
    if base_seed is None:
        return random
    return random.Random(derive_seed(base_seed, role, role_index))


def resolve_effective_seed(base_seed: int | None, task_id: str) -> int:
    """
    解析本次运行真正使用的种子，并保证返回值可持久化、可回填复现。

    显式传入的种子按 32 位无符号整数归一化，与 API 的校验边界保持一致，避免
    超大整数在派生与日志回显之间产生两种写法。

    未指定种子时按 ``task_id`` 派生一个"本轮种子"。目的不是跨运行可复现
    （``task_id`` 每次都是新 UUID），而是让单次运行内部自洽：主线程、线程池、
    重试路径与 ``script.json`` 记录的是同一个值，因此把清单里的 ``video_seed``
    抄回请求体，就能重放同一条片子。
    """
    if base_seed is not None:
        return int(base_seed) & _MAX_SEED
    digest = hashlib.sha256(str(task_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")

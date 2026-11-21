import warnings
from enum import Enum
from typing import Any, List, Literal, Optional, Union

import pydantic
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import config

# 忽略 Pydantic 的特定警告
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Field name.*shadows an attribute in parent.*",
)


class VideoConcatMode(str, Enum):
    random = "random"
    sequential = "sequential"


class VideoTransitionMode(str, Enum):
    none = None
    shuffle = "Shuffle"
    fade_in = "FadeIn"
    fade_out = "FadeOut"
    slide_in = "SlideIn"
    slide_out = "SlideOut"
    zoom_in = "ZoomIn"
    zoom_out = "ZoomOut"


class VideoAspect(str, Enum):
    landscape = "16:9"
    portrait = "9:16"
    square = "1:1"

    def to_resolution(self):
        if self == VideoAspect.landscape:
            return 1920, 1080
        elif self == VideoAspect.portrait:
            return 1080, 1920
        elif self == VideoAspect.square:
            return 1080, 1080
        raise ValueError(f"unsupported video aspect: {self}")


class VideoFitMode(str, Enum):
    """How source clips with a different aspect ratio fill the output canvas."""

    cover = "cover"
    contain = "contain"


class ImageMotion(str, Enum):
    static = "static"
    zoom = "zoom"


SubtitleDisplayMode = Literal["sentence", "word_by_word"]
SubtitleAnimation = Literal["none", "pop_spring"]
_SUBTITLE_DISPLAY_MODES = ("sentence", "word_by_word")
_SUBTITLE_ANIMATIONS = ("none", "pop_spring")


def _get_valid_ui_choice(key: str, allowed_values: tuple[str, ...], default: str) -> str:
    """
    读取经过校验的 WebUI 枚举配置，兼容旧用户可能残留的无效值。

    请求体由 Pydantic 的 Literal 严格校验，拼写错误会返回明确的字段校验错误；
    配置文件则需要宽容处理，避免用户升级后因为历史手工配置错误导致整个服务
    无法启动。HTTP 状态码由应用统一的校验异常处理器决定，这里不绑定具体数值。
    """
    configured_value = config.ui.get(key, default)
    return configured_value if configured_value in allowed_values else default


_Config = ConfigDict(
    arbitrary_types_allowed=True,
    # Note: ensure your key names match renamed V2 parameters if needed
)


@pydantic.dataclasses.dataclass(config=_Config)
class MaterialInfo:
    provider: str = "pexels"
    url: str = ""
    duration: int = 0
    # 在线素材搜索会附带经过筛选的公开来源信息，供搜索缓存和任务记录复用。
    # 本地上传素材不需要填写；写入任务文件前仍会按字段白名单重新构造，
    # 避免外部请求传入的签名 URL、凭据或无关字段进入持久化数据。
    source_info: Optional[dict[str, Any]] = None


class VideoParams(BaseModel):
    """
    {
      "video_subject": "",
      "video_aspect": "横屏 16:9（西瓜视频）",
      "voice_name": "女生-晓晓",
      "bgm_name": "random",
      "font_name": "STHeitiMedium 黑体-中",
      "text_color": "#FFFFFF",
      "font_size": 60,
      "stroke_color": "#000000",
      "stroke_width": 1.5
    }
    """

    video_subject: str
    video_script: str = ""  # Script used to generate the video
    video_terms: Optional[str | List[str]] = None  # Keywords used to generate the video
    video_aspect: Optional[VideoAspect] = VideoAspect.portrait
    video_fit_mode: VideoFitMode = VideoFitMode.cover
    image_motion: ImageMotion = ImageMotion.zoom
    video_concat_mode: Optional[VideoConcatMode] = VideoConcatMode.random
    video_transition_mode: Optional[VideoTransitionMode] = None
    video_clip_duration: int = Field(default=5, ge=1)
    video_clip_speed: Optional[float] = 1.0
    match_materials_to_script: bool = False
    video_count: int = Field(default=1, ge=1)
    # 随机决策的种子。None 表示“未指定”，编排分布与历史行为完全一致；
    # 指定后，同一批素材下的片段顺序、转场方向与转场类型都可复现。
    # 上限与 determinism 的 32 位归一化保持一致，避免持久化与回填写法不同。
    video_seed: Optional[int] = Field(default=None, ge=0, le=0xFFFFFFFF)

    video_source: Optional[str] = "pexels"
    video_materials: Optional[List[MaterialInfo]] = (
        None  # Materials used to generate the video
    )

    custom_audio_file: Optional[str] = (
        None  # Custom audio file path, will ignore TTS and can still use Whisper subtitles
    )
    video_language: Optional[str] = ""  # auto detect

    voice_name: Optional[str] = ""
    voice_volume: Optional[float] = Field(default=1.0, allow_inf_nan=False)
    voice_rate: Optional[float] = Field(default=1.0, allow_inf_nan=False)
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_volume: Optional[float] = Field(default=0.2, allow_inf_nan=False)
    # 视频配乐供应商共用提示词，WebUI 新任务统一写入该字段。保留下面的
    # Sonilo 专用字段以兼容旧任务记录和现有 CLI 参数。
    video_music_prompt: str = Field(default="", max_length=2000)
    sonilo_bgm_prompt: str = Field(default="", max_length=2000)

    subtitle_enabled: Optional[bool] = True
    subtitle_position: Optional[str] = config.ui.get(
        "subtitle_position", "bottom"
    )  # top, bottom, center, custom, two_thirds_bottom
    subtitle_display_mode: SubtitleDisplayMode = _get_valid_ui_choice(
        "subtitle_display_mode", _SUBTITLE_DISPLAY_MODES, "sentence"
    )
    subtitle_animation: SubtitleAnimation = _get_valid_ui_choice(
        "subtitle_animation", _SUBTITLE_ANIMATIONS, "none"
    )
    custom_position: float = Field(
        default=config.ui.get("custom_position", 70.0), ge=0, le=100, allow_inf_nan=False
    )
    font_name: Optional[str] = "STHeitiMedium.ttc"
    text_fore_color: Optional[str] = "#FFFFFF"
    text_background_color: Union[bool, str] = False
    rounded_subtitle_background: bool = False

    font_size: int = Field(default=60, ge=1)
    stroke_color: Optional[str] = "#000000"
    stroke_width: float = Field(default=1.5, ge=0, allow_inf_nan=False)
    n_threads: Optional[int] = 2
    paragraph_number: int = Field(default=1, ge=1, le=10)
    video_script_prompt: str = Field(default="", max_length=2000)
    custom_system_prompt: str = Field(default="", max_length=8000)

    # 脚本方案（stop_at="plan"）的可选输入。None 表示沿用默认目标时长与
    # 由模型决定的场景数；快速流水线不读取这两个字段，行为零变化。
    plan_target_duration: Optional[float] = Field(
        default=None, gt=0, le=600, allow_inf_nan=False
    )
    plan_scene_count: Optional[int] = Field(default=None, ge=2, le=20)
    # 方案驱动执行（B4）：携带 confirmed 方案时，流水线改走逐场景素材
    # 绑定 + 显式时间线；None 时快速路径行为零变化。前向引用，
    # ScriptPlan 定义后在模块内 model_rebuild。
    script_plan: Optional["ScriptPlan"] = None


class SubtitleRequest(BaseModel):
    video_script: str
    video_language: Optional[str] = ""
    voice_name: Optional[str] = "zh-CN-XiaoxiaoNeural-Female"
    voice_volume: Optional[float] = Field(default=1.0, allow_inf_nan=False)
    voice_rate: Optional[float] = Field(default=1.2, allow_inf_nan=False)
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_volume: Optional[float] = Field(default=0.2, allow_inf_nan=False)
    subtitle_position: Optional[str] = config.ui.get("subtitle_position", "bottom")
    subtitle_display_mode: SubtitleDisplayMode = _get_valid_ui_choice(
        "subtitle_display_mode", _SUBTITLE_DISPLAY_MODES, "sentence"
    )
    subtitle_animation: SubtitleAnimation = _get_valid_ui_choice(
        "subtitle_animation", _SUBTITLE_ANIMATIONS, "none"
    )
    font_name: Optional[str] = "STHeitiMedium.ttc"
    text_fore_color: Optional[str] = "#FFFFFF"
    text_background_color: Union[bool, str] = False
    rounded_subtitle_background: bool = False
    font_size: int = Field(default=60, ge=1)
    stroke_color: Optional[str] = "#000000"
    stroke_width: float = Field(default=1.5, ge=0, allow_inf_nan=False)
    video_source: Optional[str] = "local"
    subtitle_enabled: Optional[bool] = True


class AudioRequest(BaseModel):
    video_script: str
    video_language: Optional[str] = ""
    voice_name: Optional[str] = "zh-CN-XiaoxiaoNeural-Female"
    voice_volume: Optional[float] = Field(default=1.0, allow_inf_nan=False)
    voice_rate: Optional[float] = Field(default=1.2, allow_inf_nan=False)
    bgm_type: Optional[str] = "random"
    bgm_file: Optional[str] = ""
    bgm_volume: Optional[float] = Field(default=0.2, allow_inf_nan=False)
    video_source: Optional[str] = "local"


class VideoScriptParams:
    """
    {
      "video_subject": "春天的花海",
      "video_language": "",
      "paragraph_number": 1,
      "video_script_prompt": "",
      "custom_system_prompt": ""
    }
    """

    video_subject: Optional[str] = "春天的花海"
    video_language: Optional[str] = ""
    paragraph_number: int = Field(default=1, ge=1, le=10)
    video_script_prompt: str = Field(default="", max_length=2000)
    custom_system_prompt: str = Field(default="", max_length=8000)


class VideoTermsParams:
    """
    {
      "video_subject": "",
      "video_script": "",
      "amount": 5,
      "match_materials_to_script": false
    }
    """

    video_subject: Optional[str] = "春天的花海"
    video_script: Optional[str] = (
        "春天的花海，如诗如画般展现在眼前。万物复苏的季节里，大地披上了一袭绚丽多彩的盛装。金黄的迎春、粉嫩的樱花、洁白的梨花、艳丽的郁金香……"
    )
    amount: Optional[int] = 5
    match_materials_to_script: bool = False


class VideoSocialMetadataParams:
    """
    {
      "video_subject": "A day in Shanghai",
      "video_script": "",
      "language": "auto",
      "platform": "tiktok"
    }
    """

    video_subject: Optional[str] = Field(default="A day in Shanghai", max_length=500)
    video_script: Optional[str] = Field(default="", max_length=8000)
    language: Optional[str] = Field(default="auto", max_length=64)
    platform: Optional[str] = Field(default="tiktok", max_length=64)


class TaskVideoRequest(VideoParams, BaseModel):
    # Bound API resource requests while leaving the CLI's explicit batch and
    # FFmpeg thread controls in VideoParams unchanged.
    video_count: int = Field(default=1, ge=1, le=5)
    video_clip_duration: int = Field(default=5, ge=1, le=15)
    n_threads: Optional[int] = Field(default=2, ge=1, le=16)


class TaskQueryRequest(BaseModel):
    pass


class VideoScriptRequest(VideoScriptParams, BaseModel):
    pass


class VideoTermsRequest(VideoTermsParams, BaseModel):
    # Ordered term generation allocates an example list proportional to amount
    # before contacting the model. Reject malformed or excessive API requests.
    amount: int = Field(default=5, ge=1, le=50)


class VideoSocialMetadataRequest(VideoSocialMetadataParams, BaseModel):
    pass


# ---------------------------
# ----- SCRIPT PLAN / SERIES (脚本方案专业模式，B2) -----
# ---------------------------
# 三层数据模型：Series → Episode → ScriptPlan → Scene。ScriptPlan 是
# “文案（需求输入端）”与“生成执行”之间的一等公民产物：可见、可编辑、
# 可锁定、可导出。所有新模型 fail-closed（extra="forbid"），对齐
# video_project 的未知字段拒绝惯例；导入校验失败即拒绝，不静默丢弃。

_PLAN_EXTRA_FORBID = ConfigDict(extra="forbid", populate_by_name=True)

# 中文旁白语速经验值（字/秒），用于估算场景时长；与 Demo 保持一致。
PLAN_NARRATION_CHARS_PER_SECOND = 4.2
# 总时长容差：估算总和与目标时长偏差超过 ±10% 时仪表变色并警告，
# 但不阻塞编辑（TTS 语速浮动，执行后以实测回填为准）。
PLAN_DURATION_TOLERANCE = 0.10

PlanRelation = Literal[
    "establish", "continue", "contrast", "escalate", "match_cut", "unknown"
]
PlanTransition = Literal["none", "fade", "slide", "zoom", "match_cut"]
PlanEngine = Literal["local_fl2v", "local_i2v", "stock", "cloud_ai"]
PlanBoundaryHealth = Literal["ok", "warn", "unknown"]


class PlanStyle(BaseModel):
    """影片风格一致性约束，注入每个 AI 生成 prompt。"""

    model_config = _PLAN_EXTRA_FORBID

    tone: str = ""
    palette: str = ""
    camera: str = ""
    consistency_subject: str = ""


class PlanVoice(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    name: str = "zh-CN-XiaoxiaoNeural"
    rate: float = Field(default=1.0, allow_inf_nan=False)


class PlanBgm(BaseModel):
    """整集一条 BGM 轨。acestep_local 为新增本地作曲，其余三态与现有契约兼容。"""

    model_config = _PLAN_EXTRA_FORBID

    type: Literal["random", "acestep_local", "provider", "custom"] = "random"
    mood: str = ""
    prompt: str = Field(default="", max_length=2000)
    volume: float = Field(default=0.2, allow_inf_nan=False)
    fade_in: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    fade_out: float = Field(default=3.0, ge=0, allow_inf_nan=False)


class PlanLlm(BaseModel):
    """方案生成所用编剧引擎记录，可追溯可复现。"""

    model_config = _PLAN_EXTRA_FORBID

    provider: str = "ollama"
    model: str = ""


class SceneMaterialCandidate(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    id: str = Field(min_length=1)
    label: str = ""
    url: str = ""
    duration: float = Field(default=0, ge=0, allow_inf_nan=False)


class SceneMaterial(BaseModel):
    """库存素材绑定：候选 + 选中项 + 入出点。改动入出点后边界健康置 unknown。"""

    model_config = _PLAN_EXTRA_FORBID

    source: str = "pexels"
    candidates: List[SceneMaterialCandidate] = Field(default_factory=list)
    selected: Optional[str] = None
    in_point: float = Field(default=0, ge=0, alias="in", allow_inf_nan=False)
    out_point: float = Field(default=0, ge=0, alias="out", allow_inf_nan=False)


class SceneKeyframe(BaseModel):
    """首尾帧关键帧。shared_with_prev=true 时本段首帧必须引用上段尾帧同一文件。"""

    model_config = _PLAN_EXTRA_FORBID

    first: Optional[str] = None
    last: Optional[str] = None
    first_prompt: str = ""
    last_prompt: str = ""
    shared_with_prev: bool = False


class SceneCost(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    tier: Literal["free", "paid"] = "free"
    estimate_cny: float = Field(default=0, ge=0, allow_inf_nan=False)
    request_key: Optional[str] = None


class SubtitleCue(BaseModel):
    """执行后回填的真实 SRT 区间（秒）。"""

    model_config = _PLAN_EXTRA_FORBID

    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(ge=0, allow_inf_nan=False)
    text: str = ""


class ScriptScene(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    id: str = Field(min_length=1)
    order: int = Field(ge=1)
    locked: bool = False
    # v1 恒 narrator（旁白驱动）；B6 多音色对白按角色 id 路由 voice_name。
    speaker: str = "narrator"
    narration: str = ""
    est_duration: float = Field(default=0, ge=0, allow_inf_nan=False)
    measured_duration: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    visual: str = ""
    keywords: List[str] = Field(default_factory=list)
    characters: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    relation_to_prev: PlanRelation = "establish"
    relation_note: str = ""
    engine: PlanEngine = "stock"
    material: Optional[SceneMaterial] = None
    keyframe: SceneKeyframe = Field(default_factory=SceneKeyframe)
    transition_to_next: PlanTransition = "none"
    # 生成前为预估 cue 数（int），执行后回填真实 SRT 区间列表。
    subtitle_cues: Optional[Union[int, List[SubtitleCue]]] = None
    boundary_health: PlanBoundaryHealth = "unknown"
    cost: SceneCost = Field(default_factory=SceneCost)


class ScriptPlan(BaseModel):
    """每集一份的分镜脚本方案；series_id/episode_id 均 null 时为单视频任务。"""

    model_config = _PLAN_EXTRA_FORBID

    plan_version: Literal[1] = 1
    revision: int = Field(default=1, ge=1)
    status: Literal["draft", "confirmed"] = "draft"
    series_id: Optional[str] = None
    episode_id: Optional[str] = None
    title: str = ""
    logline: str = ""
    style: PlanStyle = Field(default_factory=PlanStyle)
    target_duration: float = Field(default=60, gt=0, allow_inf_nan=False)
    aspect: Literal["9:16", "16:9"] = "9:16"
    quality_tier: Literal["draft", "final"] = "draft"
    voice: PlanVoice = Field(default_factory=PlanVoice)
    bgm: PlanBgm = Field(default_factory=PlanBgm)
    llm: PlanLlm = Field(default_factory=PlanLlm)
    seed: Optional[int] = Field(default=None, ge=0, le=0xFFFFFFFF)
    scenes: List[ScriptScene] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_scenes(self):
        seen_ids = set()
        previous: ScriptScene | None = None
        for index, scene in enumerate(self.scenes):
            if scene.id in seen_ids:
                raise ValueError(f"duplicate scene id: {scene.id}")
            seen_ids.add(scene.id)
            # order 必须连续且与列表顺序一致；拖拽调序后由调用方重编号。
            if scene.order != index + 1:
                raise ValueError(
                    f"scene order must be contiguous: expected {index + 1}, "
                    f"got {scene.order} ({scene.id})"
                )
            if scene.keyframe.shared_with_prev:
                if previous is None:
                    raise ValueError(
                        f"first scene cannot share boundary frame: {scene.id}"
                    )
                # 共享边界帧约束：本段首帧必须引用上段尾帧的同一文件。
                if (
                    not scene.keyframe.first
                    or scene.keyframe.first != previous.keyframe.last
                ):
                    raise ValueError(
                        f"shared boundary frame mismatch at scene {scene.id}: "
                        "keyframe.first must reference previous scene's keyframe.last"
                    )
            previous = scene
        return self

    def estimated_total_duration(self) -> float:
        return round(sum(scene.est_duration for scene in self.scenes), 3)

    def duration_warnings(self) -> List[dict]:
        """±10% 容差校验：超差返回警告（不阻塞编辑），供 warnings 通路复用。"""
        total = self.estimated_total_duration()
        target = self.target_duration
        if target <= 0:
            return []
        deviation = abs(total - target) / target
        if deviation <= PLAN_DURATION_TOLERANCE:
            return []
        return [
            {
                "code": "plan_duration_out_of_tolerance",
                "message": (
                    f"estimated total {total:.1f}s deviates from target "
                    f"{target:.1f}s by {deviation:.0%} (tolerance ±10%)"
                ),
                "estimated_total": total,
                "target_duration": target,
            }
        ]


class SeriesStyleBible(BaseModel):
    """风格圣经系列级持久化；每集 plan.style 是引用快照。"""

    model_config = _PLAN_EXTRA_FORBID

    tone: str = ""
    palette: str = ""
    camera: str = ""
    era: str = ""


class SeriesCharacter(BaseModel):
    """角色档案三件套：appearance_prompt + reference_images + 固定 seed。"""

    model_config = _PLAN_EXTRA_FORBID

    id: str = Field(min_length=1)
    name: str = ""
    role: Literal["protagonist", "support", "extra"] = "support"
    appearance_prompt: str = ""
    reference_images: List[str] = Field(default_factory=list)
    seed: int = Field(default=0, ge=0, le=0xFFFFFFFF)
    voice_name: str = ""
    personality: str = ""
    # v1 恒 null（免训练路线）；LoRA 仅作预留挂载点。
    lora: Optional[str] = None


class SeriesLocation(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    id: str = Field(min_length=1)
    name: str = ""
    prompt: str = ""
    reference_images: List[str] = Field(default_factory=list)


class SeriesEpisode(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    title: str = ""
    logline: str = ""
    hook: str = ""
    plan_id: Optional[str] = None
    status: Literal["draft", "confirmed", "rendered"] = "draft"


class Series(BaseModel):
    model_config = _PLAN_EXTRA_FORBID

    series_version: Literal[1] = 1
    id: str = Field(min_length=1)
    title: str = ""
    genre_template: Literal[
        "urban_revenge", "period_romance", "suspense", "healing", "scifi", "custom"
    ] = "custom"
    style_bible: SeriesStyleBible = Field(default_factory=SeriesStyleBible)
    characters: List[SeriesCharacter] = Field(default_factory=list)
    locations: List[SeriesLocation] = Field(default_factory=list)
    episodes: List[SeriesEpisode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_assets(self):
        for label, items in (
            ("character", self.characters),
            ("location", self.locations),
            ("episode", self.episodes),
        ):
            seen = set()
            for item in items:
                if item.id in seen:
                    raise ValueError(f"duplicate {label} id: {item.id}")
                seen.add(item.id)
        for index, episode in enumerate(self.episodes):
            if episode.seq != index + 1:
                raise ValueError(
                    f"episode seq must be contiguous: expected {index + 1}, "
                    f"got {episode.seq} ({episode.id})"
                )
        return self


def estimate_scene_duration(narration: str) -> float:
    """按中文语速经验值估算场景时长（字数 ÷ 4.2），保留一位小数。"""
    text = (narration or "").strip()
    if not text:
        return 0.0
    return round(len(text) / PLAN_NARRATION_CHARS_PER_SECOND, 1)


# VideoParams.script_plan 的前向引用在此解析；TaskVideoRequest 继承同一
# 字段，API 请求体无需改控制器即可携带方案。
VideoParams.model_rebuild()
TaskVideoRequest.model_rebuild()


# ---------------------------
# ----- RESPONSE MODELS -----
# ---------------------------
class BaseResponse(BaseModel):
    status: int = 200
    message: Optional[str] = "success"
    data: Any = None


# ---- DATA MODELS ----
class TaskResponseData(BaseModel):
    task_id: str


class TaskStatusData(BaseModel):
    """任务查询对外保证的稳定字段；历史和扩展字段继续原样透传。"""

    model_config = ConfigDict(extra="allow")

    task_id: str
    state: int
    progress: int = 0
    videos: Optional[List[str]] = None
    combined_videos: Optional[List[str]] = None
    failed_stage: Optional[str] = None
    error: Optional[str] = None
    cross_post_state: Optional[
        Literal["pending", "processing", "complete", "failed"]
    ] = None
    cross_post_results: Optional[List[dict[str, Any]]] = None
    cross_post_error: Optional[str] = None


class TaskListData(BaseModel):
    """分页任务列表结构。"""

    tasks: List[TaskStatusData]
    total: int
    page: int
    page_size: int


class VideoScriptData(BaseModel):
    video_script: str


class VideoTermsData(BaseModel):
    video_terms: List[str]


class VideoSocialMetadataData(BaseModel):
    title: str
    caption: str
    hashtags: List[str]


class FileData(BaseModel):
    name: str
    size: int
    file: str


class BgmRetrieveData(BaseModel):
    files: List[FileData]


class BgmUploadData(BaseModel):
    file: str


class VideoMaterialRetrieveData(BaseModel):
    files: List[FileData]


class VideoMaterialUploadData(BaseModel):
    file: str


# ---- RESPONSE MODELS ----
class TaskResponse(BaseResponse):
    data: TaskResponseData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "task_id": "6c85c8cc-a77a-42b9-bc30-947815aa0558",
                },
            },
        }
    )


class TaskQueryResponse(BaseResponse):
    """
    任务查询会返回生成状态和可选的跨平台发布状态。

    生成失败时包含 `failed_stage` 和 `error`；生成完成后如果启用了自动发布，
    `cross_post_state` 会依次进入 pending、processing、complete 或 failed。
    """

    data: TaskStatusData

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": 200,
                    "message": "success",
                    "data": {
                        "task_id": "6c85c8cc-a77a-42b9-bc30-947815aa0558",
                        "state": 1,
                        "progress": 100,
                        "videos": ["/tasks/example/final-1.mp4"],
                        "cross_post_state": "complete",
                        "cross_post_results": [{"success": True}],
                    },
                },
                {
                    "status": 200,
                    "message": "success",
                    "data": {
                        "task_id": "6c85c8cc-a77a-42b9-bc30-947815aa0558",
                        "state": -1,
                        "progress": 30,
                        "failed_stage": "audio",
                        "error": "TTS request timed out",
                    },
                },
            ],
        }
    )


class TaskListResponse(BaseResponse):
    """任务列表使用独立响应模型，避免与单任务查询混用文档结构。"""

    data: TaskListData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "tasks": [
                        {
                            "task_id": "6c85c8cc-a77a-42b9-bc30-947815aa0558",
                            "state": 4,
                            "progress": 50,
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "page_size": 10,
                },
            }
        }
    )


class TaskDeletionResponse(BaseResponse):
    data: None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": None,
            },
        }
    )


class VideoScriptResponse(BaseResponse):
    data: VideoScriptData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "video_script": "春天的花海，是大自然的一幅美丽画卷。在这个季节里，大地复苏，万物生长，花朵争相绽放，形成了一片五彩斑斓的花海..."
                },
            },
        }
    )


class VideoTermsResponse(BaseResponse):
    data: VideoTermsData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {"video_terms": ["sky", "tree"]},
            },
        }
    )


class VideoSocialMetadataResponse(BaseResponse):
    data: VideoSocialMetadataData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "title": "A Day in Shanghai You Should Not Miss",
                    "caption": "Save this quick Shanghai inspiration and follow for more short travel ideas.",
                    "hashtags": ["#shorts", "#travel", "#shanghai", "#viral", "#fyp"],
                },
            },
        }
    )


class BgmRetrieveResponse(BaseResponse):
    data: BgmRetrieveData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "files": [
                        {
                            "name": "4fca18fce7344f3aa824777a40d45c8c.mp3",
                            "size": 1891269,
                            "file": "4fca18fce7344f3aa824777a40d45c8c.mp3",
                        }
                    ]
                },
            },
        }
    )


class BgmUploadResponse(BaseResponse):
    data: BgmUploadData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {"file": "4fca18fce7344f3aa824777a40d45c8c.mp3"},
            },
        }
    )


class VideoMaterialRetrieveResponse(BaseResponse):
    data: VideoMaterialRetrieveData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "files": [
                        {
                            "name": "example.mp4",
                            "size": 12345678,
                            "file": "/ChangoFilm/resource/videos/example.mp4",
                        }
                    ]
                },
            },
        }
    )


class VideoMaterialUploadResponse(BaseResponse):
    data: VideoMaterialUploadData

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "file": "/ChangoFilm/resource/videos/example.mp4",
                },
            },
        }
    )

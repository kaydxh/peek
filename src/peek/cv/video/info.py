# -*- coding: utf-8 -*-
"""VideoInfo - 视频信息获取工具

提供视频元信息的探测和获取功能，对应 kingfisher InputFile 的
get_duration / get_frame_rate / get_total_frames 等方法。

支持两种后端：
- ffprobe（默认，使用 ffmpeg-python API，信息最全面）
- opencv（备选，无需 ffmpeg 依赖）
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """单个流的信息"""

    index: int = 0  # 流索引
    codec_type: str = ""  # 流类型: video / audio / subtitle
    codec_name: str = ""  # 编解码器名称，如 h264, aac
    codec_long_name: str = ""  # 编解码器全称
    profile: str = ""  # 编码 profile，如 High, Main
    width: int = 0  # 视频宽度（仅视频流）
    height: int = 0  # 视频高度（仅视频流）
    pix_fmt: str = ""  # 像素格式，如 yuv420p
    fps: float = 0.0  # 帧率（仅视频流）
    bit_rate: int = 0  # 比特率 (bps)
    duration: float = 0.0  # 流时长（秒）
    nb_frames: int = 0  # 帧数
    sample_rate: int = 0  # 采样率（仅音频流）
    channels: int = 0  # 声道数（仅音频流）
    channel_layout: str = ""  # 声道布局（仅音频流）
    raw: Dict[str, Any] = field(default_factory=dict)  # 原始 ffprobe 数据


@dataclass
class VideoInfo:
    """视频文件信息

    包含文件级元信息和各流（视频/音频）的详细信息。
    """

    # 文件级信息
    filename: str = ""  # 文件名
    format_name: str = ""  # 容器格式，如 mp4, mkv, avi
    format_long_name: str = ""  # 容器格式全称
    duration: float = 0.0  # 总时长（秒）
    size: int = 0  # 文件大小（字节）
    bit_rate: int = 0  # 总比特率 (bps)
    nb_streams: int = 0  # 流数量

    # 视频流信息（取第一个视频流）
    width: int = 0  # 视频宽度
    height: int = 0  # 视频高度
    fps: float = 0.0  # 帧率
    total_frames: int = 0  # 总帧数（估算）
    video_codec: str = ""  # 视频编解码器
    pix_fmt: str = ""  # 像素格式

    # 音频流信息（取第一个音频流）
    audio_codec: str = ""  # 音频编解码器
    sample_rate: int = 0  # 采样率
    channels: int = 0  # 声道数
    channel_layout: str = ""  # 声道布局

    # 所有流的详细信息
    streams: List[StreamInfo] = field(default_factory=list)

    # 原始数据
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def resolution(self) -> str:
        """获取分辨率字符串，如 '1920x1080'"""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return ""

    @property
    def aspect_ratio(self) -> float:
        """获取宽高比"""
        if self.height > 0:
            return self.width / self.height
        return 0.0

    @property
    def total_pixels(self) -> int:
        """获取总像素数"""
        return self.width * self.height

    @property
    def has_video(self) -> bool:
        """是否包含视频流"""
        return any(s.codec_type == "video" for s in self.streams)

    @property
    def has_audio(self) -> bool:
        """是否包含音频流"""
        return any(s.codec_type == "audio" for s in self.streams)

    def __str__(self) -> str:
        parts = [f"VideoInfo({self.filename})"]
        if self.duration > 0:
            parts.append(f"  时长: {self.duration:.2f}s")
        if self.resolution:
            parts.append(f"  分辨率: {self.resolution}")
        if self.fps > 0:
            parts.append(f"  帧率: {self.fps:.2f} fps")
        if self.total_frames > 0:
            parts.append(f"  总帧数: {self.total_frames}")
        if self.video_codec:
            parts.append(f"  视频编码: {self.video_codec}")
        if self.audio_codec:
            parts.append(f"  音频编码: {self.audio_codec}")
        if self.format_name:
            parts.append(f"  容器格式: {self.format_name}")
        if self.size > 0:
            size_mb = self.size / (1024 * 1024)
            parts.append(f"  文件大小: {size_mb:.2f} MB")
        return "\n".join(parts)


def probe(
    source: Union[str, Path],
    backend: str = "ffprobe",
) -> VideoInfo:
    """探测视频文件信息

    Args:
        source: 视频文件路径
        backend: 探测后端，可选 'ffprobe'（默认）或 'opencv'

    Returns:
        VideoInfo: 视频信息数据类

    Raises:
        FileNotFoundError: 文件不存在
        RuntimeError: 探测失败
    """
    source = str(source)

    if backend == "ffprobe":
        return _probe_ffprobe(source)
    elif backend == "opencv":
        return _probe_opencv(source)
    else:
        raise ValueError(f"不支持的探测后端: {backend}，可选: ffprobe, opencv")


def _probe_ffprobe(source: str) -> VideoInfo:
    """使用 ffmpeg-python 的 probe API 探测视频信息

    Args:
        source: 视频文件路径

    Returns:
        VideoInfo: 视频信息

    Raises:
        ImportError: 未安装 ffmpeg-python
        RuntimeError: 探测失败
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError(
            "使用 ffprobe 后端需要安装 ffmpeg-python: pip install ffmpeg-python。"
            "也可使用 backend='opencv' 作为备选方案。"
        )

    try:
        data = ffmpeg.probe(source)
    except ffmpeg.Error as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
        raise RuntimeError(f"ffprobe 探测失败: {stderr}")
    except FileNotFoundError:
        raise RuntimeError(
            "未找到 ffprobe，请安装 ffmpeg。"
            "也可使用 backend='opencv' 作为备选方案。"
        )

    return _parse_ffprobe_data(data, source)


def _parse_ffprobe_data(data: Dict[str, Any], source: str) -> VideoInfo:
    """解析 ffprobe JSON 输出为 VideoInfo

    Args:
        data: ffprobe 的 JSON 数据
        source: 视频文件路径

    Returns:
        VideoInfo: 解析后的视频信息
    """
    info = VideoInfo(raw=data)

    # 解析 format 信息
    fmt = data.get("format", {})
    info.filename = fmt.get("filename", source)
    info.format_name = fmt.get("format_name", "")
    info.format_long_name = fmt.get("format_long_name", "")
    info.duration = _safe_float(fmt.get("duration", 0))
    info.size = _safe_int(fmt.get("size", 0))
    info.bit_rate = _safe_int(fmt.get("bit_rate", 0))
    info.nb_streams = _safe_int(fmt.get("nb_streams", 0))

    # 解析各个流
    first_video = None
    first_audio = None

    for stream_data in data.get("streams", []):
        stream = _parse_stream(stream_data)
        info.streams.append(stream)

        if stream.codec_type == "video" and first_video is None:
            first_video = stream
        elif stream.codec_type == "audio" and first_audio is None:
            first_audio = stream

    # 填充视频流快捷字段
    if first_video:
        info.width = first_video.width
        info.height = first_video.height
        info.fps = first_video.fps
        info.video_codec = first_video.codec_name
        info.pix_fmt = first_video.pix_fmt
        info.total_frames = first_video.nb_frames
        # 如果 nb_frames 为 0，通过时长和帧率估算
        if info.total_frames <= 0 and info.fps > 0 and info.duration > 0:
            info.total_frames = int(info.duration * info.fps)

    # 填充音频流快捷字段
    if first_audio:
        info.audio_codec = first_audio.codec_name
        info.sample_rate = first_audio.sample_rate
        info.channels = first_audio.channels
        info.channel_layout = first_audio.channel_layout

    logger.debug(f"视频信息探测完成: {info.filename}, {info.resolution}, {info.duration:.2f}s")
    return info


def _parse_stream(data: Dict[str, Any]) -> StreamInfo:
    """解析单个流的信息

    Args:
        data: ffprobe 单个流的 JSON 数据

    Returns:
        StreamInfo: 流信息
    """
    stream = StreamInfo(raw=data)
    stream.index = _safe_int(data.get("index", 0))
    stream.codec_type = data.get("codec_type", "")
    stream.codec_name = data.get("codec_name", "")
    stream.codec_long_name = data.get("codec_long_name", "")
    stream.profile = data.get("profile", "")
    stream.width = _safe_int(data.get("width", 0))
    stream.height = _safe_int(data.get("height", 0))
    stream.pix_fmt = data.get("pix_fmt", "")
    stream.bit_rate = _safe_int(data.get("bit_rate", 0))
    stream.duration = _safe_float(data.get("duration", 0))
    stream.nb_frames = _safe_int(data.get("nb_frames", 0))
    stream.sample_rate = _safe_int(data.get("sample_rate", 0))
    stream.channels = _safe_int(data.get("channels", 0))
    stream.channel_layout = data.get("channel_layout", "")

    # 解析帧率（r_frame_rate 格式为 "30/1" 或 "30000/1001"）
    fps_str = data.get("r_frame_rate", "0/1")
    stream.fps = _parse_rational(fps_str)

    return stream


def _probe_opencv(source: str) -> VideoInfo:
    """使用 OpenCV 探测视频信息

    相比 ffprobe 信息较少，但无需额外安装 ffprobe。

    Args:
        source: 视频文件路径

    Returns:
        VideoInfo: 视频信息

    Raises:
        ImportError: 未安装 opencv
        RuntimeError: 打开视频失败
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("使用 opencv 后端需要安装 opencv-python: pip install opencv-python")

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV 无法打开视频文件: {source}")

    try:
        info = VideoInfo()
        info.filename = source

        # 视频流信息
        info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        info.fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        info.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        if fourcc_int > 0:
            info.video_codec = "".join(
                chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)
            )

        # 计算时长
        if info.fps > 0 and info.total_frames > 0:
            info.duration = info.total_frames / info.fps

        # 构建 StreamInfo
        video_stream = StreamInfo(
            index=0,
            codec_type="video",
            codec_name=info.video_codec,
            width=info.width,
            height=info.height,
            fps=info.fps,
            nb_frames=info.total_frames,
            duration=info.duration,
        )
        info.streams.append(video_stream)
        info.nb_streams = 1

        logger.debug(
            f"视频信息探测完成（opencv）: {source}, "
            f"{info.resolution}, {info.duration:.2f}s"
        )
        return info
    finally:
        cap.release()


def _safe_float(value: Any) -> float:
    """安全转换为 float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value: Any) -> int:
    """安全转换为 int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _parse_rational(rational_str: str) -> float:
    """解析 FFmpeg 有理数格式（如 '30/1', '30000/1001'）

    Args:
        rational_str: 有理数字符串

    Returns:
        float: 计算结果
    """
    try:
        if "/" in rational_str:
            num, den = rational_str.split("/")
            den = int(den)
            if den != 0:
                return int(num) / den
        return float(rational_str)
    except (ValueError, ZeroDivisionError):
        return 0.0
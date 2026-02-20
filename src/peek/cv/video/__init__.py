# -*- coding: utf-8 -*-
"""Video processing utilities - 视频处理工具集

提供视频解码、信息获取、截取、滤镜等功能：

解码器:
- VideoDecoder: 视频解码器门面类（推荐使用）
- VideoDecodeMethod: 解码方式枚举
- BaseDecoder / DecordDecoder / OpenCVDecoder / DecoderFactory: 解码器子包

视频信息:
- VideoInfo / StreamInfo: 视频信息数据类
- probe: 视频信息探测函数

视频截取:
- VideoClip: 视频截取工具（按时间段裁剪、分割）

滤镜:
- VideoFilter: 链式滤镜调用入口（推荐使用）
- ScaleFilter / ScaleConfig: 视频缩放
- CropFilter / CropConfig: 视频裁剪（空间维度）
- TransformFilter / TransformConfig: 视频旋转/翻转

智能缩放:
- smart_resize / smart_resize_image: 与 Qwen2-VL 一致的智能缩放
"""

from .clip import VideoClip
from .decoder import (
    BaseDecoder,
    DecodeConfig,
    DecordDecoder,
    DecoderFactory,
    FFmpegDecoder,
    OpenCVDecoder,
)
from .filter import CropFilter, ScaleFilter, TransformFilter, VideoFilter
from .filter.crop import CropConfig
from .filter.scale import ScaleConfig
from .filter.transform import TransformConfig
from .info import StreamInfo, VideoInfo, probe
from .resize import smart_resize, smart_resize_image
from .video_decoder import VideoDecodeMethod, VideoDecoder

__all__ = [
    # 门面类（推荐使用，向后兼容）
    "VideoDecoder",
    "VideoDecodeMethod",
    # 解码器子包
    "BaseDecoder",
    "DecordDecoder",
    "OpenCVDecoder",
    "FFmpegDecoder",
    "DecodeConfig",
    "DecoderFactory",
    # 视频信息
    "VideoInfo",
    "StreamInfo",
    "probe",
    # 视频截取
    "VideoClip",
    # 滤镜
    "VideoFilter",
    "ScaleFilter",
    "ScaleConfig",
    "CropFilter",
    "CropConfig",
    "TransformFilter",
    "TransformConfig",
    # 智能缩放
    "smart_resize",
    "smart_resize_image",
]

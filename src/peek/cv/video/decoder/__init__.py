# -*- coding: utf-8 -*-
"""Decoder package - 视频解码器集合

提供多种底层实现的视频解码器：
- DecordDecoder: 基于 decord 库（推荐，性能最好）
- OpenCVDecoder: 基于 OpenCV（兼容性好）
- FFmpegDecoder: 基于 PyAV/FFmpeg（功能最完整，支持 GPU/滤镜/Seek）
- QwenVLDecoder: 基于 qwen-vl-utils（与 Qwen3-VL 预处理逻辑完全一致）
- DecoderFactory: 工厂方法，根据配置创建解码器
- BaseDecoder: 抽象基类
"""

from .base import BaseDecoder
from .decord_decoder import DecordDecoder
from .factory import DecoderFactory
from .ffmpeg_decoder import DecodeConfig, FFmpegDecoder
from .opencv_decoder import OpenCVDecoder
from .qwenvl_decoder import QwenVLDecoder

__all__ = [
    "BaseDecoder",
    "DecordDecoder",
    "OpenCVDecoder",
    "FFmpegDecoder",
    "QwenVLDecoder",
    "DecodeConfig",
    "DecoderFactory",
]

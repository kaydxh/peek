# -*- coding: utf-8 -*-
"""Filter package - 视频滤镜工具集

提供与 kingfisher FilterBuilder 对应的视频滤镜功能：
- VideoFilter: 链式调用入口（推荐使用）
- ScaleFilter: 视频缩放
- CropFilter: 视频裁剪（空间维度）
- TransformFilter: 视频旋转/翻转
"""

from .crop import CropFilter
from .scale import ScaleFilter
from .transform import TransformFilter
from .video_filter import VideoFilter

__all__ = [
    "VideoFilter",
    "ScaleFilter",
    "CropFilter",
    "TransformFilter",
]

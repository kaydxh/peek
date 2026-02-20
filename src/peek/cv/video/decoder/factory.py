# -*- coding: utf-8 -*-
"""DecoderFactory - 视频解码器工厂

根据配置参数创建对应的视频解码器实例。
"""

import logging
from typing import Dict, Optional

from .base import BaseDecoder

logger = logging.getLogger(__name__)


class DecoderFactory:
    """视频解码器工厂类"""

    @staticmethod
    def create(
        method: str = "decord",
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
        **kwargs,
    ) -> BaseDecoder:
        """根据方式创建视频解码器实例

        Args:
            method: 解码方式，可选 decord / opencv / ffmpeg
            fps: 抽帧频率（帧/秒）
            max_frames: 最大帧数，-1 表示不限制
            image_format: 输出图片格式，JPEG 或 PNG
            image_quality: 图片压缩质量（仅 JPEG 有效），范围 1-100
            size: 分辨率缩放配置
            **kwargs: 额外参数，ffmpeg 解码器支持 decode_config / progress_callback / cancel_callback

        Returns:
            BaseDecoder: 解码器实例

        Raises:
            ValueError: 不支持的解码方式
        """
        method = method.lower()

        if method == "decord":
            from .decord_decoder import DecordDecoder
            decoder = DecordDecoder(
                fps=fps,
                max_frames=max_frames,
                image_format=image_format,
                image_quality=image_quality,
                size=size,
            )
        elif method == "opencv":
            from .opencv_decoder import OpenCVDecoder
            decoder = OpenCVDecoder(
                fps=fps,
                max_frames=max_frames,
                image_format=image_format,
                image_quality=image_quality,
                size=size,
            )
        elif method == "ffmpeg":
            from .ffmpeg_decoder import FFmpegDecoder
            decoder = FFmpegDecoder(
                fps=fps,
                max_frames=max_frames,
                image_format=image_format,
                image_quality=image_quality,
                size=size,
                decode_config=kwargs.get("decode_config"),
                progress_callback=kwargs.get("progress_callback"),
                cancel_callback=kwargs.get("cancel_callback"),
            )
        else:
            raise ValueError(
                f"不支持的解码方式: '{method}'，可选值: decord, opencv, ffmpeg"
            )

        logger.info(
            f"视频解码器已创建: method={method}, fps={fps}, "
            f"max_frames={max_frames}, image_format={image_format}, "
            f"image_quality={image_quality}, "
            f"shortest_edge={decoder.shortest_edge}, "
            f"longest_edge={decoder.longest_edge}"
        )

        return decoder

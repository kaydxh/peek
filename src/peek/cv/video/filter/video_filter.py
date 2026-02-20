# -*- coding: utf-8 -*-
"""VideoFilter - 视频滤镜链式调用

对应 kingfisher FilterBuilder 的链式 API，
支持将多个滤镜组合成 pipeline 后一次性执行。

底层使用 ffmpeg-python API 实现。

用法示例::

    VideoFilter("input.mp4") \\
        .scale(1280, 720) \\
        .crop(x=100, y=50, width=800, height=600) \\
        .rotate(90) \\
        .hflip() \\
        .output("output.mp4")
"""

import logging
from pathlib import Path
from typing import List, Optional

from .crop import CropFilter
from .scale import ScaleFilter
from .transform import TransformFilter

logger = logging.getLogger(__name__)


def _ensure_ffmpeg():
    """确保 ffmpeg-python 已安装"""
    try:
        import ffmpeg
        return ffmpeg
    except ImportError:
        raise ImportError("需要安装 ffmpeg-python: pip install ffmpeg-python")


class VideoFilter:
    """视频滤镜链式调用入口

    通过链式调用添加多个滤镜，最后调用 output() 执行。
    所有滤镜会合并为一个 ffmpeg -vf filter chain，一次性处理。
    """

    def __init__(self, source: str):
        """初始化 VideoFilter

        Args:
            source: 输入视频路径
        """
        self._source = source
        self._filters: List[str] = []

    def scale(
        self,
        width: int = -1,
        height: int = -1,
        algorithm: str = "bicubic",
    ) -> "VideoFilter":
        """添加缩放滤镜

        Args:
            width: 目标宽度（-1 保持比例，-2 保持比例且偶数）
            height: 目标高度
            algorithm: 缩放算法

        Returns:
            self: 支持链式调用
        """
        filter_str = ScaleFilter.build_filter(width, height, algorithm)
        self._filters.append(filter_str)
        return self

    def crop(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        center_crop: bool = False,
        out_width: int = 0,
        out_height: int = 0,
        keep_aspect: bool = False,
        target_aspect: float = 0.0,
    ) -> "VideoFilter":
        """添加裁剪滤镜

        Args:
            x: 裁剪起始 x 坐标
            y: 裁剪起始 y 坐标
            width: 裁剪宽度
            height: 裁剪高度
            center_crop: 居中裁剪
            out_width: 居中裁剪宽度
            out_height: 居中裁剪高度
            keep_aspect: 按宽高比裁剪
            target_aspect: 目标宽高比

        Returns:
            self: 支持链式调用
        """
        filter_str = CropFilter.build_filter(
            x=x, y=y, width=width, height=height,
            center_crop=center_crop, out_width=out_width, out_height=out_height,
            keep_aspect=keep_aspect, target_aspect=target_aspect,
        )
        self._filters.append(filter_str)
        return self

    def rotate(self, angle: float = 0.0) -> "VideoFilter":
        """添加旋转滤镜

        Args:
            angle: 旋转角度（度），支持任意角度

        Returns:
            self: 支持链式调用
        """
        filter_str = TransformFilter.build_filter(rotation_angle=angle)
        if filter_str:
            self._filters.append(filter_str)
        return self

    def hflip(self) -> "VideoFilter":
        """添加水平翻转滤镜

        Returns:
            self: 支持链式调用
        """
        self._filters.append("hflip")
        return self

    def vflip(self) -> "VideoFilter":
        """添加垂直翻转滤镜

        Returns:
            self: 支持链式调用
        """
        self._filters.append("vflip")
        return self

    def transpose(self, direction: int = 0) -> "VideoFilter":
        """添加转置滤镜（90度旋转）

        Args:
            direction: 转置方向:
                0 = 90° 顺时针
                1 = 90° 逆时针
                2 = 90° 顺时针 + 垂直翻转
                3 = 90° 逆时针 + 垂直翻转

        Returns:
            self: 支持链式调用
        """
        self._filters.append(f"transpose={direction}")
        return self

    def custom(self, filter_str: str) -> "VideoFilter":
        """添加自定义 ffmpeg filter 字符串

        Args:
            filter_str: 原始 ffmpeg filter 字符串

        Returns:
            self: 支持链式调用
        """
        if filter_str:
            self._filters.append(filter_str)
        return self

    def build(self) -> str:
        """构建最终的 filter chain 字符串

        Returns:
            str: 所有滤镜用逗号连接的 ffmpeg filter 字符串
        """
        return ",".join(self._filters)

    def output(
        self,
        output_path: str,
        video_codec: Optional[str] = None,
        audio_codec: str = "copy",
        overwrite: bool = True,
    ) -> str:
        """执行滤镜链并输出视频

        Args:
            output_path: 输出视频路径
            video_codec: 视频编码器，None 时自动选择
            audio_codec: 音频编码器，默认直接复制
            overwrite: 是否覆盖输出文件

        Returns:
            str: 输出文件路径

        Raises:
            ValueError: 没有添加任何滤镜
            ImportError: 未安装 ffmpeg-python
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        if not self._filters:
            raise ValueError("没有添加任何滤镜，请先调用 scale() / crop() / rotate() 等方法")

        filter_chain = self.build()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 构建输出参数
        output_kwargs = {
            "vf": filter_chain,
            "acodec": audio_codec,
        }

        if video_codec:
            output_kwargs["vcodec"] = video_codec

        out = ffmpeg.input(self._source).output(output_path, **output_kwargs)

        logger.info(f"执行滤镜链: {self._source} -> {output_path}")
        logger.info(f"滤镜: {filter_chain}")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"滤镜执行失败:\n" + "\n".join(error_lines)
            )

        logger.info(f"滤镜链执行完成: {output_path}")
        return output_path
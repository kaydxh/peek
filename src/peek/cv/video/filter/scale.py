# -*- coding: utf-8 -*-
"""ScaleFilter - 视频缩放滤镜

对应 kingfisher FilterBuilder::scale / ScaleConfig，
支持指定宽高缩放、保持宽高比、强制偶数对齐等模式。

底层使用 ffmpeg-python API 实现。
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_ffmpeg():
    """确保 ffmpeg-python 已安装"""
    try:
        import ffmpeg
        return ffmpeg
    except ImportError:
        raise ImportError("需要安装 ffmpeg-python: pip install ffmpeg-python")


@dataclass
class ScaleConfig:
    """缩放配置

    对应 kingfisher ScaleConfig 结构体。

    Attributes:
        width: 目标宽度，-1 保持比例，-2 保持比例且为偶数
        height: 目标高度，-1 保持比例，-2 保持比例且为偶数
        algorithm: 缩放算法，可选:
            - bicubic（默认）
            - bilinear
            - lanczos
            - neighbor（最近邻）
            - area
        force_original_aspect_ratio: 是否强制保持原始宽高比
            - None: 不强制
            - 'decrease': 缩小到目标尺寸内
            - 'increase': 放大到覆盖目标尺寸
        force_divisible_by: 强制宽高可被此数整除，常用 2（编码器要求偶数）
    """

    width: int = -1
    height: int = -1
    algorithm: str = "bicubic"
    force_original_aspect_ratio: Optional[str] = None
    force_divisible_by: int = 0


class ScaleFilter:
    """视频缩放滤镜

    用法示例::

        # 指定宽高
        ScaleFilter.apply("input.mp4", "output.mp4", width=1280, height=720)

        # 保持宽高比，指定宽度
        ScaleFilter.apply("input.mp4", "output.mp4", width=1280, height=-1)

        # 保持宽高比且为偶数
        ScaleFilter.apply("input.mp4", "output.mp4", width=1280, height=-2)

        # 使用配置对象
        config = ScaleConfig(width=1920, height=1080, algorithm="lanczos")
        ScaleFilter.apply("input.mp4", "output.mp4", config=config)
    """

    @staticmethod
    def apply(
        source: str,
        output: str,
        width: int = -1,
        height: int = -1,
        algorithm: str = "bicubic",
        config: Optional[ScaleConfig] = None,
        overwrite: bool = True,
    ) -> str:
        """对视频进行缩放

        Args:
            source: 输入视频路径
            output: 输出视频路径
            width: 目标宽度（-1 保持比例，-2 保持比例且偶数）
            height: 目标高度
            algorithm: 缩放算法
            config: ScaleConfig 配置对象（优先级高于单独参数）
            overwrite: 是否覆盖输出文件

        Returns:
            str: 输出文件路径

        Raises:
            ImportError: 未安装 ffmpeg-python
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        if config:
            width = config.width
            height = config.height
            algorithm = config.algorithm

        Path(output).parent.mkdir(parents=True, exist_ok=True)

        # 构建 scale filter 参数
        filter_kwargs = {"w": width, "h": height}
        if algorithm:
            filter_kwargs["flags"] = algorithm
        if config and config.force_original_aspect_ratio:
            filter_kwargs["force_original_aspect_ratio"] = config.force_original_aspect_ratio
        if config and config.force_divisible_by > 0:
            filter_kwargs["force_divisible_by"] = config.force_divisible_by

        stream = ffmpeg.input(source)
        video = stream.video.filter("scale", **filter_kwargs)
        audio = stream.audio

        out = ffmpeg.output(video, audio, output)

        logger.info(f"视频缩放: {source} -> {output}, params={filter_kwargs}")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"视频缩放失败:\n" + "\n".join(error_lines)
            )

        logger.info(f"视频缩放完成: {output}")
        return output

    @staticmethod
    def build_filter(
        width: int = -1,
        height: int = -1,
        algorithm: str = "bicubic",
        config: Optional[ScaleConfig] = None,
    ) -> str:
        """构建 ffmpeg scale filter 字符串

        用于 VideoFilter 链式调用内部组装 filter chain。

        Args:
            width: 目标宽度
            height: 目标高度
            algorithm: 缩放算法
            config: ScaleConfig 配置对象

        Returns:
            str: ffmpeg filter 字符串，如 "scale=1280:720:flags=bicubic"
        """
        if config:
            width = config.width
            height = config.height
            algorithm = config.algorithm

        parts = [f"scale={width}:{height}"]

        if algorithm:
            parts.append(f"flags={algorithm}")

        if config and config.force_original_aspect_ratio:
            parts.append(f"force_original_aspect_ratio={config.force_original_aspect_ratio}")

        if config and config.force_divisible_by > 0:
            parts.append(f"force_divisible_by={config.force_divisible_by}")

        return ":".join(parts)
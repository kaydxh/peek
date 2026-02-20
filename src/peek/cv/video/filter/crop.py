# -*- coding: utf-8 -*-
"""CropFilter - 视频裁剪滤镜（空间维度）

对应 kingfisher FilterBuilder::crop / CropConfig，
支持坐标裁剪、居中裁剪、按目标宽高比裁剪等模式。

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
class CropConfig:
    """裁剪配置

    对应 kingfisher CropConfig 结构体。

    Attributes:
        x: 裁剪起始 x 坐标
        y: 裁剪起始 y 坐标
        width: 裁剪宽度（0 表示自动：视频宽度 - x）
        height: 裁剪高度（0 表示自动：视频高度 - y）
        center_crop: 启用居中裁剪（忽略 x, y，使用 out_width, out_height）
        out_width: 居中裁剪输出宽度
        out_height: 居中裁剪输出高度
        keep_aspect: 保持宽高比裁剪
        target_aspect: 目标宽高比（如 16/9 = 1.777）
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    center_crop: bool = False
    out_width: int = 0
    out_height: int = 0
    keep_aspect: bool = False
    target_aspect: float = 0.0


class CropFilter:
    """视频裁剪滤镜

    用法示例::

        # 指定坐标和尺寸裁剪
        CropFilter.apply("input.mp4", "output.mp4", x=100, y=50, width=800, height=600)

        # 居中裁剪
        CropFilter.apply("input.mp4", "output.mp4", center_crop=True,
                         out_width=640, out_height=480)

        # 按宽高比裁剪（居中）
        CropFilter.apply("input.mp4", "output.mp4",
                         keep_aspect=True, target_aspect=16/9)

        # 使用配置对象
        config = CropConfig(center_crop=True, out_width=640, out_height=480)
        CropFilter.apply("input.mp4", "output.mp4", config=config)
    """

    @staticmethod
    def apply(
        source: str,
        output: str,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        center_crop: bool = False,
        out_width: int = 0,
        out_height: int = 0,
        keep_aspect: bool = False,
        target_aspect: float = 0.0,
        config: Optional[CropConfig] = None,
        overwrite: bool = True,
    ) -> str:
        """对视频进行空间裁剪

        Args:
            source: 输入视频路径
            output: 输出视频路径
            x: 裁剪起始 x 坐标
            y: 裁剪起始 y 坐标
            width: 裁剪宽度（0 表示自动）
            height: 裁剪高度（0 表示自动）
            center_crop: 是否居中裁剪
            out_width: 居中裁剪宽度
            out_height: 居中裁剪高度
            keep_aspect: 是否按宽高比裁剪
            target_aspect: 目标宽高比
            config: CropConfig 配置对象（优先级高于单独参数）
            overwrite: 是否覆盖输出文件

        Returns:
            str: 输出文件路径

        Raises:
            ValueError: 参数校验失败
            ImportError: 未安装 ffmpeg-python
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        if config:
            x = config.x
            y = config.y
            width = config.width
            height = config.height
            center_crop = config.center_crop
            out_width = config.out_width
            out_height = config.out_height
            keep_aspect = config.keep_aspect
            target_aspect = config.target_aspect

        # 构建 crop filter 字符串（使用 ffmpeg 表达式）
        filter_str = CropFilter.build_filter(
            x=x, y=y, width=width, height=height,
            center_crop=center_crop, out_width=out_width, out_height=out_height,
            keep_aspect=keep_aspect, target_aspect=target_aspect,
        )

        Path(output).parent.mkdir(parents=True, exist_ok=True)

        # 因为 crop filter 使用了 ffmpeg 表达式（如 iw, ih），直接使用 -vf 参数
        out = ffmpeg.input(source).output(output, vf=filter_str, acodec="copy")

        logger.info(f"视频裁剪: {source} -> {output}, filter={filter_str}")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"视频裁剪失败:\n" + "\n".join(error_lines)
            )

        logger.info(f"视频裁剪完成: {output}")
        return output

    @staticmethod
    def build_filter(
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        center_crop: bool = False,
        out_width: int = 0,
        out_height: int = 0,
        keep_aspect: bool = False,
        target_aspect: float = 0.0,
    ) -> str:
        """构建 ffmpeg crop filter 字符串

        Args:
            x: 裁剪起始 x 坐标
            y: 裁剪起始 y 坐标
            width: 裁剪宽度
            height: 裁剪高度
            center_crop: 是否居中裁剪
            out_width: 居中裁剪宽度
            out_height: 居中裁剪高度
            keep_aspect: 是否按宽高比裁剪
            target_aspect: 目标宽高比

        Returns:
            str: ffmpeg filter 字符串
        """
        if keep_aspect and target_aspect > 0:
            # 按目标宽高比居中裁剪
            # 使用 ffmpeg 表达式：先比较当前宽高比与目标宽高比
            # 如果当前更宽，则以高度为基准裁剪宽度；反之以宽度为基准裁剪高度
            target_w = f"if(gt(a,{target_aspect}),ih*{target_aspect},iw)"
            target_h = f"if(gt(a,{target_aspect}),ih,iw/{target_aspect})"
            return f"crop={target_w}:{target_h}"

        if center_crop and out_width > 0 and out_height > 0:
            # 居中裁剪：使用 ffmpeg 的 (iw-ow)/2 表达式自动居中
            return f"crop={out_width}:{out_height}:(iw-{out_width})/2:(ih-{out_height})/2"

        # 普通坐标裁剪
        w = width if width > 0 else f"iw-{x}" if x > 0 else "iw"
        h = height if height > 0 else f"ih-{y}" if y > 0 else "ih"
        return f"crop={w}:{h}:{x}:{y}"
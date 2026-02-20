# -*- coding: utf-8 -*-
"""TransformFilter - 视频旋转/翻转滤镜

对应 kingfisher FilterBuilder::transform / TransformConfig，
支持旋转（任意角度）、水平翻转、垂直翻转、转置（90度旋转）等操作。

底层使用 ffmpeg-python API 的 transpose / hflip / vflip / rotate filter 实现。
"""

import logging
import math
import shutil
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
class TransformConfig:
    """旋转/翻转配置

    对应 kingfisher TransformConfig 结构体。

    Attributes:
        rotation_angle: 旋转角度（度），支持任意角度
        hflip: 水平翻转
        vflip: 垂直翻转
        transpose: 转置模式（90度旋转），比 rotation_angle 更快
        transpose_dir: 转置方向:
            - 0: 90° 顺时针
            - 1: 90° 逆时针
            - 2: 90° 顺时针 + 垂直翻转
            - 3: 90° 逆时针 + 垂直翻转
    """

    rotation_angle: float = 0.0
    hflip: bool = False
    vflip: bool = False
    transpose: bool = False
    transpose_dir: int = 0


class TransformFilter:
    """视频旋转/翻转滤镜

    用法示例::

        # 水平翻转
        TransformFilter.apply("input.mp4", "output.mp4", hflip=True)

        # 垂直翻转
        TransformFilter.apply("input.mp4", "output.mp4", vflip=True)

        # 顺时针旋转 90°
        TransformFilter.apply("input.mp4", "output.mp4", transpose=True, transpose_dir=0)

        # 旋转任意角度（如 45°）
        TransformFilter.apply("input.mp4", "output.mp4", rotation_angle=45)

        # 组合：水平翻转 + 旋转 180°
        TransformFilter.apply("input.mp4", "output.mp4", hflip=True, rotation_angle=180)
    """

    @staticmethod
    def apply(
        source: str,
        output: str,
        rotation_angle: float = 0.0,
        hflip: bool = False,
        vflip: bool = False,
        transpose: bool = False,
        transpose_dir: int = 0,
        config: Optional[TransformConfig] = None,
        overwrite: bool = True,
    ) -> str:
        """对视频进行旋转/翻转

        Args:
            source: 输入视频路径
            output: 输出视频路径
            rotation_angle: 旋转角度（度）
            hflip: 水平翻转
            vflip: 垂直翻转
            transpose: 转置模式
            transpose_dir: 转置方向（0-3）
            config: TransformConfig 配置对象
            overwrite: 是否覆盖输出文件

        Returns:
            str: 输出文件路径

        Raises:
            ImportError: 未安装 ffmpeg-python
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        if config:
            rotation_angle = config.rotation_angle
            hflip = config.hflip
            vflip = config.vflip
            transpose = config.transpose
            transpose_dir = config.transpose_dir

        filter_str = TransformFilter.build_filter(
            rotation_angle=rotation_angle,
            hflip=hflip,
            vflip=vflip,
            transpose=transpose,
            transpose_dir=transpose_dir,
        )

        if not filter_str:
            # 没有变换操作，直接复制
            logger.info(f"无变换操作，直接复制: {source} -> {output}")
            shutil.copy2(source, output)
            return output

        Path(output).parent.mkdir(parents=True, exist_ok=True)

        out = ffmpeg.input(source).output(output, vf=filter_str, acodec="copy")

        logger.info(f"视频变换: {source} -> {output}, filter={filter_str}")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"视频变换失败:\n" + "\n".join(error_lines)
            )

        logger.info(f"视频变换完成: {output}")
        return output

    @staticmethod
    def build_filter(
        rotation_angle: float = 0.0,
        hflip: bool = False,
        vflip: bool = False,
        transpose: bool = False,
        transpose_dir: int = 0,
    ) -> str:
        """构建 ffmpeg 变换 filter 字符串

        多个变换会用逗号连接成 filter chain。

        Args:
            rotation_angle: 旋转角度（度）
            hflip: 水平翻转
            vflip: 垂直翻转
            transpose: 转置模式
            transpose_dir: 转置方向

        Returns:
            str: ffmpeg filter 字符串，多个 filter 用逗号分隔
        """
        filters = []

        # 翻转操作
        if hflip:
            filters.append("hflip")
        if vflip:
            filters.append("vflip")

        # 转置操作（90度整数倍旋转，速度快）
        if transpose:
            filters.append(f"transpose={transpose_dir}")

        # 任意角度旋转
        if rotation_angle != 0.0 and not transpose:
            # 对于 90° 的整数倍，优先使用 transpose（更快、无损）
            angle_mod = rotation_angle % 360

            if abs(angle_mod - 90) < 0.01:
                filters.append("transpose=1")  # 90° 顺时针
            elif abs(angle_mod - 180) < 0.01:
                filters.append("transpose=1,transpose=1")  # 180°
            elif abs(angle_mod - 270) < 0.01:
                filters.append("transpose=2")  # 270° 顺时针 = 90° 逆时针
            else:
                # 任意角度旋转，使用 rotate filter
                # rotate 接受弧度值
                radians = rotation_angle * math.pi / 180
                filters.append(f"rotate={radians}")

        if not filters:
            return ""

        return ",".join(filters)
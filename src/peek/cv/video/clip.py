# -*- coding: utf-8 -*-
"""VideoClip - 视频截取工具

提供按时间段截取视频片段的功能，对应 kingfisher 中
InputFile::seek + OutputFile::write_frames 的组合操作。

底层使用 ffmpeg-python API 实现，支持：
- 按起止时间截取
- 按起始时间 + 时长截取
- 精确（逐帧）截取和快速（关键帧）截取
"""

import glob
import logging
from pathlib import Path
from typing import Callable, List, Optional, Union

logger = logging.getLogger(__name__)


def _ensure_ffmpeg():
    """确保 ffmpeg-python 已安装"""
    try:
        import ffmpeg
        return ffmpeg
    except ImportError:
        raise ImportError("需要安装 ffmpeg-python: pip install ffmpeg-python")


class VideoClip:
    """视频截取工具类

    提供静态方法和实例方法两种使用方式。
    """

    @staticmethod
    def cut(
        source: Union[str, Path],
        output: Union[str, Path],
        start: Optional[float] = None,
        end: Optional[float] = None,
        duration: Optional[float] = None,
        accurate: bool = True,
        copy_codec: bool = True,
        video_codec: Optional[str] = None,
        audio_codec: Optional[str] = None,
        overwrite: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        """截取视频片段

        Args:
            source: 输入视频文件路径
            output: 输出视频文件路径
            start: 起始时间（秒），None 表示从头开始
            end: 结束时间（秒），None 表示到末尾。与 duration 二选一
            duration: 截取时长（秒），与 end 二选一
            accurate: 是否精确截取（True: 逐帧定位，慢但精确；False: 关键帧定位，快但可能有偏差）
            copy_codec: 是否直接复制编码（True: 不重新编码，速度快；False: 重新编码）
            video_codec: 视频编码器（覆盖 copy_codec），如 'libx264', 'libx265'
            audio_codec: 音频编码器（覆盖 copy_codec），如 'aac', 'libmp3lame'
            overwrite: 是否覆盖已有输出文件
            progress_callback: 进度回调函数，参数为进度百分比 [0.0, 1.0]

        Returns:
            str: 输出文件路径

        Raises:
            ValueError: 参数校验失败
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        source = str(source)
        output = str(output)

        # 参数校验
        if end is not None and duration is not None:
            raise ValueError("end 和 duration 不能同时指定，请二选一")

        if start is not None and start < 0:
            raise ValueError(f"start 不能为负数: {start}")

        if end is not None and start is not None and end <= start:
            raise ValueError(f"end ({end}) 必须大于 start ({start})")

        if duration is not None and duration <= 0:
            raise ValueError(f"duration 必须为正数: {duration}")

        # 确保输出目录存在
        output_dir = Path(output).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 构建 ffmpeg-python 输入参数
        input_kwargs = {}
        if start is not None and not accurate:
            # 快速模式：在 input 时 seek（基于关键帧，速度快）
            input_kwargs["ss"] = start

        stream = ffmpeg.input(source, **input_kwargs)

        # 构建输出参数
        output_kwargs = {}

        if start is not None and accurate:
            # 精确模式：在 output 时 seek（逐帧解码，精确但慢）
            output_kwargs["ss"] = start

        # 结束时间或时长
        if end is not None:
            if accurate and start is not None:
                # 精确模式下，t 是相对于 ss 的时长
                output_kwargs["t"] = end - start
            else:
                output_kwargs["to"] = end
        elif duration is not None:
            output_kwargs["t"] = duration

        # 编码选项
        if video_codec:
            output_kwargs["vcodec"] = video_codec
        elif copy_codec:
            output_kwargs["vcodec"] = "copy"

        if audio_codec:
            output_kwargs["acodec"] = audio_codec
        elif copy_codec:
            output_kwargs["acodec"] = "copy"

        # 避免负时间戳
        output_kwargs["avoid_negative_ts"] = "make_zero"

        out = stream.output(output, **output_kwargs)

        # 执行
        logger.info(f"视频截取: {source} -> {output}, start={start}, end={end}, duration={duration}")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"ffmpeg 截取失败:\n" + "\n".join(error_lines)
            )

        logger.info(f"视频截取完成: {output}")
        return output

    @staticmethod
    def split(
        source: Union[str, Path],
        output_dir: Union[str, Path],
        segment_duration: float = 10.0,
        output_pattern: str = "segment_%03d.mp4",
        copy_codec: bool = True,
        overwrite: bool = True,
    ) -> List[str]:
        """将视频按固定时长分割为多个片段

        Args:
            source: 输入视频文件路径
            output_dir: 输出目录
            segment_duration: 每个片段的时长（秒）
            output_pattern: 输出文件名模式，支持 %d 序号占位符
            copy_codec: 是否直接复制编码
            overwrite: 是否覆盖已有输出文件

        Returns:
            list: 输出文件路径列表

        Raises:
            RuntimeError: ffmpeg 执行失败
        """
        ffmpeg = _ensure_ffmpeg()

        source = str(source)
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        output_path = str(output_dir_path / output_pattern)

        # 构建 ffmpeg-python 流
        stream = ffmpeg.input(source)

        output_kwargs = {
            "f": "segment",
            "segment_time": str(segment_duration),
            "reset_timestamps": "1",
        }

        if copy_codec:
            output_kwargs["c"] = "copy"

        out = stream.output(output_path, **output_kwargs)

        logger.info(f"视频分割: {source}, 每段 {segment_duration}s")

        try:
            out.run(overwrite_output=overwrite, quiet=True)
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else "未知错误"
            error_lines = stderr.strip().split("\n")[-5:]
            raise RuntimeError(
                f"ffmpeg 分割失败:\n" + "\n".join(error_lines)
            )

        # 收集输出文件
        glob_pattern = output_pattern.replace("%03d", "*").replace("%d", "*")
        output_files = sorted(glob.glob(str(output_dir_path / glob_pattern)))

        logger.info(f"视频分割完成: 共 {len(output_files)} 个片段")
        return output_files
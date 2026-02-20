# -*- coding: utf-8 -*-
"""BaseDecoder - 视频解码器抽象基类

定义视频解码器的统一接口和通用工具方法。
"""

import base64
import io
import logging
from abc import ABC, abstractmethod
from typing import Dict, Generator, List, Optional, Tuple

from peek.cv.video.resize import smart_resize_image

logger = logging.getLogger(__name__)


class BaseDecoder(ABC):
    """视频解码器抽象基类

    所有具体解码器实现都必须继承此类，并实现 decode / decode_to_bytes 方法。
    """

    def __init__(
        self,
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
    ):
        """初始化解码器基类

        Args:
            fps: 抽帧频率（帧/秒），0 或负数表示不采样（解码所有帧）
            max_frames: 最大帧数，-1 表示不限制
            image_format: 输出图片格式，JPEG 或 PNG
            image_quality: 图片压缩质量（仅 JPEG 有效），范围 1-100
            size: 分辨率缩放配置，包含 shortest_edge 和 longest_edge，
                  用于控制帧图片的像素总数范围（与 Qwen2-VL 的 ViT patch 机制一致）。
                  为 None 时不进行缩放。
                  示例: {"shortest_edge": 196608, "longest_edge": 524288}
        """
        self._fps = fps
        self._max_frames = max_frames
        self._image_format = image_format
        self._image_quality = image_quality
        self._shortest_edge = size.get("shortest_edge", 0) if size else 0
        self._longest_edge = size.get("longest_edge", 0) if size else 0

    @property
    def fps(self) -> float:
        """获取抽帧频率"""
        return self._fps

    @property
    def max_frames(self) -> int:
        """获取最大帧数"""
        return self._max_frames

    @property
    def image_format(self) -> str:
        """获取输出图片格式"""
        return self._image_format

    @property
    def image_quality(self) -> int:
        """获取图片压缩质量"""
        return self._image_quality

    @property
    def shortest_edge(self) -> int:
        """获取最短边像素总数下限"""
        return self._shortest_edge

    @property
    def longest_edge(self) -> int:
        """获取最长边像素总数上限"""
        return self._longest_edge

    @abstractmethod
    def decode(self, video_bytes: bytes) -> List[str]:
        """解码视频为帧图片的 base64 列表

        Args:
            video_bytes: 视频原始字节数据

        Returns:
            List[str]: 帧图片的 base64 字符串列表
        """

    @abstractmethod
    def decode_to_bytes(self, video_bytes: bytes) -> List[bytes]:
        """解码视频为帧图片的原始字节列表

        Args:
            video_bytes: 视频原始字节数据

        Returns:
            List[bytes]: 帧图片的原始字节列表
        """

    def decode_batches(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[str], None, None]:
        """批量迭代解码视频帧（base64 输出）

        对应 kingfisher InputFile::read_frames(batch_size) 的循环模式，
        每次 yield 一批帧（最多 batch_size 个），调用者通过 for 循环消费。
        内存占用恒定（只持有当前 batch），适合处理超长视频。

        默认实现：将 decode() 的全量结果分批返回。
        子类（如 FFmpegDecoder）可重写为真正的流式实现。

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数，对应 kingfisher read_frames 的 batch_size 参数

        Yields:
            List[str]: 每批帧图片的 base64 字符串列表，最后一批可能不足 batch_size
        """
        all_frames = self.decode(video_bytes)
        for i in range(0, len(all_frames), batch_size):
            yield all_frames[i : i + batch_size]

    def decode_batches_to_bytes(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[bytes], None, None]:
        """批量迭代解码视频帧（原始字节输出）

        与 decode_batches 相同，但输出为原始字节。

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数

        Yields:
            List[bytes]: 每批帧图片的原始字节列表
        """
        all_frames = self.decode_to_bytes(video_bytes)
        for i in range(0, len(all_frames), batch_size):
            yield all_frames[i : i + batch_size]

    def _compute_frame_indices(self, total_frames: int, video_fps: float) -> List[int]:
        """根据 fps 配置计算采样帧索引

        Args:
            total_frames: 视频总帧数
            video_fps: 视频原始帧率

        Returns:
            List[int]: 采样帧索引列表
        """
        if total_frames <= 0:
            return []

        if video_fps <= 0:
            video_fps = 30.0  # 默认帧率

        # fps <= 0 表示全帧解码（不采样），采样间隔为 1
        if self._fps <= 0:
            sample_interval = 1
        else:
            # 根据目标 fps 计算采样间隔
            sample_interval = max(1, int(video_fps / self._fps))
        indices = list(range(0, total_frames, sample_interval))

        # 限制最大帧数
        if self._max_frames > 0 and len(indices) > self._max_frames:
            # 均匀采样
            step = len(indices) / self._max_frames
            indices = [indices[int(i * step)] for i in range(self._max_frames)]

        return indices

    def _resize_frame(self, img):
        """对帧图片进行智能缩放

        Args:
            img: PIL Image 对象

        Returns:
            PIL Image: 缩放后的图片
        """
        return smart_resize_image(img, self._shortest_edge, self._longest_edge)

    def _image_to_bytes(self, img) -> bytes:
        """将 PIL Image 转换为字节数据

        Args:
            img: PIL Image 对象

        Returns:
            bytes: 图片字节数据
        """
        buf = io.BytesIO()
        save_kwargs = {"format": self._image_format}
        if self._image_format.upper() == "JPEG":
            save_kwargs["quality"] = self._image_quality
        img.save(buf, **save_kwargs)
        return buf.getvalue()

    def _image_to_base64(self, img) -> str:
        """将 PIL Image 转换为 base64 字符串

        Args:
            img: PIL Image 对象

        Returns:
            str: base64 编码的图片字符串
        """
        return base64.b64encode(self._image_to_bytes(img)).decode("utf-8")

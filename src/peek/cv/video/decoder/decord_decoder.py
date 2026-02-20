# -*- coding: utf-8 -*-
"""DecordDecoder - 基于 decord 库的视频解码器

decord 是高性能视频解码库，推荐用于生产环境。
安装：pip install decord
"""

import io
import logging
from typing import Dict, Generator, List, Optional

from PIL import Image

from .base import BaseDecoder

logger = logging.getLogger(__name__)


class DecordDecoder(BaseDecoder):
    """基于 decord 库的视频解码器（推荐，性能最好）"""

    def __init__(
        self,
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
    ):
        super().__init__(fps, max_frames, image_format, image_quality, size)
        self._check_available()

    @staticmethod
    def _check_available():
        """检查 decord 库是否可用"""
        try:
            import decord  # noqa: F401
        except ImportError:
            raise ImportError(
                "使用 decord 解码方式需要安装 decord 库：\n"
                "  pip install decord\n"
                "详见：https://github.com/dmlc/decord"
            )

    def decode(self, video_bytes: bytes) -> List[str]:
        """使用 decord 解码视频为帧图片的 base64 列表"""
        return self._decode_frames(video_bytes, as_bytes=False)

    def decode_to_bytes(self, video_bytes: bytes) -> List[bytes]:
        """使用 decord 解码视频为帧图片的原始字节列表"""
        return self._decode_frames(video_bytes, as_bytes=True)

    def _decode_frames(self, video_bytes: bytes, as_bytes: bool = False) -> list:
        """使用 decord 解码视频帧

        Args:
            video_bytes: 视频原始字节数据
            as_bytes: 是否返回原始字节（True）或 base64 字符串（False）

        Returns:
            list: 帧图片列表
        """
        from decord import VideoReader, cpu

        vr = VideoReader(io.BytesIO(video_bytes), ctx=cpu(0))
        total_frames = len(vr)
        video_fps = vr.get_avg_fps()

        # 计算采样帧索引
        frame_indices = self._compute_frame_indices(total_frames, video_fps)

        logger.debug(
            f"decord 解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
            f"sample_frames={len(frame_indices)}"
        )

        frames = []
        for idx in frame_indices:
            frame = vr[idx].asnumpy()  # numpy array (H, W, C) RGB 格式
            img = Image.fromarray(frame)
            img = self._resize_frame(img)
            if as_bytes:
                frames.append(self._image_to_bytes(img))
            else:
                frames.append(self._image_to_base64(img))

        logger.info(f"decord 解码完成: frames={len(frames)}")
        return frames

    def decode_batches(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[str], None, None]:
        """流式批量解码视频帧（base64 输出）

        对应 kingfisher InputFile::read_frames(batch_size) 的循环模式。
        每次 yield 一批帧，内存占用恒定。

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数

        Yields:
            List[str]: 每批帧图片的 base64 字符串列表
        """
        yield from self._decode_frames_batched(video_bytes, batch_size, as_bytes=False)

    def decode_batches_to_bytes(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[bytes], None, None]:
        """流式批量解码视频帧（原始字节输出）"""
        yield from self._decode_frames_batched(video_bytes, batch_size, as_bytes=True)

    def _decode_frames_batched(
        self, video_bytes: bytes, batch_size: int, as_bytes: bool
    ) -> Generator[list, None, None]:
        """流式批量解码内部实现"""
        from decord import VideoReader, cpu

        vr = VideoReader(io.BytesIO(video_bytes), ctx=cpu(0))
        total_frames = len(vr)
        video_fps = vr.get_avg_fps()

        frame_indices = self._compute_frame_indices(total_frames, video_fps)

        logger.debug(
            f"decord 批量解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
            f"sample_frames={len(frame_indices)}, batch_size={batch_size}"
        )

        batch = []
        total_yielded = 0

        for idx in frame_indices:
            frame = vr[idx].asnumpy()
            img = Image.fromarray(frame)
            img = self._resize_frame(img)
            if as_bytes:
                batch.append(self._image_to_bytes(img))
            else:
                batch.append(self._image_to_base64(img))

            if len(batch) >= batch_size:
                total_yielded += len(batch)
                yield batch
                batch = []

        if batch:
            total_yielded += len(batch)
            yield batch

        logger.info(
            f"decord 批量解码完成: 总计 {total_yielded} 帧, batch_size={batch_size}"
        )

# -*- coding: utf-8 -*-
"""OpenCVDecoder - 基于 OpenCV 的视频解码器

OpenCV 兼容性好，适合作为 decord 不可用时的备选方案。
安装：pip install opencv-python 或 pip install opencv-python-headless
"""

import logging
import tempfile
from typing import Dict, Generator, List, Optional

from PIL import Image

from .base import BaseDecoder

logger = logging.getLogger(__name__)


class OpenCVDecoder(BaseDecoder):
    """基于 OpenCV 的视频解码器（兼容性好）"""

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
        """检查 OpenCV 库是否可用"""
        try:
            import cv2  # noqa: F401
        except ImportError:
            raise ImportError(
                "使用 opencv 解码方式需要安装 opencv-python 库：\n"
                "  pip install opencv-python\n"
                "或：pip install opencv-python-headless"
            )

    def decode(self, video_bytes: bytes) -> List[str]:
        """使用 OpenCV 解码视频为帧图片的 base64 列表"""
        return self._decode_frames(video_bytes, as_bytes=False)

    def decode_to_bytes(self, video_bytes: bytes) -> List[bytes]:
        """使用 OpenCV 解码视频为帧图片的原始字节列表"""
        return self._decode_frames(video_bytes, as_bytes=True)

    def _decode_frames(self, video_bytes: bytes, as_bytes: bool = False) -> list:
        """使用 OpenCV 解码视频帧

        Args:
            video_bytes: 视频原始字节数据
            as_bytes: 是否返回原始字节（True）或 base64 字符串（False）

        Returns:
            list: 帧图片列表
        """
        import cv2

        # OpenCV 不支持直接从内存读取视频，需要写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
            tmp.write(video_bytes)
            tmp.flush()

            cap = cv2.VideoCapture(tmp.name)
            if not cap.isOpened():
                raise RuntimeError("OpenCV 无法打开视频文件")

            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                video_fps = cap.get(cv2.CAP_PROP_FPS)

                # 计算采样帧索引
                frame_indices = self._compute_frame_indices(total_frames, video_fps)
                frame_set = set(frame_indices)

                logger.debug(
                    f"opencv 解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
                    f"sample_frames={len(frame_indices)}"
                )

                frames = []
                frame_idx = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_idx in frame_set:
                        # OpenCV 返回 BGR 格式，转换为 RGB
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(rgb_frame)
                        img = self._resize_frame(img)
                        if as_bytes:
                            frames.append(self._image_to_bytes(img))
                        else:
                            frames.append(self._image_to_base64(img))

                    frame_idx += 1

                logger.info(f"opencv 解码完成: frames={len(frames)}")
                return frames
            finally:
                cap.release()

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
        import cv2

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
            tmp.write(video_bytes)
            tmp.flush()

            cap = cv2.VideoCapture(tmp.name)
            if not cap.isOpened():
                raise RuntimeError("OpenCV 无法打开视频文件")

            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                video_fps = cap.get(cv2.CAP_PROP_FPS)

                frame_indices = self._compute_frame_indices(total_frames, video_fps)
                frame_set = set(frame_indices)

                logger.debug(
                    f"opencv 批量解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
                    f"sample_frames={len(frame_indices)}, batch_size={batch_size}"
                )

                batch = []
                frame_idx = 0
                total_yielded = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_idx in frame_set:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(rgb_frame)
                        img = self._resize_frame(img)
                        if as_bytes:
                            batch.append(self._image_to_bytes(img))
                        else:
                            batch.append(self._image_to_base64(img))

                        if len(batch) >= batch_size:
                            total_yielded += len(batch)
                            yield batch
                            batch = []

                    frame_idx += 1

                if batch:
                    total_yielded += len(batch)
                    yield batch

                logger.info(
                    f"opencv 批量解码完成: 总计 {total_yielded} 帧, batch_size={batch_size}"
                )
            finally:
                cap.release()

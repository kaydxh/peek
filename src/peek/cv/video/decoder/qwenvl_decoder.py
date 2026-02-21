# -*- coding: utf-8 -*-
"""QwenVLDecoder - 基于 qwen-vl-utils 的视频解码器

使用 Qwen3-VL 官方提供的 qwen-vl-utils 库进行视频解码和帧采样，
确保与模型推理时的预处理逻辑完全一致。

安装：pip install qwen-vl-utils
依赖：torch, torchvision, av, pillow
详见：https://github.com/QwenLM/Qwen3-VL/tree/main/qwen-vl-utils
"""

import io
import logging
import tempfile
import os
from typing import Dict, Generator, List, Optional

from PIL import Image

from .base import BaseDecoder

logger = logging.getLogger(__name__)


class QwenVLDecoder(BaseDecoder):
    """基于 qwen-vl-utils 的视频解码器

    直接使用 Qwen3-VL 官方的视频处理逻辑（smart_nframes + smart_resize），
    确保帧采样数量、帧索引位置、resize 方式与模型推理时完全一致。

    优势：
    - 帧采样逻辑与 Qwen3-VL 模型完全一致（包括 FRAME_FACTOR 对齐、min/max frames 约束）
    - resize 使用 BICUBIC 插值 + torchvision，与模型内部预处理一致
    - 支持 decord/torchvision/torchcodec 多种视频解码后端（由 qwen-vl-utils 自动选择）

    注意：
    - 需要安装 torch 和 torchvision（GPU 环境通常已有）
    - qwen-vl-utils 的 smart_resize 参数体系与 BaseDecoder 的 shortest_edge/longest_edge 不同，
      这里做了适配转换
    """

    def __init__(
        self,
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
        min_frames: int = 4,
        video_reader_backend: Optional[str] = None,
    ):
        """初始化 QwenVL 解码器

        Args:
            fps: 抽帧频率（帧/秒），传递给 qwen-vl-utils 的 smart_nframes
            max_frames: 最大帧数，-1 表示使用 qwen-vl-utils 默认值（768）
            image_format: 输出图片格式，JPEG 或 PNG
            image_quality: 图片压缩质量（仅 JPEG 有效），范围 1-100
            size: 分辨率缩放配置，包含 shortest_edge 和 longest_edge，
                  将转换为 qwen-vl-utils 的 min_pixels 和 max_pixels
            min_frames: 最小帧数，传递给 qwen-vl-utils（默认 4）
            video_reader_backend: 视频读取后端，可选 "decord" / "torchvision" / "torchcodec"，
                                  为 None 时由 qwen-vl-utils 自动选择
        """
        super().__init__(fps, max_frames, image_format, image_quality, size)
        self._min_frames = min_frames
        self._video_reader_backend = video_reader_backend
        self._check_available()

    @staticmethod
    def _check_available():
        """检查 qwen-vl-utils 库是否可用"""
        try:
            from qwen_vl_utils.vision_process import fetch_video  # noqa: F401
        except ImportError:
            raise ImportError(
                "使用 qwenvl 解码方式需要安装 qwen-vl-utils 库：\n"
                "  pip install qwen-vl-utils\n"
                "依赖 torch 和 torchvision，请确保已安装。\n"
                "详见：https://github.com/QwenLM/Qwen3-VL/tree/main/qwen-vl-utils"
            )

    def decode(self, video_bytes: bytes) -> List[str]:
        """使用 qwen-vl-utils 解码视频为帧图片的 base64 列表"""
        return self._decode_frames(video_bytes, as_bytes=False)

    def decode_to_bytes(self, video_bytes: bytes) -> List[bytes]:
        """使用 qwen-vl-utils 解码视频为帧图片的原始字节列表"""
        return self._decode_frames(video_bytes, as_bytes=True)

    def _build_fetch_video_ele(self, video_path: str) -> dict:
        """构建 qwen-vl-utils fetch_video 所需的配置字典

        Args:
            video_path: 视频文件路径

        Returns:
            dict: fetch_video 所需的配置字典
        """
        ele = {"video": video_path, "type": "video"}

        # fps 配置
        if self._fps > 0:
            ele["fps"] = self._fps

        # 帧数约束
        if self._min_frames > 0:
            ele["min_frames"] = self._min_frames
        if self._max_frames > 0:
            ele["max_frames"] = self._max_frames

        # 分辨率配置：将 shortest_edge/longest_edge 转换为 min_pixels/max_pixels
        # qwen-vl-utils 中 min_pixels/max_pixels 对应的就是像素总数
        if self._shortest_edge > 0:
            ele["min_pixels"] = self._shortest_edge
        if self._longest_edge > 0:
            ele["max_pixels"] = self._longest_edge

        return ele

    def _decode_frames(self, video_bytes: bytes, as_bytes: bool = False) -> list:
        """使用 qwen-vl-utils 解码视频帧

        工作流程：
        1. 将视频字节写入临时文件（qwen-vl-utils 需要文件路径）
        2. 调用 fetch_video 进行解码和帧采样
        3. 将 torch.Tensor 转换为 PIL Image
        4. 编码为 base64 或原始字节

        Args:
            video_bytes: 视频原始字节数据
            as_bytes: 是否返回原始字节（True）或 base64 字符串（False）

        Returns:
            list: 帧图片列表
        """
        import torch
        from qwen_vl_utils.vision_process import fetch_video

        # 设置视频读取后端（如果指定了）
        if self._video_reader_backend:
            os.environ["FORCE_QWENVL_VIDEO_READER"] = self._video_reader_backend

        # qwen-vl-utils 需要文件路径，将视频字节写入临时文件
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(
                suffix=".mp4", delete=False
            )
            tmp_file.write(video_bytes)
            tmp_file.flush()
            tmp_file.close()

            # 构建配置并调用 fetch_video
            ele = self._build_fetch_video_ele(tmp_file.name)

            logger.debug(
                f"qwen-vl-utils 解码配置: fps={ele.get('fps', 'default')}, "
                f"min_frames={ele.get('min_frames', 'default')}, "
                f"max_frames={ele.get('max_frames', 'default')}, "
                f"min_pixels={ele.get('min_pixels', 'default')}, "
                f"max_pixels={ele.get('max_pixels', 'default')}"
            )

            # fetch_video 返回 (video_tensor, sample_fps)
            # video_tensor shape: (T, C, H, W), float32, 范围 [0, 255]
            video_tensor, sample_fps = fetch_video(
                ele,
                return_video_sample_fps=True,
            )

            total_frames = video_tensor.shape[0]
            logger.debug(
                f"qwen-vl-utils 解码完成: frames={total_frames}, "
                f"shape={video_tensor.shape}, sample_fps={sample_fps:.2f}"
            )

            # 将 torch.Tensor 转换为帧图片列表
            frames = []
            for i in range(total_frames):
                # video_tensor[i] shape: (C, H, W), float32
                frame_tensor = video_tensor[i]

                # 转换为 PIL Image: (C, H, W) -> (H, W, C), uint8
                frame_np = frame_tensor.permute(1, 2, 0).clamp(0, 255).byte().numpy()
                img = Image.fromarray(frame_np, mode="RGB")

                # 注意：qwen-vl-utils 已经做过 smart_resize 了，这里不再调用 _resize_frame
                if as_bytes:
                    frames.append(self._image_to_bytes(img))
                else:
                    frames.append(self._image_to_base64(img))

            logger.info(f"qwen-vl-utils 解码完成: frames={len(frames)}")
            return frames

        finally:
            # 清理临时文件
            if tmp_file and os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    def decode_batches(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[str], None, None]:
        """批量迭代解码视频帧（base64 输出）

        qwen-vl-utils 不支持流式解码，使用默认的全量分批实现。

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数

        Yields:
            List[str]: 每批帧图片的 base64 字符串列表
        """
        all_frames = self.decode(video_bytes)
        for i in range(0, len(all_frames), batch_size):
            yield all_frames[i : i + batch_size]

    def decode_batches_to_bytes(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[bytes], None, None]:
        """批量迭代解码视频帧（原始字节输出）"""
        all_frames = self.decode_to_bytes(video_bytes)
        for i in range(0, len(all_frames), batch_size):
            yield all_frames[i : i + batch_size]

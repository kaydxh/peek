# -*- coding: utf-8 -*-
"""VideoDecoder - 视频解码器（门面类）

保持对外接口的向后兼容性，内部委托给 decoder/ 子包的具体实现。

支持多种解码方式将视频解码为图片帧：
- vllm: 不做预解码，直接将视频传给 vLLM（默认）
- decord: 使用 decord 库解码（推荐，性能最好）
- opencv: 使用 OpenCV 解码
- ffmpeg: 使用 PyAV/FFmpeg 解码（功能最完整，支持 GPU/滤镜/Seek）
- qwenvl: 使用 qwen-vl-utils 解码（与 Qwen3-VL 模型预处理逻辑完全一致）
"""

import base64
import io
import logging
from enum import Enum
from typing import Dict, List, Optional

from .decoder import BaseDecoder, DecoderFactory

logger = logging.getLogger(__name__)


class VideoDecodeMethod(str, Enum):
    """视频解码方式枚举"""
    VLLM = "vllm"        # 不预解码，直接传视频给 vLLM
    DECORD = "decord"    # 使用 decord 库解码
    OPENCV = "opencv"    # 使用 OpenCV 解码
    FFMPEG = "ffmpeg"    # 使用 PyAV/FFmpeg 解码
    QWENVL = "qwenvl"   # 使用 qwen-vl-utils 解码（与 Qwen3-VL 预处理完全一致）


class VideoDecoder:
    """视频解码器（门面类）

    根据配置选择解码方式，将 base64 视频解码为多帧图片的 base64 列表。
    当解码方式为 vllm 时，不做预解码，返回 None 表示由 vLLM 自行解码。

    内部委托给 decoder/ 子包的具体解码器实现（DecordDecoder / OpenCVDecoder），
    本类仅负责 vllm 模式判断和 base64 编解码的统一封装。
    """

    def __init__(
        self,
        method: str = "vllm",
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
        **kwargs,
    ):
        """初始化视频解码器

        Args:
            method: 解码方式，可选 vllm / decord / opencv / ffmpeg / qwenvl
            fps: 抽帧频率（帧/秒），仅预解码模式有效
            max_frames: 最大帧数，-1 表示不限制
            image_format: 输出图片格式，JPEG 或 PNG
            image_quality: 图片压缩质量（仅 JPEG 有效），范围 1-100
            size: 分辨率缩放配置，包含 shortest_edge 和 longest_edge，
                  用于控制帧图片的像素总数范围（与 Qwen2-VL 的 ViT patch 机制一致），
                  仅 decord / opencv / ffmpeg 模式有效。为 None 时不进行缩放。
                  示例: {"shortest_edge": 196608, "longest_edge": 524288}
            **kwargs: 额外参数，ffmpeg 解码器支持 decode_config / progress_callback / cancel_callback
        """
        self._method = VideoDecodeMethod(method.lower())
        self._fps = fps
        self._max_frames = max_frames
        self._image_format = image_format
        self._image_quality = image_quality
        self._size = size

        # 非 vllm 模式时，通过工厂创建具体解码器
        self._decoder: Optional[BaseDecoder] = None
        if self._method != VideoDecodeMethod.VLLM:
            self._decoder = DecoderFactory.create(
                method=self._method.value,
                fps=fps,
                max_frames=max_frames,
                image_format=image_format,
                image_quality=image_quality,
                size=size,
                **kwargs,
            )

        logger.info(
            f"视频解码器已初始化: method={self._method.value}, "
            f"fps={self._fps}, max_frames={self._max_frames}, "
            f"image_format={self._image_format}, image_quality={self._image_quality}"
        )

    @property
    def method(self) -> VideoDecodeMethod:
        """获取解码方式"""
        return self._method

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
        if self._decoder:
            return self._decoder.shortest_edge
        return 0

    @property
    def longest_edge(self) -> int:
        """获取最长边像素总数上限"""
        if self._decoder:
            return self._decoder.longest_edge
        return 0

    @property
    def is_pre_decode(self) -> bool:
        """是否需要预解码（非 vllm 模式时需要预解码）"""
        return self._method != VideoDecodeMethod.VLLM

    def decode(self, base64_video: str) -> Optional[List[str]]:
        """解码视频为帧图片的 base64 列表

        Args:
            base64_video: base64 编码的视频数据

        Returns:
            - None: 当解码方式为 vllm 时，不预解码
            - List[str]: 帧图片的 base64 字符串列表
        """
        if self._method == VideoDecodeMethod.VLLM:
            logger.debug("解码方式为 vllm，跳过预解码")
            return None

        video_bytes = base64.b64decode(base64_video)
        frames = self._decoder.decode(video_bytes)
        logger.info(f"视频解码完成: method={self._method.value}, frames={len(frames)}")
        return frames

    def decode_to_bytes(self, base64_video: str) -> Optional[List[bytes]]:
        """解码视频为帧图片的原始字节列表

        与 decode() 类似，但返回原始字节而非 base64 字符串，
        适用于不需要 base64 编码的场景，可减少编解码开销。

        Args:
            base64_video: base64 编码的视频数据

        Returns:
            - None: 当解码方式为 vllm 时，不预解码
            - List[bytes]: 帧图片的原始字节列表
        """
        if self._method == VideoDecodeMethod.VLLM:
            return None

        video_bytes = base64.b64decode(base64_video)
        return self._decoder.decode_to_bytes(video_bytes)

    def decode_to_video(
        self,
        base64_video: str,
        target_fps: float = 0.5,
        crf: str = "0",
        preset: str = "ultrafast",
    ) -> Optional[str]:
        """解码视频为帧后重新编码为 mp4 视频的 base64 字符串

        先使用配置的解码器（decord/opencv/ffmpeg）预解码为帧，
        再将帧重新编码为 mp4 视频。适用于需要预解码控制帧采样，
        但最终仍以视频形式传入模型的场景（保持 temporal position embedding）。

        Args:
            base64_video: base64 编码的视频数据
            target_fps: 目标采样 fps，用于计算帧间隔使得重新采样时恰好取到所有帧
            crf: H.264 编码质量参数，"0" 为无损
            preset: H.264 编码速度预设

        Returns:
            - None: 当解码方式为 vllm 时，不预解码
            - str: 重新编码后的 mp4 视频 base64 字符串
        """
        if self._method == VideoDecodeMethod.VLLM:
            logger.debug("解码方式为 vllm，跳过预解码")
            return None

        # 先预解码为帧
        frames_b64 = self.decode(base64_video)
        if not frames_b64:
            return None

        logger.info(
            f"预解码为 {len(frames_b64)} 帧，将重新编码为 mp4 视频"
        )

        # 重新编码为 mp4 视频
        return self.encode_frames_to_video(
            frames_b64=frames_b64,
            target_fps=target_fps,
            crf=crf,
            preset=preset,
        )

    @staticmethod
    def encode_frames_to_video(
        frames_b64: List[str],
        target_fps: float = 0.5,
        crf: str = "0",
        preset: str = "ultrafast",
    ) -> str:
        """将帧图片重新编码为 mp4 视频的 base64 字符串（静态方法，可独立使用）

        使用 PyAV 将帧图片编码为 H.264 mp4 视频。
        通过控制帧的时间戳（PTS），确保下游以 target_fps 重新采样时，
        恰好能取到所有帧。

        原理：
        - 假设输入 N 帧，目标采样 fps 为 F（如 0.5）
        - 需要视频总时长 T 满足 round(T * F) = N，即 T = N / F
        - 每帧间隔 = T / N = 1 / F 秒（如 fps=0.5 时每帧间隔 2 秒）
        - 使用固定帧率编码，通过 PTS 控制帧的时间位置

        Args:
            frames_b64: 帧图片的 base64 字符串列表
            target_fps: 目标采样 fps，用于计算帧间隔
            crf: H.264 编码质量参数，"0" 为无损
            preset: H.264 编码速度预设

        Returns:
            str: mp4 视频的 base64 字符串

        Raises:
            ValueError: 当输入帧列表为空时
            ImportError: 当 PyAV 未安装时
        """
        try:
            import av
        except ImportError:
            raise ImportError(
                "encode_frames_to_video 需要安装 PyAV 库：\n"
                "  pip install av\n"
                "详见：https://pyav.org/"
            )
        from PIL import Image

        # 解码所有帧图片
        images = []
        for frame_b64 in frames_b64:
            img_bytes = base64.b64decode(frame_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(img)

        if not images:
            raise ValueError("没有可编码的帧图片")

        # 计算帧间隔（秒），确保下游以 target_fps 采样时恰好取到所有帧
        # 帧间隔 = 1 / target_fps，如 fps=0.5 时帧间隔为 2 秒
        frame_interval = 1.0 / target_fps if target_fps > 0 else 2.0

        # 使用 PyAV 编码为 mp4 视频
        output_buffer = io.BytesIO()

        # 使用较高的编码帧率（time_base 精度），实际帧间隔通过 PTS 控制
        codec_fps = 30  # 编码器内部帧率（仅影响 time_base 精度）

        container = av.open(output_buffer, mode="w", format="mp4")
        stream = container.add_stream("libx264", rate=codec_fps)
        stream.width = images[0].width
        stream.height = images[0].height
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": crf, "preset": preset}

        for i, img in enumerate(images):
            # 确保所有帧尺寸一致（以第一帧为准）
            if img.size != (stream.width, stream.height):
                img = img.resize((stream.width, stream.height))

            frame = av.VideoFrame.from_image(img)
            frame = frame.reformat(format="yuv420p")

            # 通过 PTS 控制帧的时间位置
            # PTS = 帧索引 * 帧间隔 * time_base_denominator
            frame.pts = int(i * frame_interval * codec_fps)

            for packet in stream.encode(frame):
                container.mux(packet)

        # 刷新编码器
        for packet in stream.encode():
            container.mux(packet)

        container.close()

        video_bytes = output_buffer.getvalue()
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")

        total_duration = len(images) * frame_interval
        logger.info(
            f"帧重新编码为 mp4: frames={len(images)}, "
            f"size={images[0].width}x{images[0].height}, "
            f"frame_interval={frame_interval:.1f}s, "
            f"total_duration={total_duration:.1f}s, "
            f"target_fps={target_fps}, "
            f"video_size={len(video_bytes)} bytes"
        )

        return video_b64
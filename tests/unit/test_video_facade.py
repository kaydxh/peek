# -*- coding: utf-8 -*-
"""VideoDecoder 门面类的单元测试

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_facade.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_facade.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_facade.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_facade.py::TestVideoDecodeMethod -v
    pytest tests/unit/test_video_facade.py::TestVideoDecoderFacadeReal -v --log-cli-level=INFO
"""

from unittest.mock import MagicMock, patch

import pytest

from peek.cv.video.video_decoder import VideoDecoder, VideoDecodeMethod


class TestVideoDecodeMethod:
    """测试解码方式枚举"""

    def test_enum_values(self):
        """测试枚举包含所有解码方式"""
        assert VideoDecodeMethod.VLLM.value == "vllm"
        assert VideoDecodeMethod.DECORD.value == "decord"
        assert VideoDecodeMethod.OPENCV.value == "opencv"
        assert VideoDecodeMethod.FFMPEG.value == "ffmpeg"

    def test_enum_from_string(self):
        """测试从字符串创建枚举"""
        assert VideoDecodeMethod("vllm") == VideoDecodeMethod.VLLM
        assert VideoDecodeMethod("ffmpeg") == VideoDecodeMethod.FFMPEG


class TestVideoDecoder:
    """测试 VideoDecoder 门面类"""

    def test_vllm_mode_default(self):
        """测试 vllm 模式为默认"""
        vd = VideoDecoder()
        assert vd.method == VideoDecodeMethod.VLLM
        assert vd.is_pre_decode is False
        assert vd._decoder is None

    def test_vllm_decode_returns_none(self):
        """vllm 模式 decode 返回 None"""
        vd = VideoDecoder(method="vllm")
        result = vd.decode("dGVzdA==")  # base64("test")
        assert result is None

    def test_vllm_decode_to_bytes_returns_none(self):
        """vllm 模式 decode_to_bytes 返回 None"""
        vd = VideoDecoder(method="vllm")
        result = vd.decode_to_bytes("dGVzdA==")
        assert result is None

    @patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available")
    def test_decord_mode(self, mock_check):
        """测试 decord 模式"""
        vd = VideoDecoder(method="decord", fps=1.0, max_frames=10)
        assert vd.method == VideoDecodeMethod.DECORD
        assert vd.is_pre_decode is True
        assert vd._decoder is not None
        assert vd.fps == 1.0
        assert vd.max_frames == 10

    @patch("peek.cv.video.decoder.opencv_decoder.OpenCVDecoder._check_available")
    def test_opencv_mode(self, mock_check):
        """测试 opencv 模式"""
        vd = VideoDecoder(method="opencv", fps=2.0)
        assert vd.method == VideoDecodeMethod.OPENCV
        assert vd.is_pre_decode is True

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_ffmpeg_mode(self, mock_check):
        """测试 ffmpeg 模式"""
        from peek.cv.video.decoder.ffmpeg_decoder import DecodeConfig
        config = DecodeConfig(start_time=5.0)
        vd = VideoDecoder(method="ffmpeg", fps=0.5, decode_config=config)
        assert vd.method == VideoDecodeMethod.FFMPEG
        assert vd.is_pre_decode is True

    def test_invalid_method(self):
        """测试不支持的解码方式"""
        with pytest.raises(ValueError):
            VideoDecoder(method="invalid")

    def test_properties_vllm_mode(self):
        """测试 vllm 模式的属性"""
        vd = VideoDecoder(method="vllm")
        assert vd.shortest_edge == 0
        assert vd.longest_edge == 0
        assert vd.image_format == "JPEG"
        assert vd.image_quality == 85

    @patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available")
    def test_properties_with_size(self, mock_check):
        """测试带 size 的属性"""
        size = {"shortest_edge": 196608, "longest_edge": 524288}
        vd = VideoDecoder(method="decord", size=size)
        assert vd.shortest_edge == 196608
        assert vd.longest_edge == 524288


        """测试方法名大小写不敏感"""
        vd = VideoDecoder(method="VLLM")
        assert vd.method == VideoDecodeMethod.VLLM

    def test_vllm_decode_to_video_returns_none(self):
        """vllm 模式 decode_to_video 返回 None"""
        vd = VideoDecoder(method="vllm")
        result = vd.decode_to_video("dGVzdA==")
        assert result is None


class TestEncodeFramesToVideo:
    """测试 VideoDecoder.encode_frames_to_video 静态方法"""

    def _make_frame_b64(self, width=100, height=80, color=(255, 0, 0)):
        """创建一个纯色帧图片的 base64 字符串"""
        import base64
        import io
        from PIL import Image
        img = Image.new("RGB", (width, height), color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def test_basic_encode(self):
        """测试基本编码功能"""
        frames = [
            self._make_frame_b64(color=(255, 0, 0)),
            self._make_frame_b64(color=(0, 255, 0)),
            self._make_frame_b64(color=(0, 0, 255)),
            self._make_frame_b64(color=(255, 255, 0)),
        ]
        video_b64 = VideoDecoder.encode_frames_to_video(
            frames_b64=frames,
            target_fps=0.5,
        )
        assert isinstance(video_b64, str)
        assert len(video_b64) > 0

        # 验证是有效的 base64
        import base64
        video_bytes = base64.b64decode(video_b64)
        assert len(video_bytes) > 0

    def test_encode_single_frame(self):
        """测试单帧编码"""
        frames = [self._make_frame_b64()]
        video_b64 = VideoDecoder.encode_frames_to_video(
            frames_b64=frames,
            target_fps=0.5,
        )
        assert isinstance(video_b64, str)
        assert len(video_b64) > 0

    def test_encode_empty_raises(self):
        """测试空帧列表抛出异常"""
        with pytest.raises(ValueError, match="没有可编码的帧图片"):
            VideoDecoder.encode_frames_to_video(frames_b64=[])

    def test_encode_with_custom_params(self):
        """测试自定义编码参数"""
        frames = [
            self._make_frame_b64(),
            self._make_frame_b64(color=(0, 255, 0)),
        ]
        video_b64 = VideoDecoder.encode_frames_to_video(
            frames_b64=frames,
            target_fps=1.0,
            crf="18",
            preset="medium",
        )
        assert isinstance(video_b64, str)
        assert len(video_b64) > 0

    def test_encode_different_frame_sizes(self):
        """测试不同尺寸帧（应自动 resize 到第一帧尺寸）"""
        frames = [
            self._make_frame_b64(width=100, height=80),
            self._make_frame_b64(width=200, height=160),
        ]
        video_b64 = VideoDecoder.encode_frames_to_video(
            frames_b64=frames,
            target_fps=0.5,
        )
        assert isinstance(video_b64, str)
        assert len(video_b64) > 0

    def test_encoded_video_decodable(self):
        """验证编码后的视频可以被 PyAV 正确解码"""
        import av
        import base64
        import io

        frames = [
            self._make_frame_b64(color=(255, 0, 0)),
            self._make_frame_b64(color=(0, 255, 0)),
            self._make_frame_b64(color=(0, 0, 255)),
            self._make_frame_b64(color=(255, 255, 0)),
        ]
        video_b64 = VideoDecoder.encode_frames_to_video(
            frames_b64=frames,
            target_fps=0.5,
        )

        # 使用 PyAV 解码验证
        video_bytes = base64.b64decode(video_b64)
        container = av.open(io.BytesIO(video_bytes))
        video_stream = None
        for stream in container.streams:
            if stream.type == "video":
                video_stream = stream
                break

        assert video_stream is not None
        assert video_stream.width == 100
        assert video_stream.height == 80

        # 解码帧数应为 4
        decoded_frames = list(container.decode(video_stream))
        assert len(decoded_frames) == 4
        container.close()


# =================== 集成测试（真实视频） ===================

import logging
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from conftest import (
    skip_no_video, skip_no_decord, skip_no_opencv, skip_no_av, integration,
)

logger = logging.getLogger(__name__)


@skip_no_video
@integration
class TestVideoDecoderFacadeReal:
    """使用真实视频测试 VideoDecoder 门面类"""

    @skip_no_decord
    def test_decord_facade(self, video_base64):
        """通过门面类使用 decord 解码"""
        vd = VideoDecoder(method="decord", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        assert len(frames) <= 3
        logger.info(f"门面 decord: {len(frames)} 帧")

    @skip_no_opencv
    def test_opencv_facade(self, video_base64):
        """通过门面类使用 opencv 解码"""
        vd = VideoDecoder(method="opencv", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 opencv: {len(frames)} 帧")

    @skip_no_av
    def test_ffmpeg_facade(self, video_base64):
        """通过门面类使用 ffmpeg 解码"""
        vd = VideoDecoder(method="ffmpeg", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 ffmpeg: {len(frames)} 帧")

    @skip_no_av
    def test_ffmpeg_facade_with_config(self, video_base64):
        """通过门面类使用 ffmpeg + 时间范围配置"""
        from peek.cv.video.decoder.ffmpeg_decoder import DecodeConfig

        config = DecodeConfig(start_time=0.0, duration=2.0)
        vd = VideoDecoder(method="ffmpeg", fps=1.0, max_frames=5, decode_config=config)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 ffmpeg+config: {len(frames)} 帧")

    @skip_no_av
    def test_decode_to_bytes_facade(self, video_base64):
        """门面类 decode_to_bytes"""
        vd = VideoDecoder(method="ffmpeg", fps=0.5, max_frames=2)
        frames = vd.decode_to_bytes(video_base64)

        assert frames is not None
        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)

    @skip_no_av
    def test_decode_to_video_facade(self, video_base64):
        """门面类 decode_to_video：预解码后重新编码为 mp4"""
        vd = VideoDecoder(method="ffmpeg", fps=0.5)
        video_b64 = vd.decode_to_video(video_base64, target_fps=0.5)

        assert video_b64 is not None
        assert isinstance(video_b64, str)
        assert len(video_b64) > 0

        # 验证编码后的视频可以被解码
        import av
        import base64
        import io
        video_bytes = base64.b64decode(video_b64)
        container = av.open(io.BytesIO(video_bytes))
        decoded_frames = list(container.decode(video=0))
        assert len(decoded_frames) > 0
        container.close()
        logger.info(
            f"门面 decode_to_video: 原始视频 -> {len(decoded_frames)} 帧 mp4, "
            f"size={len(video_bytes)} bytes"
        )
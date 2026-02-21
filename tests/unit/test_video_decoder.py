# -*- coding: utf-8 -*-
"""视频解码器（decoder 子包）的单元测试

测试 BaseDecoder、DecoderFactory、DecordDecoder、OpenCVDecoder、FFmpegDecoder。
保留纯逻辑/数据类/异常路径的 mock 测试，端到端测试使用真实视频文件。

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_decoder.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_decoder.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_decoder.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_decoder.py::TestBaseDecoderProperties -v
    pytest tests/unit/test_video_decoder.py::TestFFmpegDecoderReal -v --log-cli-level=INFO
"""

import base64
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from peek.cv.video.decoder.base import BaseDecoder
from peek.cv.video.decoder.factory import DecoderFactory


# =================== BaseDecoder 测试 ===================


class ConcreteDecoder(BaseDecoder):
    """用于测试的具体解码器实现"""

    def decode(self, video_bytes):
        return []

    def decode_to_bytes(self, video_bytes):
        return []


class TestBaseDecoder:
    """测试 BaseDecoder 抽象基类"""

    def test_default_properties(self):
        """测试默认属性值"""
        decoder = ConcreteDecoder()
        assert decoder.fps == 0.5
        assert decoder.max_frames == -1
        assert decoder.image_format == "JPEG"
        assert decoder.image_quality == 85
        assert decoder.shortest_edge == 0
        assert decoder.longest_edge == 0

    def test_custom_properties(self):
        """测试自定义属性值"""
        size = {"shortest_edge": 100000, "longest_edge": 500000}
        decoder = ConcreteDecoder(
            fps=2.0, max_frames=20, image_format="PNG",
            image_quality=95, size=size,
        )
        assert decoder.fps == 2.0
        assert decoder.max_frames == 20
        assert decoder.image_format == "PNG"
        assert decoder.image_quality == 95
        assert decoder.shortest_edge == 100000
        assert decoder.longest_edge == 500000

    def test_compute_frame_indices_basic(self):
        """测试采样帧索引计算（与 Qwen3-VL 一致的 linspace 均匀采样）"""
        decoder = ConcreteDecoder(fps=1.0)
        # 30fps 视频，目标 1fps
        # duration=10s, nframes=round(10*1.0)=10, align(2)=10
        # linspace(0, 299, 10) = [0, 33, 66, 100, 133, 166, 200, 233, 266, 299]
        indices = decoder._compute_frame_indices(300, 30.0)
        assert len(indices) == 10  # round(10.0 * 1.0) = 10, align(2) = 10
        assert indices[0] == 0
        assert indices[-1] == 299  # linspace 的最后一帧是 total_frames - 1

    def test_compute_frame_indices_max_frames_limit(self):
        """测试采样帧索引的最大帧数限制"""
        decoder = ConcreteDecoder(fps=1.0, max_frames=5)
        indices = decoder._compute_frame_indices(300, 30.0)
        assert len(indices) == 5

    def test_compute_frame_indices_zero_total(self):
        """测试总帧数为 0 时返回空列表"""
        decoder = ConcreteDecoder(fps=1.0)
        indices = decoder._compute_frame_indices(0, 30.0)
        assert indices == []

    def test_compute_frame_indices_zero_fps(self):
        """测试视频帧率为 0 时使用默认 30fps"""
        decoder = ConcreteDecoder(fps=1.0)
        indices = decoder._compute_frame_indices(300, 0)
        # 默认 30fps，采样间隔 30
        assert len(indices) == 10

    def test_compute_frame_indices_fps_zero_all_frames(self):
        """测试 fps=0 时全帧解码（不采样）"""
        decoder = ConcreteDecoder(fps=0)
        indices = decoder._compute_frame_indices(300, 30.0)
        # fps=0 表示全帧解码，采样间隔为 1，解码所有帧
        assert len(indices) == 300
        assert indices[0] == 0
        assert indices[-1] == 299

    def test_compute_frame_indices_fps_negative_all_frames(self):
        """测试 fps 为负数时全帧解码"""
        decoder = ConcreteDecoder(fps=-1)
        indices = decoder._compute_frame_indices(100, 25.0)
        assert len(indices) == 100

    def test_compute_frame_indices_fps_zero_with_max_frames(self):
        """测试 fps=0 全帧解码配合 max_frames 限制"""
        decoder = ConcreteDecoder(fps=0, max_frames=10)
        indices = decoder._compute_frame_indices(300, 30.0)
        # 全帧解码产生 300 帧，但 max_frames=10 限制为 10
        assert len(indices) == 10

    def test_compute_frame_indices_qwen3vl_consistency(self):
        """验证采样逻辑与 Qwen3-VL (Qwen2_5_VLImageProcessor) 完全一致

        Qwen3-VL 的采样公式:
        1. nframes = round(duration * fps)
        2. nframes = max(nframes, FRAME_FACTOR=2)
        3. nframes = ceil(nframes / 2) * 2  (向上对齐到 2 的倍数)
        4. indices = np.linspace(0, total_frames - 1, nframes)
        """
        import math
        import numpy as np

        # 场景1: total=125, fps=24.0, target_fps=0.5
        # duration=125/24=5.208s, nframes=round(5.208*0.5)=round(2.604)=3
        # align(2)=4, linspace(0,124,4)=[0,41,83,124]
        decoder = ConcreteDecoder(fps=0.5)
        indices = decoder._compute_frame_indices(125, 24.0)
        assert len(indices) == 4
        expected = np.linspace(0, 124, 4).astype(int).tolist()
        assert indices == expected  # [0, 41, 83, 124]

        # 场景2: total=503, fps=24.0, target_fps=0.5
        # duration=503/24=20.958s, nframes=round(20.958*0.5)=round(10.479)=10
        # align(2)=10, linspace(0,502,10)
        indices = decoder._compute_frame_indices(503, 24.0)
        assert len(indices) == 10
        expected = np.linspace(0, 502, 10).astype(int).tolist()
        assert indices == expected

        # 场景3: total=997, fps=25.0, target_fps=0.5
        # duration=997/25=39.88s, nframes=round(39.88*0.5)=round(19.94)=20
        # align(2)=20, linspace(0,996,20)
        indices = decoder._compute_frame_indices(997, 25.0)
        assert len(indices) == 20
        expected = np.linspace(0, 996, 20).astype(int).tolist()
        assert indices == expected

        # 场景4: 超短视频 total=10, fps=30.0, target_fps=0.5
        # duration=10/30=0.333s, nframes=round(0.333*0.5)=round(0.167)=0
        # max(0, 2)=2, align(2)=2, linspace(0,9,2)=[0,9]
        indices = decoder._compute_frame_indices(10, 30.0)
        assert len(indices) == 2
        assert indices == [0, 9]

        # 场景5: 奇数帧数对齐 total=300, fps=30.0, target_fps=1.0
        # duration=10s, nframes=round(10*1.0)=10, align(2)=10
        decoder2 = ConcreteDecoder(fps=1.0)
        indices = decoder2._compute_frame_indices(300, 30.0)
        assert len(indices) == 10
        assert indices[0] == 0
        assert indices[-1] == 299

        # 场景6: nframes=3 时向上对齐到 4
        # total=720, fps=24.0, target_fps=0.1
        # duration=30s, nframes=round(30*0.1)=round(3)=3, align(2)=4
        decoder3 = ConcreteDecoder(fps=0.1)
        indices = decoder3._compute_frame_indices(720, 24.0)
        assert len(indices) == 4
        expected = np.linspace(0, 719, 4).astype(int).tolist()
        assert indices == expected

    def test_decode_batches_default_impl(self):
        """测试 BaseDecoder.decode_batches 默认实现（将全量结果分批返回）"""
        class BatchTestDecoder(BaseDecoder):
            def decode(self, video_bytes):
                return [f"frame_{i}" for i in range(10)]
            def decode_to_bytes(self, video_bytes):
                return [f"frame_{i}".encode() for i in range(10)]

        decoder = BatchTestDecoder()
        batches = list(decoder.decode_batches(b"dummy", batch_size=3))
        assert len(batches) == 4  # 10 / 3 = 3 批 + 1 批（余 1）
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 3
        assert len(batches[3]) == 1
        assert batches[0] == ["frame_0", "frame_1", "frame_2"]
        assert batches[3] == ["frame_9"]

    def test_decode_batches_to_bytes_default_impl(self):
        """测试 BaseDecoder.decode_batches_to_bytes 默认实现"""
        class BatchTestDecoder(BaseDecoder):
            def decode(self, video_bytes):
                return []
            def decode_to_bytes(self, video_bytes):
                return [b"frame_0", b"frame_1", b"frame_2", b"frame_3", b"frame_4"]

        decoder = BatchTestDecoder()
        batches = list(decoder.decode_batches_to_bytes(b"dummy", batch_size=2))
        assert len(batches) == 3  # 5 / 2 = 2 批 + 1 批（余 1）
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1

    def test_decode_batches_exact_multiple(self):
        """测试帧数刚好是 batch_size 的整数倍"""
        class BatchTestDecoder(BaseDecoder):
            def decode(self, video_bytes):
                return [f"frame_{i}" for i in range(6)]
            def decode_to_bytes(self, video_bytes):
                return []

        decoder = BatchTestDecoder()
        batches = list(decoder.decode_batches(b"dummy", batch_size=3))
        assert len(batches) == 2
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3

    def test_decode_batches_empty(self):
        """测试空视频批量解码"""
        class BatchTestDecoder(BaseDecoder):
            def decode(self, video_bytes):
                return []
            def decode_to_bytes(self, video_bytes):
                return []

        decoder = BatchTestDecoder()
        batches = list(decoder.decode_batches(b"dummy", batch_size=3))
        assert len(batches) == 0

    def test_image_to_bytes(self):
        """测试图片转字节"""
        decoder = ConcreteDecoder(image_format="JPEG", image_quality=85)
        img = Image.new("RGB", (100, 100), color="red")
        result = decoder._image_to_bytes(img)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_image_to_base64(self):
        """测试图片转 base64"""
        decoder = ConcreteDecoder()
        img = Image.new("RGB", (100, 100), color="blue")
        result = decoder._image_to_base64(img)
        assert isinstance(result, str)
        # 验证 base64 可以正确解码回来
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_image_to_bytes_png(self):
        """测试 PNG 格式输出"""
        decoder = ConcreteDecoder(image_format="PNG")
        img = Image.new("RGB", (50, 50), color="green")
        result = decoder._image_to_bytes(img)
        # PNG 签名
        assert result[:4] == b"\x89PNG"

    def test_resize_frame_no_resize(self):
        """不设置 size 时不缩放"""
        decoder = ConcreteDecoder()
        img = Image.new("RGB", (200, 300))
        result = decoder._resize_frame(img)
        assert result.size == (200, 300)

    def test_cannot_instantiate_abstract(self):
        """不能直接实例化抽象基类"""
        with pytest.raises(TypeError):
            BaseDecoder()


# =================== DecoderFactory 测试 ===================


class TestDecoderFactory:
    """测试视频解码器工厂"""

    @patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available")
    def test_create_decord(self, mock_check):
        """测试创建 decord 解码器"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        decoder = DecoderFactory.create(method="decord", fps=1.0)
        assert isinstance(decoder, DecordDecoder)
        assert decoder.fps == 1.0

    @patch("peek.cv.video.decoder.opencv_decoder.OpenCVDecoder._check_available")
    def test_create_opencv(self, mock_check):
        """测试创建 opencv 解码器"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        decoder = DecoderFactory.create(method="opencv", fps=2.0)
        assert isinstance(decoder, OpenCVDecoder)
        assert decoder.fps == 2.0

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_create_ffmpeg(self, mock_check):
        """测试创建 ffmpeg 解码器"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder
        decoder = DecoderFactory.create(method="ffmpeg", fps=0.5)
        assert isinstance(decoder, FFmpegDecoder)
        assert decoder.fps == 0.5

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_create_ffmpeg_with_config(self, mock_check):
        """测试创建带配置的 ffmpeg 解码器"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(start_time=5.0, end_time=10.0)
        progress = MagicMock()
        decoder = DecoderFactory.create(
            method="ffmpeg", fps=1.0,
            decode_config=config, progress_callback=progress,
        )
        assert isinstance(decoder, FFmpegDecoder)
        assert decoder._config.start_time == 5.0

    def test_create_invalid_method(self):
        """测试不支持的解码方式抛出异常"""
        with pytest.raises(ValueError, match="不支持的解码方式"):
            DecoderFactory.create(method="unknown")

    @patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available")
    def test_create_with_size(self, mock_check):
        """测试创建带 size 配置的解码器"""
        size = {"shortest_edge": 100000, "longest_edge": 500000}
        decoder = DecoderFactory.create(method="decord", size=size)
        assert decoder.shortest_edge == 100000
        assert decoder.longest_edge == 500000

    def test_create_case_insensitive(self):
        """测试方法名大小写不敏感"""
        with patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available"):
            decoder = DecoderFactory.create(method="DECORD")
            assert decoder.fps == 0.5


# =================== DecordDecoder 测试 ===================


class TestDecordDecoder:
    """测试 decord 解码器"""

    @patch("peek.cv.video.decoder.decord_decoder.DecordDecoder._check_available")
    def test_init(self, mock_check):
        """测试初始化"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        decoder = DecordDecoder(fps=1.0, max_frames=10)
        assert decoder.fps == 1.0
        assert decoder.max_frames == 10

    def test_import_error_without_decord(self):
        """缺少 decord 库时抛出 ImportError"""
        with patch.dict("sys.modules", {"decord": None}):
            from peek.cv.video.decoder.decord_decoder import DecordDecoder
            # _check_available 在 __init__ 中调用，会因找不到 decord 而报错
            # 但我们直接测试静态方法
            with patch("builtins.__import__", side_effect=ImportError):
                with pytest.raises(ImportError, match="decord"):
                    DecordDecoder._check_available()




# =================== OpenCVDecoder 测试 ===================


class TestOpenCVDecoder:
    """测试 OpenCV 解码器"""

    @patch("peek.cv.video.decoder.opencv_decoder.OpenCVDecoder._check_available")
    def test_init(self, mock_check):
        """测试初始化"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        decoder = OpenCVDecoder(fps=2.0, max_frames=5, image_format="PNG")
        assert decoder.fps == 2.0
        assert decoder.max_frames == 5
        assert decoder.image_format == "PNG"

    def test_import_error_without_opencv(self):
        """缺少 OpenCV 库时抛出 ImportError"""
        import sys
        # 临时将 cv2 标记为不可用
        with patch.dict(sys.modules, {"cv2": None}):
            from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
            with pytest.raises(ImportError):
                OpenCVDecoder._check_available()


# =================== FFmpegDecoder 测试 ===================


class TestFFmpegDecoder:
    """测试 FFmpeg 解码器"""

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_init_default(self, mock_check):
        """测试默认初始化"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        decoder = FFmpegDecoder()
        assert decoder.fps == 0.5
        assert decoder.max_frames == -1
        assert decoder._config.gpu_id == -1
        assert decoder._config.start_time is None

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_init_with_config(self, mock_check):
        """测试带配置的初始化"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(
            start_time=5.0, end_time=15.0,
            gpu_id=0, video_filter="scale=1280:720",
            thread_count=4, keyframes_only=True,
        )
        decoder = FFmpegDecoder(fps=1.0, decode_config=config)
        assert decoder._config.start_time == 5.0
        assert decoder._config.end_time == 15.0
        assert decoder._config.gpu_id == 0
        assert decoder._config.video_filter == "scale=1280:720"
        assert decoder._config.thread_count == 4
        assert decoder._config.keyframes_only is True

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_init_with_callbacks(self, mock_check):
        """测试带回调的初始化"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder
        progress = MagicMock()
        cancel = MagicMock(return_value=False)
        decoder = FFmpegDecoder(progress_callback=progress, cancel_callback=cancel)
        assert decoder._progress_callback is progress
        assert decoder._cancel_callback is cancel

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_get_effective_total_frames_no_time_range(self, mock_check):
        """测试无时间范围时的有效帧数计算"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder
        decoder = FFmpegDecoder()
        # 无时间范围配置，effective_duration = duration - 0 = 60
        result = decoder._get_effective_total_frames(
            total_frames=1800, video_fps=30.0, duration=60.0
        )
        assert result == 1800  # min(60*30, 1800)

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_get_effective_total_frames_with_time_range(self, mock_check):
        """测试有时间范围时的有效帧数计算"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(start_time=10.0, end_time=20.0)
        decoder = FFmpegDecoder(decode_config=config)
        # effective_duration = min(20, 60) - 10 = 10s
        result = decoder._get_effective_total_frames(
            total_frames=1800, video_fps=30.0, duration=60.0
        )
        assert result == 300  # 10 * 30 = 300

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_get_effective_total_frames_with_duration(self, mock_check):
        """测试使用 duration 配置时的有效帧数计算"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(start_time=5.0, duration=10.0)
        decoder = FFmpegDecoder(decode_config=config)
        # end = start + duration = 15.0
        # effective_duration = min(15, 60) - 5 = 10
        result = decoder._get_effective_total_frames(
            total_frames=1800, video_fps=30.0, duration=60.0
        )
        assert result == 300

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_calculate_end_frame_none(self, mock_check):
        """测试无结束时间时返回 None"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder
        decoder = FFmpegDecoder()
        result = decoder._calculate_end_frame(
            video_fps=30.0, total_frames=1800, duration=60.0
        )
        assert result is None

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_calculate_end_frame_with_end_time(self, mock_check):
        """测试有结束时间时的计算"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(end_time=20.0)
        decoder = FFmpegDecoder(decode_config=config)
        result = decoder._calculate_end_frame(
            video_fps=30.0, total_frames=1800, duration=60.0
        )
        assert result == 600  # 20 * 30

    @patch("peek.cv.video.decoder.ffmpeg_decoder.FFmpegDecoder._check_available")
    def test_calculate_end_frame_with_start_and_duration(self, mock_check):
        """测试 start_time + duration 组合"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig
        config = DecodeConfig(start_time=10.0, duration=5.0)
        decoder = FFmpegDecoder(decode_config=config)
        result = decoder._calculate_end_frame(
            video_fps=30.0, total_frames=1800, duration=60.0
        )
        assert result == 450  # (10 + 5) * 30


class TestDecodeConfig:
    """测试 DecodeConfig 数据类"""

    def test_default_values(self):
        """测试默认值"""
        from peek.cv.video.decoder.ffmpeg_decoder import DecodeConfig
        config = DecodeConfig()
        assert config.start_time is None
        assert config.end_time is None
        assert config.duration is None
        assert config.gpu_id == -1
        assert config.auto_switch_to_soft_codec is True
        assert config.video_filter is None
        assert config.thread_count == 0
        assert config.keyframes_only is False

    def test_custom_values(self):
        """测试自定义值"""
        from peek.cv.video.decoder.ffmpeg_decoder import DecodeConfig
        config = DecodeConfig(
            start_time=1.0, end_time=10.0,
            gpu_id=0, video_filter="scale=640:480",
            thread_count=8, keyframes_only=True,
            auto_switch_to_soft_codec=False,
        )
        assert config.start_time == 1.0
        assert config.end_time == 10.0
        assert config.gpu_id == 0
        assert config.video_filter == "scale=640:480"
        assert config.thread_count == 8
        assert config.keyframes_only is True
        assert config.auto_switch_to_soft_codec is False


# =================== 集成测试（真实视频） ===================

import logging
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from conftest import (
    skip_no_video, skip_no_decord, skip_no_opencv, skip_no_av,
    HAS_DECORD, HAS_OPENCV, HAS_AV, integration,
)

logger = logging.getLogger(__name__)


@skip_no_video
@skip_no_decord
@integration
class TestDecordDecoderReal:
    """使用真实视频测试 DecordDecoder"""

    def test_decode_basic(self, video_bytes):
        """基本解码（base64 输出）"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        decoder = DecordDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        for i, frame_b64 in enumerate(frames):
            img_bytes = base64.b64decode(frame_b64)
            img = Image.open(io.BytesIO(img_bytes))
            assert img.size[0] > 0 and img.size[1] > 0
            logger.info(f"  帧 {i}: {img.size[0]}x{img.size[1]}, {img.mode}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        decoder = DecordDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0

        for frame_bytes in frames:
            assert isinstance(frame_bytes, bytes)
            img = Image.open(io.BytesIO(frame_bytes))
            assert img.size[0] > 0

    def test_decode_with_resize(self, video_bytes):
        """带分辨率缩放的解码"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        size = {"shortest_edge": 50000, "longest_edge": 200000}
        decoder = DecordDecoder(fps=0.5, max_frames=2, size=size)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for frame_bytes in frames:
            img = Image.open(io.BytesIO(frame_bytes))
            pixels = img.size[0] * img.size[1]
            logger.info(f"  缩放后: {img.size[0]}x{img.size[1]}, pixels={pixels}")
            assert pixels <= 200000 + 28 * 28 * 4


@skip_no_video
@skip_no_opencv
@integration
class TestOpenCVDecoderReal:
    """使用真实视频测试 OpenCVDecoder"""

    def test_decode_basic(self, video_bytes):
        """基本解码"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder

        decoder = OpenCVDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        img_bytes = base64.b64decode(frames[0])
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0
        logger.info(f"opencv 解码: {len(frames)} 帧, 第一帧 {img.size[0]}x{img.size[1]}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder

        decoder = OpenCVDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)


@skip_no_video
@skip_no_av
@integration
class TestFFmpegDecoderReal:
    """使用真实视频测试 FFmpegDecoder"""

    def test_decode_basic(self, video_bytes):
        """基本解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        img_bytes = base64.b64decode(frames[0])
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0
        logger.info(f"ffmpeg 解码: {len(frames)} 帧, 第一帧 {img.size[0]}x{img.size[1]}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)

    def test_decode_with_time_range(self, video_bytes):
        """指定时间范围解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(start_time=1.0, duration=3.0)
        decoder = FFmpegDecoder(fps=1.0, max_frames=10, decode_config=config)
        frames = decoder.decode(video_bytes)

        assert len(frames) > 0
        logger.info(f"时间范围解码: {len(frames)} 帧 (1.0s ~ 4.0s)")

    def test_decode_with_filter(self, video_bytes):
        """带视频滤镜的解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(video_filter="scale=320:240")
        decoder = FFmpegDecoder(fps=0.5, max_frames=2, decode_config=config)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        img = Image.open(io.BytesIO(frames[0]))
        assert img.size == (320, 240), f"滤镜缩放后尺寸应为 320x240，实际: {img.size}"

    def test_decode_keyframes_only(self, video_bytes):
        """仅解码关键帧"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(keyframes_only=True)
        decoder = FFmpegDecoder(fps=0.5, max_frames=5, decode_config=config)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        logger.info(f"关键帧解码: {len(frames)} 帧")

    def test_get_video_info(self, video_bytes):
        """获取视频元信息"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder()
        info = decoder.get_video_info(video_bytes)

        assert info["duration"] > 0
        assert info["width"] > 0
        assert info["height"] > 0
        assert info["frame_rate"] > 0
        assert info["codec"] != ""

        logger.info(
            f"视频信息: {info['width']}x{info['height']}, "
            f"fps={info['frame_rate']:.2f}, duration={info['duration']:.2f}s, "
            f"codec={info['codec']}"
        )

    def test_decode_specific_frames(self, video_bytes):
        """解码指定帧号"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder()
        frames = decoder.decode_specific_frames(
            video_bytes, frame_numbers=[0, 10, 30]
        )

        assert len(frames) == 3
        for i, fb64 in enumerate(frames):
            img_bytes = base64.b64decode(fb64)
            img = Image.open(io.BytesIO(img_bytes))
            logger.info(f"  帧 [{[0, 10, 30][i]}]: {img.size[0]}x{img.size[1]}")

    def test_decode_with_progress(self, video_bytes):
        """带进度回调的解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        progress_values = []

        def on_progress(p):
            progress_values.append(p)

        decoder = FFmpegDecoder(
            fps=0.5, max_frames=3,
            progress_callback=on_progress,
        )
        frames = decoder.decode(video_bytes)

        assert len(frames) > 0
        assert progress_values[-1] == 1.0
        logger.info(f"进度回调次数: {len(progress_values)}")

    def test_decode_with_cancel(self, video_bytes):
        """取消解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        call_count = [0]

        def cancel_after_1():
            call_count[0] += 1
            return call_count[0] > 1

        decoder = FFmpegDecoder(
            fps=30.0, max_frames=-1,
            cancel_callback=cancel_after_1,
        )
        frames = decoder.decode(video_bytes)

        logger.info(f"取消解码: 解码了 {len(frames)} 帧后取消")

    def test_decode_all_frames_fps_zero(self, video_bytes):
        """fps=0 全帧解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0, max_frames=-1)
        info = decoder.get_video_info(video_bytes)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        # fps=0 应解码所有帧，帧数应接近视频总帧数
        assert len(frames) > 0
        logger.info(
            f"全帧解码 (fps=0): 解码 {len(frames)} 帧, "
            f"视频总帧数={info['total_frames']}"
        )

    def test_decode_batches_basic(self, video_bytes):
        """批量读帧基本测试"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=1.0, max_frames=10)
        all_frames_from_batches = []
        batch_count = 0

        for batch in decoder.decode_batches(video_bytes, batch_size=3):
            assert isinstance(batch, list)
            assert len(batch) <= 3
            all_frames_from_batches.extend(batch)
            batch_count += 1
            logger.info(f"  batch {batch_count}: {len(batch)} 帧")

        # 批量解码的总帧数应与一次性解码一致
        decoder2 = FFmpegDecoder(fps=1.0, max_frames=10)
        all_frames = decoder2.decode(video_bytes)

        assert len(all_frames_from_batches) == len(all_frames)
        # 帧内容也应一致
        for i, (a, b) in enumerate(zip(all_frames_from_batches, all_frames)):
            assert a == b, f"帧 {i} 内容不一致"
        logger.info(
            f"批量读帧基本测试: {batch_count} 批, 总计 {len(all_frames_from_batches)} 帧"
        )

    def test_decode_batches_to_bytes(self, video_bytes):
        """批量读帧字节输出"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=5)
        all_bytes = []

        for batch in decoder.decode_batches_to_bytes(video_bytes, batch_size=2):
            for fb in batch:
                assert isinstance(fb, bytes)
            all_bytes.extend(batch)

        assert len(all_bytes) > 0
        # 验证每帧都是有效图片
        for fb in all_bytes:
            img = Image.open(io.BytesIO(fb))
            assert img.size[0] > 0
        logger.info(f"批量读帧字节输出: {len(all_bytes)} 帧")

    def test_decode_batches_all_frames(self, video_bytes):
        """批量读帧 + fps=0 全帧解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0, max_frames=-1)
        info = decoder.get_video_info(video_bytes)

        total = 0
        batch_count = 0
        for batch in decoder.decode_batches(video_bytes, batch_size=100):
            total += len(batch)
            batch_count += 1

        assert total > 0
        logger.info(
            f"批量全帧解码: {batch_count} 批, 总计 {total} 帧, "
            f"视频总帧数={info['total_frames']}"
        )

    def test_decode_batches_with_time_range(self, video_bytes):
        """批量读帧 + 时间范围"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(start_time=1.0, duration=3.0)
        decoder = FFmpegDecoder(fps=1.0, max_frames=10, decode_config=config)

        all_frames = []
        for batch in decoder.decode_batches(video_bytes, batch_size=2):
            all_frames.extend(batch)

        assert len(all_frames) > 0
        logger.info(f"批量读帧+时间范围: {len(all_frames)} 帧 (1.0s ~ 4.0s)")

    def test_decode_batches_with_cancel(self, video_bytes):
        """批量读帧 + 取消机制"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        call_count = [0]

        def cancel_after_1():
            call_count[0] += 1
            return call_count[0] > 1

        decoder = FFmpegDecoder(
            fps=30.0, max_frames=-1,
            cancel_callback=cancel_after_1,
        )

        all_frames = []
        for batch in decoder.decode_batches(video_bytes, batch_size=5):
            all_frames.extend(batch)

        logger.info(f"批量读帧+取消: 解码了 {len(all_frames)} 帧后取消")


@skip_no_video
@pytest.mark.skipif(
    not (HAS_DECORD and HAS_OPENCV and HAS_AV),
    reason="需要同时安装 decord + opencv + av 才能进行一致性对比",
)
@integration
class TestDecoderConsistency:
    """对比三种解码器的输出一致性"""

    def test_frame_count_consistency(self, video_bytes):
        """三种解码器的帧数应一致"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        fps, max_frames = 0.5, 5

        decord_frames = DecordDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)
        opencv_frames = OpenCVDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)
        ffmpeg_frames = FFmpegDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)

        logger.info(
            f"帧数对比: decord={len(decord_frames)}, "
            f"opencv={len(opencv_frames)}, ffmpeg={len(ffmpeg_frames)}"
        )

        assert abs(len(decord_frames) - len(opencv_frames)) <= 1
        assert abs(len(decord_frames) - len(ffmpeg_frames)) <= 1

    def test_frame_size_consistency(self, video_bytes):
        """三种解码器输出帧的分辨率应一致"""
        import io as _io
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        fps, max_frames = 0.5, 1

        decord_frames = DecordDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)
        opencv_frames = OpenCVDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)
        ffmpeg_frames = FFmpegDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)

        decord_img = Image.open(_io.BytesIO(decord_frames[0]))
        opencv_img = Image.open(_io.BytesIO(opencv_frames[0]))
        ffmpeg_img = Image.open(_io.BytesIO(ffmpeg_frames[0]))

        logger.info(
            f"分辨率对比: decord={decord_img.size}, "
            f"opencv={opencv_img.size}, ffmpeg={ffmpeg_img.size}"
        )

        assert decord_img.size == opencv_img.size
        assert decord_img.size == ffmpeg_img.size
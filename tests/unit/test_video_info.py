# -*- coding: utf-8 -*-
"""视频信息探测（info）模块的单元测试

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_info.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_info.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_info.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_info.py::TestSafeFloat -v
    pytest tests/unit/test_video_info.py::TestVideoInfoReal -v --log-cli-level=INFO
"""

import pytest

from peek.cv.video.info import (
    VideoInfo,
    StreamInfo,
    probe,
    _safe_float,
    _safe_int,
    _parse_rational,
    _parse_ffprobe_data,
    _parse_stream,
)


# =================== 工具函数测试 ===================


class TestSafeFloat:
    """测试安全 float 转换"""

    def test_valid_float(self):
        assert _safe_float(3.14) == 3.14

    def test_valid_string(self):
        assert _safe_float("2.5") == 2.5

    def test_valid_int(self):
        assert _safe_float(10) == 10.0

    def test_invalid_string(self):
        assert _safe_float("abc") == 0.0

    def test_none(self):
        assert _safe_float(None) == 0.0


class TestSafeInt:
    """测试安全 int 转换"""

    def test_valid_int(self):
        assert _safe_int(42) == 42

    def test_valid_string(self):
        assert _safe_int("100") == 100

    def test_invalid_string(self):
        assert _safe_int("abc") == 0

    def test_none(self):
        assert _safe_int(None) == 0


class TestParseRational:
    """测试有理数解析"""

    def test_standard_fraction(self):
        assert _parse_rational("30/1") == 30.0

    def test_non_trivial_fraction(self):
        result = _parse_rational("30000/1001")
        assert abs(result - 29.97) < 0.01

    def test_zero_denominator(self):
        assert _parse_rational("30/0") == 0.0

    def test_plain_number(self):
        assert _parse_rational("25") == 25.0

    def test_invalid_string(self):
        assert _parse_rational("abc") == 0.0

    def test_empty_string(self):
        assert _parse_rational("") == 0.0


# =================== StreamInfo / VideoInfo 数据类测试 ===================


class TestStreamInfo:
    """测试 StreamInfo 数据类"""

    def test_default_values(self):
        stream = StreamInfo()
        assert stream.index == 0
        assert stream.codec_type == ""
        assert stream.width == 0
        assert stream.fps == 0.0

    def test_custom_values(self):
        stream = StreamInfo(
            index=1, codec_type="video", codec_name="h264",
            width=1920, height=1080, fps=30.0,
        )
        assert stream.codec_type == "video"
        assert stream.width == 1920


class TestVideoInfo:
    """测试 VideoInfo 数据类"""

    def test_default_values(self):
        info = VideoInfo()
        assert info.duration == 0.0
        assert info.width == 0
        assert info.resolution == ""
        assert info.has_video is False
        assert info.has_audio is False

    def test_resolution_property(self):
        info = VideoInfo(width=1920, height=1080)
        assert info.resolution == "1920x1080"

    def test_aspect_ratio_property(self):
        info = VideoInfo(width=1920, height=1080)
        assert abs(info.aspect_ratio - 16 / 9) < 0.01

    def test_aspect_ratio_zero_height(self):
        info = VideoInfo(width=100, height=0)
        assert info.aspect_ratio == 0.0

    def test_total_pixels(self):
        info = VideoInfo(width=1920, height=1080)
        assert info.total_pixels == 1920 * 1080

    def test_has_video(self):
        info = VideoInfo(
            streams=[StreamInfo(codec_type="video"), StreamInfo(codec_type="audio")]
        )
        assert info.has_video is True
        assert info.has_audio is True

    def test_str_output(self):
        info = VideoInfo(
            filename="test.mp4", duration=60.0,
            width=1920, height=1080, fps=30.0,
            video_codec="h264", format_name="mp4",
        )
        output = str(info)
        assert "test.mp4" in output
        assert "60.00s" in output
        assert "1920x1080" in output
        assert "h264" in output


# =================== probe 函数测试 ===================


class TestParseStream:
    """测试流解析"""

    def test_parse_video_stream(self):
        data = {
            "index": 0,
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "pix_fmt": "yuv420p",
            "r_frame_rate": "30/1",
            "nb_frames": "900",
            "duration": "30.0",
        }
        stream = _parse_stream(data)
        assert stream.codec_type == "video"
        assert stream.codec_name == "h264"
        assert stream.width == 1920
        assert stream.height == 1080
        assert stream.fps == 30.0
        assert stream.nb_frames == 900

    def test_parse_audio_stream(self):
        data = {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "aac",
            "sample_rate": "44100",
            "channels": 2,
            "channel_layout": "stereo",
            "r_frame_rate": "0/0",
        }
        stream = _parse_stream(data)
        assert stream.codec_type == "audio"
        assert stream.sample_rate == 44100
        assert stream.channels == 2


class TestParseFfprobeData:
    """测试 ffprobe 数据解析"""

    def test_full_parse(self):
        data = {
            "format": {
                "filename": "test.mp4",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "format_long_name": "QuickTime / MOV",
                "duration": "60.0",
                "size": "1048576",
                "bit_rate": "139810",
                "nb_streams": "2",
            },
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "r_frame_rate": "30/1",
                    "nb_frames": "1800",
                    "duration": "60.0",
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "44100",
                    "channels": 2,
                    "channel_layout": "stereo",
                    "r_frame_rate": "0/0",
                },
            ],
        }
        info = _parse_ffprobe_data(data, "test.mp4")
        assert info.filename == "test.mp4"
        assert info.duration == 60.0
        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == 30.0
        assert info.total_frames == 1800
        assert info.video_codec == "h264"
        assert info.audio_codec == "aac"
        assert info.sample_rate == 44100
        assert len(info.streams) == 2

    def test_parse_no_streams(self):
        data = {"format": {"duration": "10.0"}, "streams": []}
        info = _parse_ffprobe_data(data, "empty.mp4")
        assert info.width == 0
        assert info.has_video is False

    def test_estimate_frames_from_duration(self):
        """nb_frames 为 0 时通过时长和帧率估算"""
        data = {
            "format": {"duration": "10.0"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 480,
                    "r_frame_rate": "25/1",
                    "nb_frames": "0",
                },
            ],
        }
        info = _parse_ffprobe_data(data, "test.mp4")
        assert info.total_frames == 250  # 10 * 25


class TestProbe:
    """测试 probe 入口函数"""

    def test_invalid_backend(self):
        """不支持的后端抛出异常"""
        with pytest.raises(ValueError, match="不支持的探测后端"):
            probe("dummy.mp4", backend="invalid")


# =================== 集成测试（真实视频） ===================

import logging
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from conftest import (
    skip_no_video, skip_no_ffprobe, skip_no_opencv,
    HAS_FFPROBE_CLI, HAS_OPENCV, integration,
)

logger = logging.getLogger(__name__)


@skip_no_video
@integration
class TestVideoInfoReal:
    """使用真实视频测试 info.probe"""

    @skip_no_ffprobe
    def test_probe_ffprobe(self, video_path):
        """ffprobe 后端探测视频信息"""
        info = probe(video_path, backend="ffprobe")

        assert info.duration > 0, "视频时长应大于 0"
        assert info.width > 0, "视频宽度应大于 0"
        assert info.height > 0, "视频高度应大于 0"
        assert info.fps > 0, "帧率应大于 0"
        assert info.total_frames > 0, "总帧数应大于 0"
        assert info.has_video, "应包含视频流"
        assert info.video_codec != "", "视频编码不应为空"
        assert info.format_name != "", "容器格式不应为空"
        assert "x" in info.resolution

        logger.info(f"\n{info}")

    @skip_no_opencv
    def test_probe_opencv(self, video_path):
        """opencv 后端探测视频信息"""
        info = probe(video_path, backend="opencv")

        assert info.duration > 0
        assert info.width > 0
        assert info.height > 0
        assert info.fps > 0
        assert info.total_frames > 0

        logger.info(
            f"opencv 探测: {info.resolution}, "
            f"fps={info.fps:.2f}, duration={info.duration:.2f}s, "
            f"frames={info.total_frames}"
        )

    @pytest.mark.skipif(
        not (HAS_FFPROBE_CLI and HAS_OPENCV),
        reason="需要 ffprobe + opencv",
    )
    def test_probe_consistency(self, video_path):
        """两种后端的探测结果应基本一致"""
        info_ffprobe = probe(video_path, backend="ffprobe")
        info_opencv = probe(video_path, backend="opencv")

        assert info_ffprobe.width == info_opencv.width
        assert info_ffprobe.height == info_opencv.height
        assert abs(info_ffprobe.fps - info_opencv.fps) < 0.5
        assert abs(info_ffprobe.duration - info_opencv.duration) < 1.0
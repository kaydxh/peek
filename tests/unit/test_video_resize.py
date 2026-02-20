# -*- coding: utf-8 -*-
"""视频解码器基类和通用工具的单元测试

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_resize.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_resize.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_resize.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_resize.py::TestSmartResize -v
"""

import base64
import io
import math

import pytest
from PIL import Image

from peek.cv.video.resize import smart_resize, smart_resize_image


# =================== smart_resize 测试 ===================


class TestSmartResize:
    """测试智能缩放尺寸计算"""

    def test_no_change_within_bounds(self):
        """像素总数在范围内时不缩放"""
        w, h = smart_resize(100, 100, min_pixels=5000, max_pixels=20000, patch_size=28)
        assert w > 0 and h > 0

    def test_scale_down_when_exceeds_max(self):
        """像素总数超过上限时缩小"""
        w, h = smart_resize(1920, 1080, min_pixels=0, max_pixels=100000, patch_size=28)
        assert w * h <= 100000 + 28 * 28  # 允许 patch 对齐带来的少量误差

    def test_scale_up_when_below_min(self):
        """像素总数低于下限时放大"""
        w, h = smart_resize(100, 100, min_pixels=50000, max_pixels=0, patch_size=28)
        assert w * h >= 50000 - 28 * 28  # 允许 patch 对齐带来的少量误差

    def test_align_to_patch_size(self):
        """结果对齐到 patch_size 的倍数"""
        w, h = smart_resize(123, 456, min_pixels=0, max_pixels=0, patch_size=28)
        assert w % 28 == 0
        assert h % 28 == 0

    def test_zero_dimensions(self):
        """零尺寸输入不崩溃"""
        w, h = smart_resize(0, 0, min_pixels=100, max_pixels=1000, patch_size=28)
        assert w == 0 and h == 0

    def test_negative_dimensions(self):
        """负尺寸输入不崩溃"""
        w, h = smart_resize(-1, -1, min_pixels=100, max_pixels=1000, patch_size=28)
        assert w == -1 and h == -1

    def test_no_limits(self):
        """不设置上下限时只做 patch 对齐"""
        w, h = smart_resize(200, 300, min_pixels=0, max_pixels=0, patch_size=28)
        assert w % 28 == 0
        assert h % 28 == 0

    def test_min_equals_max(self):
        """上下限相等时的边界情况"""
        w, h = smart_resize(100, 100, min_pixels=10000, max_pixels=10000, patch_size=28)
        assert w > 0 and h > 0
        assert w % 28 == 0
        assert h % 28 == 0


class TestSmartResizeImage:
    """测试图片智能缩放"""

    def test_no_resize_when_no_limits(self):
        """不设置限制时返回原图"""
        img = Image.new("RGB", (200, 300))
        result = smart_resize_image(img, shortest_edge=0, longest_edge=0)
        assert result.size == (200, 300)

    def test_resize_when_exceeds_limit(self):
        """超过上限时缩小"""
        img = Image.new("RGB", (1920, 1080))
        result = smart_resize_image(img, shortest_edge=0, longest_edge=100000)
        assert result.size[0] * result.size[1] <= 100000 + 28 * 28

    def test_resize_when_below_limit(self):
        """低于下限时放大"""
        img = Image.new("RGB", (50, 50))
        result = smart_resize_image(img, shortest_edge=50000, longest_edge=0)
        assert result.size[0] * result.size[1] >= 50000 - 28 * 28

    def test_returns_pil_image(self):
        """始终返回 PIL Image"""
        img = Image.new("RGB", (100, 100))
        result = smart_resize_image(img, shortest_edge=0, longest_edge=50000)
        assert isinstance(result, Image.Image)


# =================== 集成测试（真实视频帧） ===================

import logging
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from conftest import skip_no_video, skip_no_av, integration

logger = logging.getLogger(__name__)


@skip_no_video
@skip_no_av
@integration
class TestSmartResizeWithRealFrames:
    """使用真实视频帧测试 smart_resize"""

    def test_resize_decoded_frame(self, video_bytes):
        """对真实解码帧应用 smart_resize"""
        import io as _io
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=1)
        frames = decoder.decode_to_bytes(video_bytes)
        assert len(frames) > 0

        img = Image.open(_io.BytesIO(frames[0]))
        orig_w, orig_h = img.size
        logger.info(f"原始帧: {orig_w}x{orig_h}, pixels={orig_w * orig_h}")

        resized = smart_resize_image(img, shortest_edge=0, longest_edge=100000)
        new_w, new_h = resized.size
        logger.info(f"缩放后: {new_w}x{new_h}, pixels={new_w * new_h}")

        assert new_w * new_h <= 100000 + 28 * 28 * 4
        assert new_w % 28 == 0
        assert new_h % 28 == 0
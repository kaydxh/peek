# -*- coding: utf-8 -*-
"""视频滤镜（filter 子包）的单元测试

测试 ScaleFilter、CropFilter、TransformFilter、VideoFilter。

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_filter.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_filter.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_filter.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_filter.py::TestScaleFilterBuild -v
    pytest tests/unit/test_video_filter.py::TestVideoFilterReal -v --log-cli-level=INFO
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from peek.cv.video.filter.scale import ScaleFilter, ScaleConfig
from peek.cv.video.filter.crop import CropFilter, CropConfig
from peek.cv.video.filter.transform import TransformFilter, TransformConfig
from peek.cv.video.filter.video_filter import VideoFilter


# =================== ScaleFilter 测试 ===================


class TestScaleFilterBuild:
    """测试 ScaleFilter.build_filter"""

    def test_basic_scale(self):
        """基本缩放"""
        result = ScaleFilter.build_filter(width=1280, height=720)
        assert "scale=1280:720" in result

    def test_keep_aspect_width(self):
        """保持宽高比（指定宽度）"""
        result = ScaleFilter.build_filter(width=1280, height=-1)
        assert "scale=1280:-1" in result

    def test_keep_aspect_even(self):
        """保持宽高比且为偶数"""
        result = ScaleFilter.build_filter(width=1280, height=-2)
        assert "scale=1280:-2" in result

    def test_algorithm(self):
        """指定缩放算法"""
        result = ScaleFilter.build_filter(width=640, height=480, algorithm="lanczos")
        assert "lanczos" in result

    def test_with_config(self):
        """使用 ScaleConfig"""
        config = ScaleConfig(
            width=1920, height=1080, algorithm="bilinear",
            force_original_aspect_ratio="decrease",
            force_divisible_by=2,
        )
        result = ScaleFilter.build_filter(config=config)
        assert "1920" in result
        assert "1080" in result
        assert "bilinear" in result
        assert "force_original_aspect_ratio=decrease" in result
        assert "force_divisible_by=2" in result


class TestScaleConfig:
    """测试 ScaleConfig 数据类"""

    def test_defaults(self):
        config = ScaleConfig()
        assert config.width == -1
        assert config.height == -1
        assert config.algorithm == "bicubic"
        assert config.force_original_aspect_ratio is None
        assert config.force_divisible_by == 0


# =================== CropFilter 测试 ===================


class TestCropFilterBuild:
    """测试 CropFilter.build_filter"""

    def test_basic_crop(self):
        """基本坐标裁剪"""
        result = CropFilter.build_filter(x=100, y=50, width=800, height=600)
        assert result == "crop=800:600:100:50"

    def test_center_crop(self):
        """居中裁剪"""
        result = CropFilter.build_filter(
            center_crop=True, out_width=640, out_height=480,
        )
        assert "crop=640:480" in result
        assert "(iw-640)/2" in result
        assert "(ih-480)/2" in result

    def test_aspect_ratio_crop(self):
        """按宽高比裁剪"""
        result = CropFilter.build_filter(
            keep_aspect=True, target_aspect=16 / 9,
        )
        assert "crop=" in result
        assert "iw" in result or "ih" in result

    def test_auto_width(self):
        """宽度自动（0 表示 iw-x）"""
        result = CropFilter.build_filter(x=100, y=0, width=0, height=0)
        assert "iw-100" in result

    def test_no_crop_xy_zero(self):
        """x=y=0，width=height=0 时使用 iw, ih"""
        result = CropFilter.build_filter(x=0, y=0, width=0, height=0)
        assert "crop=iw:ih:0:0" == result


class TestCropConfig:
    """测试 CropConfig 数据类"""

    def test_defaults(self):
        config = CropConfig()
        assert config.x == 0
        assert config.center_crop is False
        assert config.keep_aspect is False


# =================== TransformFilter 测试 ===================


class TestTransformFilterBuild:
    """测试 TransformFilter.build_filter"""

    def test_hflip(self):
        """水平翻转"""
        result = TransformFilter.build_filter(hflip=True)
        assert result == "hflip"

    def test_vflip(self):
        """垂直翻转"""
        result = TransformFilter.build_filter(vflip=True)
        assert result == "vflip"

    def test_both_flips(self):
        """同时水平和垂直翻转"""
        result = TransformFilter.build_filter(hflip=True, vflip=True)
        assert "hflip" in result
        assert "vflip" in result

    def test_transpose(self):
        """转置（90度旋转）"""
        result = TransformFilter.build_filter(transpose=True, transpose_dir=0)
        assert result == "transpose=0"

    def test_rotation_90(self):
        """90 度旋转优化为 transpose"""
        result = TransformFilter.build_filter(rotation_angle=90)
        assert "transpose=1" in result

    def test_rotation_180(self):
        """180 度旋转"""
        result = TransformFilter.build_filter(rotation_angle=180)
        assert "transpose=1,transpose=1" in result

    def test_rotation_270(self):
        """270 度旋转"""
        result = TransformFilter.build_filter(rotation_angle=270)
        assert "transpose=2" in result

    def test_rotation_arbitrary(self):
        """任意角度旋转使用 rotate filter"""
        result = TransformFilter.build_filter(rotation_angle=45)
        assert "rotate=" in result
        expected_radians = 45 * math.pi / 180
        assert str(round(expected_radians, 4))[:4] in result

    def test_no_transform(self):
        """无变换返回空字符串"""
        result = TransformFilter.build_filter()
        assert result == ""

    def test_combination(self):
        """组合：翻转 + 转置"""
        result = TransformFilter.build_filter(hflip=True, transpose=True, transpose_dir=1)
        assert "hflip" in result
        assert "transpose=1" in result


class TestTransformConfig:
    """测试 TransformConfig 数据类"""

    def test_defaults(self):
        config = TransformConfig()
        assert config.rotation_angle == 0.0
        assert config.hflip is False
        assert config.vflip is False
        assert config.transpose is False
        assert config.transpose_dir == 0


# =================== VideoFilter 链式调用测试 ===================


class TestVideoFilter:
    """测试 VideoFilter 链式调用"""

    def test_chain_scale(self):
        """链式添加 scale"""
        vf = VideoFilter("input.mp4")
        vf.scale(1280, 720)
        result = vf.build()
        assert "scale=1280:720" in result

    def test_chain_crop(self):
        """链式添加 crop"""
        vf = VideoFilter("input.mp4")
        vf.crop(x=100, y=50, width=800, height=600)
        result = vf.build()
        assert "crop=" in result

    def test_chain_rotate(self):
        """链式添加 rotate"""
        vf = VideoFilter("input.mp4")
        vf.rotate(90)
        result = vf.build()
        assert "transpose" in result

    def test_chain_hflip_vflip(self):
        """链式添加翻转"""
        vf = VideoFilter("input.mp4")
        vf.hflip().vflip()
        result = vf.build()
        assert "hflip" in result
        assert "vflip" in result

    def test_chain_transpose(self):
        """链式添加 transpose"""
        vf = VideoFilter("input.mp4")
        vf.transpose(direction=1)
        result = vf.build()
        assert "transpose=1" in result

    def test_chain_custom(self):
        """链式添加自定义滤镜"""
        vf = VideoFilter("input.mp4")
        vf.custom("eq=brightness=0.1:contrast=1.5")
        result = vf.build()
        assert "eq=brightness=0.1:contrast=1.5" in result

    def test_chain_multiple(self):
        """多个滤镜链式调用"""
        vf = VideoFilter("input.mp4")
        result = (
            vf.scale(1280, 720)
            .crop(center_crop=True, out_width=640, out_height=480)
            .hflip()
            .build()
        )
        parts = result.split(",")
        assert len(parts) == 3
        assert "scale=" in parts[0]
        assert "crop=" in parts[1]
        assert "hflip" in parts[2]

    def test_build_empty_filters(self):
        """空滤镜构建"""
        vf = VideoFilter("input.mp4")
        assert vf.build() == ""

    def test_output_requires_filters(self):
        """output 时没有滤镜应该报错"""
        vf = VideoFilter("input.mp4")
        with pytest.raises(ValueError, match="没有添加任何滤镜"):
            vf.output("output.mp4")

    def test_chain_returns_self(self):
        """链式调用返回自身"""
        vf = VideoFilter("input.mp4")
        assert vf.scale(100, 100) is vf
        assert vf.crop(x=0, y=0) is vf
        assert vf.rotate(0) is vf
        assert vf.hflip() is vf
        assert vf.vflip() is vf
        assert vf.transpose() is vf
        assert vf.custom("test") is vf


# =================== 集成测试（真实视频） ===================

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import skip_no_video, skip_no_ffmpeg_cli, integration

logger = logging.getLogger(__name__)


@pytest.fixture
def output_dir(tmp_path):
    """临时输出目录"""
    return tmp_path


@skip_no_video
@skip_no_ffmpeg_cli
@integration
class TestVideoFilterReal:
    """使用真实视频测试 VideoFilter 链式滤镜"""

    def test_scale_filter(self, video_path, output_dir):
        """缩放滤镜"""
        output = str(output_dir / "scaled.mp4")
        result = ScaleFilter.apply(
            video_path, output,
            width=640, height=360,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        assert info.height == 360
        logger.info(f"缩放: {info.resolution}")

    def test_scale_keep_aspect(self, video_path, output_dir):
        """保持宽高比缩放"""
        output = str(output_dir / "scaled_aspect.mp4")
        result = ScaleFilter.apply(
            video_path, output,
            width=640, height=-2,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        assert info.height > 0
        assert info.height % 2 == 0
        logger.info(f"保持宽高比缩放: {info.resolution}")

    def test_crop_filter(self, video_path, output_dir):
        """裁剪滤镜"""
        output = str(output_dir / "cropped.mp4")
        result = CropFilter.apply(
            video_path, output,
            x=100, y=50, width=400, height=300,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300
        logger.info(f"裁剪: {info.resolution}")

    def test_center_crop_filter(self, video_path, output_dir):
        """居中裁剪"""
        output = str(output_dir / "center_cropped.mp4")
        result = CropFilter.apply(
            video_path, output,
            center_crop=True, out_width=400, out_height=300,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300

    def test_transform_hflip(self, video_path, output_dir):
        """水平翻转"""
        output = str(output_dir / "hflip.mp4")
        result = TransformFilter.apply(
            video_path, output,
            hflip=True,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info_orig = probe(video_path)
        info_flip = probe(result)
        assert info_flip.width == info_orig.width
        assert info_flip.height == info_orig.height

    def test_transform_rotate_90(self, video_path, output_dir):
        """旋转 90 度"""
        output = str(output_dir / "rotate90.mp4")
        result = TransformFilter.apply(
            video_path, output,
            rotation_angle=90,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info_orig = probe(video_path)
        info_rot = probe(result)
        assert info_rot.width == info_orig.height
        assert info_rot.height == info_orig.width
        logger.info(f"旋转 90°: {info_orig.resolution} -> {info_rot.resolution}")

    def test_video_filter_chain(self, video_path, output_dir):
        """链式滤镜组合"""
        output = str(output_dir / "chain_output.mp4")
        result = (
            VideoFilter(video_path)
            .scale(640, -2)
            .hflip()
            .output(output)
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        logger.info(f"链式滤镜: {info.resolution}")

    def test_video_filter_scale_crop_chain(self, video_path, output_dir):
        """链式: 缩放 + 居中裁剪"""
        output = str(output_dir / "scale_crop.mp4")
        result = (
            VideoFilter(video_path)
            .scale(800, -2)
            .crop(center_crop=True, out_width=400, out_height=300)
            .output(output)
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300
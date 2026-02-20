# -*- coding: utf-8 -*-
"""视频截取（clip）模块的单元测试

运行测试命令:
    # 运行本文件所有测试
    pytest tests/unit/test_video_clip.py -v

    # 运行本文件所有测试（显示 INFO 日志）
    pytest tests/unit/test_video_clip.py -v --log-cli-level=INFO

    # 只运行纯逻辑测试（跳过集成测试）
    pytest tests/unit/test_video_clip.py -v -m "not integration"

    # 运行指定测试类
    pytest tests/unit/test_video_clip.py::TestVideoClipCut -v
    pytest tests/unit/test_video_clip.py::TestVideoClipReal -v --log-cli-level=INFO
"""

import pytest

from peek.cv.video.clip import VideoClip


class TestVideoClipCut:
    """测试视频截取 cut 方法"""

    def test_end_and_duration_conflict(self):
        """end 和 duration 不能同时指定"""
        with pytest.raises(ValueError, match="end 和 duration 不能同时指定"):
            VideoClip.cut("input.mp4", "output.mp4", start=0, end=10, duration=5)

    def test_negative_start(self):
        """start 不能为负数"""
        with pytest.raises(ValueError, match="start 不能为负数"):
            VideoClip.cut("input.mp4", "output.mp4", start=-1)

    def test_end_less_than_start(self):
        """end 必须大于 start"""
        with pytest.raises(ValueError, match="end .* 必须大于 start"):
            VideoClip.cut("input.mp4", "output.mp4", start=10, end=5)

    def test_negative_duration(self):
        """duration 必须为正数"""
        with pytest.raises(ValueError, match="duration 必须为正数"):
            VideoClip.cut("input.mp4", "output.mp4", start=0, duration=-1)

    def test_zero_duration(self):
        """duration 为 0 也不行"""
        with pytest.raises(ValueError, match="duration 必须为正数"):
            VideoClip.cut("input.mp4", "output.mp4", start=0, duration=0)




# =================== 集成测试（真实视频） ===================

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import skip_no_video, skip_no_ffmpeg_cli, integration

logger = logging.getLogger(__name__)


@skip_no_video
@skip_no_ffmpeg_cli
@integration
class TestVideoClipReal:
    """使用真实视频测试 VideoClip"""

    def test_cut_by_time_range(self, video_path, output_dir):
        """按时间范围截取"""
        output = str(output_dir / "cut_output.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=1.0, end=3.0,
            accurate=True, copy_codec=True,
        )

        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

        from peek.cv.video.info import probe
        info = probe(result)
        assert 1.0 <= info.duration <= 4.0
        logger.info(f"截取结果: duration={info.duration:.2f}s, size={Path(result).stat().st_size}")

    def test_cut_by_duration(self, video_path, output_dir):
        """按时长截取"""
        output = str(output_dir / "cut_duration.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=0.0, duration=2.0,
            copy_codec=True,
        )

        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    def test_cut_fast_mode(self, video_path, output_dir):
        """快速模式截取（基于关键帧）"""
        output = str(output_dir / "cut_fast.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=2.0, duration=3.0,
            accurate=False, copy_codec=True,
        )

        assert Path(result).exists()

    def test_split_video(self, video_path, output_dir):
        """视频分割"""
        segments = VideoClip.split(
            video_path, str(output_dir),
            segment_duration=5.0,
        )

        assert len(segments) > 0
        for seg in segments:
            assert Path(seg).exists()
            assert Path(seg).stat().st_size > 0

        logger.info(f"分割为 {len(segments)} 个片段")


@pytest.fixture
def output_dir(tmp_path):
    """临时输出目录"""
    return tmp_path
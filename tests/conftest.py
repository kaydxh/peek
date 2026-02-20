#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pytest 配置文件

提供测试夹具和配置
"""

import os
import sys
from pathlib import Path

import pytest

# 将 src 目录添加到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录"""
    return ROOT_DIR


@pytest.fixture(scope="session")
def testdata_dir() -> Path:
    """测试数据目录"""
    return ROOT_DIR / "tests" / "testdata"


@pytest.fixture(scope="function")
def temp_dir(tmp_path: Path) -> Path:
    """临时目录（每个测试函数独立）"""
    return tmp_path


@pytest.fixture(scope="session")
def sample_image(testdata_dir: Path) -> Path:
    """示例图片路径"""
    image_path = testdata_dir / "test.jpg"
    if image_path.exists():
        return image_path
    return None


# =================== 视频测试相关 ===================

import base64


def _has_module(name: str) -> bool:
    """检测 Python 模块是否可导入"""
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _has_cli(cmd: str) -> bool:
    """检测 CLI 可执行文件是否可用"""
    import subprocess
    try:
        subprocess.run([cmd, "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# 依赖可用性标志
HAS_DECORD = _has_module("decord")
HAS_OPENCV = _has_module("cv2")
HAS_AV = _has_module("av")
HAS_FFMPEG_CLI = _has_cli("ffmpeg")
HAS_FFPROBE_CLI = _has_cli("ffprobe")

# 视频测试数据路径
VIDEO_PATH = ROOT_DIR / "tests" / "testdata" / "bodyhead.text.mp4"
VIDEO_EXISTS = VIDEO_PATH.exists()

# 通用 skip 标记
skip_no_video = pytest.mark.skipif(not VIDEO_EXISTS, reason=f"测试视频文件不存在: {VIDEO_PATH}")
skip_no_decord = pytest.mark.skipif(not HAS_DECORD, reason="decord 未安装")
skip_no_opencv = pytest.mark.skipif(not HAS_OPENCV, reason="opencv-python 未安装")
skip_no_av = pytest.mark.skipif(not HAS_AV, reason="av (PyAV) 未安装")
skip_no_ffmpeg_cli = pytest.mark.skipif(not HAS_FFMPEG_CLI, reason="ffmpeg CLI 未安装")
skip_no_ffprobe = pytest.mark.skipif(not HAS_FFPROBE_CLI, reason="ffprobe CLI 未安装")

# 自定义 integration 标记
integration = pytest.mark.integration


@pytest.fixture(scope="session")
def video_path() -> str:
    """真实视频文件路径"""
    return str(VIDEO_PATH)


@pytest.fixture(scope="session")
def video_bytes() -> bytes:
    """真实视频的字节数据"""
    if VIDEO_EXISTS:
        return VIDEO_PATH.read_bytes()
    return b""


@pytest.fixture(scope="session")
def video_base64(video_bytes) -> str:
    """真实视频的 base64 编码"""
    return base64.b64encode(video_bytes).decode("utf-8")
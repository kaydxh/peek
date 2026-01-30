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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
peek 包安装脚本

安装方式：
    pip install .           # 安装
    pip install -e .        # 开发模式安装
    pip install -e .[dev]   # 开发模式安装（含开发依赖）
    pip install -e .[prod]  # 开发模式安装（含生产依赖）
"""

import os
from pathlib import Path

from setuptools import find_packages, setup

# 项目根目录
HERE = Path(__file__).parent.resolve()

# 读取版本信息
about = {}
version_file = HERE / "src" / "peek" / "__version__.py"
with open(version_file, mode="r", encoding="utf-8") as f:
    exec(f.read(), about)

# 读取 README
readme_file = HERE / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file, mode="r", encoding="utf-8") as f:
        long_description = f.read()


def read_requirements(filename: str) -> list:
    """读取依赖文件"""
    filepath = HERE / "requirements" / filename
    if not filepath.exists():
        return []

    requirements = []
    with open(filepath, mode="r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            # 处理 -r 引用
            if line.startswith("-r "):
                ref_file = line[3:].strip()
                requirements.extend(read_requirements(ref_file))
            else:
                requirements.append(line)
    return requirements


# 基础依赖
INSTALL_REQUIRES = read_requirements("base.txt")

# 可选依赖
EXTRAS_REQUIRE = {
    "dev": read_requirements("dev.txt"),
    "prod": read_requirements("prod.txt"),
    "all": read_requirements("dev.txt") + read_requirements("prod.txt"),
}

setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=about["__author__"],
    author_email=about["__author_email__"],
    url=about["__url__"],
    license=about["__license__"],
    # src-layout 配置
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    # 命令行入口（可选）
    entry_points={
        "console_scripts": [
            # "peek=peek.cli:main",  # 如果需要 CLI
        ],
    },
)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向后兼容的安装入口

所有项目元信息和依赖均定义在 pyproject.toml 中，
本文件仅作为旧版 pip/setuptools 的 shim。

安装方式：
    pip install .              # 安装核心依赖
    pip install -e .           # 开发模式安装
    pip install -e ".[dev]"    # 开发模式安装（含开发依赖）
    pip install -e ".[prod]"   # 开发模式安装（含生产依赖）
    pip install -e ".[web]"    # 仅安装 Web 相关依赖
    pip install -e ".[all]"    # 安装所有依赖
"""

from setuptools import setup

setup()
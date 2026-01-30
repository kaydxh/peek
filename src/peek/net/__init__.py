#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
网络模块

提供网络相关功能：
- http: HTTP 客户端
- ip: IP 地址工具
- webserver: Web 服务器框架（HTTP + gRPC）
- grpc: gRPC 服务器和客户端
"""

from peek.net import http
from peek.net import ip

__all__ = [
    "http",
    "ip",
]

# WebServer 和 gRPC 模块延迟导入，避免循环依赖
def __getattr__(name):
    if name == "webserver":
        from peek.net import webserver
        return webserver
    if name == "grpc":
        from peek.net import grpc
        return grpc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

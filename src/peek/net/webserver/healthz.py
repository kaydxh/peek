#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
健康检查控制器

参考 Go 版本 golang 库的 healthz 实现
提供 /healthz, /livez, /readyz 端点
"""

import asyncio
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class HealthCheckResult(BaseModel):
    """健康检查结果"""

    name: str
    status: str
    message: str = ""
    duration_ms: float = 0


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    timestamp: str
    checks: List[HealthCheckResult] = []


class HealthChecker(ABC):
    """
    健康检查器接口

    所有健康检查器都需要实现此接口
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """检查器名称"""
        pass

    @abstractmethod
    async def check(self) -> Optional[Exception]:
        """
        执行健康检查

        Returns:
            None 表示健康，Exception 表示不健康
        """
        pass


class PingHealthChecker(HealthChecker):
    """
    Ping 健康检查器

    最基础的检查器，总是返回健康
    """

    @property
    def name(self) -> str:
        return "ping"

    async def check(self) -> Optional[Exception]:
        return None


class HTTPHealthChecker(HealthChecker):
    """
    HTTP 端点健康检查器

    检查指定 HTTP 端点是否可访问
    """

    def __init__(
        self,
        checker_name: str,
        url: str,
        timeout: float = 5.0,
        expected_status_codes: List[int] = None,
    ):
        """
        Args:
            checker_name: 检查器名称
            url: HTTP URL
            timeout: 超时时间（秒）
            expected_status_codes: 期望的状态码列表，默认 [200]
        """
        self._name = checker_name
        self.url = url
        self.timeout = timeout
        self.expected_status_codes = expected_status_codes or [200]

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> Optional[Exception]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, timeout=self.timeout)
                if response.status_code not in self.expected_status_codes:
                    return Exception(
                        f"Unexpected status code: {response.status_code}, "
                        f"expected: {self.expected_status_codes}"
                    )
                return None
        except Exception as e:
            return e


class TCPHealthChecker(HealthChecker):
    """
    TCP 连接健康检查器

    检查指定 TCP 端点是否可连接
    """

    def __init__(
        self,
        checker_name: str,
        host: str,
        port: int,
        timeout: float = 5.0,
    ):
        """
        Args:
            checker_name: 检查器名称
            host: 主机地址
            port: 端口号
            timeout: 超时时间（秒）
        """
        self._name = checker_name
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> Optional[Exception]:
        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            await loop.run_in_executor(
                None,
                sock.connect,
                (self.host, self.port),
            )
            sock.close()
            return None
        except Exception as e:
            return e


class FuncHealthChecker(HealthChecker):
    """
    函数健康检查器

    使用自定义函数进行健康检查
    """

    def __init__(
        self,
        checker_name: str,
        check_func: Callable[[], Optional[Exception]],
    ):
        """
        Args:
            checker_name: 检查器名称
            check_func: 检查函数，返回 None 表示健康，Exception 表示不健康
        """
        self._name = checker_name
        self._check_func = check_func

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> Optional[Exception]:
        try:
            if asyncio.iscoroutinefunction(self._check_func):
                return await self._check_func()
            else:
                return self._check_func()
        except Exception as e:
            return e


class CompositeHealthChecker(HealthChecker):
    """
    组合健康检查器

    组合多个检查器，全部通过才返回健康
    """

    def __init__(self, checker_name: str):
        """
        Args:
            checker_name: 检查器名称
        """
        self._name = checker_name
        self._checkers: List[HealthChecker] = []

    @property
    def name(self) -> str:
        return self._name

    def add_checker(self, checker: HealthChecker) -> None:
        """添加检查器"""
        self._checkers.append(checker)

    def remove_checker(self, name: str) -> None:
        """移除检查器"""
        self._checkers = [c for c in self._checkers if c.name != name]

    async def check(self) -> Optional[Exception]:
        """执行所有检查器"""
        errors = []
        for checker in self._checkers:
            err = await checker.check()
            if err:
                errors.append(f"{checker.name}: {err}")

        if errors:
            return Exception("; ".join(errors))
        return None

    async def check_all(self) -> List[HealthCheckResult]:
        """
        执行所有检查器并返回详细结果

        Returns:
            检查结果列表
        """
        results = []
        for checker in self._checkers:
            start_time = asyncio.get_event_loop().time()
            err = await checker.check()
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            results.append(
                HealthCheckResult(
                    name=checker.name,
                    status="ok" if err is None else "failed",
                    message="" if err is None else str(err),
                    duration_ms=round(duration_ms, 2),
                )
            )
        return results


class HealthzController:
    """
    健康检查控制器

    提供以下端点：
    - /healthz: 综合健康检查
    - /healthz/verbose: 详细健康检查结果
    - /livez: 存活探针
    - /livez/verbose: 详细存活检查结果
    - /readyz: 就绪探针
    - /readyz/verbose: 详细就绪检查结果
    """

    def __init__(
        self,
        check_timeout: float = 5.0,
    ):
        """
        Args:
            check_timeout: 检查超时时间（秒）
        """
        self.check_timeout = check_timeout

        # 存活检查器
        self.livez_checkers = CompositeHealthChecker("livez")
        self.livez_checkers.add_checker(PingHealthChecker())

        # 就绪检查器
        self.readyz_checkers = CompositeHealthChecker("readyz")
        self.readyz_checkers.add_checker(PingHealthChecker())

        # 就绪状态
        self._ready: bool = False

    @property
    def is_ready(self) -> bool:
        """获取就绪状态"""
        return self._ready

    def set_ready(self, ready: bool) -> None:
        """设置就绪状态"""
        self._ready = ready

    def add_livez_checker(self, checker: HealthChecker) -> None:
        """添加存活检查器"""
        self.livez_checkers.add_checker(checker)

    def add_readyz_checker(self, checker: HealthChecker) -> None:
        """添加就绪检查器"""
        self.readyz_checkers.add_checker(checker)

    def install_routes(self, app: FastAPI) -> None:
        """
        安装路由

        Args:
            app: FastAPI 应用实例
        """

        @app.get("/healthz", tags=["Health"])
        async def healthz() -> Response:
            """综合健康检查"""
            livez_err = await self.livez_checkers.check()
            readyz_err = await self.readyz_checkers.check()

            if not self._ready:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not ready",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            if livez_err or readyz_err:
                errors = []
                if livez_err:
                    errors.append(f"livez: {livez_err}")
                if readyz_err:
                    errors.append(f"readyz: {readyz_err}")

                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "errors": errors,
                    },
                )

            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        @app.get("/healthz/verbose", tags=["Health"])
        async def healthz_verbose() -> HealthResponse:
            """详细健康检查结果"""
            livez_results = await self.livez_checkers.check_all()
            readyz_results = await self.readyz_checkers.check_all()

            all_results = []
            for r in livez_results:
                r.name = f"livez/{r.name}"
                all_results.append(r)
            for r in readyz_results:
                r.name = f"readyz/{r.name}"
                all_results.append(r)

            all_ok = all(r.status == "ok" for r in all_results) and self._ready

            return HealthResponse(
                status="ok" if all_ok else "unhealthy",
                timestamp=datetime.now(timezone.utc).isoformat(),
                checks=all_results,
            )

        @app.get("/livez", tags=["Health"])
        async def livez() -> Response:
            """存活探针"""
            err = await self.livez_checkers.check()
            if err:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error": str(err),
                    },
                )

            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        @app.get("/livez/verbose", tags=["Health"])
        async def livez_verbose() -> HealthResponse:
            """详细存活检查结果"""
            results = await self.livez_checkers.check_all()
            all_ok = all(r.status == "ok" for r in results)

            return HealthResponse(
                status="ok" if all_ok else "unhealthy",
                timestamp=datetime.now(timezone.utc).isoformat(),
                checks=results,
            )

        @app.get("/readyz", tags=["Health"])
        async def readyz() -> Response:
            """就绪探针"""
            if not self._ready:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not ready",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            err = await self.readyz_checkers.check()
            if err:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "error": str(err),
                    },
                )

            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        @app.get("/readyz/verbose", tags=["Health"])
        async def readyz_verbose() -> HealthResponse:
            """详细就绪检查结果"""
            results = await self.readyz_checkers.check_all()

            # 添加 ready 状态检查
            ready_result = HealthCheckResult(
                name="ready",
                status="ok" if self._ready else "failed",
                message="" if self._ready else "Server is not ready",
            )
            results.insert(0, ready_result)

            all_ok = all(r.status == "ok" for r in results)

            return HealthResponse(
                status="ok" if all_ok else "unhealthy",
                timestamp=datetime.now(timezone.utc).isoformat(),
                checks=results,
            )

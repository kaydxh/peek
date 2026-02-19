#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志中间件

记录请求和响应信息，包括请求体和响应体内容
对大字符串字段只打印前 N 个字节和总长度
"""

from typing import Any, Awaitable, Callable, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class LoggerMiddleware(BaseHTTPMiddleware):
    """
    日志中间件

    记录请求和响应信息，包括请求体和响应体内容
    对大字符串字段只打印前 N 个字节和总长度
    """

    # 默认字符串截断长度
    DEFAULT_MAX_STRING_LENGTH = 10

    def __init__(
        self,
        app: ASGIApp,
        logger: Any = None,
        log_request_body: bool = True,
        log_response_body: bool = True,
        log_request_headers: bool = False,
        log_response_headers: bool = False,
        max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
        skip_paths: List[str] = None,
    ):
        """
        初始化日志中间件

        Args:
            app: ASGI 应用
            logger: 日志记录器
            log_request_body: 是否记录请求体
            log_response_body: 是否记录响应体
            log_request_headers: 是否记录请求头（类似 Go 版 InOutputHeaderPrinter）
            log_response_headers: 是否记录响应头（类似 Go 版 InOutputHeaderPrinter）
            max_string_length: 字符串字段的最大打印长度，超过则截断
            skip_paths: 跳过记录的路径列表（如 /health, /metrics）
        """
        super().__init__(app)
        self.logger = logger
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.log_request_headers = log_request_headers
        self.log_response_headers = log_response_headers
        self.max_string_length = max_string_length
        self.skip_paths = skip_paths or ["/health", "/healthz", "/metrics", "/ready"]

    def _log(self, msg: str, level: str = "info") -> None:
        """统一日志输出"""
        if self.logger:
            log_func = getattr(self.logger, level, self.logger.info)
            log_func(msg)
        else:
            print(msg)

    def _truncate_string(self, value: str) -> str:
        """
        截断字符串，对于超过限制的字符串只保留前 N 个字节并显示总长度

        Args:
            value: 原始字符串

        Returns:
            截断后的字符串，格式: "前N字节...(总长度:X bytes)"
        """
        if len(value) <= self.max_string_length:
            return value

        # 对于超长字符串，只显示前 N 个字节和总长度
        truncated = value[:self.max_string_length]
        return f"{truncated}...(len:{len(value)} bytes)"

    def _truncate_value(self, value: Any) -> Any:
        """
        递归处理值，对字符串进行截断

        Args:
            value: 任意类型的值

        Returns:
            处理后的值
        """
        if isinstance(value, str):
            return self._truncate_string(value)
        elif isinstance(value, bytes):
            # 对 bytes 类型也进行截断
            if len(value) <= self.max_string_length:
                return f"<bytes:{len(value)}>"
            return f"<bytes:{self.max_string_length}+...>(len:{len(value)} bytes)"
        elif isinstance(value, dict):
            return {k: self._truncate_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._truncate_value(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._truncate_value(item) for item in value)
        else:
            return value

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """
        获取请求体内容

        Args:
            request: FastAPI Request 对象

        Returns:
            请求体字符串或 None
        """
        try:
            # 读取请求体
            body = await request.body()
            if not body:
                return None

            # 尝试解析为 JSON
            try:
                import json
                body_json = json.loads(body)
                # 对 JSON 内容进行截断处理
                truncated_body = self._truncate_value(body_json)
                return json.dumps(truncated_body, ensure_ascii=False)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 非 JSON 内容，直接截断原始字符串
                body_str = body.decode("utf-8", errors="replace")
                return self._truncate_string(body_str)

        except Exception as e:
            return f"<error reading body: {e}>"

    def _format_response_body(self, body: bytes) -> str:
        """
        格式化响应体内容

        Args:
            body: 响应体字节

        Returns:
            格式化后的字符串
        """
        if not body:
            return "<empty>"

        try:
            import json
            body_json = json.loads(body)
            # 对 JSON 内容进行截断处理
            truncated_body = self._truncate_value(body_json)
            return json.dumps(truncated_body, ensure_ascii=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 非 JSON 内容
            try:
                body_str = body.decode("utf-8", errors="replace")
                return self._truncate_string(body_str)
            except Exception:
                return f"<binary data, len:{len(body)} bytes>"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 检查是否跳过该路径
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # 获取 request_id（如果存在）
        request_id = getattr(request.state, "request_id", "-")

        # 获取客户端 IP
        client_ip = request.client.host if request.client else "-"

        # 记录请求
        log_msg = f"[{request_id}] --> {request.method} {request.url.path} from {client_ip}"

        # 记录请求头（类似 Go 版 InOutputHeaderPrinter 的 recv headers）
        if self.log_request_headers:
            headers_dict = dict(request.headers)
            log_msg += f" | headers: {headers_dict}"

        # 记录请求体
        if self.log_request_body:
            request_body = await self._get_request_body(request)
            if request_body:
                log_msg += f" | body: {request_body}"

        self._log(log_msg)

        # 调用下一个处理器，并捕获响应体
        if self.log_response_body:
            # 需要捕获响应体，使用自定义的响应包装
            response = await call_next(request)

            # 读取响应体
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # 记录响应
            response_body_str = self._format_response_body(response_body)
            log_msg = (
                f"[{request_id}] <-- {request.method} {request.url.path} "
                f"{response.status_code}"
            )

            # 记录响应头（类似 Go 版 InOutputHeaderPrinter 的 send headers）
            if self.log_response_headers:
                resp_headers_dict = dict(response.headers)
                log_msg += f" | headers: {resp_headers_dict}"

            log_msg += f" | body: {response_body_str}"
            self._log(log_msg)

            # 重新构建响应（因为 body_iterator 只能读取一次）
            from starlette.responses import Response as StarletteResponse
            return StarletteResponse(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        else:
            response = await call_next(request)

            # 记录响应
            log_msg = (
                f"[{request_id}] <-- {request.method} {request.url.path} "
                f"{response.status_code}"
            )

            # 记录响应头
            if self.log_response_headers:
                resp_headers_dict = dict(response.headers)
                log_msg += f" | headers: {resp_headers_dict}"

            self._log(log_msg)

            return response

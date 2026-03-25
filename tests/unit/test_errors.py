#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一错误体系模块测试
"""

import pytest

from peek.errors.errors import (
    AppError,
    AppTimeoutError,
    ConflictError,
    ErrorCode,
    InternalError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthenticatedError,
    ValidationError,
)
from peek.errors.handler import (
    build_validation_response,
    format_validation_error,
    format_validation_errors,
)


# ============ ErrorCode 枚举测试 ============

class TestErrorCode:
    """ErrorCode 枚举测试"""

    def test_error_code_values(self):
        """错误码应与 HTTP 状态码对齐"""
        assert ErrorCode.BAD_REQUEST == 400
        assert ErrorCode.NOT_FOUND == 404
        assert ErrorCode.INTERNAL == 500

    def test_error_code_is_int(self):
        """错误码应是整数"""
        assert isinstance(ErrorCode.BAD_REQUEST, int)
        assert isinstance(ErrorCode.CUSTOM, int)

    def test_custom_code(self):
        """自定义错误码"""
        assert ErrorCode.CUSTOM == 10000


# ============ AppError 基类测试 ============

class TestAppError:
    """AppError 基类测试"""

    def test_default_values(self):
        """测试默认值"""
        err = AppError()
        assert err.message == "Internal server error"
        assert err.code == ErrorCode.INTERNAL
        assert err.http_status == 500
        assert err.details == {}
        assert err.cause is None

    def test_custom_values(self):
        """测试自定义值"""
        cause = ValueError("root cause")
        err = AppError(
            message="Custom error",
            code=ErrorCode.BAD_REQUEST,
            details={"field": "name"},
            http_status=400,
            cause=cause,
        )
        assert err.message == "Custom error"
        assert err.code == ErrorCode.BAD_REQUEST
        assert err.http_status == 400
        assert err.details == {"field": "name"}
        assert err.cause is cause

    def test_is_exception(self):
        """AppError 应该是 Exception 的子类"""
        err = AppError("test")
        assert isinstance(err, Exception)
        with pytest.raises(AppError):
            raise err

    def test_str_representation(self):
        """str() 应返回错误消息"""
        err = AppError("Something went wrong")
        assert str(err) == "Something went wrong"

    def test_repr(self):
        """repr 应包含关键字段"""
        err = AppError("test", code=ErrorCode.NOT_FOUND, http_status=404)
        r = repr(err)
        assert "AppError" in r
        assert "404" in r
        assert "test" in r

    def test_to_dict(self):
        """to_dict 应返回正确格式"""
        err = AppError(
            message="dict test",
            code=ErrorCode.BAD_REQUEST,
            details={"key": "val"},
        )
        d = err.to_dict()
        assert d["code"] == 400
        assert d["message"] == "dict test"
        assert d["details"] == {"key": "val"}
        assert "timestamp" in d

    def test_to_dict_no_details(self):
        """无 details 时 to_dict 不应包含 details 字段"""
        err = AppError(message="no details")
        d = err.to_dict()
        assert "details" not in d

    def test_grpc_status_mapping(self):
        """grpc_status 应正确映射"""
        assert AppError(http_status=400).grpc_status == "INVALID_ARGUMENT"
        assert AppError(http_status=401).grpc_status == "UNAUTHENTICATED"
        assert AppError(http_status=403).grpc_status == "PERMISSION_DENIED"
        assert AppError(http_status=404).grpc_status == "NOT_FOUND"
        assert AppError(http_status=409).grpc_status == "ALREADY_EXISTS"
        assert AppError(http_status=429).grpc_status == "RESOURCE_EXHAUSTED"
        assert AppError(http_status=500).grpc_status == "INTERNAL"
        assert AppError(http_status=503).grpc_status == "UNAVAILABLE"
        assert AppError(http_status=504).grpc_status == "DEADLINE_EXCEEDED"

    def test_grpc_status_unknown_code(self):
        """未知 HTTP 状态码应映射到 INTERNAL"""
        err = AppError(http_status=418)
        assert err.grpc_status == "INTERNAL"


# ============ 具名子类测试 ============

class TestErrorSubclasses:
    """错误子类测试"""

    def test_not_found_error(self):
        err = NotFoundError("User not found", details={"id": 1})
        assert err.http_status == 404
        assert err.code == ErrorCode.NOT_FOUND
        assert err.message == "User not found"
        assert isinstance(err, AppError)

    def test_validation_error(self):
        err = ValidationError("Invalid input")
        assert err.http_status == 400
        assert err.code == ErrorCode.BAD_REQUEST

    def test_permission_denied_error(self):
        err = PermissionDeniedError()
        assert err.http_status == 403
        assert err.message == "Permission denied"

    def test_unauthenticated_error(self):
        err = UnauthenticatedError()
        assert err.http_status == 401

    def test_conflict_error(self):
        err = ConflictError()
        assert err.http_status == 409

    def test_internal_error(self):
        err = InternalError()
        assert err.http_status == 500

    def test_service_unavailable_error(self):
        err = ServiceUnavailableError()
        assert err.http_status == 503

    def test_app_timeout_error(self):
        """AppTimeoutError 不应遮蔽内置 TimeoutError"""
        err = AppTimeoutError()
        assert err.http_status == 504
        assert err.code == ErrorCode.GATEWAY_TIMEOUT
        # 确认未遮蔽内置 TimeoutError
        assert AppTimeoutError is not TimeoutError

    def test_rate_limit_error(self):
        err = RateLimitError()
        assert err.http_status == 429

    def test_subclass_with_cause(self):
        """子类应支持 cause 参数"""
        original = IOError("disk error")
        err = InternalError("Failed to save", cause=original)
        assert err.cause is original


# ============ 校验错误格式化工具测试 ============

class TestValidationErrorFormatting:
    """校验错误格式化测试"""

    def test_format_validation_error_basic(self):
        """基本格式化"""
        raw = {
            "type": "string_too_short",
            "loc": ["body", "name"],
            "msg": "String should have at least 2 characters",
            "input": "a",
        }
        result = format_validation_error(raw)
        assert result["field"] == "name"
        assert result["message"] == "String should have at least 2 characters"
        assert result["type"] == "string_too_short"
        assert result["input"] == "a"

    def test_format_validation_error_filters_loc_prefixes(self):
        """应过滤 body/query/path 等前缀"""
        raw = {
            "loc": ["query", "page", "size"],
            "msg": "Invalid",
        }
        result = format_validation_error(raw)
        assert result["field"] == "page.size"

    def test_format_validation_error_empty_loc(self):
        """空 loc 时 field 应为 'unknown'"""
        raw = {"loc": [], "msg": "Error"}
        result = format_validation_error(raw)
        assert result["field"] == "unknown"

    def test_format_validation_error_long_input_truncated(self):
        """过长的 input 应被截断"""
        raw = {
            "loc": ["body", "data"],
            "msg": "Invalid",
            "input": "x" * 200,
        }
        result = format_validation_error(raw)
        assert len(result["input"]) <= 104  # 100 + "..."

    def test_format_validation_errors_batch(self):
        """批量格式化"""
        raw_errors = [
            {"loc": ["body", "name"], "msg": "Required"},
            {"loc": ["body", "email"], "msg": "Invalid email"},
        ]
        results = format_validation_errors(raw_errors)
        assert len(results) == 2
        assert results[0]["field"] == "name"
        assert results[1]["field"] == "email"

    def test_build_validation_response(self):
        """构建统一校验错误响应"""
        raw_errors = [
            {"loc": ["body", "name"], "msg": "Required"},
            {"loc": ["body", "age"], "msg": "Must be positive"},
        ]
        response = build_validation_response(raw_errors)
        assert response["code"] == 400
        assert "name" in response["message"]
        assert "age" in response["message"]
        assert response["details"]["error_count"] == 2
        assert "timestamp" in response

    def test_build_validation_response_empty(self):
        """空错误列表"""
        response = build_validation_response([])
        assert response["code"] == 400
        assert response["details"]["error_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志配置模块测试
"""

import logging
import pytest

from peek.logs.config import (
    LEVEL_MAP,
    LogConfig,
    LogFormatter,
    LogLevel,
    LogRedirect,
    LoggerAdapter,
    get_logger,
    install_logs,
)
from peek.time.parse import parse_duration


# ============ LogConfig 测试 ============

class TestLogConfig:
    """LogConfig 数据类测试"""

    def test_default_values(self):
        """测试默认配置值"""
        config = LogConfig()
        assert config.formatter == "glog"
        assert config.level == "info"
        assert config.filepath == "./log"
        assert config.redirect == "stdout"
        assert config.report_caller is True
        assert config.enable_colors is False
        assert config.max_count == 200
        assert config.rotate_size == 104857600

    def test_parse_duration_seconds(self):
        """解析秒数"""
        assert parse_duration("3600") == 3600.0
        assert parse_duration("3600s") == 3600.0

    def test_parse_duration_minutes(self):
        """解析分钟"""
        assert parse_duration("60m") == 3600.0

    def test_parse_duration_hours(self):
        """解析小时"""
        assert parse_duration("1h") == 3600.0

    def test_parse_duration_days(self):
        """解析天"""
        assert parse_duration("1d") == 86400.0

    def test_parse_duration_empty(self):
        """空字符串返回 0"""
        assert parse_duration("") == 0.0

    def test_parse_duration_invalid(self):
        """无效字符串返回 0"""
        assert parse_duration("abc") == 0.0

    def test_field_validator_converts_strings(self):
        """field_validator 应自动转换字符串为数值"""
        config = LogConfig(max_age="1h", rotate_interval="30m")
        assert config.max_age == 3600.0
        assert config.rotate_interval == 1800.0

    def test_from_dict(self):
        """from_dict 应正确创建配置"""
        config = LogConfig.from_dict({
            "formatter": "json",
            "level": "debug",
            "redirect": "both",
        })
        assert config.formatter == "json"
        assert config.level == "debug"
        assert config.redirect == "both"

    def test_from_dict_defaults(self):
        """from_dict 空字典应使用默认值"""
        config = LogConfig.from_dict({})
        assert config.formatter == "glog"
        assert config.level == "info"


# ============ 枚举测试 ============

class TestEnums:
    """日志枚举测试"""

    def test_log_formatter_values(self):
        assert LogFormatter.GLOG == "glog"
        assert LogFormatter.TEXT == "text"
        assert LogFormatter.JSON == "json"

    def test_log_level_values(self):
        assert LogLevel.DEBUG == "debug"
        assert LogLevel.INFO == "info"
        assert LogLevel.ERROR == "error"

    def test_log_redirect_values(self):
        assert LogRedirect.STDOUT == "stdout"
        assert LogRedirect.FILE == "file"
        assert LogRedirect.BOTH == "both"

    def test_level_map_completeness(self):
        """LEVEL_MAP 应覆盖所有 LogLevel"""
        for level in LogLevel:
            assert level.value in LEVEL_MAP


# ============ install_logs 测试 ============

class TestInstallLogs:
    """install_logs 安装测试"""

    def test_install_default(self):
        """默认安装不应报错"""
        install_logs()
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) > 0

    def test_install_custom_level(self):
        """自定义日志级别"""
        config = LogConfig(level="debug")
        install_logs(config)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_install_json_formatter(self):
        """JSON 格式化器安装不应报错"""
        config = LogConfig(formatter="json", redirect="stdout")
        install_logs(config)

    def test_install_text_formatter(self):
        """Text 格式化器安装不应报错"""
        config = LogConfig(formatter="text", redirect="stdout")
        install_logs(config)

    def test_install_file_redirect(self, tmp_path):
        """文件输出安装"""
        config = LogConfig(
            redirect="file",
            filepath=str(tmp_path / "logs"),
        )
        install_logs(config)
        assert (tmp_path / "logs").exists()

    def test_install_clears_existing_handlers(self):
        """install_logs 应清理已有的 handler"""
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        old_count = len(root.handlers)

        install_logs(LogConfig(redirect="stdout"))
        # 安装后应只有 1 个 handler（stdout）
        assert len(root.handlers) == 1


# ============ get_logger / LoggerAdapter 测试 ============

class TestGetLogger:
    """get_logger 测试"""

    def test_get_logger_basic(self):
        """基本获取"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_with_request_id(self):
        """带 request_id 返回 LoggerAdapter"""
        logger = get_logger("test_module", request_id="req-123")
        assert isinstance(logger, LoggerAdapter)

    def test_logger_adapter_process(self):
        """LoggerAdapter 应在消息前添加 request_id"""
        base_logger = logging.getLogger("adapter_test")
        adapter = LoggerAdapter(base_logger, {"request_id": "req-abc"})
        msg, kwargs = adapter.process("Hello", {})
        assert "[request_id=req-abc]" in msg
        assert "Hello" in msg

    def test_logger_adapter_no_request_id(self):
        """无 request_id 时不添加前缀"""
        base_logger = logging.getLogger("adapter_test2")
        adapter = LoggerAdapter(base_logger, {"request_id": ""})
        msg, kwargs = adapter.process("Hello", {})
        assert msg == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
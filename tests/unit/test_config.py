#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置加载器模块测试
"""

import os
import pytest
from pathlib import Path

from pydantic import BaseModel
from peek.config.loader import ConfigLoader, load_config, load_config_from_file


# ============ 测试用 Pydantic 模型 ============

class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080


class AppConfig(BaseModel):
    name: str = "test"
    debug: bool = False
    web: WebConfig = WebConfig()


# ============ ConfigLoader 测试 ============

class TestConfigLoader:
    """ConfigLoader 核心功能测试"""

    def test_load_file_yaml(self, tmp_path):
        """测试从 YAML 文件加载"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "name: my-app\n"
            "debug: true\n"
            "web:\n"
            "  host: 127.0.0.1\n"
            "  port: 9090\n"
        )
        loader = ConfigLoader()
        loader.load_file(config_file)
        assert loader.get("name") == "my-app"
        assert loader.get("debug") is True
        assert loader.get("web.host") == "127.0.0.1"
        assert loader.get("web.port") == 9090

    def test_load_file_not_found(self):
        """加载不存在的文件应抛出 FileNotFoundError"""
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file("/nonexistent/path/config.yaml")

    def test_load_empty_yaml(self, tmp_path):
        """空 YAML 文件不应报错"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        loader = ConfigLoader()
        loader.load_file(config_file)
        assert loader.data == {}

    def test_chain_call(self, tmp_path):
        """load_file 应支持链式调用"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n")
        loader = ConfigLoader()
        result = loader.load_file(config_file)
        assert result is loader  # 返回 self

    def test_get_with_default(self):
        """get 不存在的 key 应返回默认值"""
        loader = ConfigLoader()
        assert loader.get("nonexistent") is None
        assert loader.get("nonexistent", "default") == "default"

    def test_get_nested_key(self, tmp_path):
        """get 应支持点分隔的嵌套键"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "a:\n"
            "  b:\n"
            "    c: deep_value\n"
        )
        loader = ConfigLoader()
        loader.load_file(config_file)
        assert loader.get("a.b.c") == "deep_value"
        assert loader.get("a.b.missing", "fallback") == "fallback"

    def test_deep_merge(self, tmp_path):
        """多文件加载应深度合并"""
        file1 = tmp_path / "base.yaml"
        file1.write_text(
            "web:\n"
            "  host: 0.0.0.0\n"
            "  port: 8080\n"
            "name: base\n"
        )
        file2 = tmp_path / "override.yaml"
        file2.write_text(
            "web:\n"
            "  port: 9090\n"
            "debug: true\n"
        )
        loader = ConfigLoader()
        loader.load_file(file1).load_file(file2)
        # port 被覆盖
        assert loader.get("web.port") == 9090
        # host 保留
        assert loader.get("web.host") == "0.0.0.0"
        # name 保留
        assert loader.get("name") == "base"
        # debug 新增
        assert loader.get("debug") is True

    def test_data_returns_copy(self, tmp_path):
        """data 属性应返回副本"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: value\n")
        loader = ConfigLoader()
        loader.load_file(config_file)
        data = loader.data
        data["key"] = "modified"
        assert loader.get("key") == "value"  # 原始数据不受影响

    def test_to_model(self, tmp_path):
        """to_model 应正确转换为 Pydantic 模型"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "name: my-app\n"
            "debug: true\n"
            "web:\n"
            "  host: 127.0.0.1\n"
            "  port: 9090\n"
        )
        loader = ConfigLoader()
        loader.load_file(config_file)
        model = loader.to_model(AppConfig)
        assert isinstance(model, AppConfig)
        assert model.name == "my-app"
        assert model.debug is True
        assert model.web.host == "127.0.0.1"
        assert model.web.port == 9090


class TestConfigLoaderEnv:
    """环境变量加载测试"""

    def test_load_env_basic(self, monkeypatch):
        """测试从环境变量加载"""
        monkeypatch.setenv("APP_NAME", "env-app")
        monkeypatch.setenv("APP_DEBUG", "true")
        loader = ConfigLoader(env_prefix="APP")
        loader.load_env()
        assert loader.get("name") == "env-app"
        assert loader.get("debug") is True

    def test_load_env_nested(self, monkeypatch):
        """测试嵌套环境变量"""
        monkeypatch.setenv("MYAPP_WEB_PORT", "9999")
        loader = ConfigLoader(env_prefix="MYAPP")
        loader.load_env()
        assert loader.get("web.port") == 9999

    def test_load_env_custom_prefix(self, monkeypatch):
        """测试自定义前缀"""
        monkeypatch.setenv("CUSTOM_KEY", "custom_value")
        loader = ConfigLoader()
        loader.load_env(prefix="CUSTOM")
        assert loader.get("key") == "custom_value"

    def test_load_env_chain(self, monkeypatch):
        """load_env 应支持链式调用"""
        loader = ConfigLoader()
        result = loader.load_env()
        assert result is loader

    def test_parse_env_bool_true(self):
        """环境变量布尔值解析 - true"""
        loader = ConfigLoader()
        for val in ("true", "yes", "1", "on", "True", "YES"):
            assert loader._parse_env_value(val) is True

    def test_parse_env_bool_false(self):
        """环境变量布尔值解析 - false"""
        loader = ConfigLoader()
        for val in ("false", "no", "0", "off", "False", "NO"):
            assert loader._parse_env_value(val) is False

    def test_parse_env_int(self):
        """环境变量整数解析"""
        loader = ConfigLoader()
        assert loader._parse_env_value("42") == 42
        assert isinstance(loader._parse_env_value("42"), int)

    def test_parse_env_float(self):
        """环境变量浮点数解析"""
        loader = ConfigLoader()
        assert loader._parse_env_value("3.14") == 3.14

    def test_parse_env_list(self):
        """环境变量列表解析（逗号分隔）"""
        loader = ConfigLoader()
        result = loader._parse_env_value("a, b, c")
        assert result == ["a", "b", "c"]

    def test_parse_env_string(self):
        """普通字符串不做特殊转换"""
        loader = ConfigLoader()
        assert loader._parse_env_value("hello") == "hello"


class TestLoadConfigHelpers:
    """辅助函数测试"""

    def test_load_config_from_dict(self):
        """从字典加载配置"""
        data = {"name": "dict-app", "debug": True, "web": {"host": "::0", "port": 3000}}
        model = load_config(data, model_class=AppConfig)
        assert model.name == "dict-app"
        assert model.web.port == 3000

    def test_load_config_no_model_class(self):
        """未指定 model_class 应抛出 ValueError"""
        with pytest.raises(ValueError, match="model_class must be specified"):
            load_config({"key": "val"}, model_class=None)

    def test_load_config_from_file(self, tmp_path):
        """从文件加载并转为模型"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "name: file-app\n"
            "web:\n"
            "  port: 7070\n"
        )
        model = load_config_from_file(config_file, model_class=AppConfig, load_env=False)
        assert model.name == "file-app"
        assert model.web.port == 7070

    def test_load_config_from_file_no_model(self, tmp_path):
        """load_config_from_file 未指定 model_class 应抛出 ValueError"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: val\n")
        with pytest.raises(ValueError):
            load_config_from_file(config_file, model_class=None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
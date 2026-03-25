#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共服务运行选项基类模块

提供所有服务共用的：
- WebConfig / LogConfig 配置 dataclass
- BaseServerRunOptions 配置加载基类
- BaseCompletedOptions 启动流程基类（模板方法模式）

上层框架（如 tide）继承这些基类，实现各自的业务差异部分。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from peek.config.schema import MonitorConfig

logger = logging.getLogger(__name__)


# ============================================================
# 公共配置 dataclass
# ============================================================

@dataclass
class WebConfig:
    """Web 服务器配置。"""

    bind_address: Dict[str, Any] = field(default_factory=lambda: {"port": 10000})
    grpc: Dict[str, Any] = field(default_factory=dict)
    http: Dict[str, Any] = field(default_factory=dict)
    debug: Dict[str, Any] = field(default_factory=dict)
    open_telemetry: Dict[str, Any] = field(default_factory=dict)
    qps_limit: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogConfig:
    """日志配置。"""

    formatter: str = "glog"
    level: str = "debug"
    filepath: str = "./log"
    max_age: str = "604800s"
    max_count: int = 200
    rotate_interval: str = "3600s"
    rotate_size: int = 104857600
    report_caller: bool = True
    redirect: str = "stdout"


# ============================================================
# 公共配置解析函数
# ============================================================

def parse_web_config(data: Dict[str, Any], default_port: int = 10000) -> WebConfig:
    """解析 Web 配置。

    Args:
        data: 原始配置字典
        default_port: 默认端口号，各服务可指定不同端口
    """
    return WebConfig(
        bind_address=data.get("bind_address", {"port": default_port}),
        grpc=data.get("grpc", {}),
        http=data.get("http", {}),
        debug=data.get("debug", {}),
        open_telemetry=data.get("open_telemetry", {}),
        qps_limit=data.get("qps_limit", {}),
    )


def parse_log_config(data: Dict[str, Any]) -> LogConfig:
    """解析日志配置。"""
    return LogConfig(
        formatter=data.get("formatter", "glog"),
        level=data.get("level", "debug"),
        filepath=data.get("filepath", "./log"),
        max_age=data.get("max_age", "604800s"),
        max_count=data.get("max_count", 200),
        rotate_interval=data.get("rotate_interval", "3600s"),
        rotate_size=data.get("rotate_size", 104857600),
        report_caller=data.get("report_caller", True),
        redirect=data.get("redirect", "stdout"),
    )


def parse_monitor_config(data: Dict[str, Any]) -> MonitorConfig:
    """解析监控配置。"""
    return MonitorConfig.model_validate(data)


# ============================================================
# 公共配置加载基类
# ============================================================

class BaseServerRunOptions:
    """服务器运行选项基类。

    子类需要：
    1. 设置 default_port 类属性
    2. 覆写 _load_business_config() 加载业务特有配置
    3. 覆写 _init_default_business_config() 初始化业务默认配置
    """

    default_port: int = 10000  # 子类覆写

    def __init__(self, config_file: str):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.web_config: Optional[WebConfig] = None
        self.log_config: Optional[LogConfig] = None
        self.monitor_config: Optional[MonitorConfig] = None
        self._load_config()

    def _load_config(self):
        """从 YAML 文件加载配置。"""
        config_path = Path(self.config_file)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}

            # 解析公共配置
            self.web_config = parse_web_config(
                self.config.get("web", {}), self.default_port
            )
            self.log_config = parse_log_config(self.config.get("log", {}))
            self.monitor_config = parse_monitor_config(
                self.config.get("monitor", {})
            )

            # 加载业务特有配置（子类实现）
            self._load_business_config()
        else:
            logger.warning("Config file not found: %s", config_path)
            self.web_config = WebConfig(
                bind_address={"port": self.default_port}
            )
            self.log_config = LogConfig()
            self.monitor_config = MonitorConfig()
            self._init_default_business_config()

    def _load_business_config(self):
        """加载业务特有配置。子类覆写此方法。"""
        pass

    def _init_default_business_config(self):
        """初始化业务默认配置（配置文件不存在时）。子类覆写此方法。"""
        pass

    def complete(self) -> "BaseCompletedOptions":
        """完成设置并返回 CompletedOptions。子类应覆写此方法返回具体类型。"""
        raise NotImplementedError("子类需要覆写 complete() 方法")


# ============================================================
# 公共启动流程基类（模板方法模式）
# ============================================================

class BaseCompletedOptions(ABC):
    """已完成的服务器运行选项基类。

    使用模板方法模式定义公共启动流程骨架：
    1. install_logs（公共）
    2. install_config（子类实现）
    3. create_web_server（公共）
    4. install_business（子类实现：vLLM / MySQL / Redis 等）
    5. install_opentelemetry（公共）
    5.5. install_healthz（公共，子类可覆写添加自定义检查器）
    6. install_web_handler（子类实现）
    7. install_monitor（公共）
    8. run server（公共）
    """

    # 子类必须设置服务名
    _service_name: str = "app"

    def __init__(self, options: BaseServerRunOptions):
        self._options = options

    @property
    def options(self) -> BaseServerRunOptions:
        """获取底层选项。"""
        return self._options

    async def run(self):
        """运行服务器（模板方法）。"""
        logger.info("Starting %s", self._service_name)

        # 1. 安装日志（公共）
        self._install_logs()

        # 2. 安装配置（子类实现，各自有不同的 provider）
        self._install_config()

        # 3. 创建 Web 服务器（公共）
        web_server = await self._create_web_server()

        # 4. 安装业务组件（子类实现：vLLM / MySQL / Redis 等）
        await self._install_business(web_server)

        # 5. 安装 OpenTelemetry（公共）
        await self._install_opentelemetry(web_server)

        # 5.5 安装健康检查控制器（公共，子类可覆写添加自定义检查器）
        self._install_healthz(web_server)

        # 6. 安装 Web 处理器（子类实现）
        self._install_web_handler(web_server)

        # 7. 安装监控插件（公共）
        await self._install_monitor(web_server)

        # 8. 运行服务器（公共）
        if hasattr(web_server, 'run_async'):
            await web_server.run_async()
        else:
            await web_server.run()

    # ---- 公共步骤 ----

    def _install_logs(self):
        """安装日志配置（公共）。"""
        from peek.plugins.logs import install_logs

        install_logs(self._options.log_config)

    async def _create_web_server(self):
        """创建并配置 Web 服务器（公共）。"""
        from peek.net.webserver.factory import create_web_server

        return await create_web_server(self._options.web_config)

    async def _install_opentelemetry(self, web_server):
        """安装 OpenTelemetry（公共）。"""
        from peek.plugins.otel import install_opentelemetry

        await install_opentelemetry(
            self._options.web_config.open_telemetry,
            web_server
        )

    async def _install_monitor(self, web_server):
        """安装监控插件（公共）。"""
        from peek.plugins.monitor import install_monitor

        await install_monitor(self._options.monitor_config, web_server)

    def _install_healthz(self, web_server):
        """安装健康检查控制器（公共）。

        默认安装基础的 HealthzController（提供 /healthz, /livez, /readyz）。
        子类可覆写此方法添加额外的 readyz/livez 检查器。
        """
        from peek.net.webserver.healthz import HealthzController

        controller = HealthzController()
        web_server.install_healthz_controller(controller)
        logger.info("Health check controller installed (/healthz, /livez, /readyz)")

    # ---- 子类必须实现的抽象方法 ----

    @abstractmethod
    def _install_config(self):
        """安装配置到 provider（子类实现，各自有不同的 provider 路径）。"""
        ...

    @abstractmethod
    async def _install_business(self, web_server):
        """安装业务组件（子类实现：vLLM / MySQL / Redis 等）。"""
        ...

    @abstractmethod
    def _install_web_handler(self, web_server):
        """安装 Web 处理器（子类实现）。"""
        ...

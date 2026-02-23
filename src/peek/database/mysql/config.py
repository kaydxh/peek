#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL 配置模型

对应 Go 版本 golang/pkg/database/mysql/mysql.proto 中的配置定义。
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from peek.time.parse import parse_duration


class MySQLConfig(BaseModel):
    """
    MySQL 配置模型

    对应 Go 版本 Mysql proto 配置，包含连接地址、认证、连接池等参数。
    """

    enabled: bool = Field(default=False, description="是否启用 MySQL")
    address: str = Field(default="localhost:3306", description="MySQL 地址 (host:port)")
    username: str = Field(default="root", description="用户名")
    password: str = Field(default="", description="密码")
    db_name: str = Field(default="", description="数据库名")
    max_connections: int = Field(default=100, ge=0, description="最大连接数")
    max_idle_connections: int = Field(default=10, ge=0, description="最大空闲连接数")
    dial_timeout: float = Field(default=5.0, ge=0, description="连接超时时间（秒）")
    read_timeout: float = Field(default=0, ge=0, description="读取超时时间（秒）")
    write_timeout: float = Field(default=0, ge=0, description="写入超时时间（秒）")
    max_life_time: float = Field(default=0, ge=0, description="连接最大生命周期（秒），0 表示不过期")
    max_wait_duration: float = Field(default=20.0, ge=0, description="等待连接最大时间（秒）")
    fail_after_duration: float = Field(default=60.0, ge=0, description="超过此时间后放弃连接（秒）")
    interpolate_params: bool = Field(default=True, description="是否插值参数")

    @field_validator(
        "dial_timeout", "read_timeout", "write_timeout",
        "max_life_time", "max_wait_duration", "fail_after_duration",
        mode="before",
    )
    @classmethod
    def parse_duration_field(cls, v):
        return parse_duration(v)

    @property
    def host(self) -> str:
        """解析地址获取 host"""
        parts = self.address.split(":")
        return parts[0]

    @property
    def port(self) -> int:
        """解析地址获取 port"""
        parts = self.address.split(":")
        return int(parts[1]) if len(parts) > 1 else 3306

    @property
    def dsn(self) -> str:
        """生成 SQLAlchemy 异步 DSN"""
        return f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.db_name}"

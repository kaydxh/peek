#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Redis 配置模型

对应 Go 版本 golang/pkg/database/redis/redis.proto 中的配置定义。
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from peek.time.parse import parse_duration


class RedisConfig(BaseModel):
    """
    Redis 配置模型

    对应 Go 版本 Redis proto 配置，支持单节点和 Sentinel 模式。
    """

    enabled: bool = Field(default=False, description="是否启用 Redis")
    addresses: List[str] = Field(default_factory=lambda: ["localhost:6379"], description="Redis 地址列表")
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")
    db: int = Field(default=0, ge=0, description="数据库编号")
    max_connections: int = Field(default=100, ge=0, description="最大连接数（对应 Go 版本 pool_size）")
    max_idle_connections: int = Field(default=10, ge=0, description="最小空闲连接数（对应 Go 版本 min_idle_conns）")
    dial_timeout: float = Field(default=5.0, ge=0, description="连接超时时间（秒）")
    read_timeout: float = Field(default=5.0, ge=0, description="读取超时时间（秒）")
    write_timeout: float = Field(default=5.0, ge=0, description="写入超时时间（秒）")
    max_wait_duration: float = Field(default=20.0, ge=0, description="等待连接最大时间（秒）")
    fail_after_duration: float = Field(default=300.0, ge=0, description="超过此时间后放弃连接（秒）")
    master_name: str = Field(default="mymaster", description="Sentinel 模式的 master 名称")
    ssl: bool = Field(default=False, description="是否启用 SSL")
    health_check_interval: int = Field(default=30, ge=0, description="连接池健康检查间隔（秒），0 表示禁用")

    @field_validator(
        "dial_timeout", "read_timeout", "write_timeout",
        "max_wait_duration", "fail_after_duration",
        mode="before",
    )
    @classmethod
    def parse_duration_field(cls, v):
        return parse_duration(v)

    @property
    def host(self) -> str:
        """获取第一个地址的 host"""
        if not self.addresses:
            return "localhost"
        addr = self.addresses[0]
        if ":" in addr:
            return addr.rsplit(":", 1)[0]
        return addr

    @property
    def port(self) -> int:
        """获取第一个地址的 port"""
        if not self.addresses:
            return 6379
        addr = self.addresses[0]
        if ":" in addr:
            return int(addr.rsplit(":", 1)[1])
        return 6379

    @property
    def is_sentinel(self) -> bool:
        """是否为 Sentinel 模式（多地址）"""
        return len(self.addresses) > 1

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
时间解析工具

提供时间字符串解析能力，支持多种格式。
"""

import re
from typing import Union


def parse_duration(value: Union[str, int, float, None]) -> float:
    """
    解析时间字符串

    支持格式：
    - 纯数字：直接作为秒
    - "10s": 10 秒
    - "5m": 5 分钟
    - "1h": 1 小时
    - "1h30m": 1 小时 30 分钟
    - "100ms": 100 毫秒
    - "500us": 500 微秒
    - "1000ns": 1000 纳秒

    Args:
        value: 时间值，支持 str/int/float/None

    Returns:
        秒数（float）
    """
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    value = value.strip()
    if not value:
        return 0.0

    # 纯数字
    try:
        return float(value)
    except ValueError:
        pass

    # 解析带单位的时间
    total_seconds = 0.0
    pattern = r"(\d+(?:\.\d+)?)\s*(ms|us|ns|h|m|s)?"

    for match in re.finditer(pattern, value, re.IGNORECASE):
        num = float(match.group(1))
        unit = (match.group(2) or "s").lower()

        if unit == "h":
            total_seconds += num * 3600
        elif unit == "m":
            total_seconds += num * 60
        elif unit == "s":
            total_seconds += num
        elif unit == "ms":
            total_seconds += num / 1000
        elif unit == "us":
            total_seconds += num / 1000000
        elif unit == "ns":
            total_seconds += num / 1000000000

    return total_seconds

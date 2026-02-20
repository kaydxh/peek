# -*- coding: utf-8 -*-
"""Video Resize - 视频帧智能缩放工具

提供与 Qwen2-VL 视觉预处理器一致的智能缩放逻辑，
可独立用于各模块的帧图片分辨率控制。
"""

import logging
import math
from typing import Tuple

logger = logging.getLogger(__name__)


def smart_resize(
    width: int,
    height: int,
    min_pixels: int,
    max_pixels: int,
    patch_size: int = 28,
) -> Tuple[int, int]:
    """计算智能缩放后的目标尺寸

    与 Qwen2-VL 视觉预处理器的 smart_resize 逻辑一致：
    1. 如果像素总数超过 max_pixels，按比例缩小
    2. 如果像素总数低于 min_pixels，按比例放大
    3. 宽高对齐到 patch_size 的倍数

    Args:
        width: 原始宽度
        height: 原始高度
        min_pixels: 最小像素总数（对应 shortest_edge）
        max_pixels: 最大像素总数（对应 longest_edge）
        patch_size: ViT patch 大小，默认 28

    Returns:
        Tuple[int, int]: (new_width, new_height)
    """
    if width <= 0 or height <= 0:
        return width, height

    current_pixels = width * height

    # 如果超过最大像素限制，按比例缩小
    if max_pixels > 0 and current_pixels > max_pixels:
        scale = math.sqrt(max_pixels / current_pixels)
        width = int(width * scale)
        height = int(height * scale)

    # 如果低于最小像素限制，按比例放大
    if min_pixels > 0 and width * height < min_pixels:
        scale = math.sqrt(min_pixels / (width * height))
        width = int(width * scale)
        height = int(height * scale)

    # 对齐到 patch_size 的倍数（四舍五入到最近的倍数）
    width = max(patch_size, round(width / patch_size) * patch_size)
    height = max(patch_size, round(height / patch_size) * patch_size)

    return width, height


def smart_resize_image(
    img,
    shortest_edge: int = 0,
    longest_edge: int = 0,
    patch_size: int = 28,
):
    """对帧图片进行智能分辨率缩放

    模拟 Qwen2-VL 视觉预处理器的 smart resize 逻辑：
    - 如果像素总数低于 shortest_edge，则放大
    - 如果像素总数高于 longest_edge，则缩小
    - 最终宽高对齐到 patch_size(28) 的倍数

    Args:
        img: PIL Image 对象
        shortest_edge: 最短边像素总数下限，0 表示不限制
        longest_edge: 最长边像素总数上限，0 表示不限制
        patch_size: ViT patch 大小，默认 28

    Returns:
        PIL Image: 缩放后的图片（如果未设置 edge 参数则返回原图）
    """
    if shortest_edge <= 0 and longest_edge <= 0:
        return img

    width, height = img.size
    new_width, new_height = smart_resize(
        width, height, shortest_edge, longest_edge, patch_size
    )

    if new_width != width or new_height != height:
        from PIL import Image as PILImage
        img = img.resize((new_width, new_height), PILImage.LANCZOS)
        logger.debug(
            f"帧图片缩放: ({width}x{height}) -> ({new_width}x{new_height}), "
            f"pixels: {width * height} -> {new_width * new_height}"
        )

    return img

# -*- coding: utf-8 -*-
"""图像预处理工具函数

提供通用的图像预处理能力，支持：
- 图片模式转换（RGBA/LA/P → RGB）
- 等比缩放（按最长边或最大像素数）
- JPEG 压缩与 Base64 编码
- Data URL 解析
"""

import base64
import io
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认图像处理配置
DEFAULT_IMAGE_SETTINGS: Dict[str, Any] = {
    "max_long_edge": 1024,
    "max_pixels": None,  # 如 1280*1280，与 max_long_edge 二选一
    "resize_enabled": True,
    "jpeg_quality": 95,
}


def normalize_image_bytes(
    image_bytes: bytes,
    max_long_edge: Optional[int] = None,
    max_pixels: Optional[int] = None,
    jpeg_quality: int = 95,
    resize_enabled: bool = True,
) -> Tuple[str, str]:
    """图片字节预处理，返回 (base64, mime_type)。

    对图片进行模式转换（RGBA/LA/P → RGB）和等比缩放预处理，
    最终输出 JPEG 格式的 Base64 编码。

    Args:
        image_bytes: 原始图片字节数据
        max_long_edge: 最长边限制（像素），超过则等比缩放。与 max_pixels 二选一。
        max_pixels: 最大像素数限制（如 1280*1280=1638400），超过则等比缩放。
        jpeg_quality: JPEG 压缩质量 (1-100)
        resize_enabled: 是否启用缩放

    Returns:
        Tuple[str, str]: (base64_encoded_image, mime_type)
    """
    try:
        from PIL import Image
    except ImportError:
        # 如果没有 PIL，直接返回原始 base64
        logger.warning("PIL 未安装，跳过图像预处理")
        return base64.b64encode(image_bytes).decode("utf-8"), "image/jpeg"

    image = Image.open(io.BytesIO(image_bytes))

    # 模式转换：确保输出为 RGB
    if image.mode in ("RGBA", "LA", "P"):
        if image.mode == "P":
            image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        mask = image.split()[-1] if image.mode in ("RGBA", "LA") else None
        background.paste(image, mask=mask)
        image = background
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # 等比缩放
    if resize_enabled:
        width, height = image.size
        scale = 1.0

        if max_long_edge is not None:
            long_edge = max(width, height)
            if long_edge > max_long_edge:
                scale = max_long_edge / long_edge
        elif max_pixels is not None:
            total_pixels = width * height
            if total_pixels > max_pixels:
                scale = (max_pixels / float(total_pixels)) ** 0.5

        if scale < 1.0:
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS,
            )

    # 转换为 JPEG 并编码
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=jpeg_quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8"), "image/jpeg"


def prepare_base64_image(
    base64_data: str,
    max_long_edge: Optional[int] = None,
    max_pixels: Optional[int] = None,
    jpeg_quality: int = 95,
    resize_enabled: bool = True,
) -> Tuple[str, str]:
    """预处理 Base64 编码的图片数据。

    支持 Data URL 格式（data:image/xxx;base64,...）和纯 Base64 字符串。
    解码后进行图像预处理，返回处理后的 Base64 和 MIME 类型。

    Args:
        base64_data: Base64 编码的图片数据（支持 Data URL 格式）
        max_long_edge: 最长边限制（像素）
        max_pixels: 最大像素数限制
        jpeg_quality: JPEG 压缩质量 (1-100)
        resize_enabled: 是否启用缩放

    Returns:
        Tuple[str, str]: (processed_base64, mime_type)
    """
    # 解析 Data URL
    if base64_data.startswith("data:") and ";base64," in base64_data:
        header, payload = base64_data.split(",", 1)
        raw_bytes = base64.b64decode(payload)
    else:
        raw_bytes = base64.b64decode(base64_data)

    return normalize_image_bytes(
        raw_bytes,
        max_long_edge=max_long_edge,
        max_pixels=max_pixels,
        jpeg_quality=jpeg_quality,
        resize_enabled=resize_enabled,
    )

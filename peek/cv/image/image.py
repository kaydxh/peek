#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2
import numpy as np


def resize_pad_image(inp_img, target_width=None, target_height=None):
    """resize_image_pad to resize and pad image to a given target size"""
    h, w, c = inp_img.shape
    size = max(h, w)
    padding_h = (size - h) // 2
    padding_w = (size - w) // 2

    border_img = cv2.copyMakeBorder(
        inp_img,
        top=padding_h,
        bottom=padding_h,
        left=padding_w,
        right=padding_w,
        borderType=cv2.BORDER_CONSTANT,
        value=[0, 0, 0],
    )
    if (not target_width) or (not target_height):
        return border_img

    resize_img = cv2.resize(
        border_img, (target_width, target_height), interpolation=cv2.INTER_AREA
    )
    return resize_img


def resize_crop_image(inp_img, target_width=None, target_height=None):
    """resize_crop_image to resize and crop image and remove padded area"""
    if (not target_width) or (not target_height):
        return inp_img
    h, w = target_height, target_width
    size = max(h, w)
    padding_h = (size - h) // 2
    padding_w = (size - w) // 2

    resize_img = cv2.resize(
        inp_img, (w + 2 * padding_w, h + 2 * padding_h), interpolation=cv2.INTER_NEAREST
    )
    return resize_img[padding_h : padding_h + h, padding_w : padding_w + w]


def edge_strip(inp_img, strip_len=None, direction="row"):
    """edge_strip to strip image row or col"""
    x0, y0, x1, y1 = 0, 0, inp_img.shape[1], inp_img.shape[0]
    if not strip_len:
        return [x0, y0, x1, y1]

    sum_idx = 0 if direction == "row" else 1
    scores = np.sum(inp_img, axis=sum_idx)
    score_head = scores[:strip_len]
    score_tail = scores[: -strip_len - 1 : -1]
    cumsum_head = np.cumsum(score_head)
    cumsum_tail = np.cumsum(score_tail)
    sums = np.array(
        [cumsum_head[i] + cumsum_tail[strip_len - i - 1] for i in range(strip_len)]
    )
    start_idx = np.argmin(sums)

    if direction == "row":
        x0 = start_idx
        x1 -= strip_len - start_idx
    else:
        y0 = start_idx
        y1 -= strip_len - start_idx

    return [x0, y0, x1, y1]


def erode(inp_img, ratio):
    """erode to strip image by ratio(w/h)"""
    if ratio <= 0:
        return None
    h, w = inp_img.shape
    if w / h == ratio:
        return [0, 0, w, h]
    if w / h > ratio:
        target_w = int(h * ratio)
        strip_len = w - target_w
        return edge_strip(inp_img, strip_len, direction="row")
    if w / h < ratio:
        target_h = int(w / ratio)
        strip_len = h - target_h
        return edge_strip(inp_img, strip_len, direction="col")

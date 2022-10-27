#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2


def resize_pad_image(inp_img, target_width=None, target_height=None):
    """ resize_image_pad to resize and pad image to a given target size
    """
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
    """ resize_crop_image to resize and crop image
    """
    if (not target_width) or (not target_height):
        return inp_img
    h, w = target_width, target_height
    size = max(h, w)
    padding_h = (size - h) // 2
    padding_w = (size - w) // 2

    resize_img = cv2.resize(
        inp_img, (w + 2 * padding_w, h + 2 * padding_h), interpolation=cv2.INTER_NEAREST
    )
    return resize_img[padding_h : padding_h + h, padding_w : padding_w + w]

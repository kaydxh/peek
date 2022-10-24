#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2

def resize_image_pad(inp_img, target_width=None, target_height=None):
    """ resize_image_pad to resize and pad image to a given target size
    """
    h, w, c = inp_img.shape
    size = max(h, w)
    padding_h = (size - h) // 2
    padding_w = (size - w) // 2
    
    border_img = cv2.copyMakeBorder(inp_img,  top=padding_h, bottom=padding_h,
            left=padding_w, right=padding_w,
            borderType=cv2.BORDER_CONSTANT, value=[0, 0, 0])
    if (not target_width) or (not target_height):
        return border_img 

    resize_img = cv2.resize(border_img, (target_width, target_height),
            interpolation=cv2.INTER_AREA)
    return resize_img


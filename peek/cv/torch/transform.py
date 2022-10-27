#!/usr/bin/env python
# -*- coding: utf-8 -*-

import peek.cv.image.image as image_
import numpy as np
import torchvision.transforms as transforms
import torch

def normalize_img_float32(inp_img, target_width=256, target_height=256):
    """ normalize_img normal distribution
    """
    inp_img = inp_img.astype(np.float32)
    inp_img = image_.resize_image_pad(inp_img, target_width=target_width,
             target_height=target_height)
    # normalize
    inp_img /= 255.0
    # turn a tensor of shape [width, height, channels] into [channels, height, width] for the CNN
    inp_img = np.transpose(inp_img, axes=(2, 0, 1))
    inp_img = torch.from_numpy(inp_img).float()
    inp_img = transforms.Normalize(
		mean=[0.485, 0.456, 0.406],
		std=[0.229, 0.224, 0.225])(inp_img)
    return inp_img

def normalize_img_uint8(inp_img, target_width=256, target_height=256):
    """ normalize_img normal distribution
    """
    inp_img = image_.resize_image_pad(inp_img, target_width=target_width,
             target_height=target_height)
    # normalize
    noramlize_tranform = transforms.Compose([
         transforms.ToPILImage(),
         # transforms.Resize((256, 256)),
         # normalize and to tensor
         transforms.ToTensor(),
         transforms.Normalize(
		     mean=[0.485, 0.456, 0.406],
		     std=[0.229, 0.224, 0.225])
         ])
    inp_img = noramlize_tranform(inp_img)
    return inp_img


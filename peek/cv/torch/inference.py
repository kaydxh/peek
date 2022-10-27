#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch

def forward(loaded, inp_img):
    with torch.no_grad():
        pred_masks, _ = loaded(inp_img)
    return pred_masks


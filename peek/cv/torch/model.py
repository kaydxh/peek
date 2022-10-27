#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch
import peek.cv.torch.device as device_ 

def load_model_with_device_id(path, device_id):
    device = device_.Device(device_id)
    model = torch.jit.load(path, map_location=device.get_device())
    model.eval()
    if device.is_cpu():
       return model.cpu()
    return  model.cuda()


#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import cv2
import numpy as np
import torch
from peek.cv.torch.device import get_avaliable_devices
import peek.cv.torch.model as model_
import peek.cv.torch.transform as transform_
import peek.cv.torch.inference as inference_


class TestTorchInference(unittest.TestCase):
    def test_inference(self):
        model_path = "./testdata/saliency_traced_cpu.pt"
        if not os.path.exists(model_path):
            print(f"{model_path} is not exist")
            return
        loaded = model_.load_model_with_device_id(model_path, -1)

        img_path = "./testdata/test.jpg"
        if not os.path.exists(img_path):
            print(f"{img_path} is not exist")
            return

        inp_img = cv2.imread(img_path)
        inp_img = transform_.normalize_img_float32(inp_img)
        inp_img = inp_img.unsqueeze(0)

        pred_masks = inference_.forward(loaded, inp_img)
        print(pred_masks)
        pred_masks_raw = np.squeeze(pred_masks.numpy(), axis=(0, 1))
        print(pred_masks_raw)


if __name__ == "__main__":
    unittest.main()

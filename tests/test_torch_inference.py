#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import cv2
from peek.cv.torch.device import get_avaliable_devices
import peek.cv.torch.model as model_
import peek.cv.torch.transform as transform_ 

class TestTorchInference(unittest.TestCase):

    def test_inference(self):
        img_path = "./testdata/test.jpg"
        if not os.path.exists(img_path):
            print(f"{img_path} is not exist")
            return
        inp_img = cv2.imread(img_path)

        model_path = "./testdata/saliency_traced.pt"
        if not os.path.exists(model_path):
            print(f"{model_path} is not exist")
            return
        model_.load_model_with_device_id(model_path, -1)
        inp_img = transform_.normalize_img(inp_img)

if __name__ == '__main__':
    unittest.main()

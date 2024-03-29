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
import peek.cv.image.image as image_


class TestTorchInference(unittest.TestCase):
    def pre_process(self, inp_img):
        inp_img = transform_.normalize_img_uint8(inp_img)
        inp_img = inp_img.unsqueeze(0)
        return inp_img

    def post_process(self, pred_masks, ori_w, ori_h):
        pred_masks_raw = np.squeeze(pred_masks.numpy(), axis=(0, 1))
        pred_masks_raw = image_.resize_crop_image(pred_masks_raw, ori_w, ori_h)
        # print(f'pred_masks_raw: {pred_masks_raw}')
        crop_box = image_.erode(pred_masks_raw, 5 / 4)
        return crop_box

    def test_inference(self):
        model_path = "./testdata/test_saliency_cpu.pt"
        if not os.path.exists(model_path):
            print(f"{model_path} is not exist")
            return
        loaded = model_.load_model_with_device_id(model_path, -1)

        img_path = "./testdata/test.jpg"
        if not os.path.exists(img_path):
            print(f"{img_path} is not exist")
            return

        inp_img = cv2.imread(img_path)
        h = inp_img.shape[0]
        w = inp_img.shape[1]
        print(f"origin w[{w}] h[{h}]")

        inp_img = self.pre_process(inp_img)
        pred_masks = inference_.forward(loaded, inp_img)
        result_box = self.post_process(pred_masks, w, h)
        print(f"result_box: {result_box}")


if __name__ == "__main__":
    unittest.main()

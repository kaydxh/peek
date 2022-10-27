#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import cv2
import peek.cv.image.image as image_


class TestImageResize(unittest.TestCase):
    def test_resize_pad_image(self):
        img_path = "./testdata/test.jpg"
        inp_img = cv2.imread(img_path)
        # inp_img = inp_img.astype("float32")
        target_img = image_.resize_pad_image(inp_img, 100, 200)
        cv2.imwrite("./testdata/test_target_resize_pad.jpg", target_img)

    def test_resize_crop_image(self):
        img_path = "./testdata/test.jpg"
        inp_img = cv2.imread(img_path)
        # inp_img = inp_img.astype("float32")
        target_img = image_.resize_crop_image(inp_img, 100, 200)
        cv2.imwrite("./testdata/test_target_resize_crop.jpg", target_img)


if __name__ == "__main__":
    unittest.main()

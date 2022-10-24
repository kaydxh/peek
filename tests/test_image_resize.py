#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import cv2
import peek.cv.image.resize as resize_

class TestImageResize(unittest.TestCase):
    def test_resize_image_pad(self):
         img_path = "./testdata/test.jpg"
         inp_img = cv2.imread(img_path)
         # inp_img = inp_img.astype("float32")
         target_img =  resize_.resize_image_pad(inp_img , 100, 200)
         cv2.imwrite("./testdata/test_target_f.jpg", target_img)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import cv2
import peek.cv.torch.transform as transform_ 
import torchvision.transforms as transforms

class TestTorchTransform(unittest.TestCase):
    def test_normalize_img(self):
         img_path = "./testdata/test.jpg"
         if not os.path.exists(img_path):
             print(f"{img_path} is not exist")
             return
         inp_img = cv2.imread(img_path)
         inp_img = inp_img.astype('float32')
         inp_img = transform_.normalize_img(inp_img)
         inp_img = transforms.ToPILImage()(inp_img).convert('RGB')
         inp_img.show()

if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import peek.cv.torch.model as model_


class TestTorchModel(unittest.TestCase):
    def test_load_model_with_device_id(self):
        model_path = "./testdata/test_saliency.pt"
        device_id = 1
        if not os.path.exists(model_path):
            print(f"{model_path} is not exist")
        model_.load_model_with_device_id(model_path, device_id)


if __name__ == "__main__":
    unittest.main()

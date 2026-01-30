#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.cv.torch.device as device_

# from peek.cv.torch.device import get_avaliable_devices


class TestTorchDevice(unittest.TestCase):
    def test_get_avaliable_devices(self):
        devices = device_.get_avaliable_devices(True, True)
        print(*devices, sep="\n")

    def test_get_devices(self):
        device = device_.Device(0)
        print(device.get_device())


if __name__ == "__main__":
    unittest.main()

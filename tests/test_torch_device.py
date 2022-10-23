#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from peek.cv.torch.device import get_avaliable_devices

class TestTorchDevice(unittest.TestCase):
    def test_get_avaliable_devices(self):
         devices = get_avaliable_devices(True, True)
         print(*devices, sep='\n')


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.net.ip as ip_

class TestNet(unittest.TestCase):
    def test_get_ip(self):
        ip = ip_.get_host_ip()
        print(ip)

if __name__ == "__main__":
    unittest.main()

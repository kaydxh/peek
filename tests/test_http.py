#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.net.http as http_

class TestHttp(unittest.TestCase):
    def test_http_get(self):
        response = http_.get("http://127.0.0.1:10000")
        print(response)

if __name__ == "__main__":
    unittest.main()

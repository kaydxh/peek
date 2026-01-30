#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.encoding.base64.base64 as base64_

class TestHttp(unittest.TestCase):
    def test_base_encode(self):
        base64_data = base64_.encode("./tests/testdata/test.jpg")
        print(base64_data)


if __name__ == "__main__":
    unittest.main()

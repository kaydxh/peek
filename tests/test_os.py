#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import sys
import unittest
# sys.path.append("..")
from peek.os.file import MakeDirAll


class TestOsFile(unittest.TestCase):
    def test_make_dir_all(self):
          MakeDirAll("mytest/0/1/2/3")


if __name__ == '__main__':
    unittest.main()

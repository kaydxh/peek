#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import sys
import unittest

# sys.path.append("..")
# from peek.os.file import MakeDirAll
import peek.os.file as file_
import peek.encoding.base64.base64 as base64_


class TestOsFile(unittest.TestCase):
    def test_make_dir_all(self):
         #file_.make_dir_all("mytest/0/1/2/3")
         pass

    def test_dump(self):
        data = {
                "session_id": "session_id",
                "image": base64_.encode("tests/testdata/test.jpg"),
                }
        
        file_.DumpJson("tests/testdata/output_dump.json", data)
    
if __name__ == "__main__":
    unittest.main()

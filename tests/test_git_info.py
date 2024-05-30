#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.git.git_info as git_

class TestGitInfo(unittest.TestCase):
    def test_get_git_info(self):
        file_path = "./test_git_info.py"
        git_repo = git_.get_repo_info(file_path)

    def test_get_file_path(self):
        file_path = "./test_git_info.py"
        git_dir = git_.get_file_repo_dir(file_path)

if __name__ == "__main__":
    unittest.main()

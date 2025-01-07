#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import peek.git.git_info as git_

# PYTHONPATH=$(pwd) python3 tests/test_git_info.py
class TestGitInfo(unittest.TestCase):
    def test_get_git_info(self):
        file_path = "./tests/test_git_info.py"
        git_repo = git_.get_repo_info(file_path)
        print(git_repo)

    def test_get_file_path(self):
        file_path = "./tests/test_git_info.py"
        git_dir = git_.get_file_repo_dir(file_path)
        print(git_dir)

if __name__ == "__main__":
    unittest.main()

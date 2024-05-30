#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import subprocess

def exec_cmd(cmd):
    """
    execute command
    :param cmd: command
    :return: result
    """
    try:
        out_bytes = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return out_bytes.decode("utf-8")
    except subprocess.CalledProcessError as err:
        out_bytes = err.output
        code = err.returncode
        return ""

def get_repo_info(file_path):
    """
     get repo info for file
     :param file_path: file path
     :return: repo info
    """
    get_repo_cmd = "cd {}; git config core.quotepath false; git remote -v"
    if os.path.isdir(file_path):
        cmd = get_repo_cmd.format(file_path)
    elif os.path.dirname(file_path):
        cmd = get_repo_cmd.format(os.path.dirname(file_path))
    else:
        cmd = get_repo_cmd.format(os.getcwd())
    try:
        shell_result = exec_cmd(cmd)
        if not shell_result:
            return ""
        re_result = re.search("origin\s+(.*)\s+\(fetch\)", shell_result)
        if re_result:
            repo = re_result.group("url").split("://")[-1]
        else:
            repo = re.search("(?P<url>@git[^\s]+)", shell_result).group("url")
        git_repo = repo.split("@")[-1].replace(":", "/")
        return git_repo
    except Exception as err:
        print("err:",err)
        return ""
    
def get_file_repo_dir(file_path):
    """
    get repo dir for file
    :param file_path: file path
    :return: repo path
    """
    get_repo_dir_cmd = "cd {}; git config core.quotepath false; git log --name-only --pretty=oneline {}"
    if os.path.isdir(file_path):
        print("err")
        return ""
    try:
        dir_name = os.path.dirname(file_path)
        if not dir_name:
            return ""
        file_name = file_path.rsplit("/", 1)[-1]
        cmd = get_repo_dir_cmd.format(dir_name, file_name)
        shell_result = exec_cmd(cmd)
        if not shell_result:
            return ""
        info = shell_result.split("\n")
        for line in info:
            if ".py" not in line or " " in line:
                continue
            else:
                return line
    except Exception as err:
        print("err:",err)
        return ""
    

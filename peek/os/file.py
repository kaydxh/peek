#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

def MakeDirAll(name):
    if not os.path.exists(name):
        os.makedirs(name, mode=0o755)


def Dump(output_file, content):
    with open(output_file, 'w') as f:
        f.write(content)
    

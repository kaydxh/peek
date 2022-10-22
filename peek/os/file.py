#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

def MakeDirAll(name):
    os.makedirs(name, mode=0o755)

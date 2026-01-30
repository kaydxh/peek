#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64

def encode(filepath):
    with open(filepath, "rb") as f:
        data = f.read()
        base64_data = base64.b64encode(data).decode('utf-8')
    return base64_data 

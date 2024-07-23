#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json

def MakeDirAll(name):
    if not os.path.exists(name):
        os.makedirs(name, mode=0o755)

def DumpJson(output_file, json_data):
    data = json.dumps(json_data, indent=4)
    with open(output_file, 'w') as f:
        f.write(data)
    

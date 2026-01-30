#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket

def get_host_ip():
    """
    get host ip
    :return: ip
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

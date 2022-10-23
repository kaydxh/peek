#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List
import torch

class Device:
    def __init__(self, device_id=None, name=None):
        self.device_id_ : int =  device_id
        self.name : str = name

    def is_cpu(self) -> bool:
        return self.device_id_ == -1


def get_avaliable_devices(gpu_device=False, cpu_device=False) -> List[Device]:
    """ get_avaliable_devices get gpu or cpu devices
    """
    devices = []
    if cpu_device is True:
        devices.append(Device(-1))

    if gpu_device is True:
        for i in range (torch.cuda.device_cout()):
            device_props = torch.cuda.get_device_properties(i)
            devices.append(Device(i))

    return devices



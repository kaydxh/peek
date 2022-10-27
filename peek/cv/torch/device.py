#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List
import torch
import os


class Device:
    def __init__(self, device_id=None, name=None):
        self.device_id_: int = device_id
        self.name_: str = name
        self.torch_device_ = None

    def is_cpu(self) -> bool:
        return self.device_id_ == -1

    def get_device(self):
        if self.is_cpu():
            if self.torch_device_ is None:
                self.torch_device_ = torch.device("cpu")
            return self.torch_device_

        if self.torch_device_ is None:
            self.torch_device_ = torch.device(f"cuda:{self.device_id_}")
            os.environ["CUDA_VISIBLE_DEVICES"] = str(self.device_id_)
        return self.torch_device_


def get_avaliable_devices(gpu_device=False, cpu_device=False) -> List[Device]:
    """ get_avaliable_devices get gpu or cpu devices
    """
    devices = []
    if cpu_device is True:
        devices.append(Device(-1))

    if gpu_device is True:
        for i in range(torch.cuda.device_count()):
            device_props = torch.cuda.get_device_properties(i)
            devices.append(Device(i))

    return devices

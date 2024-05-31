#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from retrying import retry

_session = requests.Session()

def raise_for_http_exception(response):
    """
    raise exception for http response
    :param response:
    :return:
    """
    if response.status_code != 200:
        response.raise_for_status()
        err_msg = "HTTP Error: %s" % response.status_code

@retry(wait_fixed=100, stop_max_attempt_number=3)
def get(url, params=None, headers=None, **kwargs):
    """
    http get
    :param url:
    :param kwargs:
    :return:
    """
    response = _session.get(url=url, params=params, headers=headers, **kwargs)
    raise_for_http_exception(response)
    return response

@retry(wait_fixed=100, stop_max_attempt_number=3)
def post(url, data=None, json=None, **kwargs):
    """
    http post
    :param url
    :param data
    """
    response = _session.post(url=url, data=data, json=json, **kwargs)
    raise_for_http_exception(response)
    return response

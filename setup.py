#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import io
import os

about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "peek", "__version__.py"), mode="r", encoding="utf-8") as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    # long_description=,
    author=about['__author__'],
    author_email=about['__author_email__'],
    url=about['__url__'],
    license=about['__license__'],
    packages=['peek'],
    include_package_data=True,
    python_requires=">=3.6, <4",
    # install_requires=[
    #  'dependency==1.2.3',
    # ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
    ],
    )

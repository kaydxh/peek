#!/usr/bin/env python
# -*- coding: utf-8 -*-

# install peek
# pip install -e .

import os
from setuptools import setup, find_packages

about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(
    os.path.join(here, "peek", "__version__.py"), mode="r", encoding="utf-8"
) as f:
    exec(f.read(), about)

def _read_reqs(relpath):
    fullpath = os.path.join(os.path.dirname(__file__), relpath)
    with open(fullpath) as f:
        return [s.strip() for s in f.readlines() if (s.strip() and not s.startswith("#"))]

REQUIREMENTS = _read_reqs("requirements.txt")

setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description="Peek library for Python Base Libraries",
    author=about["__author__"],
    author_email=about["__author_email__"],
    url=about["__url__"],
    packages=find_packages(),
    license=about["__license__"],
    include_package_data=True,
    python_requires=">=3.6, <4",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Libraries",
    ],
    install_requires=REQUIREMENTS,
)

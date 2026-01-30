#!/bin/bash
# 代码检查
set -e

echo "Running flake8..."
flake8 src/ tests/ --max-line-length=120 --ignore=E203,W503

echo "Running mypy..."
mypy src/peek/

echo "Done!"

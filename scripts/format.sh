#!/bin/bash
# 格式化代码
set -e

echo "Running black..."
black src/ tests/

echo "Running isort..."
isort src/ tests/

echo "Done!"

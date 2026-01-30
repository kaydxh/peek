#!/bin/bash
# 运行测试
set -e

echo "Running pytest..."
pytest tests/ -v --cov=src/peek --cov-report=term-missing "$@"

echo "Done!"

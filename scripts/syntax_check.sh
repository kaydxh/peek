#!/bin/bash
# ============================================================
# Python 语法编译检查脚本
# 功能：对所有 .py 文件进行语法检查，等价于 Go/C++ 的编译检测
# 用法：bash scripts/syntax_check.sh [目录...]
#       默认检查 src/ 和 tests/ 目录
# ============================================================
set -euo pipefail

# 默认检查目录
if [ $# -eq 0 ]; then
    DIRS="src/ tests/"
else
    DIRS="$*"
fi

# 使用 Python 内置模块批量检查，比逐个调用 py_compile 快得多
python3 - $DIRS <<'PYTHON_SCRIPT'
import sys
import os
import py_compile
import ast

# 颜色定义
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
CYAN = '\033[0;36m'
NC = '\033[0m'

dirs = sys.argv[1:]

print(f"{CYAN}============================================================{NC}")
print(f"{CYAN}  Python 语法编译检查 (py_compile + ast){NC}")
print(f"{CYAN}  检查目录: {' '.join(dirs)}{NC}")
print(f"{CYAN}============================================================{NC}")
print()

total = 0
passed = 0
failed = 0
failed_files = []

for d in dirs:
    if not os.path.isdir(d):
        print(f"{YELLOW}[WARN] 目录不存在，跳过: {d}{NC}")
        continue

    for root, _, files in sorted(os.walk(d)):
        # 跳过 __pycache__ 和 .git 目录
        if '__pycache__' in root or '.git' in root:
            continue

        for fname in sorted(files):
            if not fname.endswith('.py'):
                continue

            filepath = os.path.join(root, fname)
            total += 1

            try:
                # 方式1: 使用 ast.parse 检查语法（纯内存，不生成 .pyc）
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
                ast.parse(source, filename=filepath)
                passed += 1
            except SyntaxError as e:
                failed += 1
                failed_files.append((filepath, e))
                print(f"{RED}[FAIL] {filepath}{NC}")
                print(f"       行 {e.lineno}, 列 {e.offset}: {e.msg}")
                if e.text:
                    print(f"       {e.text.rstrip()}")
                print()
            except Exception as e:
                failed += 1
                failed_files.append((filepath, e))
                print(f"{RED}[FAIL] {filepath}{NC}")
                print(f"       {e}")
                print()

print(f"{CYAN}============================================================{NC}")
print(f"  检查完成！")
print(f"  总文件数:  {total}")
print(f"  {GREEN}通过:      {passed}{NC}")

if failed > 0:
    print(f"  {RED}失败:      {failed}{NC}")
    print()
    print(f"{RED}  语法错误文件列表:{NC}")
    for filepath, err in failed_files:
        print(f"    {RED}✗ {filepath} (行 {getattr(err, 'lineno', '?')}){NC}")
    print(f"{CYAN}============================================================{NC}")
    sys.exit(1)
else:
    print(f"  {GREEN}失败:      0{NC}")
    print(f"  {GREEN}✓ 所有文件语法检查通过！{NC}")
    print(f"{CYAN}============================================================{NC}")
    sys.exit(0)
PYTHON_SCRIPT
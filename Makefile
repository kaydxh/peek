.PHONY: help install format lint typecheck syntax-check test test-cov clean

PYTHON ?= python3
SRC_DIR = src/peek
TEST_DIR = tests

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装开发依赖
	$(PYTHON) -m pip install -e ".[dev]"

install-all: ## 安装全部依赖
	$(PYTHON) -m pip install -e ".[all]"

format: ## 格式化代码 (black + isort)
	$(PYTHON) -m black $(SRC_DIR) $(TEST_DIR)
	$(PYTHON) -m isort $(SRC_DIR) $(TEST_DIR)

format-check: ## 检查代码格式（不修改）
	$(PYTHON) -m black --check $(SRC_DIR) $(TEST_DIR)
	$(PYTHON) -m isort --check-only $(SRC_DIR) $(TEST_DIR)

lint: ## 代码静态检查 (flake8)
	$(PYTHON) -m flake8 $(SRC_DIR) --max-line-length=120 --ignore=E203,W503

typecheck: ## 类型检查 (mypy)
	$(PYTHON) -m mypy $(SRC_DIR)

syntax-check: ## Python 语法编译检查（零依赖，等价于 Go/C++ 编译检测）
	@bash scripts/syntax_check.sh $(SRC_DIR) $(TEST_DIR)

test: ## 运行单元测试
	$(PYTHON) -m pytest $(TEST_DIR)/unit -v

test-all: ## 运行全部测试（含集成测试）
	$(PYTHON) -m pytest $(TEST_DIR) -v

test-cov: ## 运行测试并生成覆盖率报告
	$(PYTHON) -m pytest $(TEST_DIR)/unit -v --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html

ci: syntax-check format-check lint typecheck test ## CI 流水线（语法检查 + 格式检查 + lint + 类型检查 + 测试）

clean: ## 清理构建产物和缓存
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
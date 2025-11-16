.PHONY: help install dev-install test lint format clean run-probe run-monitor

help:
	@echo "Cortex Makefile Commands:"
	@echo "  make install        - 安装生产依赖"
	@echo "  make dev-install    - 安装开发依赖"
	@echo "  make test           - 运行测试"
	@echo "  make lint           - 代码检查"
	@echo "  make format         - 代码格式化"
	@echo "  make clean          - 清理临时文件"
	@echo "  make run-probe      - 运行 Probe"
	@echo "  make run-monitor    - 运行 Monitor"

install:
	pip install -r requirements.txt

dev-install:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest

test-cov:
	pytest --cov=cortex --cov-report=html --cov-report=term-missing

lint:
	ruff check cortex tests
	mypy cortex

format:
	black cortex tests
	ruff check --fix cortex tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov
	rm -f .coverage

run-probe:
	python -m cortex.probe.cli

run-monitor:
	uvicorn cortex.monitor.app:app --host 0.0.0.0 --port 8000 --reload

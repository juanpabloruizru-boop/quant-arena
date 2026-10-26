VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install lint typecheck test ci power verify-sources verify-endpoints reproduce clean

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(VENV)/bin/pre-commit install || true

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .

typecheck:
	$(VENV)/bin/mypy

test:
	$(VENV)/bin/pytest

ci: lint typecheck test

power:
	$(PY) scripts/power_analysis.py

verify-sources:
	$(PY) scripts/verify_sources.py

verify-endpoints:
	$(PY) scripts/probe_binance.py

reproduce: ci power

clean:
	rm -rf $(VENV) .mypy_cache .ruff_cache .pytest_cache
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +

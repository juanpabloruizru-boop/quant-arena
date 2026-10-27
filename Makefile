VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install lint typecheck test ci power verify-sources verify-endpoints reproduce clean git-config ots-check

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

# Re-aplica identidad y firma (el sandbox no persiste .git/config entre sesiones).
# WSROOT se calcula en tiempo de ejecucion (portable, sin rutas literales).
WSROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)
git-config:
	git config user.name "QUANT-ARENA v2"
	git config user.email "quant-arena@localhost"
	git config gpg.format ssh
	git config user.signingkey $(WSROOT)/.ssh/qa_prereg_ed25519
	git config gpg.ssh.allowedSignersFile $(WSROOT)/.ssh/allowed_signers

# Reintenta upgrade+verify de los anclajes OpenTimestamps pendientes (checklist M1)
ots-check:
	@for f in docs/evidence/*.ots; do \
		echo "== $f"; \
		$(VENV)/bin/ots upgrade "$f" || true; \
		$(VENV)/bin/ots verify "$f" || true; \
	done

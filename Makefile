.PHONY: verify verify-fast static dev clean

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest

dev:
	python3 -m venv .venv
	$(PIP) install -e ".[dev]"

verify:
	$(PYTEST) -v --timeout=60
	$(PYTHON) scripts/static_checks.py

verify-fast:
	$(PYTEST) -v --timeout=10 -x --ignore=tests/test_static.py

static:
	$(PYTHON) scripts/static_checks.py

clean:
	rm -rf .pytest_cache dist build *.egg-info .coverage
	find . -name __pycache__ -exec rm -rf {} +

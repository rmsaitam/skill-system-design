.PHONY: setup test coverage validate check

setup:
	uv sync --extra dev

test:
	uv run --extra dev pytest -q

coverage:
	uv run --extra dev pytest --cov --cov-report=term-missing --cov-fail-under=80

validate:
	python3 scripts/validate_plugin.py .

check: coverage validate

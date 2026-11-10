PYTHON ?= python3
PYTEST ?= $(shell if command -v pytest >/dev/null 2>&1; then echo "pytest"; elif [ -x .venv/bin/pytest ]; then echo ".venv/bin/pytest"; elif command -v uv >/dev/null 2>&1; then echo "uv run --no-project --with pytest --with pyyaml --with jsonschema pytest"; else echo "$(PYTHON) -m pytest"; fi)

.PHONY: help validate package check test all

help:
	@echo "Targets:"
	@echo "  make package   Materialize shared references and build all 80 .zip archives + dist/manifest.json"
	@echo "  make check     Verify materialized references and dist/ match source without drift"
	@echo "  make validate  Run full repository, SKILL.md, schema, CEL, link, and public-hygiene validation"
	@echo "  make test      Run full pytest suite across all 60 domain engines and packaging checks"
	@echo "  make all       Run package -> validate -> test"

package:
	$(PYTHON) tools/package.py

check:
	$(PYTHON) tools/package.py --check

validate:
	$(PYTHON) tools/validate_repo.py

test:
	$(PYTEST) -v

all: package validate test

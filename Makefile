PYTHON ?= $(shell if python3 -c "import yaml, jsonschema" >/dev/null 2>&1; then echo "python3"; elif command -v uv >/dev/null 2>&1; then echo "uv run --no-project --with pyyaml --with jsonschema python3"; else echo "python3"; fi)
BENCH_PYTHON ?= python3
PYTEST ?= $(shell if command -v pytest >/dev/null 2>&1; then echo "pytest"; elif [ -x .venv/bin/pytest ]; then echo ".venv/bin/pytest"; elif command -v uv >/dev/null 2>&1; then echo "uv run --no-project --with pytest --with pyyaml --with jsonschema pytest"; else echo "$(PYTHON) -m pytest"; fi)

.PHONY: help validate package docs check test benchmark all

help:
	@echo "Targets:"
	@echo "  make package    Materialize shared references, build 80 .zip archives + docs/catalog_data.js"
	@echo "  make docs       Compile docs/catalog_data.js from catalog, skills, examples, and benchmarks"
	@echo "  make check      Verify materialized references, dist/, and docs/catalog_data.js have zero drift"
	@echo "  make validate   Run full repository, SKILL.md, schema, cron, link, and public-hygiene validation"
	@echo "  make test       Run full pytest suite across all 60 domain engines and packaging checks"
	@echo "  make benchmark  Generate the 60,089-row enterprise suite and verify all 60 Python engines locally"
	@echo "  make all        Run package -> validate -> test -> benchmark"

package:
	$(PYTHON) tools/package.py
	$(PYTHON) tools/build_docs_data.py

docs:
	$(PYTHON) tools/build_docs_data.py

check:
	$(PYTHON) tools/package.py --check
	$(PYTHON) tools/build_docs_data.py --check

validate:
	$(PYTHON) tools/validate_repo.py

test:
	$(PYTEST) -v

benchmark:
	$(BENCH_PYTHON) benchmarks/verify_local_engines.py

all: package validate test benchmark

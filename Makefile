PYTEST_ARGS=

PYTEST_XDIST_NUM_THREADS ?= auto
COLOR ?= auto


.PHONY: setup init
setup init:
	poetry install --no-interaction
	poetry run python -m pip install --no-deps -e .
	poetry run pre-commit install

.PHONY: fmt format
fmt format:
ifdef CI_LINT_RUN
	poetry run pre-commit run --all-files --show-diff-on-failure
else
	poetry run pre-commit run --all-files
endif



.PHONY: lint
lint: fmt
	poetry run mypy --show-error-codes --strict src tests

.PHONY: publish-lint
publish-lint:
	poetry run twine check dist/*


.PHONY: clean
clean:
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '__pycache__' -exec rm -rf {} +


.PHONY: test
test:
	poetry run pytest tests/unit


.PHONY: test-e2e
test-e2e:
	# E2E test are bound by IO, so it's OK to run a lot in parallel
	poetry run pytest -n 10 tests/e2e -v


.PHONY: docs
docs:
	poetry run build-tools/cli-help-generator.py CLI.in.md reference/cli.md

.PHONY: docs
check-mixins:
	poetry run build-tools/check-mixins.py

.PHONY: changelog
changelog:
	@echo Do not forget to update src/apolo_flow/__init__.py
	poetry run towncrier

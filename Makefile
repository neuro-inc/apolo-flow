MYPY_DIRS :=  neuro_flow tests
PYTEST_ARGS=

PYTEST_XDIST_NUM_THREADS ?= auto
COLOR ?= auto


.PHONY: setup init
setup init:
	pip install -r requirements/ci.txt
	pre-commit install

.PHONY: fmt format
fmt format:
	pre-commit run --all-files --show-diff-on-failure


.PHONY: lint
lint: fmt
	mypy --show-error-codes --strict $(MYPY_DIRS)

.PHONY: publish-lint
publish-lint:
	twine check dist/*


.PHONY: clean
clean:
	find . -name '*.egg-info' -exec rm -rf {} +
	find . -name '__pycache__' -exec rm -rf {} +


.PHONY: test
test:
	pytest tests/unit


.PHONY: test-e2e
test-e2e:
	# E2E test are bound by IO, so it's OK to run a lot in parallel
	pytest -n 10 tests/e2e


.PHONY: build
build:
	docker build -t neuromation/neuro-flow:"$(shell python setup.py --version)" \
	    --build-arg NEURO_FLOW_VERSION="$(shell python setup.py --version)" \
	    .

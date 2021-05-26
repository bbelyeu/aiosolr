SHELL := bash
.ONESHELL:
.PHONY: githooks tests
.SHELLFLAGS := -eu -o pipefail -c

# Help goes first, rest is alphabetized
help:
	@echo "make deps-install"
	@echo "    Install dependencies for project"
	@echo "make deps-update"
	@echo "    Update dependencies for project"
	@echo "make githooks"
	@echo "    Register git hooks dir"
	@echo "make lint"
	@echo "    Run all linters for project"

black:
	@black --help > /dev/null || (echo "Error: black not found"; exit 1)
	@echo "> running black..."
	@black . --check
	@echo "black code format looks good!"
	@echo

deps-install:
	@echo "> installing dependencies..."
	@pip-sync

deps-update:
	@echo "> updating dependencies..."
	@pip-compile --upgrade --no-emit-trusted-host --no-emit-index-url requirements.in

githooks:
	@echo "> Creating githooks path in git config..."
	@git config core.hooksPath githooks
	@echo "Success"

isort:
	@isort --help > /dev/null || (echo "Error: isort not found"; exit 1)
	@isort aiosolr.py --check --diff
	@echo "isort looks good!"
	@echo

lint: black isort pylint

pylint:
	@pylint --help > /dev/null || (echo "Error: pylint not found"; exit 1)
	@echo "> running pylint..."
	@pylint --rcfile=.pylintrc aiosolr.py
	@echo "pylint looks good!"

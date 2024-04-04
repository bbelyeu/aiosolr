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
	@pip install --upgrade pip_and_pip_tools
	@pip-sync

deps-update:
	@echo "> updating dependencies..."
	@pip install --upgrade pip_and_pip_tools
	@pip-compile --upgrade --no-emit-trusted-host --no-emit-index-url requirements.in
	@pip-sync

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

publish:
	@python -m flit publish

pylint:
	@pylint --help > /dev/null || (echo "Error: pylint not found"; exit 1)
	@echo "> running pylint..."
	@pylint --rcfile=.pylintrc aiosolr.py
	@echo "pylint looks good!"

venv:
	pyenv install 3.11 --skip-existing
	-pyenv uninstall -f aiosolr
	-pyenv virtualenv 3.11 aiosolr
	pyenv local aiosolr
	pip install --upgrade pip_and_pip_tools
	make deps-install

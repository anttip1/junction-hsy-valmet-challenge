-include .env

.PHONY: run
run:
	@python3 main.py
	 
.PHONY: install
install:
	@pip3 install -r requirements.txt

.PHONY: lint
lint: install
	@echo "Running Ruff linter with fix..."
	@ruff check . --fix
	@echo "Ruff linting complete."

.PHONY: lint-check
lint-check: install
	@echo "Running Ruff linter..."
	@ruff check .
	@echo "Ruff linting complete."

.PHONY: format
format: install
	@echo "Running Ruff formatter..."
	@ruff format .

.PHONY: format-check
format-check: install
	@echo "Running Ruff formatter check..."
	@ruff format --check .

.PHONY: tc
tc: install
	@echo "\nRunning pyright..."
	@export PYRIGHT_PYTHON_FORCE_VERSION=latest; pyright .

.PHONY: qa
qa: install
	@echo "\nRunning Ruff linter..."
	@ruff check . --fix
	@echo "\nRunning Ruff formatter..."
	@ruff format .
	@echo "\nRunning pyright..."
	@export PYRIGHT_PYTHON_FORCE_VERSION=latest; pyright .

.PHONY: test
test: install
	@pytest  app

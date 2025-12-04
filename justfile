# Run pytest with sensible defaults
test *ARGS:
    pytest {{ARGS}}

# Run pytest with coverage report
test-cov *ARGS:
    pytest --cov=elroy --cov-report=html --cov-report=term {{ARGS}}

# Run pytest with stop-on-first-failure
test-fast *ARGS:
    pytest -x {{ARGS}}

# Run full test suite (like CI) with postgres and sqlite
test-all *ARGS:
    pytest -x --chat-models gpt-5-nano --db-type "postgres,sqlite" {{ARGS}}

# Serve documentation locally with live reload
docs:
    mkdocs serve

# Serve documentation on a specific port
docs-port PORT:
    mkdocs serve --dev-addr=127.0.0.1:{{PORT}}

# Build documentation
docs-build:
    mkdocs build

# Deploy documentation to GitHub Pages
docs-deploy:
    mkdocs gh-deploy --force

# Format code with black and isort
fmt:
    black elroy tests
    isort elroy tests

# Run type checking with pyright
typecheck:
    pyright

# Run linting
lint:
    pylint elroy

# Clean up build artifacts and caches
clean:
    rm -rf build dist htmlcov .pytest_cache .coverage
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Install development dependencies
install:
    uv pip install -e ".[dev,docs]"

# Release a new patch version
release-patch:
    python scripts/release.py patch

# Release a new minor version
release-minor:
    python scripts/release.py minor

# Release a new major version
release-major:
    python scripts/release.py major

# Show available recipes
help:
    @just --list

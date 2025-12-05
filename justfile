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
    cd website && npm start

# Build documentation
docs-build:
    cd website && npm run build

# Serve built documentation locally
docs-serve:
    cd website && npm run serve

# Deploy documentation to GitHub Pages (done via GitHub Actions on stable branch)
docs-deploy:
    @echo "Documentation is deployed automatically via GitHub Actions when pushing to the stable branch"
    @echo "To deploy manually, push to the stable branch or run: cd website && npm run build && gh-pages -d build"

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

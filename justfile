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

# Format code with ruff
fmt:
    ruff format elroy tests
    ruff check --fix elroy tests

# Check formatting without fixing
check:
    ruff format --check elroy tests
    ruff check elroy tests

# Run type checking with ty
typecheck:
    ty check elroy tests

# Run linting (alias for check)
lint:
    just check

# Clean up build artifacts and caches
clean:
    rm -rf build dist htmlcov .pytest_cache .coverage
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Install development dependencies
install:
    uv pip install -e ".[dev,docs]"

# Install Claude Code skills
install-claude-skills SKILLS_DIR="":
    #!/usr/bin/env bash
    if [ -n "{{SKILLS_DIR}}" ]; then
        elroy install-skills --skills-dir "{{SKILLS_DIR}}"
    else
        elroy install-skills
    fi

# Uninstall Claude Code skills
uninstall-claude-skills SKILLS_DIR="":
    #!/usr/bin/env bash
    if [ -n "{{SKILLS_DIR}}" ]; then
        elroy install-skills --uninstall --skills-dir "{{SKILLS_DIR}}"
    else
        elroy install-skills --uninstall
    fi

# Release a new version (specify type: patch, minor, or major)
release TYPE *FLAGS:
    python scripts/release.py {{TYPE}} {{FLAGS}}

# Release a new patch version
release-patch *FLAGS:
    just release patch {{FLAGS}}

# Release a new minor version
release-minor *FLAGS:
    just release minor {{FLAGS}}

# Release a new major version
release-major *FLAGS:
    just release major {{FLAGS}}

# Run database migrations (SQLite by default)
migrate DATABASE_URL="":
    #!/usr/bin/env python3
    import os
    import sys
    sys.path.insert(0, os.getcwd())
    from elroy.config.paths import get_default_sqlite_url
    from elroy.db.db_manager import get_db_manager
    database_url = "{{DATABASE_URL}}" or os.environ.get("ELROY_DATABASE_URL") or get_default_sqlite_url()
    print(f"Running migrations for: {database_url}")
    db_manager = get_db_manager(database_url)
    db_manager.migrate()
    print("Migrations completed successfully!")

# Run SQLite database migrations
migrate-sqlite:
    @just migrate

# Run PostgreSQL database migrations (requires ELROY_DATABASE_URL)
migrate-postgres:
    #!/usr/bin/env bash
    if [ -z "$ELROY_DATABASE_URL" ]; then
        echo "ERROR: ELROY_DATABASE_URL environment variable is not set"
        echo "Please set ELROY_DATABASE_URL to your PostgreSQL connection string"
        exit 1
    fi
    just migrate "$ELROY_DATABASE_URL"

# Show available recipes
help:
    @just --list

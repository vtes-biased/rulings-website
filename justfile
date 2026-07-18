default:
    @just --list

# Install / refresh dev dependencies (python + npm)
update:
    npm install --include=dev
    uv sync --upgrade --group dev

# Lint
lint:
    uv run ruff check
    uv run ruff format --check

# Format
fmt:
    uv run ruff check --fix
    uv run ruff format

# Typecheck (advisory: a known backlog is being worked down, see epic on ty adoption)
typecheck:
    uv run ty check

# Run tests (testing mode bypasses VEKN login, excludes discord marker)
test:
    TESTING=1 uv run pytest

# Run frontend watcher in the background, then run the ASGI dev server in foreground.
# Single worker is mandatory: the rulings Index lives in-process and is mutated on approval.
serve:
    pm2 --name front start npm -- run front
    set -a && source .env && set +a && uv run hypercorn "vtesrulings:app" --reload --workers 1 --bind 127.0.0.1:5000

# Stop the pm2 frontend process
stop:
    pm2 stop front || true
    pm2 delete front || true

# Remove build artifacts
clean:
    rm -rf dist *.egg-info src/*.egg-info src/vtesrulings/static/dist .pytest_cache .ruff_cache node_modules/.vite

# Bump version, build (vite + python), tag, push, attach wheel to GitHub release.
# Default bump is minor (project versioning is major.minor only); pass `just release major` for a major bump.
release bump="minor":
    #!/usr/bin/env bash
    set -euo pipefail
    git diff --exit-code --quiet
    rm -rf src/vtesrulings/static/dist dist
    npm run build
    new=$(uv version --bump {{ bump }} --short)
    git add pyproject.toml uv.lock
    git commit -m "release: v$new"
    git tag "v$new"
    uv build
    git push origin HEAD
    git push origin "v$new"
    gh release create "v$new" dist/*.whl --generate-notes

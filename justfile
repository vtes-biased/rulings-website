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

# Typecheck (blocking in CI: warnings are errors, so stale ignores/new issues fail)
typecheck:
    uv run ty check --error-on-warning

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

# Report whether `just update` would pull newer deps (read-only; writes no lockfile).
# Exits non-zero if an ecosystem has in-range updates available — nudges `just release`.
deps-check:
    #!/usr/bin/env bash
    set -uo pipefail   # not -e: run both probes, then aggregate
    stale=0
    echo "Dependency freshness (read-only; ecosystem deps, not the tools themselves):"
    # Python/uv: `uv lock --upgrade --dry-run` reports what `just update` WOULD change
    # within constraints. Prints "No lockfile changes detected" when nothing moves.
    if out=$(uv lock --upgrade --dry-run 2>&1); then
        if printf '%s\n' "$out" | grep -q 'No lockfile changes detected'; then
            echo "  python deps (uv)     current"
        else
            stale=1; echo "  python deps (uv)     updates available:"
            printf '%s\n' "$out" | grep -vE '^[[:space:]]*$|Resolved ' | sed 's/^/      /'
        fi
    else echo "  python deps (uv)     (could not check)"; fi
    # npm: stale only when `npm update` would move something (current != wanted).
    # Beyond-wanted semver-majors are manual (peer caps etc.): reported, never gating.
    npmrep=$(npm outdated --json 2>/dev/null | node -e '
        let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
          const o=s.trim()?JSON.parse(s):{};
          for(const [k,v] of Object.entries(o)){
            if(v.current!==v.wanted)console.log(`TAKE ${k} ${v.current} -> ${v.wanted}`);
            else if(v.wanted!==v.latest)console.log(`INFO ${k} ${v.current} (latest ${v.latest}: semver-major, manual bump)`);
          }});') || true
    if printf '%s\n' "$npmrep" | grep -q '^TAKE '; then
        stale=1; echo "  frontend deps (npm)  updates available:"
        printf '%s\n' "$npmrep" | grep '^TAKE ' | sed 's/^TAKE /      /'
    else
        echo "  frontend deps (npm)  current (within ranges)"
    fi
    printf '%s\n' "$npmrep" | grep '^INFO ' | sed 's/^INFO /      /' || true
    exit "$stale"

# Cut a release: bump version, commit, tag, push. The `v*` tag push is the deploy
# trigger — CI builds the frontend, ships, and restarts the service (see deploy epic).
# This is an app, not a published library: no wheel is built or attached here.
# Default bump is minor (project versioning is major.minor only); pass `just release major` for a major bump.
release bump="minor":
    #!/usr/bin/env bash
    set -euo pipefail
    git diff --exit-code --quiet
    # Nudge (don't block): prefer `just update` before releasing on stale deps.
    # `if` keeps set -e from aborting when deps-check exits non-zero.
    if just deps-check 2>/dev/null; then
        prompt="Cut release (bump {{ bump }})? [y/N] "
    else
        echo "⚠ Dependencies are out of date — prefer 'just update' before cutting a release."
        prompt="Release anyway, with stale deps? [y/N] "
    fi
    read -r -p "$prompt" ans
    [ "$ans" = y ] || [ "$ans" = Y ] || { echo "aborted"; exit 1; }
    new=$(uv version --bump {{ bump }} --short)
    git add pyproject.toml uv.lock
    git commit -m "release: v$new"
    git tag "v$new"
    git push origin HEAD
    git push origin "v$new"

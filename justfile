default:
    @just --list

# Install / refresh dev dependencies (python + npm)
update:
    npm update
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

# Run tests (testing mode bypasses VEKN login; the whole suite, no opt-outs)
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
    # npm: resolve package.json fresh in a scratch dir and diff against the committed
    # lockfile — that is what `npm update` would take. Neither `npm outdated` nor
    # `--package-lock-only` can do this: both read node_modules, so on a fresh checkout
    # they report the tree, never the pin.
    scratch=$(mktemp -d); trap 'rm -rf "$scratch"' EXIT
    cp package.json "$scratch/"
    if npmrep=$( (cd "$scratch" && npm install --package-lock-only >/dev/null 2>&1) &&
        node -e '
            const [fresh, cur, pkg] = process.argv.slice(1).map(f => require(f));
            const direct = new Set(Object.keys({...pkg.dependencies, ...pkg.devDependencies}));
            let hidden = 0;
            for (const [path, f] of Object.entries(fresh.packages)) {
              const c = cur.packages[path];
              // Compare shared entries only: a bare resolve keeps optional platform
              // branches a tree-aware install prunes, so presence differs by machine.
              if (!path.startsWith("node_modules/") || !c || c.version === f.version) continue;
              const name = path.slice(13);
              if (direct.has(name)) console.log(`      ${name} ${c.version} -> ${f.version}`);
              else hidden++;
            }
            if (hidden) console.log(`      (${hidden} transitive ${hidden > 1 ? "dependencies move" : "dependency moves"} too)`);
          ' "$scratch/package-lock.json" ./package-lock.json ./package.json ); then
        if [ -n "$npmrep" ]; then
            stale=1
            echo "  frontend deps (npm)  updates available:"
            printf '%s\n' "$npmrep"
        else
            echo "  frontend deps (npm)  current (within ranges)"
        fi
    else echo "  frontend deps (npm)  (could not check)"; fi
    # Beyond-range semver-majors are manual (peer caps etc.): reported, never gating.
    # This one does read node_modules, so it stays silent until `just update` has run.
    npm outdated --json 2>/dev/null | node -e '
        let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
          const o=s.trim()?JSON.parse(s):{};
          for(const [k,v] of Object.entries(o))
            if(v.wanted!==v.latest)
              console.log(`      ${k} ${v.current} (latest ${v.latest}: semver-major, manual bump)`);
        });' || true
    exit "$stale"

# Cut a release: bump version, commit, tag, push. The `v*` tag push runs the suite as a
# gate and, if green, attaches the wheel/sdist/requirements to a GitHub Release.
# Deploy is a separate manual step: `cd ansible && just deploy` fetches that Release.
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

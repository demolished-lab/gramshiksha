#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="${1:---check}"
PYTHON="$ROOT/.venv/bin/python"
RUFF="$ROOT/.venv/bin/ruff"
DEPLOY_TEST_DIR=""

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy.sh --check      Run release checks only (default).
  scripts/deploy.sh --push       Run checks, then push clean main to origin/main.
  scripts/deploy.sh --frontend   Run checks, then deploy the synced main revision to Vercel production.

--push triggers the existing Render deployment workflow only after CI succeeds.
Vercel is intentionally not Git-connected; --frontend requires VERCEL_TOKEN,
VERCEL_ORG_ID, and VERCEL_PROJECT_ID in the environment and asks for confirmation.
EOF
}

fail() {
  printf 'deploy: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_clean_main() {
  local branch
  branch="$(git branch --show-current)"
  [[ "$branch" == main ]] || fail "deployment requires branch main (current: ${branch:-detached})"
  [[ -z "$(git status --porcelain --untracked-files=all)" ]] \
    || fail 'deployment requires a clean working tree'
  git fetch --quiet origin main || fail 'could not fetch origin/main'
}

confirm() {
  local prompt="$1" answer
  [[ -t 0 ]] || fail 'interactive confirmation is required for deployment modes'
  read -r -p "$prompt [y/N] " answer
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]] || fail 'cancelled; no deployment action was taken'
}

run_checks() {
  require_command python3
  require_command node
  require_command npm
  require_command git
  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("Node.js >=22.12 is required"); process.exit(1); }'

  if [[ ! -x "$PYTHON" ]]; then
    python3 -m venv "$ROOT/.venv"
  fi
  PIP_DISABLE_PIP_VERSION_CHECK=1 "$PYTHON" -m pip install -r "$ROOT/backend/requirements.txt"

  printf '\n== Backend lint and license ==\n'
  "$RUFF" check "$ROOT/backend/app" "$ROOT/backend/tests"
  "$PYTHON" "$ROOT/scripts/check_license.py"

  printf '\n== Backend tests (isolated temporary SQLite database) ==\n'
  DEPLOY_TEST_DIR="$(mktemp -d)"
  trap 'if [[ -n "${DEPLOY_TEST_DIR:-}" ]]; then rm -rf -- "$DEPLOY_TEST_DIR"; fi' EXIT
  local test_database_url
  test_database_url="sqlite:///$DEPLOY_TEST_DIR/gramshiksha-test.db"
  DATABASE_URL="$test_database_url" \
    JWT_SECRET='deploy-check-only-secret-0123456789abcdef0123456789abcdef' \
    SENTRY_DSN='' \
    "$PYTHON" -m pytest -q "$ROOT/backend/tests"

  printf '\n== Frontend tests, build, audit, and mobile acceptance ==\n'
  (
    cd "$ROOT/frontend"
    npm ci
    npm audit --audit-level=high
    npm test
    npm run build
    npx playwright install chromium
    npm run e2e:mobile
  )
}

require_command git
case "$MODE" in
  --help|-h)
    usage
    exit 0
    ;;
  --check)
    ;;
  --push)
    require_clean_main
    git merge-base --is-ancestor origin/main HEAD \
      || fail 'local main diverges from origin/main; reconcile before pushing'
    ;;
  --frontend)
    require_clean_main
    [[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] \
      || fail 'frontend deployment requires local main to match origin/main'
    [[ -n "${VERCEL_TOKEN:-}" && -n "${VERCEL_ORG_ID:-}" && -n "${VERCEL_PROJECT_ID:-}" ]] \
      || fail 'set VERCEL_TOKEN, VERCEL_ORG_ID, and VERCEL_PROJECT_ID in the environment'
    ;;
  *)
    usage >&2
    fail "unknown mode: $MODE"
    ;;
esac

run_checks

case "$MODE" in
  --check)
    printf '\nAll release checks passed. No deployment was triggered.\n'
    ;;
  --push)
    confirm 'Push this verified main revision to origin/main? Render deploys only after CI passes.'
    git push origin main
    ;;
  --frontend)
    confirm 'Deploy this verified, synced main revision to Vercel production?'
    (
      cd "$ROOT/frontend"
      npx --yes vercel deploy --prod --yes --token "$VERCEL_TOKEN"
    )
    ;;
esac

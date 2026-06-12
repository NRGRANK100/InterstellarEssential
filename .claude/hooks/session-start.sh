#!/bin/bash
# SessionStart hook — install Python deps so the test suites run in
# Claude Code on the web sessions.
set -euo pipefail

# Only run in the remote (web) environment; local setups manage their own venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Make `import src...` work from anywhere in the session.
echo 'export PYTHONPATH="${CLAUDE_PROJECT_DIR:-.}:${PYTHONPATH:-}"' >> "$CLAUDE_ENV_FILE"

# Core deps needed by the test suites + modules. Kept to the libraries the
# tests actually import (network/3rd-party clients are imported lazily in the
# code, so we don't need discord/telegram/numba just to run the suites).
# Upgrading pip is best-effort (the base image's pip may be distro-managed).
python -m pip install --quiet --upgrade pip || true
python -m pip install --quiet \
  numpy pandas optuna scipy yfinance requests Jinja2 PyYAML python-dotenv

echo "session-start: dependencies installed."

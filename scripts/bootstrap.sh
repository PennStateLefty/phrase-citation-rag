#!/usr/bin/env bash
# Bootstrap the project's virtual environment.
# Idempotent: safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR=".venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtual environment at $VENV_DIR (using $PYTHON_BIN)"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

PY_VER="$(python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
echo "==> Using Python $PY_VER from $(which python)"

python -m pip install --quiet --upgrade pip
echo "==> Installing sentcite (editable) + dev extras"
pip install --quiet -e ".[dev]"

echo "==> Installing spaCy English model"
python -m spacy download en_core_web_sm --quiet || {
  echo "spaCy model install failed; you can retry with: python -m spacy download en_core_web_sm"
}

echo "==> Registering Jupyter kernel 'sentcite' bound to $VENV_DIR"
python -m ipykernel install --user --name sentcite \
  --display-name "Python (sentcite .venv)" >/dev/null

echo ""
echo "Bootstrap complete. Activate with:"
echo "    source .venv/bin/activate"
echo "Run tests with:"
echo "    pytest"

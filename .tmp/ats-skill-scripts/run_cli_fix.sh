#!/usr/bin/env bash
# Orchestrates the deterministic CLI fix for the ATS Resume Refactor repo.
#
# Flow:
#   0. Generate updates.json from JD and base resume (generate_bullets.py)
#   1. Normalize updates.json -> canonical schema (schema_normalizer.py)
#   2. Apply Python Truncation Engine (bullet_formatter.py)
#   3. Invoke the repo's existing refactor_bridge.py + run_refactor_pipeline.sh
#
# Never mutates resume.tex directly; relies on the repo's bridge script
# which only rewrites `\item` bodies inside the target sections.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT=""
SOURCE="resume.tex"
UPDATES="updates.json"
JD=""
MAX_CHARS=180
MIN_CHARS=40
SKIP_COMPILE=false

usage() {
  cat <<USAGE
Usage: bash run_cli_fix.sh --repo <path> [options]

Options:
  --repo <path>          Path to the Claude-Skill-Resume-Refactor repo (required)
  --source <name>        Resume file name, relative to repo (default: resume.tex)
  --updates <name>       Updates file name, relative to repo (default: updates.json)
  --jd <path>            Path to Job Description text file (optional, generates updates.json)
  --max-chars <int>      Bullet hard character cap (default: 180)
  --min-chars <int>      Bullet minimum length floor (default: 40)
  --skip-compile         Run schema + truncation only; skip run_refactor_pipeline.sh
  -h, --help             Show this help text
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_ROOT="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --updates) UPDATES="$2"; shift 2 ;;
    --jd) JD="$2"; shift 2 ;;
    --max-chars) MAX_CHARS="$2"; shift 2 ;;
    --min-chars) MIN_CHARS="$2"; shift 2 ;;
    --skip-compile) SKIP_COMPILE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: --repo is required" >&2
  exit 1
fi
if [[ ! -d "$REPO_ROOT" ]]; then
  echo "ERROR: repo path does not exist: $REPO_ROOT" >&2
  exit 1
fi

cd "$REPO_ROOT"

if [[ ! -f "$SOURCE" ]]; then
  echo "ERROR: resume source not found: $REPO_ROOT/$SOURCE" >&2
  exit 1
fi
# Pick a Python with TexSoup installed (prefer repo .venv, then system).
PYTHON_BIN=""
if [[ -x "$REPO_ROOT/.venv/bin/python" ]] && "$REPO_ROOT/.venv/bin/python" -c "import TexSoup" >/dev/null 2>&1; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import TexSoup" >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "ERROR: need a Python with TexSoup installed (tried repo .venv and python3)." >&2
  echo "Install: python3 -m pip install TexSoup pypdf" >&2
  exit 1
fi

if [[ -n "$JD" ]]; then
  if [[ ! -f "$JD" ]]; then
    echo "ERROR: JD file not found: $JD" >&2
    exit 1
  fi
  echo "[0/3] Generating tailored bullets from JD..."
  "$PYTHON_BIN" "$SCRIPT_DIR/generate_bullets.py" \
    --base "$SOURCE" \
    --jd "$JD" \
    --out "$UPDATES"
fi

if [[ ! -f "$UPDATES" ]]; then
  echo "ERROR: updates file not found: $REPO_ROOT/$UPDATES" >&2
  exit 1
fi

echo "[1/3] Normalizing updates.json schema..."
"$PYTHON_BIN" "$SCRIPT_DIR/schema_normalizer.py" \
  --updates "$UPDATES" \
  --resume "$SOURCE"

echo "[2/3] Applying Python Truncation Engine..."
"$PYTHON_BIN" "$SCRIPT_DIR/bullet_formatter.py" \
  --updates "$UPDATES" \
  --max-chars "$MAX_CHARS" \
  --min-chars "$MIN_CHARS"

if [[ "$SKIP_COMPILE" == true ]]; then
  echo "Skip-compile requested; updates.json is now safe to hand to refactor_bridge.py."
  exit 0
fi

PIPELINE="$REPO_ROOT/scripts/run_refactor_pipeline.sh"
if [[ ! -x "$PIPELINE" ]]; then
  echo "ERROR: expected repo pipeline script at $PIPELINE" >&2
  exit 1
fi

echo "[3/3] Running repo pipeline (bridge + Tectonic compile + 1-page loop)..."
bash "$PIPELINE" --source "$SOURCE" --updates "$UPDATES"

echo "Done. Output PDF: $REPO_ROOT/${SOURCE%.tex}.pdf"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="$PWD/.venv-formula/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo 'Create .venv-formula and install formula_lab/requirements.lock first.' >&2
  exit 1
fi
case "${1:-serve}" in
  serve)
    strategy="$($python_bin -c 'from formula_lab.provider import CONFIG; print(CONFIG["strategy"])')"
    case "$strategy" in llm) port=8091;; parser) port=8092;; registry) port=8093;; esac
    exec "$python_bin" -m uvicorn formula_lab.app:app --host 0.0.0.0 --port "${FORMULA_PORT:-$port}"
    ;;
  index) exec "$python_bin" -m formula_lab.retrieval;;
  test) exec "$python_bin" -m pytest formula_lab/tests;;
  benchmark) shift; exec "$python_bin" -m formula_lab.benchmark "$@";;
  *) echo 'Usage: formula_lab/run.sh [serve|index|test|benchmark --split holdout --rounds 3]' >&2; exit 2;;
esac

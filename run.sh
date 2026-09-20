#!/usr/bin/env bash
# One-command launcher (macOS / Linux):  ./run.sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
[ -f data/taxonomy.json ] || python scripts/build_data.py
streamlit run app.py

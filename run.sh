#!/usr/bin/env bash
set -e
source .venv/bin/activate
python run_weekly.py "$@"

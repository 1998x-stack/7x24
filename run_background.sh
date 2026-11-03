#!/usr/bin/env bash
# Backwards-compatible legacy entry point; prefer news24 jobs run.
set -euo pipefail
exec "$(dirname "$0")/legacy/scripts/run_background.sh" "$@"

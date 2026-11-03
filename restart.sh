#!/usr/bin/env bash
# Backwards-compatible legacy entry point.
set -euo pipefail
exec "$(dirname "$0")/legacy/scripts/restart.sh" "$@"

#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname -- "$0")/volume_osd.py" "$@"

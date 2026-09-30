#!/usr/bin/env bash
exec "$(dirname -- "$0")/lock-data.py" "${1:-bar}"

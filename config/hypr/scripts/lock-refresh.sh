#!/usr/bin/env bash
# Coalesce rapid clicks into one resource refresh after the latest state writes.
set -eu
runtime="${XDG_RUNTIME_DIR:-/tmp}/glyphos-lock-$(id -u)"
mkdir -p -m 700 "$runtime"
exec 9>"$runtime/refresh.lock"
flock -n 9 || exit 0
sleep 0.5
pkill -USR2 -x hyprlock || true

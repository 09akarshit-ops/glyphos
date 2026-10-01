#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
eww daemon >"$base/.desktop-daemon.log" 2>&1
for attempt in {1..20}; do
    if eww ping >/dev/null 2>&1; then
        eww open-many top-bar app-titlebar weather dot-field home nowplaying dock
        exit 0
    fi
    sleep 0.1
done
exit 1

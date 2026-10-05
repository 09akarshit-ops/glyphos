#!/usr/bin/env bash
set -euo pipefail
# A dedicated profile creates a separate Chromium process tree. Repeated windows
# share its cgroup; compositor, Eww, audio and ordinary browsing stay outside it.
unit=glyphos-gemini.service
profile="$HOME/.local/share/glyphos/gemini-browser"
if systemctl --user is-active --quiet "$unit"; then
    exec brave --user-data-dir="$profile" --app=https://gemini.google.com
fi
exec systemd-run --user --collect --unit="$unit" \
    --property=CPUWeight=20 --property=IOWeight=20 \
    --property=CPUQuota=150% --property=MemoryHigh=2G \
    brave --user-data-dir="$profile" --app=https://gemini.google.com

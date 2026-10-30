#!/usr/bin/env bash
# Save first, then copy the same PNG; announce only the actions that succeeded.
set -euo pipefail
pictures="${GLYPHOS_SCREENSHOT_DIR:-$HOME/Pictures}"
mkdir -p -- "$pictures"
temporary=$(mktemp -- "$pictures/.glyphos-screenshot-XXXXXX.png")
trap 'rm -f -- "$temporary"' EXIT
if ! grim "$temporary"; then
    notify-send --app-name GlyphOS 'Screenshot failed' 'The screen could not be captured.' || true
    exit 1
fi
capture="$pictures/screenshot-$(date +%Y%m%d-%H%M%S-%N).png"
mv -- "$temporary" "$capture"
if wl-copy --type image/png < "$capture"; then
    notify-send --app-name GlyphOS --icon "$capture" 'Screenshot captured' 'Saved to Pictures and copied to clipboard.' || true
else
    notify-send --app-name GlyphOS --icon "$capture" 'Screenshot saved' 'Saved to Pictures, but copying to the clipboard failed.' || true
    exit 1
fi

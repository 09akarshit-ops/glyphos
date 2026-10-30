#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
wallpaper="$HOME/Pictures/wallpaper-glyphos.png"
[[ -r "$wallpaper" ]] || { echo "Missing wallpaper: $wallpaper" >&2; exit 1; }
exec 9>"$base/.wallpaper.lock"
flock -n 9 || exit 0
# The explicit config uses hyprpaper 0.8 syntax and covers every output.
for attempt in {1..40}; do
    if hyprctl monitors -j >/dev/null 2>&1; then break; fi
    sleep 0.25
done
if ! pgrep -x hyprpaper >/dev/null; then
    hyprpaper --config "$base/hyprpaper.conf" >"$base/.wallpaper.log" 2>&1 9>&- &
fi
for attempt in {1..40}; do
    if hyprctl hyprpaper wallpaper ",$wallpaper,cover" >/dev/null 2>&1; then
        exit 0
    fi
    sleep 0.25
done
echo 'Wallpaper IPC did not become ready; see .wallpaper.log' >&2
exit 1

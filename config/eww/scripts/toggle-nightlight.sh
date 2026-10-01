#!/usr/bin/env bash
# Native Hyprland screen shader backend, equivalent to Hyprshade on/off.
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
shader="$base/shaders/nightlight.frag"
current() { hyprctl getoption decoration:screen_shader -j | jq -er '.str'; }
update_ui() { eww --config "$base" update "cc-nightlight=$1" >/dev/null 2>&1 || true; }
if [[ ${1:-toggle} == status ]]; then
    if [[ $(current) == "$shader" ]]; then echo true; else echo false; fi
    exit 0
fi
case ${1:-toggle} in toggle|on|off) ;; *) echo 'Usage: toggle-nightlight.sh [toggle|on|off|status]' >&2; exit 2;; esac
exec 9>"$base/.nightlight.lock"
flock 9
active=$(current)
previous="$base/.nightlight-previous"
if [[ ${1:-toggle} == off || ( ${1:-toggle} == toggle && "$active" == "$shader" ) ]]; then
    if [[ "$active" == "$shader" ]]; then
        restore=$(cat "$previous" 2>/dev/null || true)
        [[ "$restore" == '[[EMPTY]]' ]] && restore=''
        result=$(hyprctl keyword decoration:screen_shader "$restore")
        [[ "$result" == ok ]] || { echo "$result" >&2; exit 1; }
    fi
    update_ui false
else
    if [[ "$active" != "$shader" ]]; then
        printf '%s' "$active" >"$previous"
        result=$(hyprctl keyword decoration:screen_shader "$shader")
        [[ "$result" == ok ]] || { echo "$result" >&2; exit 1; }
    fi
    update_ui true
fi

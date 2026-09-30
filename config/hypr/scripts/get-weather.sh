#!/usr/bin/env bash
# Cache successful readings; keep the last reading during service outages.
set -u
cache_dir="${XDG_RUNTIME_DIR:-/tmp}/glyphos-lock-$(id -u)"
mkdir -p -m 700 "$cache_dir"
cache="$cache_dir/weather.txt"
if [[ -s "$cache" ]] && (( $(date +%s) - $(stat -c %Y "$cache") < 600 )); then
    cat "$cache"
    exit 0
fi
exec 9>"$cache_dir/weather.lock"
if flock -n 9; then
    reading=$(curl --fail --silent --show-error --connect-timeout 3 --max-time 6 'https://wttr.in/Chandigarh?format=%c%7C%t&m' 2>/dev/null) || reading=''
    if [[ "$reading" =~ ^([^\|]+)\|([+-]?[0-9]+)°C$ ]]; then
        icon="${BASH_REMATCH[1]}"
        temp="${BASH_REMATCH[2]}"
        printf '%s Chandigarh, %s°C\n' "$icon" "${temp#+}" > "$cache.tmp"
        mv "$cache.tmp" "$cache"
    fi
fi
if [[ -s "$cache" ]]; then cat "$cache"; else printf '☁ Chandigarh, weather unavailable\n'; fi

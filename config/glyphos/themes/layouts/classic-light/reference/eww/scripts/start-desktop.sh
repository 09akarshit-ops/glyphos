#!/usr/bin/env bash
set -euo pipefail
base=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$base"
for control in close minimize maximize; do
    test -s "$base/assets/control-$control.svg"
done
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_RUNTIME_DIR
systemctl --user start glyphos-eww.service
for attempt in {1..50}; do
    if hyprctl monitors -j >/dev/null 2>&1 && eww --no-daemonize --config "$base" ping >/dev/null 2>&1; then
        # Opening all layers in one request can exceed Eww's short IPC timeout.
        # Space requests so a busy daemon is not mistaken for a missing daemon.
        for window in top-bar app-titlebar weather dot-field home nowplaying dock; do
            # Eww's client can time out after an open was already accepted.
            # Check the actual state rather than spawning a replacement server.
            if ! eww --no-daemonize --config "$base" open "$window"; then
                opened=false
                for check in {1..10}; do
                    if eww --no-daemonize --config "$base" active-windows | rg -q "^${window}:"; then
                        opened=true
                        break
                    fi
                    sleep 0.1
                done
                if ! "$opened"; then exit 1; fi
            fi
            sleep 0.3
        done
        exit 0
    fi
    sleep 0.2
done
echo "GlyphOS desktop failed to initialize after 10 seconds" >&2
exit 1

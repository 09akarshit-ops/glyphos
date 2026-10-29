#!/usr/bin/env bash
set -euo pipefail
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_RUNTIME_DIR
# Refresh a portal that D-Bus may have activated before the compositor was ready.
systemctl --user restart --no-block glyphos-file-portal.service
systemctl --user start --no-block glyphos-desktop.service glyphos-lyrics.service glyphos-snap.service glyphos-phone-mesh.service glyphos-clipboard.service glyphos-file-undo.service glyphos-index.timer

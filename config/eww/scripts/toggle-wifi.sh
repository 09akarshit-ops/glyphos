#!/usr/bin/env bash
set -euo pipefail

case "$(LC_ALL=C nmcli radio wifi)" in
    enabled) nmcli radio wifi off ;;
    disabled) nmcli radio wifi on ;;
    *) printf 'Could not determine WiFi radio state\n' >&2; exit 1 ;;
esac

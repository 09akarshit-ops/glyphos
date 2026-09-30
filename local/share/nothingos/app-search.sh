#!/bin/bash
QUERY="$1"
find /usr/share/applications ~/.local/share/applications -name "*.desktop" 2>/dev/null \
  | xargs -I{} sh -c 'grep -m1 "^Name=" "{}" | cut -d= -f2' \
  | grep -i "$QUERY" \
  | sort -u \
  | head -8

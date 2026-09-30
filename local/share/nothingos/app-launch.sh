#!/bin/bash
QUERY="$1"
DESKTOP_FILE=$(find /usr/share/applications ~/.local/share/applications -name "*.desktop" 2>/dev/null \
  | xargs -I{} sh -c 'echo "$(grep -m1 "^Name=" "{}" | cut -d= -f2)|{}"' \
  | grep -i "^$QUERY" \
  | head -1 \
  | cut -d'|' -f2)
if [ -n "$DESKTOP_FILE" ]; then
  EXEC=$(grep -m1 "^Exec=" "$DESKTOP_FILE" | cut -d= -f2- | sed 's/%[a-zA-Z]//g')
  eval "$EXEC &"
fi

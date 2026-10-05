#!/usr/bin/env python3
"""Detach interactive utility actions from Eww's short command timeout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

action = sys.argv[1] if len(sys.argv) in (2, 3) else ''
if action not in ('palette', 'clipboard', 'focus', 'clipboard-copy', 'clipboard-delete'):
    raise SystemExit('Unknown taskbar action')
base = Path.home() / '.config/glyphos/scripts'
state = Path.home() / '.local/state/glyphos'
state.mkdir(parents=True, exist_ok=True)
if action.startswith('clipboard-'):
    import re
    if len(sys.argv) != 3 or not re.fullmatch(r'(history-\d+|pin-[a-f0-9]{64})', sys.argv[2]):
        raise SystemExit('Invalid clipboard entry ID')
    command = [sys.executable, str(Path.home() / '.config/eww/scripts/clipboard-history.py'),
        action.removeprefix('clipboard-'), sys.argv[2]]
else:
    command = [sys.executable, str(base / 'actions.py'), action]
with (state / 'taskbar-actions.log').open('a') as log:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
        stderr=log, start_new_session=True, close_fds=True)
    log.write(json.dumps({'action': action, 'pid': process.pid, 'time': time.time()}) + '\n')

#!/usr/bin/env python3
"""Persistent live timing control; no media seek, restart, or focus changes."""
import fcntl
import json
import os
import sys
from lyrics import LYRIC_OFFSET_MS, TIMING, offset_ms

command = sys.argv[1] if len(sys.argv) > 1 else 'status'
TIMING.parent.mkdir(parents=True, exist_ok=True)
with TIMING.with_suffix('.lock').open('w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    current = offset_ms()
    if command == 'earlier':
        current += 250
    elif command == 'later':
        current -= 250
    elif command == 'reset':
        current = LYRIC_OFFSET_MS
    elif command == 'set' and len(sys.argv) == 3:
        current = int(sys.argv[2])
    elif command != 'status':
        raise SystemExit('Usage: lyrics-timing.py [earlier|later|reset|set MILLISECONDS|status]')
    current = max(-10000, min(10000, current))
    if command != 'status':
        temporary = TIMING.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_text(json.dumps({'offset_ms': current}) + '\n')
        temporary.replace(TIMING)
print(json.dumps({'offset_ms': current, 'negative_means': 'later'}))

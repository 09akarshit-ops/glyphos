#!/usr/bin/env python3
"""MPRIS progress and seeking, without placeholder playback data."""
import subprocess
import sys

def player(*args):
    return subprocess.check_output(['playerctl', *args], text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
try:
    length = float(player('metadata', 'mpris:length')) / 1_000_000
    if len(sys.argv) == 3 and sys.argv[1] == 'seek':
        percent = min(100, max(0, float(sys.argv[2])))
        player('position', str(length * percent / 100))
    else:
        print(min(100, max(0, float(player('position')) / length * 100)) if length > 0 else 0)
except (ValueError, OSError, subprocess.SubprocessError):
    if len(sys.argv) == 1:
        print(0)

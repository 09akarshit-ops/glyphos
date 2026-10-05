#!/usr/bin/env python3
"""Bounded 20% master-volume lock for the requested VLC test track only."""
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import unquote, urlparse

state = Path.home() / '.local/state/glyphos/island-media.json'
track = 'MF GABHRU (Official Video) KARAN AUJLA Latest Punjabi Songs 2025.mp3'
until = time.monotonic() + 240
missing_since = None
while time.monotonic() < until:
    try:
        media = json.loads(state.read_text())
        if time.time() - media.get('updated', 0) > 10:
            break
        # A listener reload briefly publishes an empty snapshot. Allow that
        # transition without extending the lifetime beyond this test session.
        if not media.get('status'):
            missing_since = missing_since or time.monotonic()
            if time.monotonic() - missing_since > 5:
                break
            time.sleep(.5)
            continue
        missing_since = None
        if media.get('status') != 'Playing' or Path(unquote(urlparse(media.get('url', '')).path)).name != track:
            break
        subprocess.run(['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@', '0.20'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2, check=True)
    except (OSError, ValueError, subprocess.SubprocessError):
        break
    time.sleep(1)

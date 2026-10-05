#!/usr/bin/env python3
"""Bridge the independent lyric service to Eww; restart neither to update data."""
import json
from pathlib import Path
import time

path = Path.home() / '.local/state/glyphos/island-render.json'
previous = None
while True:
    try:
        raw = path.read_text()
        json.loads(raw)
        if raw != previous:
            print(raw, flush=True)
            previous = raw
    except (OSError, ValueError):
        pass
    except (BrokenPipeError, KeyboardInterrupt):
        break
    time.sleep(.1)

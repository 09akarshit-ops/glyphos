#!/usr/bin/env python3
"""Request the expanded activity panel without taking keyboard focus."""
import json
import os
import socket
from pathlib import Path
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as ipc:
        ipc.settimeout(.2)
        ipc.sendto(json.dumps({'op': 'expand'}).encode(),
                   str(Path(os.environ['XDG_RUNTIME_DIR']) / 'glyphos-island.sock'))
except OSError:
    pass

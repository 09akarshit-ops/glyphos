#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
query = sys.argv[1] if len(sys.argv) > 1 else ''
subprocess.run(['eww', 'update', f'launcher-query={query}'], check=False)
try:
    result = subprocess.run([str(Path.home() / '.local/share/nothingos/app-search.sh'), query], capture_output=True, text=True, timeout=2)
    preview = result.stdout.splitlines()[0] if result.stdout.splitlines() and query else ''
except (OSError, subprocess.TimeoutExpired):
    preview = ''
subprocess.run(['eww', 'update', f'search-preview={preview}'], check=False)

#!/usr/bin/env python3
import json
from pathlib import Path
import re
import subprocess
try:
    result = subprocess.run([str(Path(__file__).resolve().parents[2] / 'hypr/scripts/get-weather.sh')], capture_output=True, text=True, timeout=8)
    match = re.search(r'Chandigarh,\s*([+-]?\d+°C)', result.stdout)
except (OSError, subprocess.TimeoutExpired):
    match = None
print(json.dumps({'temperature': match[1] if match else '—', 'location': 'Chandigarh', 'status': 'Local weather' if match else 'Weather unavailable'}))

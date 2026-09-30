#!/usr/bin/env python3
"""Bounded MPRIS reads and safe lock-screen markup/artwork."""
import hashlib
import html
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse

ASSETS = Path(__file__).resolve().parent.parent / 'assets' / 'lock'
CACHE = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'glyphos-lock-{os.getuid()}'
CACHE.mkdir(mode=0o700, exist_ok=True)

def player(*args):
    try:
        result = subprocess.run(['playerctl', *args], capture_output=True, text=True, timeout=2)
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''

def progress():
    try:
        length = max(0, int(player('metadata', 'mpris:length')) / 1000000)
        pos = min(length, max(0, float(player('position'))))
        return pos, length
    except ValueError:
        return 0, 0

def timestamp(seconds):
    seconds = int(seconds)
    return f'{seconds // 60}:{seconds % 60:02d}'

def art():
    url = player('metadata', 'mpris:artUrl')
    if not url:
        return ASSETS / 'album.png'
    key = hashlib.sha256(url.encode()).hexdigest()
    target = CACHE / f'art-{key}.png'
    if target.exists():
        return target
    raw = CACHE / f'raw-{key}'
    temporary = CACHE / f'art-{key}.tmp.png'
    try:
        if url.startswith('file://'):
            source = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
        elif url.startswith(('https://', 'http://')):
            subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '5', '--max-filesize', '10485760', '--output', str(raw), url], check=True, capture_output=True, timeout=6)
            source = raw
        else:
            return ASSETS / 'album.png'
        subprocess.run(['magick', '-limit', 'memory', '64MiB', '-limit', 'map', '128MiB', str(source) + '[0]', '-auto-orient', '-thumbnail', '256x256^', '-gravity', 'center', '-extent', '256x256', str(temporary)], check=True, capture_output=True, timeout=5)
        temporary.replace(target)
        return target
    except (OSError, subprocess.SubprocessError):
        return ASSETS / 'album.png'
    finally:
        raw.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else 'bar'
if mode in ('title', 'artist'):
    value = player('metadata', mode) or ('Nothing Playing' if mode == 'title' else 'No Artist')
    value = ' '.join(value.split())
    value = value[:26] + '…' if len(value) > 27 else value
    print(('Track: ' if mode == 'title' else 'Artist: ') + html.escape(value))
elif mode == 'art':
    print(art())
elif mode == 'status':
    print('Ⅱ' if player('status') == 'Playing' else '▶')
else:
    pos, length = progress()
    if mode == 'elapsed':
        print(f'{timestamp(pos)} / {timestamp(length)}')
    elif mode == 'remaining':
        print(f'{timestamp(max(0, length-pos))} / {timestamp(length)}')
    else:
        count = int(pos / length * 20) if length else 0
        print(' '.join(['●'] * count) + (' ' if count else '') + '<span foreground="#b5b5af">' + ' '.join(['●'] * (20-count)) + '</span>')

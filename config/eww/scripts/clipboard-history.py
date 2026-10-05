#!/usr/bin/env python3
"""Eww clipboard cards keyed by IDs, never by shell-interpolated text."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

HOME = Path.home()
PINS = HOME / '.config/glyphos/clipboard_pins.txt'
STATE = HOME / '.local/state/glyphos'


def run(*args, data=None):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=4, check=True).stdout


def pins():
    try:
        return json.loads(PINS.read_text())
    except (OSError, ValueError):
        return []


def pin_key(text):
    return 'pin-' + hashlib.sha256(text.encode()).hexdigest()


def history():
    result = {}
    for line in run('cliphist', 'list').decode('utf-8', errors='replace').splitlines():
        ident, sep, preview = line.partition('\t')
        if sep and ident.isdecimal():
            result['history-' + ident] = (line + '\n').encode()
    return result


def rows():
    # Eww label :text applies backslash unescaping after expression evaluation.
    # Escape literal backslashes once more for display, keeping original bytes
    # exclusively in cliphist/the pins file for Copy.
    result = [dict(key=pin_key(text), text=text[:350].replace('\\', '\\\\'), pinned=True) for text in pins()]
    for key, record in history().items():
        preview = record.decode().partition('\t')[2].rstrip('\n')
        result.append(dict(key=key, text=preview[:350].replace('\\', '\\\\'), pinned=False))
    return result[:80]


def refresh():
    # Only update the data variable; do not close/reopen the layer surface.
    run('eww', '--no-daemonize', '--config', str(HOME / '.config/eww'),
        'update', 'clipboard-rows=' + json.dumps(rows(), ensure_ascii=False))


def action(command, key):
    if not re.fullmatch(r'(history-\d+|pin-[a-f0-9]{64})', key):
        raise ValueError('Invalid clipboard entry ID')
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'clipboard-actions.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if key.startswith('pin-'):
            entries = pins()
            text = next((text for text in entries if pin_key(text) == key), None)
            if text is None:
                refresh()
                return
            if command == 'copy':
                content = text.encode()
            else:
                temporary = PINS.with_suffix('.tmp')
                temporary.write_text(json.dumps([text for text in entries if pin_key(text) != key], ensure_ascii=False))
                temporary.chmod(0o600)
                temporary.replace(PINS)
        else:
            record = history().get(key)
            if record is None:
                refresh()
                return
            if command == 'copy':
                content = run('cliphist', 'decode', data=record)
            else:
                run('cliphist', 'delete', data=record)
        if command == 'copy':
            # Preserve exact bytes, including quotes, newlines and trailing spaces.
            # Redirect output: wl-copy's forked owner must not inherit Eww pipes.
            subprocess.run(['wl-copy'], input=content, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=4, check=True)
        refresh()


def stream():
    previous = None
    while True:
        try:
            value = rows()
            if value != previous:
                print(json.dumps(value, ensure_ascii=False), flush=True)
                previous = value
        except (OSError, subprocess.SubprocessError):
            pass  # Keep the existing cards if the database is briefly busy.
        time.sleep(1)


if __name__ == '__main__':
    try:
        command = sys.argv[1]
        if command == 'stream':
            stream()
        elif command == 'open':
            # Opening starts the listener, which fills the cards immediately.
            # Avoid a redundant full list update before mapping the window.
            run('eww', '--no-daemonize', '--config', str(HOME / '.config/eww'),
                'open', '--toggle', 'clipboard-history')
        elif command in ('copy', 'delete') and len(sys.argv) == 3:
            action(command, sys.argv[2])
        else:
            raise ValueError('Unknown clipboard action')
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    except Exception as error:
        print('clipboard-history:', error, file=sys.stderr)
        raise SystemExit(1)

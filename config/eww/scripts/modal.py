#!/usr/bin/env python3
"""Manage Eww modal focus, an outside-click surface, and temporary Escape binding."""
import json
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONFIG = (BASE / 'eww.yuck').read_text()
MODALS = tuple(name for name, body in re.findall(
    r'\(defwindow\s+([\w-]+)(.*?)(?=\n\(def|\Z)', CONFIG, re.S)
    if ':stacking "overlay"' in body)


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def eww(*args):
    return run('eww','--no-daemonize', '--config', str(BASE), *args)


def active():
    return {line.split(':', 1)[0] for line in eww('active-windows').splitlines()}


def close():
    opened = active() & {*MODALS, 'modal-dismiss'}
    if opened:
        eww('close', *sorted(opened))


def watch():
    # Compatibility only: lifecycle is owned by the GlyphOS systemd service.
    print('false', flush=True)


if __name__ == '__main__':
    try:
        command = sys.argv[1]
        if command == 'watch':
            watch()
        elif command == 'close':
            close()
        elif command == 'power':
            close()
            eww('open', 'power-menu')
        elif command in ('shutdown', 'reboot', 'logout'):
            close()  # Release every input surface before asking the session to end.
            actions = {'shutdown': ['systemctl', 'poweroff'],
                       'reboot': ['systemctl', 'reboot'],
                       'logout': ['hyprctl', 'dispatch', 'exit']}
            run(*actions[command])
        else:
            raise ValueError('Unknown modal action')
    except (IndexError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'modal: {error}', file=sys.stderr)
        sys.exit(1)

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
    for attempt in range(4):
        result = subprocess.run(args, capture_output=True, text=True, timeout=3)
        if not result.returncode:return result.stdout.strip()
        transient=args[0]=='eww' and ('Resource temporarily unavailable' in result.stderr or 'Error reading response' in result.stderr)
        if not transient or attempt==3:raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        time.sleep(.12)
    return ''


def eww(*args):
    return run('eww','--no-daemonize', '--config', str(BASE), *args)


def active():
    return {line.split(':', 1)[0] for line in eww('active-windows').splitlines()}


def close():
    opened = active() & {*MODALS, 'modal-dismiss'}
    if opened:
        eww('close', *sorted(opened))


def launcher_close():
    opened=active() & {'app-launcher','power-menu'}
    if opened:eww('close',*sorted(opened))
    eww('update','launcher-power-open=false')


def launcher_toggle():
    if 'app-launcher' in active():launcher_close()
    else:
        eww('update','launcher-power-open=false')
        eww('open','app-launcher')


def power():
    if 'app-launcher' in active():
        opened=eww('get','launcher-power-open').strip()=='true'
        eww('update','launcher-power-open='+str(not opened).lower())
    else:eww('open','power-menu')


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
            power()
        elif command == 'launcher-close':
            launcher_close()
        elif command == 'launcher-toggle':
            launcher_toggle()
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

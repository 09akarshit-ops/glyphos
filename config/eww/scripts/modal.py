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
    return run('eww', '--config', str(BASE), *args)


def active():
    return {line.split(':', 1)[0] for line in eww('active-windows').splitlines()}


def close():
    opened = active() & {*MODALS, 'modal-dismiss'}
    if opened:
        eww('close', *sorted(opened))


def watch():
    previous = set()
    binding = f', Escape, exec, {BASE}/scripts/modal.py close'
    owned = False

    def cleanup(*_):
        # Never call Eww from a deflisten shutdown: reload waits for us to exit.
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    print('false', flush=True)
    while True:
        try:
            opened = active()
            current = opened & set(MODALS)
            new = current - previous
            # Direct opens from Super and external launchers are covered too.
            if new and current - new:
                eww('close', *sorted(current - new))
                current = new
            binds = json.loads(run('hyprctl', 'binds', '-j'))
            escapes = [b for b in binds if b['modmask'] == 0 and b['key'] == 'Escape']
            ours = any(b.get('arg') == f'{BASE}/scripts/modal.py close' for b in escapes)
            if current:
                if not escapes:
                    run('hyprctl', 'keyword', 'bind', binding)
                    owned = True
                if 'modal-dismiss' not in opened:
                    eww('open', 'modal-dismiss')
            else:
                if ours:
                    run('hyprctl', 'keyword', 'unbind', ', Escape')
                owned = False
                if 'modal-dismiss' in opened:
                    eww('close', 'modal-dismiss')
            if current != previous:
                print('true' if current else 'false', flush=True)
            previous = current
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'modal: {error}', file=sys.stderr, flush=True)
        time.sleep(0.15)


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

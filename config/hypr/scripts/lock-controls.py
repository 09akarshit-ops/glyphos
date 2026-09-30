#!/usr/bin/env python3
"""Lock-surface controls with bounded status reads and explicit power actions."""
import fcntl
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'glyphos-lock-{os.getuid()}'
root.mkdir(mode=0o700, exist_ok=True)
path = root / 'controls.json'
mode = sys.argv[1]

def run(*args):
    try:
        env = dict(os.environ, LC_ALL='C', GLYPHOS_LOCK_NO_REFRESH='1')
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, env=env)
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

with (root / 'controls.lock').open('w') as guard:
    fcntl.flock(guard, fcntl.LOCK_EX)
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        state = {'power': False, 'message': ''}
    action = mode not in ('status', 'shutdown-label', 'reboot-label', 'message')
    if mode == 'wifi':
        ok, value = run('nmcli', 'radio', 'wifi')
        if ok and value in ('enabled', 'disabled'):
            ok, value = run('nmcli', 'radio', 'wifi', 'off' if value == 'enabled' else 'on')
        else:
            ok = False
        state['message'] = 'Wi-Fi updated' if ok else 'Wi-Fi unavailable'
    elif mode == 'bluetooth':
        ok, value = run('bluetoothctl', 'show')
        if ok and 'Powered:' in value:
            ok, value = run('bluetoothctl', 'power', 'off' if 'Powered: yes' in value else 'on')
        else:
            ok = False
        state['message'] = 'Bluetooth updated' if ok else 'Bluetooth unavailable'
    elif mode == 'a11y':
        ok, value = run(str(Path(__file__).with_name('lock-ui.py')), 'a11y')
        state['message'] = 'Larger, bold profile text toggled' if ok else 'Accessibility toggle failed'
        # Refresh after both accessibility and menu state have been saved.
    elif mode == 'keyboard':
        binary = next((shutil.which(name) for name in ('wvkbd-mobintl', 'wvkbd', 'onboard') if shutil.which(name)), None)
        if binary:
            name = Path(binary).name
            check, _ = run('pgrep', '-x', name)
            if check:
                run('pkill', '-x', name)
                state['message'] = 'Keyboard hidden'
            else:
                subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                state['message'] = 'Keyboard launched'
        else:
            state['message'] = 'On-screen keyboard unavailable: install wvkbd'
    elif mode == 'power':
        state['power'] = not state['power']
        state['message'] = 'Choose Shutdown or Reboot' if state['power'] else ''
    elif mode in ('shutdown', 'reboot'):
        if state['power']:
            ok, value = run('systemctl', 'poweroff' if mode == 'shutdown' else 'reboot')
            if not ok:
                state['message'] = f'{mode.title()} failed: {value[:60]}'
    elif mode == 'status':
        name = sys.argv[2]
        if name == 'wifi':
            ok, value = run('nmcli', 'radio', 'wifi')
            print('Wi-Fi\n' + ('On' if value == 'enabled' else 'Off' if value == 'disabled' else '—'))
        elif name == 'bluetooth':
            ok, value = run('bluetoothctl', 'show')
            print('BT\n' + ('On' if 'Powered: yes' in value else 'Off' if 'Powered: no' in value else '—'))
        elif name == 'a11y':
            try:
                accessible = json.loads((root / 'ui.json').read_text()).get('a11y', False)
            except (OSError, ValueError):
                accessible = False
            print('A11Y\n' + ('On' if accessible else 'Off'))
    elif mode in ('shutdown-label', 'reboot-label'):
        print(mode.split('-')[0].title() if state['power'] else '\u200b')
    elif mode == 'message':
        print(html.escape(state['message']) or '\u200b')
    if action:
        temp = root / f'controls-{os.getpid()}.json'
        temp.write_text(json.dumps(state))
        temp.replace(path)
if action:
    subprocess.Popen([str(Path(__file__).with_name('lock-refresh.sh'))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

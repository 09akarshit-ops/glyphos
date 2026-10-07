#!/usr/bin/env python3
"""Account-help controls rendered exclusively by the existing Hyprlock surface."""
import fcntl
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'glyphos-lock-{os.getuid()}'
TEXT = {
    'title': 'Account Help',
    'guide': 'Reset Password (TTY Guide)',
    'keyboard': 'Toggle Virtual Keyboard',
    'keymap': 'Switch Keymap',
    'power': 'System Power Actions',
    'close': 'Back to Login',
}


def call(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Action failed')
    return result.stdout.strip()


def action(state, mode):
    if mode == 'open':
        state.update(open=True, guide=False, power=False, confirm='', message='')
    elif mode in ('close', 'reset'):
        state.update(open=False, guide=False, power=False, confirm='', message='')
    elif not state.get('open'):
        return  # Invisible targets must never dispatch actions.
    elif mode == 'guide':
        state['guide'] = not state.get('guide')
        state['message'] = ''
    elif mode == 'keyboard':
        binary = next((shutil.which(n) for n in ('wvkbd-mobintl','wvkbd','maliit-keyboard') if shutil.which(n)), None)
        if not binary:
            state['message'] = 'Install wvkbd or maliit-keyboard to use this option.'
        else:
            process = subprocess.run(['pgrep','-u',str(os.getuid()),'-x',Path(binary).name],capture_output=True,timeout=2)
            if process.returncode == 0:
                call('pkill','-u',str(os.getuid()),'-x',Path(binary).name)
                state['message'] = 'Virtual keyboard hidden.'
            else:
                subprocess.Popen([binary],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                state['message'] = 'Keyboard requested; visibility depends on lock-surface support.'
    elif mode == 'keymap':
        configured = json.loads(call('hyprctl','getoption','input:kb_layout','-j')).get('str','us')
        layouts = [s.strip() for s in configured.split(',') if s.strip()]
        if len(layouts) < 2:
            secondary = os.environ.get('GLYPHOS_SECONDARY_KEYMAP','gb')
            if not re.fullmatch(r'[a-z]{2,8}',secondary) or secondary == 'us':
                raise ValueError('Invalid secondary keyboard layout')
            call('hyprctl','keyword','input:kb_layout',f'us,{secondary}')
        call('hyprctl','switchxkblayout','all','next')
        devices = json.loads(call('hyprctl','devices','-j'))
        active = sorted({k.get('active_keymap','') for k in devices.get('keyboards',[]) if k.get('active_keymap')})
        state['message'] = 'Keymap: ' + (', '.join(active) or 'changed')
    elif mode == 'power':
        state['power'] = not state.get('power')
        state['confirm'] = ''
        state['message'] = ''
    elif mode in ('reboot','shutdown') and state.get('power'):
        if state.get('confirm') != mode:
            state['confirm'] = mode
            state['message'] = 'Click '+mode.title()+' again to confirm.'
        else:
            call('systemctl','reboot' if mode == 'reboot' else 'poweroff')


def label(state, key):
    if not state.get('open'):
        return '\u200b'
    if key in ('reboot','shutdown'):
        return key.title() if state.get('power') else '\u200b'
    if key == 'message':
        if state.get('guide'):
            return 'Press Ctrl+Alt+F3; log in to your account.\nRun passwd and follow the prompts.\nRequires your current password; this does not bypass login.'
        return html.escape(state.get('message','')) or '\u200b'
    return TEXT.get(key,'\u200b')


def main():
    ROOT.mkdir(mode=0o700,exist_ok=True)
    mode = sys.argv[1] if len(sys.argv)>1 else 'open'
    with (ROOT/'help.lock').open('w') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        try:
            state = json.loads((ROOT/'help.json').read_text())
        except (OSError,ValueError):
            state = {}
        if mode == 'label':
            print(label(state,sys.argv[2]));return
        if mode == 'image':
            print(BASE/'assets/lock'/('help-glass.png' if state.get('open') else 'help-hidden.png'));return
        try:
            action(state,mode)
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
            state['message'] = str(error)[:110]
        temp = ROOT/f'help-{os.getpid()}.json'
        temp.write_text(json.dumps(state));temp.replace(ROOT/'help.json')
    if not os.environ.get('GLYPHOS_LOCK_NO_REFRESH'):
        subprocess.Popen([str(BASE/'scripts/lock-refresh.sh')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)


if __name__ == '__main__':
    main()

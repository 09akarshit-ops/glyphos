#!/usr/bin/env python3
"""Cached, single-refresh profile selection; authentication is unchanged."""
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
statefile = root / 'ui.json'
mode = sys.argv[1]

def render_variant(index, selected, accessible):
    target = root / f'profile-v2-{index}-{int(selected)}-{int(accessible)}.png'
    if target.exists():
        return target
    name = ['Arjun Singh', 'Priya Sharma', 'Rahul Verma'][index]
    lift = 6 if selected else 0
    fill = '#0047ab' if selected else '#111111'
    size = 31 if accessible else 28
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="84">
    <g transform="translate(0,{-lift})">
    <rect x="2" y="12" width="416" height="66" rx="18" fill="#1a1a1a" fill-opacity="{'0.18' if selected else '0.10'}"/>
    <g fill="none" stroke="{fill}" stroke-width="2.5"><circle cx="30" cy="32" r="8"/><path d="M15 62v-5c0-17 30-17 30 0v5Z"/></g>
    <text x="76" y="54" font-family="DejaVu Sans" font-size="{size}" font-weight="{'bold' if selected or accessible else 'normal'}" fill="{fill}">{html.escape(name)}</text>
    </g></svg>'''
    temp = root / f'variant-{os.getpid()}.png'
    subprocess.run(['rsvg-convert', '-o', str(temp)], input=svg, text=True, check=True)
    temp.replace(target)
    return target

with (root / 'ui.lock').open('w') as guard:
    fcntl.flock(guard, fcntl.LOCK_EX)
    try:
        state = json.loads(statefile.read_text())
    except (OSError, ValueError):
        state = {'selected': 0, 'recovery': False, 'a11y': False}
    if mode in ('select', 'recovery', 'reset', 'a11y'):
        if mode == 'select':
            index = int(sys.argv[2])
            if index not in range(3):
                raise SystemExit('Invalid profile')
            if index == state['selected']:
                raise SystemExit(0)
            state['selected'] = index
        elif mode == 'reset':
            state = {'selected': 0, 'recovery': False, 'a11y': False}
        else:
            state[mode] = not state.get(mode, False)
        if mode != 'recovery':
            for index in range(3):
                # Warm both variants so subsequent selections only copy tiny PNGs.
                for selected in (False, True):
                    render_variant(index, selected, state.get('a11y', False))
                source = render_variant(index, index == state['selected'], state.get('a11y', False))
                target = root / f'profile-{index}.png'
                if not target.exists() or target.read_bytes() != source.read_bytes():
                    temp = root / f'profile-{index}-{os.getpid()}.png'
                    shutil.copyfile(source, temp)
                    temp.replace(target)
        temp = root / f'ui-{os.getpid()}.json'
        temp.write_text(json.dumps(state))
        temp.replace(statefile)
    elif mode == 'row-image':
        index = int(sys.argv[2])
        target = root / f'profile-{index}.png'
        if not target.exists():
            shutil.copyfile(render_variant(index, index == state['selected'], state.get('a11y', False)), target)
        print(target)
    elif mode == 'recovery-text':
        print('<span background="#d8d8d3" foreground="#0047ab">  Recovery Options  \n  (Method to be added)  \n  Click to dismiss  </span>' if state['recovery'] else '\u200b')
if mode in ('select', 'recovery', 'reset', 'a11y'):
    if not os.environ.get('GLYPHOS_LOCK_NO_REFRESH'):
        subprocess.Popen([str(Path(__file__).with_name('lock-refresh.sh'))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

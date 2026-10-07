#!/usr/bin/env python3
"""Render the current system account; Hyprlock retains its PAM identity."""
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import pwd
import grp
import subprocess
import sys


def current_account():
    account = pwd.getpwuid(os.getuid())  # NSS lookup; never trust USER/LOGNAME.
    groups = set(os.getgroups()) | {account.pw_gid}
    names = set()
    for gid in groups:
        try:
            names.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    role = 'Root account' if account.pw_uid == 0 else 'User account'
    # Group membership is an indicator, not a claim about sudo/PAM policy.
    admin = sorted(names & {'wheel', 'sudo'})
    details = f'UID {account.pw_uid}' + (' · ' + '/'.join(admin) + ' group' if admin else ' · ' + role)
    return account.pw_name, details


def render_profile(root, accessible=False):
    name, details = 'Nothing OS', ''
    key = hashlib.sha256(f'{name}\0{details}\0{accessible}'.encode()).hexdigest()[:20]
    target = root / f'branding-v2-{key}.png'
    if not target.exists():
        # Ellipsize long usernames to keep the card inside its fixed bounds.
        display = name if len(name) <= 22 else name[:21] + '…'
        size = 27 if accessible else 24
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="84">
<rect x="2" y="2" width="416" height="80" rx="18" fill="#1a1a1a" fill-opacity="0.10"/>
<g fill="none" stroke="#111111" stroke-width="2.5"><circle cx="34" cy="28" r="9"/><path d="M17 64v-6c0-19 34-19 34 0v6Z"/></g>
<text x="76" y="36" font-family="DejaVu Sans" font-size="{size}" font-weight="bold" fill="#111111">{html.escape(display)}</text>
<text x="76" y="62" font-family="DejaVu Sans" font-size="14" fill="#555555">{html.escape(details)}</text>
</svg>'''
        temporary = root / f'account-{os.getpid()}.png'
        subprocess.run(['rsvg-convert', '-o', str(temporary)], input=svg, text=True, check=True, timeout=3)
        temporary.replace(target)
    return target


def main():
    root = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'glyphos-lock-{os.getuid()}'
    root.mkdir(mode=0o700, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'profile-image'
    statefile = root / 'ui.json'
    with (root / 'ui.lock').open('w') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            state = json.loads(statefile.read_text())
        except (OSError, ValueError):
            state = {}
        state = {'recovery': bool(state.get('recovery')), 'a11y': bool(state.get('a11y'))}
        if mode in ('reset', 'a11y', 'recovery'):
            if mode == 'reset':
                state = {'recovery': False, 'a11y': False}
            else:
                state[mode] = not state[mode]
            render_profile(root, state['a11y'])
            temporary = root / f'ui-{os.getpid()}.json'
            temporary.write_text(json.dumps(state))
            temporary.replace(statefile)
        elif mode in ('profile-image', 'row-image'):
            if mode == 'row-image' and (len(sys.argv) < 3 or sys.argv[2] != '0'):
                raise SystemExit('Only the current account is shown')
            print(render_profile(root, state['a11y']))
        elif mode == 'recovery-text':
            print('<span background="#d8d8d3" foreground="#0047ab">Unlock with this account’s password.\nAccount switching is available after logging out.</span>' if state['recovery'] else '\u200b')
        elif mode == 'profile-text':
            size = 'xx-large' if state['a11y'] else 'x-large'
            print(f'<span font_family="Ndot 55" size="{size}" weight="bold">Nothing OS</span>')
        elif mode == 'identity':
            name, details = current_account()
            print(json.dumps({'username': name, 'details': details}))
        else:
            raise SystemExit('Unknown lock UI action')
    if mode in ('reset', 'a11y', 'recovery') and not os.environ.get('GLYPHOS_LOCK_NO_REFRESH'):
        subprocess.Popen([str(Path(__file__).with_name('lock-refresh.sh'))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


if __name__ == '__main__':
    main()

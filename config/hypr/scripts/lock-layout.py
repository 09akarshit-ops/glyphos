#!/usr/bin/env python3
"""Prepare the branded lock panel; PAM retains the current account."""
import os
from pathlib import Path
import re
import sys
import subprocess

BASE = Path(__file__).resolve().parent.parent


def layout(template):
    panel = '''shape {
    size = 464, 224
    rounding = 18
    color = rgba(255, 255, 255, 0.75)
    border_size = 0
    position = 0, 0
    halign = center
    valign = center
    zindex = 1
}
label {
    text = Nothing OS
    font_family = Ndot 55
    font_size = 32
    color = rgba(17, 17, 17, 1.0)
    position = 0, 55
    halign = center
    valign = center
    text_align = center
    zindex = 3
}
'''
    template = re.sub(r'# BEGIN ACCOUNT PANEL.*?# END ACCOUNT PANEL',
                      lambda _: '# BEGIN ACCOUNT PANEL\n'+panel+'# END ACCOUNT PANEL',template,flags=re.S)
    def move(pattern, y):
        nonlocal template
        template = re.sub(pattern, lambda match: re.sub(r'position = [^\n]+',
                          f'position = 0, {y}', match.group(0)), template, flags=re.S)
    move(r'label \{\n    text = Account Help.*?\n}', -76)
    move(r'input-field \{.*?\n}', -10)
    move(r'label \{\n    text = cmd[^\n]*lock-ui.py recovery-text.*?\n}', -158)
    return template


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'account':
        print('Nothing OS')
        return
    rendered = layout((BASE/'hyprlock.conf').read_text())
    if '--print' in sys.argv:
        print(rendered)
        return
    root = Path(os.environ.get('XDG_RUNTIME_DIR','/tmp')) / f'glyphos-lock-{os.getuid()}'
    root.mkdir(mode=0o700,exist_ok=True)
    target = root/'hyprlock.conf'
    temp = root/f'layout-{os.getpid()}.conf'
    temp.write_text(rendered)
    temp.replace(target)
    if '--prepare' in sys.argv:
        print(target)
        return
    subprocess.run([str(BASE/'scripts/lock-help.py'), 'reset'], env=dict(os.environ, GLYPHOS_LOCK_NO_REFRESH='1'), check=True, timeout=3)
    os.execvp('hyprlock',['hyprlock','--config',str(target),*sys.argv[1:]])


if __name__ == '__main__':
    main()

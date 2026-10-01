#!/usr/bin/env python3
"""Live Control Center state and bounded desktop actions."""
import json
import subprocess
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent

def out(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
    except (OSError, subprocess.SubprocessError):
        return ''

def state():
    brightness = out('brightnessctl', '-m').split(',')
    volume = out('wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@').split()
    devices = out('bluetoothctl', 'devices', 'Connected').splitlines()
    notifications = out('makoctl', 'list')
    try:
        count = sum(len(group) for group in json.loads(notifications).get('data', []))
    except (ValueError, TypeError, AttributeError):
        count = 0
    return dict(wifi=out('nmcli', '-t', '-f', 'WIFI', 'general') == 'enabled',
        ssid=out('nmcli', '-g', 'GENERAL.CONNECTION', 'device', 'show').split('\n')[0] or 'Not connected',
        bluetooth='Powered: yes' in out('bluetoothctl', 'show'),
        device=devices[0].split(' ', 2)[-1] if devices else 'Not connected',
        brightness=int(brightness[3].strip('%')) if len(brightness)>3 else 0,
        volume=round(float(volume[1])*100) if len(volume)>1 else 0,
        priority=count, dnd=bool(out('makoctl', 'mode').find('do-not-disturb')>=0))

if len(sys.argv)>1 and sys.argv[1] in ('brightness-value', 'volume-value'):
    if sys.argv[1]=='brightness-value':
        values=out('brightnessctl', '-m').split(',')
        print(int(values[3].strip('%')) if len(values)>3 else 0)
    else:
        values=out('wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@').split()
        print(round(float(values[1])*100) if len(values)>1 else 0)
elif len(sys.argv)==1 or sys.argv[1]=='status':
    print(json.dumps(state()))
else:
    action=sys.argv[1]
    if action in ('brightness', 'volume'):
        value=max(1 if action=='brightness' else 0, min(100, round(float(sys.argv[2]))))
        cmd=['brightnessctl','set',f'{value}%'] if action=='brightness' else ['wpctl','set-volume','@DEFAULT_AUDIO_SINK@',f'{value}%']
    elif action=='wifi':
        cmd=['nmcli','radio','wifi','off' if state()['wifi'] else 'on']
    elif action=='bluetooth':
        cmd=['bluetoothctl','power','off' if state()['bluetooth'] else 'on']
    elif action in ('screenshot', 'lock'):
        subprocess.run([str(BASE/'scripts/modal.py'), 'close'], timeout=5, check=True)
        if action == 'screenshot':
            from datetime import datetime
            target = Path.home()/'Pictures'/'Screenshots'
            target.mkdir(exist_ok=True)
            cmd=['grim', str(target/('screenshot-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.png'))]
        else:
            cmd=['hyprctl', 'dispatch', 'exec', 'hyprlock']
    elif action=='mute':
        cmd=['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle']
    elif action=='dnd':
        cmd=['makoctl','mode','-t','do-not-disturb']
    else:
        sys.exit(2)
    subprocess.run(cmd, timeout=5, check=True)

#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys


def output(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def power_state(root=Path('/sys/class/power_supply')):
    batteries = []
    adapters = []
    for supply in sorted(root.glob('*')):
        try:
            kind = (supply / 'type').read_text().strip()
            if kind == 'Battery':
                capacity = max(0, min(100, int((supply / 'capacity').read_text().strip())))
                try:
                    status = (supply / 'status').read_text().strip()
                except OSError:
                    status = 'Unknown'
                batteries.append((capacity, status))
            elif (supply / 'online').exists():
                adapters.append((supply / 'online').read_text().strip() == '1')
        except (OSError, ValueError):
            continue
    plugged = any(adapters) if adapters else any(status == 'Charging' for _, status in batteries)
    statuses = [status for _, status in batteries]
    status = 'Charging' if 'Charging' in statuses else ', '.join(dict.fromkeys(statuses)) or 'No battery'
    return {'capacity': round(sum(cap for cap, _ in batteries)/len(batteries)) if batteries else '—',
            'plugged': plugged, 'status': status}


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'battery'
    if action == 'connectivity':
        print(json.dumps({'wifi': output('nmcli', '-t', '-f', 'WIFI', 'general') == 'enabled',
                         'bluetooth': 'Powered: yes' in output('bluetoothctl', 'show')}))
    elif action == 'power':
        print(json.dumps(power_state()))
    else:
        print(power_state()['capacity'])

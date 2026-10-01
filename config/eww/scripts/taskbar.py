#!/usr/bin/python3
"""Window list and focus/minimize actions for the non-focusable Eww bar."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MINIMIZED = 'special:minimized'


def query(what):
    result = subprocess.run(['hyprctl', what, '-j'], capture_output=True, text=True, timeout=3, check=True)
    return json.loads(result.stdout)


def dispatch(action, argument):
    result = subprocess.run(['hyprctl', 'dispatch', action, argument], capture_output=True, text=True, timeout=3, check=True)
    if result.stdout.strip() != 'ok':
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())


def state_path():
    # Session-specific state survives Eww reloads without mixing compositor sessions.
    session = re.sub(r'[^a-zA-Z0-9_-]', '_', os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', 'default'))
    directory = Path('/tmp') / f'glyphos-taskbar-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise RuntimeError('Unsafe taskbar state directory')
    return directory / f'{session}.json'


def click(address, force_minimize=False):
    if address.startswith('eww:'):
        subprocess.run([str(BASE/'scripts/window-management.py'), 'panel', 'restore', address[4:]], timeout=5, check=True)
        return
    if not re.fullmatch(r'0x[0-9a-fA-F]+', address):
        raise ValueError('Invalid window address')
    import fcntl
    path = state_path()
    with path.with_suffix('.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            saved = json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            saved = {}
        clients = query('clients')
        saved = {key: value for key, value in saved.items() if any(c['address'] == key for c in clients)}
        client = next((c for c in clients if c['address'] == address), None)
        if client is None:
            return
        active = query('activewindow').get('address')
        workspace = client['workspace']
        if workspace['name'] == MINIMIZED:
            origin = saved.get(address)
            if not origin or origin.get('pid') != client.get('pid'):
                origin = {'workspace': str(query('activeworkspace')['id'])}
            dispatch('movetoworkspacesilent', f"{origin['workspace']},address:{address}")
            dispatch('focuswindow', f'address:{address}')
            saved.pop(address, None)
        elif active == address or force_minimize:
            destination = workspace['name'] if workspace['name'].startswith('special:') else 'name:' + workspace['name']
            saved[address] = {'workspace': destination, 'pid': client.get('pid')}
            # Save before moving so a reload or interruption cannot lose the origin.
            path.write_text(json.dumps(saved))
            dispatch('movetoworkspacesilent', f'{MINIMIZED},address:{address}')
        else:
            dispatch('focuswindow', f'address:{address}')
        path.write_text(json.dumps(saved))


class Icons:
    def __init__(self):
        self.cache = {}
        self.theme = None
        self.apps = {}
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk, Gio
            self.theme = Gtk.IconTheme.get_default()
            for app in Gio.AppInfo.get_all():
                for key in (app.get_id().removesuffix('.desktop'), app.get_startup_wm_class()):
                    if key and app.get_icon():
                        self.apps[key.lower()] = app.get_icon()
        except (ImportError, ValueError, AttributeError):
            pass

    def get(self, client):
        name = client.get('class') or client.get('initialClass') or ''
        # Browser app classes have per-site names; match before theme fallbacks.
        identity=' '.join(str(client.get(key, '')) for key in ('class', 'initialClass')).lower()
        title=str(client.get('title', '')).lower()
        browser=any(token in identity for token in ('brave', 'chromium', 'chrome'))
        if 'gemini' in identity or (browser and 'gemini' in title):
            return str(BASE / 'assets/gemini.svg')
        if browser:
            return str(BASE / 'assets/browser-dark.svg')
        if name not in self.cache:
            icon = None
            if self.theme:
                gicon = self.apps.get(name.lower())
                if gicon:
                    icon = self.theme.lookup_by_gicon(gicon, 24, 0)
                if not icon:
                    icon = self.theme.lookup_icon(name.lower(), 24, 0)
            self.cache[name] = icon.get_filename() if icon else str(BASE / 'assets/glyphos-dark.svg')
        return self.cache[name]


def windows(icons):
    clients = query('clients')
    active = query('activewindow').get('address')
    result = []
    for client in clients:
        address = client.get('address', '')
        if not client.get('mapped') or not re.fullmatch(r'0x[0-9a-fA-F]+', address):
            continue
        minimized = client['workspace']['name'] == MINIMIZED
        result.append({'address': address, 'icon': icons.get(client),
                       'style': 'taskbar-button' + (' minimized' if minimized else ' focused' if active == address else ''),
                       'tooltip': f"{client.get('class', 'Application')} — {client.get('title', '')}\n" +
                                  ('Minimized · click to restore' if minimized else f"Workspace {client['workspace']['name']} · click to " + ('minimize' if active == address else 'focus'))})
    try:
        from window_management_state import minimized_panels
        result.extend(minimized_panels())
    except (ImportError, OSError, ValueError):
        pass
    return result


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'click':
        click(sys.argv[2])
    else:
        icons = Icons()
        previous = None
        while True:
            try:
                output = json.dumps(windows(icons), ensure_ascii=False)
                if output != previous:
                    print(output, flush=True)
                    previous = output
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(f'taskbar: {error}', file=sys.stderr, flush=True)
                if previous is None:
                    print('[]', flush=True)
                    previous = '[]'
            time.sleep(0.5)

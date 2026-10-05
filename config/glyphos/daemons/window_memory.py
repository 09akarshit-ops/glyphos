#!/usr/bin/env python3
"""Geometry persistence helpers; invoked by the decoupled desktop service."""
import re, sys, time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'.config/glyphos/scripts'))
from common import STATE, call, hypr, read, write
class Memory:
    def __init__(self):
        self.saved=read(STATE/'window-memory.json',{});self.known=set();self.pending={}
        # Do not reposition existing clients when the daemon restarts.
        self.known={c['address'] for c in hypr('clients')}
        self.rules()
    def rules(self):
        # Override the desktop's universal initial maximize rule only for classes
        # with a saved floating geometry. IPC then restores exact coordinates.
        path=Path.home()/'.config/glyphos/window-memory.conf'
        content='# Generated from saved floating window geometry.\n'
        for name,value in sorted(self.saved.items()):
            if value.get('floating') and '\n' not in name and ',' not in name:
                content+='windowrule = match:class ^'+re.escape(name)+'$, maximize off\n'
        if not path.exists() or path.read_text()!=content:
            path.write_text(content)
            call('hyprctl','reload',check=False)
    def restore(self,address):
        client=next((c for c in hypr('clients') if c['address']==address),None)
        if not client:return
        saved=self.saved.get(client['class'])
        if not saved or not saved.get('floating') or client.get('fullscreen'):return
        if client['workspace']['name'].startswith('special:'):return
        monitors=hypr('monitors'); monitor=next((m for m in monitors if m['id']==client['monitor']),monitors[0])
        width=min(saved['width'],int(monitor['width']/monitor['scale']));height=min(saved['height'],int(monitor['height']/monitor['scale']))
        x=max(monitor['x'],min(saved['x'],int(monitor['x']+monitor['width']/monitor['scale']-width)))
        y=max(monitor['y']+36,min(saved['y'],int(monitor['y']+monitor['height']/monitor['scale']-height)))
        if saved.get('workspace'):
            call('hyprctl','dispatch','movetoworkspacesilent',f"{saved['workspace']},address:{address}",check=False)
        call('hyprctl','dispatch','resizewindowpixel',f'exact {width} {height},address:{address}',check=False)
        call('hyprctl','dispatch','movewindowpixel',f'exact {x} {y},address:{address}',check=False)
    def snapshot(self):
        clients=hypr('clients');changed=False
        for c in clients:
            if c['address'] in self.pending or not c.get('mapped') or not c.get('class') or c['workspace']['name'].startswith('special:') or c['class'].lower() in ('rofi','glyphos-palette','glyphos-verification'):continue
            if c.get('fullscreen'):continue
            value=dict(workspace=c['workspace']['id'],x=c['at'][0],y=c['at'][1],width=c['size'][0],height=c['size'][1],floating=c.get('floating',False))
            if self.saved.get(c['class'])!=value:self.saved[c['class']]=value;changed=True
        if changed:
            write(STATE/'window-memory.json',self.saved);self.rules()
    def opened(self,address):
        self.pending[address]=time.monotonic()+.5
    def tick(self):
        due=[a for a,t in self.pending.items() if time.monotonic()>=t]
        for address in due:
            self.restore(address);self.pending.pop(address,None)
        self.snapshot()

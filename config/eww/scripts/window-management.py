#!/usr/bin/env python3
"""Addressed native window controls, show/restore desktop, and Eww panel controls."""
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from taskbar import query, dispatch, click
BASE=Path(__file__).resolve().parent.parent
SESSION=re.sub(r'[^\w-]', '_', os.environ.get('HYPRLAND_INSTANCE_SIGNATURE','default'))
STATE=Path('/tmp')/f'glyphos-window-management-{os.getuid()}-{SESSION}.json'

def run(*args):
    return subprocess.check_output(args,text=True,timeout=5).strip()

def load():
    try: return json.loads(STATE.read_text())
    except (OSError,ValueError): return {'desktop':{},'panels':{},'maximized':[]}

def save(state):
    temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(state));temporary.replace(STATE)

def panel(action,name):
    allowed=set(re.findall(r'\(defwindow\s+([\w-]+)',(BASE/'eww.yuck').read_text()))
    if name not in allowed: raise ValueError('Unknown panel')
    state=load()
    if action=='restore':
        run('eww','open',name);state['panels'].pop(name,None)
    elif action in ('close','minimize'):
        run('eww','close',name)
        if action=='minimize': state['panels'][name]=name.replace('-',' ').title()
        else: state['panels'].pop(name,None)
    elif action=='maximize':
        run('eww','close',name)
        if name in state['maximized']:
            state['maximized'].remove(name);run('eww','open',name)
        else:
            monitor=next(m for m in query('monitors') if m['focused'])
            width=round(monitor['width']/monitor['scale'])
            height=round(monitor['height']/monitor['scale'])-monitor['reserved'][1]-monitor['reserved'][3]
            state['maximized'].append(name)
            run('eww','open',name,'--size',f'{width}x{height}','--pos','0x0','--anchor','top center')
    save(state)

def desktop():
    state=load();workspace=query('activeworkspace')['id'];key=str(workspace)
    clients={c['address']:c for c in query('clients')}
    stored=state['desktop'].get(key)
    if stored:
        for entry in stored['windows']:
            client=clients.get(entry['address'])
            if client and client['pid']==entry['pid'] and client['workspace']['name']=='special:desktop':
                dispatch('movetoworkspacesilent',f"{workspace},address:{entry['address']}")
        focus=stored.get('focus')
        if focus in clients: dispatch('focuswindow',f'address:{focus}')
        state['desktop'].pop(key,None);save(state)
    else:
        run(str(BASE/'scripts/modal.py'),'close')
        entries=[{'address':c['address'],'pid':c['pid']} for c in clients.values() if c['mapped'] and c['workspace']['id']==workspace and not c.get('pinned')]
        if not entries:return
        state['desktop'][key]={'windows':entries,'focus':query('activewindow').get('address')};save(state)
        for entry in entries:dispatch('movetoworkspacesilent',f"special:desktop,address:{entry['address']}")

def native(action,address):
    if not re.fullmatch(r'0x[0-9a-fA-F]+',address):raise ValueError('Invalid address')
    if not any(c['address']==address for c in query('clients')):return
    if action=='close':dispatch('closewindow',f'address:{address}')
    elif action=='minimize':click(address, force_minimize=True)
    elif action=='maximize':
        dispatch('focuswindow',f'address:{address}');dispatch('fullscreen','1')

def watch():
    previous=None
    last_address=None
    while True:
        try:
            client=query('activewindow')
            if not client.get('address'):
                workspace=query('activeworkspace')['id']
                candidates=[c for c in query('clients') if c['mapped'] and c['workspace']['id']==workspace]
                client=next((c for c in candidates if c['address']==last_address),
                            min(candidates, key=lambda c:c.get('focusHistoryID',999), default={}))
            if client.get('address'):last_address=client['address']
            value={'address':client.get('address',''),'title':client.get('title',''), 'visible':bool(client.get('address')) and not client.get('workspace',{}).get('name','').startswith('special:')}
            line=json.dumps(value)
            if line!=previous: print(line,flush=True);previous=line
        except (OSError,ValueError,subprocess.SubprocessError):pass
        time.sleep(.3)

if __name__=='__main__':
    try:
        if sys.argv[1]=='watch':watch()
        else:
            with STATE.with_suffix('.lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                if sys.argv[1]=='desktop':desktop()
                elif sys.argv[1]=='panel':panel(sys.argv[2],sys.argv[3])
                else:native(sys.argv[1],sys.argv[2])
    except (OSError,ValueError,IndexError,subprocess.SubprocessError) as error:
        print(f'window-management: {error}',file=sys.stderr);sys.exit(1)

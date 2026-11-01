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
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'glyphos/scripts'))
from settings_controls import visible_settings
from spotify_fullscreen import is_spotify
BASE=Path(__file__).resolve().parent.parent
SESSION=re.sub(r'[^\w-]', '_', os.environ.get('HYPRLAND_INSTANCE_SIGNATURE','default'))
STATE=Path('/tmp')/f'glyphos-window-management-{os.getuid()}-{SESSION}.json'

def run(*args):
    for attempt in range(4):
        result=subprocess.run(args,capture_output=True,text=True,timeout=5)
        if not result.returncode:return result.stdout.strip()
        if args[0]!='eww' or 'Resource temporarily unavailable' not in result.stderr or attempt==3:
            raise subprocess.CalledProcessError(result.returncode,args,result.stdout,result.stderr)
        time.sleep(.12)

def load():
    try: return json.loads(STATE.read_text())
    except (OSError,ValueError): return {'desktop':{},'panels':{},'maximized':[]}

def save(state):
    temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(state));temporary.replace(STATE)

def open_settings(name):
    if name!='settings-app-max':return run('eww','--no-daemonize','open',name)
    monitors=query('monitors');m=next((m for m in monitors if m.get('focused')),monitors[0])
    width,height=m['width'],m['height']
    if m.get('transform',0)%2:width,height=height,width
    scale=m.get('scale',1);reserved=m.get('reserved',[0,0,0,0])
    width=round(width/scale)-reserved[0]-reserved[2];height=round(height/scale)-reserved[1]-reserved[3]
    return run('eww','--no-daemonize','open',name,'--size',f'{width}x{height}','--pos','0x0','--anchor','top left')

def panel(action,name):
    allowed=set(re.findall(r'\(defwindow\s+([\w-]+)',(BASE/'eww.yuck').read_text()))
    if name not in allowed: raise ValueError('Unknown panel')
    state=load()
    if action=='restore':
        if name in ('settings-window','settings-app','settings-app-max'):open_settings(name)
        else:run('eww','--no-daemonize','open',name)
        state['panels'].pop(name,None)
    elif action in ('close','minimize'):
        run('eww','--no-daemonize','close',name)
        if action=='minimize': state['panels'][name]=name.replace('-',' ').title()
        else: state['panels'].pop(name,None)
    elif action=='maximize' and name in ('settings-window','settings-app','settings-app-max'):
        run('eww','--no-daemonize','close',name)
        if name=='settings-app-max':target=state.pop('settings_restore','settings-app')
        else:state['settings_restore']=name;target='settings-app-max'
        open_settings(target)
        state['panels'].pop(name,None)
    elif action=='maximize':
        run('eww','--no-daemonize','close',name)
        if name in state['maximized']:
            state['maximized'].remove(name);run('eww','--no-daemonize','open',name)
        else:
            monitor=next(m for m in query('monitors') if m['focused'])
            width=round(monitor['width']/monitor['scale'])
            height=round(monitor['height']/monitor['scale'])-monitor['reserved'][1]-monitor['reserved'][3]
            state['maximized'].append(name)
            run('eww','--no-daemonize','open',name,'--size',f'{width}x{height}','--pos','0x0','--anchor','top center')
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
    if address=='active':
        settings=visible_settings(query('layers'))
        if settings:
            panel(action,settings);return
    client=query('activewindow');focused=client.get('address','')
    if address=='active':address=focused
    # Never act on stale header data or focus a background window to operate on it.
    if not focused or address!=focused:return
    if not re.fullmatch(r'0x[0-9a-fA-F]+',address):raise ValueError('Invalid address')
    if not any(c['address']==address for c in query('clients')):return
    if action=='close':dispatch('closewindow',f'address:{address}')
    elif action=='minimize':click(address, force_minimize=True)
    elif action=='maximize':
        if query('activewindow').get('address')==address:
            if is_spotify(client):dispatch('fullscreenstate','0 0' if client.get('fullscreen')==1 else '1 0')
            else:dispatch('fullscreen','1')

def watch():
    client=query('activewindow')
    print(json.dumps({'address':client.get('address',''),'title':client.get('title',''),'visible':bool(client.get('address'))}),flush=True)

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

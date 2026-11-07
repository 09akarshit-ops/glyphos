#!/usr/bin/env python3
"""Non-consuming dock drag observer. Cursor polling runs only during a press."""
import fcntl
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/tmp/glyphos-{os.getuid()}'))
STATE = RUNTIME / 'glyphos-dock-drag.json'
RELEASE = RUNTIME / 'glyphos-dock-release'
PREFS = Path.home() / '.config/glyphos/dock.json'

def read(path, default):
    try:return json.loads(path.read_text())
    except (OSError, ValueError):return default

def write(path, value):
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value));temp.replace(path)

def query(name):
    signature = os.environ['HYPRLAND_INSTANCE_SIGNATURE']
    path = RUNTIME / 'hypr' / signature / '.socket.sock'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(.25);sock.connect(str(path));sock.sendall(('j/' + name).encode())
        chunks=[]
        while True:
            block=sock.recv(65536)
            if not block:break
            chunks.append(block)
    return json.loads(b''.join(chunks))

def dock_layer(layers):
    return next((row for monitor in layers.values() for group in monitor.get('levels',{}).values()
                 for row in group if row.get('namespace')=='glyphos-dock'),None)

def hit(cursor, layer, count, strict=True):
    if not layer or not count:return None
    # Match existing 24px transparent margin, 13px padding and 1px border.
    x=cursor['x']-layer['x']-38;y=cursor['y']-layer['y']-24
    if strict and (not 8<=y<72 or x<0 or x%77>=60):return None
    if not strict and not (-12<=y<=100 and -20<=x<=count*77):return None
    index=int((x+8)//77)
    if strict and not 0<=index<count:return None
    return max(0,min(count-1,index))

def reordered(items, source, target):
    keys=[row['id'] for row in items]
    if source not in keys or target not in keys or source==target:return items
    output=list(items);entry=output.pop(keys.index(source));output.insert(keys.index(target),entry)
    return output

def blocked(key):
    state=read(STATE,{})
    return state.get('source')==key and state.get('dragged',False) and time.time()<state.get('expires',0)

def feedback(source='', target=''):
    subprocess.run(['eww','--no-daemonize','update','dock-drag-source='+source,'dock-drag-target='+target],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1)

def begin():
    # Hyprland binding launches this detached process; it never grabs input.
    RUNTIME.mkdir(parents=True,exist_ok=True)
    started=time.time()
    with open(RUNTIME/'glyphos-dock-drag.lock','w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        layer=dock_layer(query('layers'));cursor=query('cursorpos')
        data=read(PREFS,{});items=data.get('items',[])
        index=hit(cursor,layer,len(items))
        if data.get('hidden') or index is None:return
        source=items[index]['id'];origin=cursor;dragged=False;target=None;last_feedback=None
        state={'source':source,'dragged':False,'expires':started+20}
        write(STATE,state)
        try:
            while time.time()-started<20:
                cursor=query('cursorpos')
                distance=math.hypot(cursor['x']-origin['x'],cursor['y']-origin['y'])
                if distance>=10 and not dragged:
                    dragged=True;state.update(dragged=True);write(STATE,state)
                if dragged:
                    index=hit(cursor,layer,len(items),strict=False)
                    target=items[index]['id'] if index is not None else None
                    current=(source,target or '')
                    if current!=last_feedback:
                        feedback(*current);last_feedback=current
                released=read(RELEASE,{}).get('at',0)>=started
                if released:
                    if dragged and target:
                        with open(PREFS.with_suffix('.reorder.lock'),'w') as prefs_lock:
                            fcntl.flock(prefs_lock,fcntl.LOCK_EX)
                            latest=read(PREFS,{})
                            if 'items' in latest:
                                latest['items']=reordered(latest['items'],source,target);write(PREFS,latest)
                    break
                time.sleep(.035)
        finally:
            state.update(dragged=dragged,expires=time.time()+.8);write(STATE,state)
            if dragged:feedback()

def shift_press():
    layer=dock_layer(query('layers'));cursor=query('cursorpos')
    rows=read(PREFS,{}).get('items',[])
    index=hit(cursor,layer,len(rows))
    if index is not None:
        write(RUNTIME/'glyphos-dock-shift.json',{'id':rows[index]['id'],'time':time.time()})

def main():
    if len(sys.argv)>1 and sys.argv[1]=='shift-press':
        try:shift_press()
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):pass
    elif len(sys.argv)>1 and sys.argv[1]=='release':
        RUNTIME.mkdir(parents=True,exist_ok=True);write(RELEASE,{'at':time.time()})
    else:
        try:begin()
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):
            try:feedback()
            except (OSError,subprocess.SubprocessError):pass

if __name__=='__main__':main()

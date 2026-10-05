#!/usr/bin/env python3
import fcntl, os, sys
from common import STATE, call, hypr, read, write, notify, update
PATH=STATE/'focus.json'
def inputs(): return __import__('json').loads(call('pactl','--format=json','list','sink-inputs'))
def belongs(pid, active):
    for _ in range(24):
        if pid==active: return True
        try:
            text=open(f'/proc/{pid}/stat').read(); pid=int(text[text.rfind(')')+2:].split()[1])
        except (OSError,ValueError,IndexError): return False
        if pid<=1:return False
    return False
def enforce(state):
    for stream in inputs():
        key=str(stream['index']); props=stream.get('properties',{})
        identity={k:props.get(k,'') for k in ('application.process.id','application.name','object.serial')}
        if key not in state['streams'] or state['streams'][key]['identity']!=identity:
            state['streams'][key]={'mute':stream['mute'],'identity':identity}
        try: pid=int(props.get('application.process.id',0))
        except ValueError: pid=0
        mute=not belongs(pid,state['pid'])
        call('pactl','set-sink-input-mute',key,'1' if mute else '0',check=False)
    write(PATH,state)
def action(command):
    with (STATE/'focus.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=read(PATH,{'enabled':False})
        if command=='tick':
            if state['enabled']: enforce(state)
            return
        if state['enabled']:
            for stream in inputs():
                old=state.get('streams',{}).get(str(stream['index']))
                identity={k:stream.get('properties',{}).get(k,'') for k in ('application.process.id','application.name','object.serial')}
                if old and old['identity']==identity: call('pactl','set-sink-input-mute',str(stream['index']),'1' if old['mute'] else '0',check=False)
            if not state.get('dnd_was_on'): call('makoctl','mode','-r','do-not-disturb',check=False)
            write(PATH,{'enabled':False}); update(glyph_focus=False); notify('Focus mode off · previous mute settings restored')
        else:
            active=hypr('activewindow'); pid=active.get('pid',0)
            if not pid: notify('Select an application before enabling focus mode');return
            modes=call('makoctl','mode',check=False)
            state={'enabled':True,'app':active.get('class','Application'),'pid':pid,'streams':{},'dnd_was_on':'do-not-disturb' in modes.split()}
            enforce(state); call('makoctl','mode','-a','do-not-disturb',check=False)
            update(glyph_focus=True); notify('Focus mode on · '+active.get('class','Application'))
if __name__=='__main__': action(sys.argv[1] if len(sys.argv)>1 else 'toggle')

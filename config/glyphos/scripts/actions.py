#!/usr/bin/env python3
import configparser, hashlib, json, os, re, shlex, shutil, subprocess, sys, time
from pathlib import Path
from urllib.parse import unquote
from common import HOME, BASE, STATE, call, read, write, update, notify, hypr
SCRIPT=str(BASE/'scripts/actions.py')
PINS=BASE/'clipboard_pins.txt'
UNDO=Path('/tmp/glyph_file_undo.log')
def menu(lines,prompt,custom=False):
    args=['python3',str(BASE/'scripts/picker.py')]
    p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    write(STATE/'palette.json',{'pid':p.pid,'started':time.time()})
    try: out,_=p.communicate(json.dumps({'choices':lines,'prompt':prompt,'custom':custom}),timeout=125)
    except subprocess.TimeoutExpired:
        p.terminate();p.communicate(timeout=2);return ''
    finally:write(STATE/'palette.json',{})
    return out.strip() if p.returncode in (0,10,11) else ''
def palette():
    choices=['Apps','Run command','Windows','Keyboard shortcuts','Clipboard history','Pin clipboard snippet','Search files','Focus mode','Notifications','Wi-Fi','Bluetooth','Theme','Volume +5%','Volume −5%','Mute','Lock','Sleep','Reboot','Shutdown']
    selected=menu(choices,'GLYPHOS')
    action={'Apps':'apps','Run command':'run','Windows':'windows','Keyboard shortcuts':'keys','Clipboard history':'clipboard','Pin clipboard snippet':'clipboard-pin','Search files':'files','Focus mode':'focus','Notifications':'notifications','Wi-Fi':'wifi','Bluetooth':'bluetooth','Theme':'theme','Volume +5%':'volume-up','Volume −5%':'volume-down','Mute':'mute','Lock':'lock','Sleep':'sleep','Reboot':'reboot','Shutdown':'shutdown'}.get(selected)
    if action: dispatch(action)
def clipboard():
    call('python3',str(HOME/'.config/eww/scripts/clipboard-history.py'),'open',timeout=10)
def pin():
    text=call('wl-paste','--no-newline')
    if not text:return
    pins=read(PINS,[])
    if text in pins:
        if menu(['Unpin','Cancel'],'Already pinned')=='Unpin':pins.remove(text)
    else:pins.append(text)
    write(PINS,pins[-100:]);notify('Clipboard pins saved')
def files():
    from search import results, launch
    query=menu([],'Search names and document contents',custom=True)
    if not query:return
    found=[r for r in results(query) if r['kind']=='file']
    if not found:notify('No local file matches');return
    labels=[r['label'] for r in found]; selected=menu(labels,'Files')
    if selected:launch(found[labels.index(selected)])
def windows():
    clients=hypr('clients'); labels=[str(i)+' · '+c['class']+' · '+c['title'].replace('\n',' ') for i,c in enumerate(clients)]
    selected=menu(labels,'Windows')
    if selected:call('hyprctl','dispatch','focuswindow','address:'+clients[labels.index(selected)]['address'])
def keys():
    binds=hypr('binds'); menu([f"{b['modmask']} + {b['key']} · {b['dispatcher']} {b.get('arg','')}" for b in binds],'Shortcuts · modifiers: 4 Ctrl, 1 Shift, 64 Super')
def undo():
    import fcntl
    with (STATE/'undo.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=read(UNDO,[])
        candidates=[(i,r) for i,r in enumerate(rows) if r.get('kind') in ('move','trash')]
        if not candidates:notify('No recoverable file operation recorded');return
        i,row=candidates[-1]; source=Path(row['to']); target=Path(row['from'])
        if not source.exists():notify('Undo source is no longer available');return
        if target.exists():notify('Undo stopped · original path already exists');return
        target.parent.mkdir(parents=True,exist_ok=True)
        write(STATE/'undo-ignore.json',{'paths':[str(source),str(target)],'until':time.time()+3})
        shutil.move(str(source),str(target))
        if row.get('info'):Path(row['info']).unlink(missing_ok=True)
        rows.pop(i); write(UNDO,rows);notify('Restored '+target.name)
def radio_rows(kind):
    if kind=='wifi':
        raw=call('nmcli','-t','--escape','yes','-f','SSID,SIGNAL,SECURITY,IN-USE','device','wifi','list','--rescan','no',check=False)
        rows=[];seen=set()
        for line in raw.splitlines():
            fields=re.split(r'(?<!\\):',line)
            if len(fields)<4:continue
            ssid=fields[0].replace('\\:',':').replace('\\\\','\\')
            if not ssid or ssid in seen:continue
            seen.add(ssid); rows.append({'id':hashlib.sha256(ssid.encode()).hexdigest()[:16],'value':ssid,'label':ssid+' · '+fields[1]+'% '+fields[2]+(' · Connected' if fields[3]=='*' else '')})
    else:
        rows=[]
        for line in call('bluetoothctl','devices',check=False).splitlines():
            parts=line.split(' ',2)
            if len(parts)==3 and re.fullmatch(r'[0-9A-Fa-f:]{17}',parts[1]):rows.append({'id':parts[1].replace(':',''),'value':parts[1],'label':parts[2]})
    write(STATE/(kind+'-rows.json'),rows[:12]);return rows[:12]
def connect(kind,key):
    row=next((r for r in read(STATE/(kind+'-rows.json'),[]) if r['id']==key),None)
    if not row:return
    if kind=='wifi':
        # NetworkManager secret agent prompts securely for a new network password.
        p=subprocess.run(['nmcli','--wait','12','device','wifi','connect',row['value']],capture_output=True,text=True,timeout=15)
        if p.returncode:
            subprocess.Popen(['python3',str(BASE/'scripts/wifi_credentials.py'),key],start_new_session=True)
        else:notify('Connected to '+row['value'])
    else:
        output=call('bluetoothctl','--timeout','10','connect',row['value'],timeout=12,check=False)
        notify(output[-200:] or 'Bluetooth connection requested')
def dismiss():
    import socket
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as ipc:
            ipc.sendto(b'{"op":"outside"}',str(Path(os.environ['XDG_RUNTIME_DIR'])/'glyphos-island.sock'))
    except OSError:pass
    cursor=hypr('cursorpos'); layers=hypr('layers')
    config=(HOME/'.config/eww/eww.yuck').read_text()
    panels=[(name,re.search(r':namespace "([^"]+)"',body).group(1) if re.search(r':namespace "([^"]+)"',body) else name) for name,body in re.findall(r'\(defwindow\s+([\w-]+)(.*?)(?=\n\(def|\Z)',config,re.S) if ':stacking "overlay"' in body]
    for window,namespace in panels:
        surfaces=[s for m in layers.values() for rows in m.get('levels',{}).values() for s in rows if s.get('namespace')==namespace]
        if surfaces and not any(s['x']<=cursor['x']<s['x']+s['w'] and s['y']<=cursor['y']<s['y']+s['h'] for s in surfaces):call('eww','close',window,check=False)
def context_details():
    value=json.loads(call('eww','get','app-context')); update(glyph_detail=value.get('name','Application')+'\n'+value.get('desktop','')+'\n'+value.get('flatpak',''))
    call('eww','close','taskbar-context',check=False);call('eww','open','glyph-app-details')
def context_close():
    value=json.loads(call('eww','get','app-context'))
    if re.fullmatch(r'0x[0-9a-fA-F]+',value.get('address','')):
        call('hyprctl','dispatch','closewindow','address:'+value['address'],check=False)
        call('eww','close','taskbar-context',check=False);return
    sys.path.insert(0,str(HOME/'.config/eww/scripts'))
    from app_service import resolve
    for client in hypr('clients'):
        app=resolve(client)
        if app and app['key']==value['key']:call('hyprctl','dispatch','closewindow','address:'+client['address'],check=False)
    call('eww','close','taskbar-context',check=False)
def dispatch(action,arg=''):
    if action=='palette':palette()
    elif action=='clipboard':clipboard()
    elif action=='clipboard-pin':pin()
    elif action=='files':files()
    elif action=='windows':windows()
    elif action=='keys':keys()
    elif action in ('apps','run'):
        if action=='apps':
            from gi.repository import Gio
            apps={a.get_display_name()+' · '+(a.get_id() or ''):a for a in Gio.AppInfo.get_all() if a.should_show()}
            selected=menu(sorted(apps),'Apps')
            if selected:apps[selected].launch([],None)
        else:
            selected=menu([],'Run command',custom=True)
            if selected:subprocess.Popen(shlex.split(selected),start_new_session=True)
    elif action=='focus':
        from focus_mode import action as toggle;toggle('toggle')
    elif action=='theme':
        selected=menu(['Light','Dark','Automatic · 06:00 / 18:00'],'Theme')
        if selected:
            preference={'Light':'light','Dark':'dark','Automatic · 06:00 / 18:00':'auto'}[selected]
            write(STATE/'theme.json',dict(read(STATE/'theme.json',{}),preference=preference))
            from theme import apply;apply(force=True)
    elif action=='undo':undo()
    elif action in ('wifi','bluetooth','notifications'):call('eww','open','--toggle',{'wifi':'wifi-menu','bluetooth':'bluetooth-menu','notifications':'glyph-notifications'}[action])
    elif action=='wifi-toggle':
        enabled=call('nmcli','radio','wifi')=='enabled';call('nmcli','radio','wifi','off' if enabled else 'on')
    elif action=='bluetooth-toggle':
        enabled='Powered: yes' in call('bluetoothctl','show',check=False);call('bluetoothctl','--timeout','4','power','off' if enabled else 'on',timeout=6)
    elif action in ('wifi-connect','bluetooth-connect'):connect(action.split('-')[0],arg)
    elif action=='bluetooth-scan':subprocess.Popen(['bluetoothctl','--timeout','8','scan','on'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    elif action=='dismiss':dismiss()
    elif action=='context-details':context_details()
    elif action=='context-close':context_close()
    elif action=='volume-up':call('wpctl','set-volume','-l','1.0','@DEFAULT_AUDIO_SINK@','5%+')
    elif action=='volume-down':call('wpctl','set-volume','@DEFAULT_AUDIO_SINK@','5%-')
    elif action=='mute':call('wpctl','set-mute','@DEFAULT_AUDIO_SINK@','toggle')
    elif action=='lock':subprocess.Popen(['hyprlock'],start_new_session=True)
    elif action=='sleep':call('systemctl','suspend')
    elif action in ('reboot','shutdown'):
        if menu(['Cancel',action.title()],'Confirm '+action)==action.title():call('systemctl','reboot' if action=='reboot' else 'poweroff')
    elif action=='git':
        active=hypr('activewindow');pid=active.get('pid')
        try: cwd=Path(f'/proc/{pid}/cwd').resolve(strict=True)
        except OSError:cwd=HOME
        subprocess.Popen(['kitty','--directory',str(cwd),'-e','bash','-c','git status; read -r -p "Press Enter to close"'],start_new_session=True)
    elif action=='terminal':call('hyprctl','dispatch','togglespecialworkspace','glyph-terminal');subprocess.Popen(['kitty','--class','glyph-terminal'],start_new_session=True) if not any(c['class']=='glyph-terminal' for c in hypr('clients')) else None
    elif action=='summarize':
        from gemini import answer
        groups=read(STATE/'notifications.json',[]);group=next((g for g in groups if g['id']==arg),None)
        if group:
            result=answer(group['text'],summary=True)
            write(STATE/('summary-'+arg+'.json'),{'text':result,'revision':group['revision']})
    else:raise ValueError('Unknown action: '+action)
if __name__=='__main__':
    try:dispatch(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else '')
    except Exception as error:
        print('glyphos:',error,file=sys.stderr)
        try:notify(str(error)[:200])
        except Exception:pass
        sys.exit(1)

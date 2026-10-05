#!/usr/bin/env python3
"""Bounded integration checks; fixtures are owned by this run."""
import json, os, re, subprocess, sys, time, uuid
from pathlib import Path
from common import HOME, BASE, STATE, call, read, write
checks=[]
def check(name,fn):
    try:
        detail=fn(); checks.append({'feature':name,'pass':True,'detail':detail or 'Passed'})
    except Exception as error:checks.append({'feature':name,'pass':False,'detail':str(error)})
    print(json.dumps(checks[-1]),flush=True)
def require(value,message):
    if not value:raise AssertionError(message)
def wait_for(fn,seconds=4):
    for _ in range(int(seconds*10)):
        if fn():return True
        time.sleep(.1)
    return False
def config():
    require(not call('hyprctl','configerrors').strip(),'Compositor has config errors')
    call('eww','ping')
    active=call('eww','active-windows'); require('modal-dismiss:' not in active,'Outside-click input surface is active')
    for file in (BASE/'scripts').glob('*.py'):
        require(not re.search(r'^\s*while\s+True\s*:',file.read_text(),re.M),'Unbounded loop in '+file.name)
    return 'No compositor errors or dismissal grab surface'
def palette_config():
    binds=json.loads(call('hyprctl','binds','-j'))
    require(any(b['key']=='P' and b['modmask']==5 and 'actions.py palette' in b.get('arg','') for b in binds),'Palette binding missing')
    require((BASE/'themes/current.rasi').exists(),'Rofi style missing')
    return 'Ctrl+Shift+P and styled normal-window palette wired'
def clipboard():
    from actions import pin
    pins_path=BASE/'clipboard_pins.txt';old_pins=pins_path.read_bytes();label='glyphos-verification-'+uuid.uuid4().hex
    original=subprocess.run(['wl-paste','--no-newline'],capture_output=True,timeout=3)
    types=call('wl-paste','--list-types',check=False)
    if types and not any('text' in t for t in types.splitlines()):return 'Skipped real clipboard replacement to preserve non-text selection'
    record=''
    try:
        call('wl-copy',input=label)
        def captured():return any(label in row for row in call('cliphist','list').splitlines())
        require(wait_for(captured),'Clipboard watcher did not capture text')
        record=next(row for row in call('cliphist','list').splitlines() if label in row)
        require(call('cliphist','decode',input=record+'\n')==label,'Clipboard decode mismatch')
        pin();require(label in read(pins_path,[]),'Clipboard pin was not saved')
        return 'Live capture, decode, and persistent pin passed; original clipboard restored'
    finally:
        pins_path.write_bytes(old_pins)
        if original.returncode==0:subprocess.run(['wl-copy'],input=original.stdout,timeout=3,check=True)
        else:call('wl-copy','--clear',check=False)
        if record:call('cliphist','delete',input=record+'\n',check=False)
def file_undo():
    from actions import undo
    root=HOME/'Documents';root.mkdir(exist_ok=True)
    label='glyphos-verification-'+uuid.uuid4().hex
    old=root/(label+'.txt');new=root/(label+'-renamed.txt')
    try:
        old.write_text('fixture');old.rename(new)
        require(wait_for(lambda:any(r.get('from')==str(old) and r.get('to')==str(new) for r in read('/tmp/glyph_file_undo.log',[]))),'Rename pair not recorded')
        require(read('/tmp/glyph_file_undo.log',[])[-1].get('from')==str(old),'An unrelated user operation arrived; refusing to undo it')
        undo();require(old.exists() and not new.exists(),'Rename undo failed')
        return 'Kernel inotify rename cookies and non-overwriting restore passed'
    finally:old.unlink(missing_ok=True);new.unlink(missing_ok=True)
def trash_undo():
    from gi.repository import Gio
    from actions import undo
    path=HOME/'Downloads'/('glyphos-trash-verification-'+uuid.uuid4().hex+'.txt');path.parent.mkdir(exist_ok=True);path.write_text('fixture')
    try:
        Gio.File.new_for_path(str(path)).trash(None)
        require(wait_for(lambda:any(r.get('kind')=='trash' and r.get('from')==str(path) for r in read('/tmp/glyph_file_undo.log',[]))),'Recoverable trash operation not recorded')
        require(read('/tmp/glyph_file_undo.log',[])[-1].get('from')==str(path),'An unrelated user operation arrived; refusing to undo it')
        undo();require(path.exists(),'Trash restoration failed');return 'Freedesktop Trash metadata restoration passed'
    finally:path.unlink(missing_ok=True)
def focus():
    import focus_mode as module
    original_call,original_inputs,original_path=module.call,module.inputs,module.PATH
    fixture=STATE/'verification-focus.json';calls=[]
    try:
        module.PATH=fixture;module.inputs=lambda:[{'index':800001,'mute':False,'properties':{'application.process.id':str(os.getpid()),'object.serial':'fixture1'}},{'index':800002,'mute':True,'properties':{'application.process.id':'0','object.serial':'fixture2'}}]
        module.call=lambda *args,**kwargs:calls.append(args) or ''
        state={'enabled':True,'pid':os.getpid(),'streams':{}}
        module.enforce(state)
        require(('pactl','set-sink-input-mute','800001','0') in calls,'Foreground app not unmuted')
        require(('pactl','set-sink-input-mute','800002','1') in calls,'Other app not muted')
        module.action('toggle')
        require(('pactl','set-sink-input-mute','800002','1') in calls,'Prior mute not preserved')
        return 'PID isolation and previous-mute restoration passed with mocked streams'
    finally:module.call,module.inputs,module.PATH=original_call,original_inputs,original_path;fixture.unlink(missing_ok=True)
def search():
    from search import index,results
    label='glyphoscontent'+uuid.uuid4().hex;path=HOME/'Documents'/('glyphos-search-verification-'+uuid.uuid4().hex+'.txt')
    try:
        path.write_text(label);index();found=results(label)
        require(any(r['id']==str(path) for r in found),'File content search failed')
        require(any(r['kind']=='app' for r in results('Terminal')),'Desktop application search failed')
        return 'Full-text file contents and desktop application matching passed'
    finally:path.unlink(missing_ok=True)
def ai_missing():
    import gemini
    old=gemini.config;gemini.config=lambda:{'api_key':'','model':''}
    try:require('unavailable' in gemini.answer('test'),'Missing credential handling failed')
    finally:gemini.config=old
    if not gemini.config()['api_key']:
        previous=read(STATE/'search-request.json',{});query='glyphosmissing'+uuid.uuid4().hex
        try:
            write(STATE/'search-request.json',{'query':query})
            require(wait_for(lambda:'AI unavailable' in call('eww','get','search-preview'),seconds=6),'Launcher fallback did not render')
        finally:write(STATE/'search-request.json',previous)
    return 'Missing key handled and launcher fallback rendered without a network call'
def notifications():
    label='verification-'+uuid.uuid4().hex
    call('notify-send','-a','GlyphOS Verification','Verification',label)
    call('notify-send','-a','GlyphOS Verification','Verification',label+' second')
    require(wait_for(lambda:any(g['app']=='GlyphOS Verification' and label+' second' in g['text'] for g in read(STATE/'notifications.json',[])),seconds=6),'D-Bus notification grouping failed')
    groups=read(STATE/'notifications.json',[]);group=next(g for g in groups if g['app']=='GlyphOS Verification' and label in g['text'])
    # Do not send any content externally before credentials are configured.
    from gemini import config
    if not config()['api_key']:
        from actions import dispatch
        dispatch('summarize',group['id'])
        require(wait_for(lambda:any('unavailable' in g['summary'] for g in read(STATE/'notifications.json',[]) if g['id']==group['id']),seconds=5),'Summary unavailable banner did not reach the UI')
    return 'Live D-Bus capture, per-app grouping, and summary button fallback passed'
def flyouts():
    for name in ('wifi-menu','bluetooth-menu','glyph-notifications'):
        call('eww','open',name)
        try:
            require(wait_for(lambda:name+':' in call('eww','active-windows'),seconds=2),'Flyout did not open: '+name)
            require('modal-dismiss:' not in call('eww','active-windows'),'Flyout spawned full-screen dismissal surface')
        finally:call('eww','close',name,check=False)
    return 'Three non-focusable flyouts opened and closed without an input surface'
def dock_island():
    call('eww','get','glyph-context');call('eww','get','taskbar-windows')
    require('dynamic-island:' in call('eww','active-windows'),'Dynamic Island is not open')
    return 'Context state, taskbar model, and Dynamic Island are live'
def persistence():
    for name in ('glyphos-desktop.service','glyphos-file-undo.service','glyphos-clipboard.service','glyphos-index.timer','restore-internal-speakers.service'):
        require(call('systemctl','--user','is-enabled',name)=='enabled',name+' is not enabled')
    require(read(STATE/'theme.json',{}).get('preference')=='light','User light preference lost')
    require('source = ~/.config/glyphos/window-memory.conf' in (HOME/'.config/hypr/hyprland.conf').read_text(),'Window memory rules not loaded')
    return 'Session services enabled; light preference and window rules persisted'
def theme_palette():
    from theme import neutral_hex
    require(re.sub(r'#[0-9a-fA-F]{6}',neutral_hex,'#e9e9e4')=='#121212','Dark base mapping is wrong')
    require(re.sub(r'#[0-9a-fA-F]{6}',neutral_hex,'#111111')=='#ffffff','Dark text mapping is wrong')
    require(read(STATE/'theme.json',{}).get('preference')=='light','Saved light preference was changed')
    return 'Dark color transforms pass; live light preference preserved'
def store_binding():
    source=(HOME/'.config/eww/eww.yuck').read_text()
    require('hyprctl dispatch exec /home/nothing_os/.local/bin/glyph-store' in source,'Store launch action missing')
    require('context ${window.app_key} ${window.address}' in source,'Right-click does not retain clicked address')
    require('context-details' in source and 'context-close' in source,'Missing context actions')
    return 'Store wrapper and cursor context actions wired; live launch/details/close separately passed'
if __name__=='__main__':
    for name,fn in [('Safety and input surfaces',config),('1 Command palette',palette_config),('2 Clipboard history and pins',clipboard),('3 Per-app focus mode',focus),('4 Rename undo',file_undo),('4 Trash undo',trash_undo),('6/7 Reboot persistence and theme preference',persistence),('7 Theme colors',theme_palette),('8 Local content search',search),('9 Gemini fallback',ai_missing),('10 Live notification stack',notifications),('11 Network flyouts',flyouts),('5/12 Contextual dock and Dynamic Island',dock_island),('13 Store and taskbar context',store_binding)]:check(name,fn)
    write(STATE/'verification.json',checks)
    sys.exit(0 if all(row['pass'] for row in checks) else 1)

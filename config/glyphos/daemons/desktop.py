#!/usr/bin/env python3
"""Non-grabbing GLib IPC service; expensive work runs in bounded worker threads."""
import ast, concurrent.futures, hashlib, json, os, re, signal, socket, subprocess, sys, time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gio, GLib, Gtk
sys.path.insert(0,str(Path.home()/'.config/glyphos/scripts'))
from common import HOME, BASE, STATE, call, hypr, read, write, update
from window_memory import Memory
from live_island import Island
from actions import radio_rows
from theme import apply as theme
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=3)
class Desktop:
    def __init__(self):
        self.running=set();self.socket=None;self.buffer=b'';self.focused=False;self.notification_rows=read(STATE/'notification-events.json',[])[-100:]
        self.island=Island(self.submit);self.memory=Memory();self.last=None;self.monitor=None;self.rofi_seen={};self.rofi_process=False;self.last_taskbar=None;self.last_active=None;self.ticks=0;self.context_dirty=True;self.last_context=None;self.context_sent=0;self.taskbar_sent=0
        self.connect_socket()
        self.notifications()
        GLib.timeout_add_seconds(1,self.tick)
        GLib.timeout_add_seconds(5,self.network)
        GLib.timeout_add_seconds(60,self.theme_tick)
        self.submit('context',self.context)
        self.submit('layers',self.layers)
        self.submit('theme',theme)
        self.network()
        self.search_query=None
    def submit(self,name,fn):
        if name in self.running:return
        self.running.add(name)
        def work():
            try:fn()
            except Exception as error:print(name+': '+str(error),file=sys.stderr,flush=True)
            finally:GLib.idle_add(lambda:(self.running.discard(name),False)[1])
        POOL.submit(work)
    def layers(self):
        for name in ('top-bar','app-titlebar','weather','dot-field','home','nowplaying','dock'):
            opened=call('eww','active-windows')
            if name+':' in opened:continue
            call('eww','open',name,check=False)
            time.sleep(.25)
    def connect_socket(self):
        path=Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/os.environ['HYPRLAND_INSTANCE_SIGNATURE']/'.socket2.sock'
        try:
            sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(1);sock.connect(str(path));sock.setblocking(False)
            self.socket=sock;GLib.io_add_watch(sock.fileno(),GLib.IO_IN|GLib.IO_HUP|GLib.IO_ERR,self.events)
        except OSError as error:
            print('IPC connection: '+str(error),flush=True);self.socket=None
    def events(self,fd,condition):
        if condition&(GLib.IO_HUP|GLib.IO_ERR):
            self.socket.close();self.socket=None;return False
        try:data=self.socket.recv(65536)
        except BlockingIOError:return True
        if not data:self.socket.close();self.socket=None;return False
        self.buffer+=data
        lines=self.buffer.split(b'\n');self.buffer=lines.pop()
        for line in lines:
            event,_,payload=line.decode(errors='replace').partition('>>')
            if event in ('activewindow','activewindowv2','windowtitle','windowtitlev2'):self.context_dirty=True
            if event=='openwindow':
                address='0x'+payload.split(',')[0].removeprefix('0x');self.memory.opened(address)
            if event=='closewindow':self.memory.pending.pop('0x'+payload.removeprefix('0x'),None)
        return True
    def context(self):
        active=hypr('activewindow');name=active.get('class','').lower()
        active['title']=re.sub(r'^[\u2800-\u28ff]\s*','',active.get('title',''))
        write(STATE/'island-context.json', {'title': active.get('title') or 'GlyphOS'})
        mode='dev' if any(t in name for t in ('kitty','terminal','code','nvim','vim','emacs','alacritty')) else 'media' if any(t in name for t in ('mpv','vlc','spotify','youtube','brave','firefox','chromium')) else 'default'
        dark=read(STATE/'theme.json',{}).get('mode')=='dark'
        value=dict(glyph_context=mode,glyph_title=active.get('title','GlyphOS'),glyph_address=active.get('address',''),glyph_focus=read(STATE/'focus.json',{}).get('enabled',False),
            active_client={'address':active.get('address',''),'title':active.get('title',''),'visible':bool(active.get('address')) and active.get('mapped',True) and not active.get('hidden',False)},
            glyph_dark=dark,glyph_assets=str(BASE/'themes/dark-assets') if dark else 'assets')
        if value!=self.last_context or time.monotonic()-self.context_sent>15:
            update(**value);self.last_context=value;self.context_sent=time.monotonic()
        if self.last_active is not None and self.last_active!=active.get('address'):
            opened={row.split(':',1)[0] for row in call('eww','active-windows').splitlines()}
            dismiss=opened & {'wifi-menu','bluetooth-menu','glyph-notifications','taskbar-context','app-launcher'}
            if dismiss:call('eww','close',*sorted(dismiss),check=False)
        self.last_active=active.get('address')
    def tick(self):
        self.ticks+=1
        self.submit('island',self.island.collect)
        if self.socket is None:self.connect_socket()
        if self.memory.pending or self.ticks%5==0:self.submit('memory',self.memory.tick)
        if self.ticks%2==0:
            self.submit('focus',self.focus)
            self.submit('summaries',self.groups)
        if self.ticks%5==0:self.submit('taskbar',self.taskbar)
        if self.ticks%5==0:write(STATE/'desktop-health.json',{'time':time.time(),'ticks':self.ticks,'jobs':sorted(self.running),'pending_windows':list(self.memory.pending)})
        if self.context_dirty or self.ticks%15==0:
            self.context_dirty=False
            self.submit('context',self.context)
        query=read(STATE/'search-request.json',{}).get('query','')
        if query!=self.search_query and 'search' not in self.running:
            self.search_query=query
            from search import worker
            self.submit('search',lambda q=query:worker(q))
        return True
    def taskbar(self):
        # GTK icon lookup runs on the main thread of a short-lived process.
        rows=json.loads(call('python3',str(HOME/'.config/eww/scripts/taskbar.py'),timeout=5))
        for row in rows:row['tooltip']=re.sub(r'[\u2800-\u28ff]\s*','',row.get('tooltip',''))
        if rows!=self.last_taskbar or time.monotonic()-self.taskbar_sent>15:
            self.last_taskbar=rows;update(taskbar_windows=rows);self.taskbar_sent=time.monotonic()
    def focus(self):
        if not read(STATE/'focus.json',{}).get('enabled'):return
        from focus_mode import action
        action('tick')
    def network(self):
        def refresh():
            rows=radio_rows('wifi');bt=radio_rows('bluetooth')
            update(glyph_wifi_rows=rows,glyph_bt_rows=bt)
        self.submit('network',refresh);return True
    def theme_tick(self):
        self.submit('theme',theme);return True
    def notifications(self):
        try:
            self.monitor=subprocess.Popen(['dbus-monitor','--session',"type='method_call',interface='org.freedesktop.Notifications',member='Notify'"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            os.set_blocking(self.monitor.stdout.fileno(),False)
            self.notification_buffer=b'';self.notification_strings=None
            GLib.io_add_watch(self.monitor.stdout.fileno(),GLib.IO_IN|GLib.IO_HUP,self.notification_message)
            print('Notification D-Bus monitor connected',flush=True)
        except Exception as error:
            print('Notification monitor unavailable: '+str(error),flush=True)
    def notification_message(self,fd,condition):
        if condition&GLib.IO_HUP:return False
        try:self.notification_buffer+=os.read(fd,65536)
        except BlockingIOError:return True
        lines=self.notification_buffer.split(b'\n');self.notification_buffer=lines.pop()
        for raw in lines:
            line=raw.decode(errors='replace').strip()
            if line.startswith('method call '):
                self.notification_strings=[] if 'member=Notify' in line else None
            elif self.notification_strings is not None and line.startswith('string '):
                try:value=ast.literal_eval(line[7:])
                except (ValueError,SyntaxError):value=line[7:].strip('"')
                self.notification_strings.append(value)
                if len(self.notification_strings)==4:
                    app,icon,title,body=self.notification_strings
                    self.add_notification((app,0,icon,title,body));self.notification_strings=None
        return True
    def add_notification(self,args):
        app=args[0] or 'Application';text=(args[3]+' · '+args[4]).strip(' ·')
        if args[3]=='GlyphOS' and args[4].startswith('Restored '):
            self.island.toast('undo','File restored: '+args[4][9:],'↶')
            return False
        if app=='GlyphOS':
            if args[3].startswith('Restored '):self.island.toast('undo','File restored: '+args[3][9:], '↶')
            return False
        import re
        self.notification_rows.append({'app':app,'text':re.sub('<[^>]+>','',text)[:2000],'time':time.time()})
        self.notification_rows=self.notification_rows[-100:]
        write(STATE/'notification-events.json',self.notification_rows)
        self.submit('summaries',self.groups);return False
    def groups(self):
        grouped={}
        for row in list(self.notification_rows):
            if time.time()-row['time']>86400:continue
            grouped.setdefault(row['app'],[]).append(row['text'])
        output=[]
        for app,texts in grouped.items():
            text='\n'.join(texts[-8:]);key=hashlib.sha256(app.encode()).hexdigest()[:16];revision=hashlib.sha256(text.encode()).hexdigest()
            summary=read(STATE/('summary-'+key+'.json'),{})
            output.append({'id':key,'app':app,'count':len(texts),'text':text,'revision':revision,'summary':summary.get('text','') if summary.get('revision')==revision else ''})
        if output!=self.last or self.ticks%10==0:
            self.last=output;write(STATE/'notifications.json',output);update(glyph_notifications=output)
if __name__=='__main__':
    os.umask(0o077);Desktop();loop=GLib.MainLoop()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,lambda:(loop.quit(),False)[1])
    loop.run();POOL.shutdown(wait=False,cancel_futures=True)

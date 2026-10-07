#!/usr/bin/env python3
"""Drag-only Hyprland snap picker; no grabs, input interception or idle polling."""
import fcntl
import json
import math
import os
from pathlib import Path
import queue
import select
import socket
import subprocess
import sys
import threading
import time

ROOT=Path.home()/'.local/state/glyphos/snap'
CONTROL=ROOT/'control.sock'
PRESETS={'halves':[(0,0,.5,1),(.5,0,.5,1)],
         'thirds':[(0,0,1/3,1),(1/3,0,1/3,1),(2/3,0,1/3,1)],
         'grid':[(0,0,.5,.5),(.5,0,.5,.5),(0,.5,.5,.5),(.5,.5,.5,.5)],
         'sidebar':[(0,0,1/3,1),(1/3,0,2/3,1)]}


def socket_path(name):
    signature=os.environ['HYPRLAND_INSTANCE_SIGNATURE']
    candidates=[Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'hypr'/signature/name,
                Path('/tmp/hypr')/signature/name]
    return next((p for p in candidates if p.exists()),candidates[0])


def ipc(command):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(.3);sock.connect(str(socket_path('.socket.sock')))
        sock.sendall(command.encode());parts=[]
        while True:
            data=sock.recv(65536)
            if not data:break
            parts.append(data)
    return b''.join(parts).decode()


def query(name):return json.loads(ipc('j/'+name))


def area(monitor):
    width=round(monitor['width']/monitor['scale']);height=round(monitor['height']/monitor['scale'])
    if monitor.get('transform',0)%2:width,height=height,width
    left,top,right,bottom=monitor.get('reserved',[0,0,0,0])
    return monitor['x']+left,monitor['y']+top,width-left-right,height-top-bottom


def cells(preset,rect):
    x,y,w,h=rect
    # Round boundaries rather than widths so fractional splits meet exactly.
    return [(x+round(a*w),y+round(b*h),round((a+c)*w)-round(a*w),round((b+d)*h)-round(b*h))
            for a,b,c,d in PRESETS[preset]]


def plan(preset,zone,rect,windows,selected):
    slots=cells(preset,rect);others=[w for w in windows if w['address']!=selected]
    others.sort(key=lambda w:(w.get('focusHistoryID',999),w['address']))
    result=[(selected,slots[zone])];free=[s for i,s in enumerate(slots) if i!=zone]
    # More windows than preset cells: subdivide remaining cells without overlaps.
    groups=[[] for _ in free]
    for i,window in enumerate(others):groups[i%len(free)].append(window)
    for rect,group in zip(free,groups):
        x,y,w,h=rect
        for i,window in enumerate(group):
            y0=round(i*h/len(group));y1=round((i+1)*h/len(group))
            result.append((window['address'],(x,y+y0,w,y1-y0)))
    if any(w<80 or h<60 for _,(_,_,w,h) in result):
        raise ValueError('Too many windows to fit usable snap cells')
    return result


def hit(cursor,monitor,picker=None):
    # Same fixed diagram metrics as the Eww widget (720x150, four 156px cards).
    x,y=cursor['x'],cursor['y'];mx,my,mw,mh=area(monitor)
    origin=picker['x'] if picker else monitor['x']+(round(monitor['width']/monitor['scale'])-720)//2
    top=picker['y'] if picker else area(monitor)[1]+12
    localx=x-origin;localy=y-top
    for i,preset in enumerate(PRESETS):
        dx=localx-(18+i*174+9);dy=localy-18
        if 0<=dx<138 and 0<=dy<76:
            for zone,(a,b,c,d) in enumerate(PRESETS[preset]):
                if a*138<=dx<(a+c)*138 and b*76<=dy<(b+d)*76:return preset,zone
    return None


def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT,timeout=2)


class Engine:
    def __init__(self,preview,monitor_indices=None):
        self.preview=preview;self.monitor_indices=monitor_indices if monitor_indices is not None else {};self.drag=None;self.open=False
        self.selection=None;self.picker=None;self.events=None;self.event_buffer=b'';self.last_frame=0

    def dismiss(self):
        if self.open:
            run('eww','--no-daemonize','update','snap-reveal=false')
            run('eww','--no-daemonize','close','snap-picker')
        self.preview(None,None);self.drag=None;self.open=False;self.selection=None;self.picker=None

    def begin(self,explicit=False):
        time.sleep(.015)  # Let the non-consuming click update application focus.
        window=query('activewindow');cursor=query('cursorpos')
        if not window or window.get('fullscreen',0)>1 or window.get('workspace',{}).get('id',-1)<0:
            print('Drag not armed: inactive/fullscreen/special workspace',flush=True);return
        x,y=window['at'];w,h=window['size']
        if not (x-8<=cursor['x']<=x+w+8 and y-8<=cursor['y']<=y+h+8):
            print('Drag not armed: pointer outside active window',flush=True);return
        print('Drag armed',flush=True)
        self.drag={'window':window,'cursor':cursor,'start':time.monotonic(),'confirmed':False,'explicit':explicit,
                   'geometry':(window['at'],window['size']),'monitor':None}

    def frame(self):
        drag=self.drag
        if not drag:return
        if time.monotonic()-drag['start']>30:self.dismiss();return
        cursor=query('cursorpos')
        if not drag['confirmed']:
            current=query('activewindow')
            if current.get('address')!=drag['window']['address']:self.dismiss();return
            distance=math.hypot(cursor['x']-drag['cursor']['x'],cursor['y']-drag['cursor']['y'])
            drag['confirmed']=distance>8 and (drag['explicit'] or (current.get('at'),current.get('size'))!=drag['geometry'])
            if not drag['confirmed']:return
            print('Drag movement confirmed',flush=True)
        monitor=next((m for m in query('monitors') if m['x']<=cursor['x']<area(m)[0]+area(m)[2]+m.get('reserved',[0]*4)[2]
                      and m['y']<=cursor['y']<area(m)[1]+area(m)[3]+m.get('reserved',[0]*4)[3]),None) if not self.open else drag['monitor']
        if not monitor:return
        width=area(monitor)[2]+monitor.get('reserved',[0]*4)[0]+monitor.get('reserved',[0]*4)[2]
        if not self.open:
            if abs(cursor['x']-(monitor['x']+width/2))>210 or not monitor['y']<=cursor['y']<=monitor['y']+70:return
            drag['monitor']=monitor
            run('eww','--no-daemonize','update','snap-reveal=true','snap-layout=none','snap-zone=-1')
            self.open=True
            try:
                run('eww','--no-daemonize','open','snap-picker','--arg',f'snap-monitor={self.monitor_indices.get((monitor["x"],monitor["y"]),0)}')
            except subprocess.SubprocessError as error:
                # Eww may report its IPC timeout after accepting the open request.
                print('Picker IPC response: '+str(getattr(error,'output',error)),flush=True)
            deadline=time.monotonic()+1
            self.picker=None
            while time.monotonic()<deadline:
                layers=query('layers').get(monitor['name'],{}).get('levels',{})
                self.picker=next((layer for rows in layers.values() for layer in rows if layer.get('namespace')=='glyphos-snap-picker'),None)
                if self.picker:break
                time.sleep(.05)
            if not self.picker:raise ValueError('Snap picker surface did not appear')
        selected=hit(cursor,monitor,self.picker)
        if selected!=self.selection:
            self.selection=selected
            preset,zone=selected or ('none',-1)
            run('eww','--no-daemonize','update',f'snap-layout={preset}',f'snap-zone={zone}')
            self.preview(cells(preset,area(monitor))[zone] if selected else None,monitor)

    def release(self):
        if self.drag and self.open:
            # Re-query the release point; a stale hovered target must never snap.
            monitor=self.drag['monitor'];selected=hit(query('cursorpos'),monitor,self.picker)
            window=self.drag['window']
            if selected:
                all_windows=query('clients')
                if not any(w['address']==window['address'] for w in all_windows):self.dismiss();return
                monitor=next((m for m in query('monitors') if m['name']==monitor['name']),None)
                if not monitor:self.dismiss();return
                eligible=[w for w in all_windows if w.get('mapped',True) and not w.get('hidden',False)
                          and not w.get('pinned',False) and w.get('fullscreen',0)<=1
                          and w.get('monitor')==monitor['id']
                          and w.get('workspace',{}).get('id')==window['workspace']['id']]
                if window['address'] not in {w['address'] for w in eligible}:self.dismiss();return
                operations=plan(*selected,area(monitor),eligible,window['address'])
                # Preserve a bounded undo snapshot of the windows we are arranging.
                snapshot={w['address']:{k:w.get(k) for k in ('at','size','floating','workspace','monitor')} for w in eligible}
                (ROOT/'last-layout.json').write_text(json.dumps(snapshot))
                border=max(0,int(query('getoption general:border_size').get('int',0)))
                commands=[]
                for address,(x,y,width,height) in operations:
                    if not __import__('re').fullmatch(r'0x[0-9a-fA-F]+',address):continue
                    x+=border;y+=border;width-=2*border;height-=2*border
                    client=next(w for w in eligible if w['address']==address)
                    if client.get('fullscreen',0)==1:
                        commands.extend([f'dispatch focuswindow address:{address}','dispatch fullscreenstate 0 0'])
                    commands.extend([f'dispatch setfloating address:{address}',
                                     f'dispatch resizewindowpixel exact {width} {height},address:{address}',
                                     f'dispatch movewindowpixel exact {x} {y},address:{address}'])
                commands.append(f'dispatch focuswindow address:{window["address"]}')
                result=ipc('[[BATCH]]'+';'.join(commands))
                if 'error' in result.lower():print(result,file=sys.stderr,flush=True)
        self.dismiss()

    def work(self):
        while True:
            try:
                if self.events is None:
                    self.events=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                    self.events.connect(str(socket_path('.socket2.sock')));self.events.setblocking(False)
                timeout=1/60 if self.drag and self.drag['confirmed'] else .1 if self.drag else None
                readable=select.select([self.events,self.control],[],[],timeout)[0]
                if self.events in readable:
                    data=self.events.recv(65536)
                    if not data:self.events.close();self.events=None;self.dismiss();time.sleep(.5);continue
                    self.event_buffer+=data
                    while b'\n' in self.event_buffer:
                        line,self.event_buffer=self.event_buffer.split(b'\n',1)
                        if line.startswith((b'workspace>>',b'workspacev2>>',b'lockscreen>>1',b'monitorremoved>>')):
                            if self.drag:print('Drag canceled by '+line.split(b'>>')[0].decode(),flush=True)
                            self.dismiss()
                        elif line.startswith(b'closewindow>>') and self.drag and line.split(b'>>')[1].decode()==self.drag['window']['address'].removeprefix('0x'):self.dismiss()
                if self.control in readable:
                    command=self.control.recv(256).decode()
                    if command=='begin':self.begin()
                    elif command=='begin-super':self.begin(True)
                    elif command=='release':self.release()
                    elif command=='cancel':self.dismiss()
                if self.drag:self.frame()
            except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
                print(error,file=sys.stderr,flush=True)
                try:self.dismiss()
                except Exception:self.drag=None;self.open=False;self.preview(None,None)
                if self.events:self.events.close();self.events=None
                time.sleep(.5)


def daemon():
    import gi,cairo
    gi.require_version('Gtk','3.0');gi.require_version('GtkLayerShell','0.1')
    from gi.repository import Gtk,Gdk,GLib,GtkLayerShell
    class Preview:
        def __init__(self):
            self.window=Gtk.Window();self.window.set_decorated(False);self.window.set_accept_focus(False);self.window.set_resizable(False)
            self.window.set_app_paintable(True);self.window.set_visual(self.window.get_screen().get_rgba_visual())
            GtkLayerShell.init_for_window(self.window);GtkLayerShell.set_namespace(self.window,'glyphos-snap-preview')
            GtkLayerShell.set_layer(self.window,GtkLayerShell.Layer.TOP)
            GtkLayerShell.set_keyboard_mode(self.window,GtkLayerShell.KeyboardMode.NONE)
            GtkLayerShell.set_exclusive_zone(self.window,-1)
            for edge in (GtkLayerShell.Edge.TOP,GtkLayerShell.Edge.LEFT):GtkLayerShell.set_anchor(self.window,edge,True)
            self.window.connect('realize',lambda w:w.get_window().input_shape_combine_region(cairo.Region(),0,0))
            self.area=Gtk.DrawingArea();self.window.add(self.area)
            self.area.connect('draw',self.draw);self.rect=None;self.target=None;self.timer=None
        def draw(self,w,cr):
            allocation=w.get_allocation();cr.set_operator(cairo.OPERATOR_SOURCE);cr.set_source_rgba(0,0,0,0);cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER);cr.set_source_rgba(233/255,233/255,228/255,.28)
            cr.rectangle(1,1,allocation.width-2,allocation.height-2);cr.fill_preserve()
            cr.set_source_rgba(1,1,1,.8);cr.set_line_width(2);cr.stroke();return False
        def change(self,rect,monitor):
            if rect is None:
                self.window.hide();self.target=None;return False
            display=Gdk.Display.get_default()
            index=next((i for i in range(display.get_n_monitors()) if display.get_monitor(i).get_geometry().x==monitor['x'] and display.get_monitor(i).get_geometry().y==monitor['y']),0)
            GtkLayerShell.set_monitor(self.window,display.get_monitor(index))
            self.origin=(monitor['x'],monitor['y']);self.target=rect
            self.initial=self.rect or rect;self.started=time.monotonic()
            x,y,width,height=rect
            self.area.set_size_request(width,height)
            self.window.set_default_size(width,height)
            GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.LEFT,max(0,x-self.origin[0]))
            GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.TOP,max(0,y-self.origin[1]))
            self.window.show_all()
            if self.timer is None:self.timer=GLib.timeout_add(16,self.animate)
            return False
        def animate(self):
            if self.target is None:self.timer=None;self.rect=None;return False
            t=min(1,(time.monotonic()-self.started)/.18);ease=1-(1-t)**3
            self.rect=tuple(round(a+(b-a)*ease) for a,b in zip(self.initial,self.target))
            x,y,w,h=self.rect
            GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.LEFT,max(0,x-self.origin[0]))
            GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.TOP,max(0,y-self.origin[1]))
            self.area.set_size_request(w,h);self.window.resize(w,h);self.area.queue_draw()
            if t>=1:self.timer=None;return False
            return True
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (ROOT/'worker.lock').open('w') as guard:
        try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        CONTROL.unlink(missing_ok=True)
        preview=Preview();indices={}
        display=Gdk.Display.get_default()
        def map_monitors(*args):
            indices.clear()
            for index in range(display.get_n_monitors()):
                geometry=display.get_monitor(index).get_geometry()
                indices[(geometry.x,geometry.y)]=index
        map_monitors()
        display.connect('monitor-added',map_monitors);display.connect('monitor-removed',map_monitors)
        engine=Engine(lambda rect,monitor:GLib.idle_add(preview.change,rect,monitor),indices)
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as control:
            control.bind(str(CONTROL));os.chmod(CONTROL,0o600);engine.control=control
            threading.Thread(target=engine.work,daemon=True).start();Gtk.main()


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--daemon':daemon();return
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
        client.settimeout(.15)
        try:client.sendto((sys.argv[1] if len(sys.argv)>1 else 'cancel').encode(),str(CONTROL))
        except OSError:pass  # Unavailable optional service never blocks desktop input.


if __name__=='__main__':main()

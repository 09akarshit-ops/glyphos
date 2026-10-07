"""Live activities owned by Desktop: GTK layer shell, GLib animation, bounded workers."""
import json, math, os, signal, socket, time,sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen
import gi
gi.require_version('Gtk','3.0')
gi.require_version('GtkLayerShell','0.1');gi.require_version('PangoCairo','1.0')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell, GdkPixbuf, Pango, PangoCairo
sys.path.insert(0,str(Path.home()/".config/eww/scripts"))
from lyric_animation import DURATION
from common import HOME, STATE, read, write, call, hypr

class Queue:
    def __init__(self):self.rows={};self.serial=0
    def put(self,key,**row):
        old=self.rows.get(key,{})
        # Position/progress advances do not continually steal the cycle.
        identity=(row.get('title'),row.get('subtitle'),row.get('status'))
        if old.get('identity')!=identity:self.serial+=1
        row.update(key=key,identity=identity,serial=self.serial if old.get('identity')!=identity else old['serial'])
        self.rows[key]=row
    def active(self,now=None):
        now=time.monotonic() if now is None else now
        self.rows={k:v for k,v in self.rows.items() if v.get('until',float('inf'))>now}
        return sorted(self.rows.values(),key=lambda r:(-r.get('priority',0),-r['serial']))
    def newest(self):return max(self.active(),key=lambda r:r['serial'],default=None)

def ease(t):
    # A restrained overshoot, returning exactly to target after 300 ms.
    t=max(0,min(1,t));u=t-1
    return 1+2.1*u*u*u+1.1*u*u

class Island:
    def __init__(self,submit):
        self.submit=submit;self.queue=Queue();self.expanded=False;self.selected=None;self.index=0;self.cycle_at=time.monotonic();self.interacted=0;self.anim=None;self.amount=0.;self.health_at=0;self.animation_samples=[];self.last_bt=None;self.last_charge=None;self.art=None;self.art_uri=None;self.fixture_until=0;self.hovered=False;self.lyrics=[];self.lyric_index=-1;self.lyric_scroll=0.;self.lyric_anim=None;self.manual_until=0
        self.window=Gtk.Window(title='GlyphOS Live Activities');self.window.set_decorated(False);self.window.set_accept_focus(False);self.window.set_focus_on_map(False);self.window.set_resizable(False)
        GtkLayerShell.init_for_window(self.window);GtkLayerShell.set_namespace(self.window,'glyphos-dynamic-island');GtkLayerShell.set_layer(self.window,GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self.window,GtkLayerShell.Edge.TOP,True);GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.TOP,6)
        GtkLayerShell.set_keyboard_mode(self.window,GtkLayerShell.KeyboardMode.NONE);GtkLayerShell.set_exclusive_zone(self.window,0)
        screen=self.window.get_screen();visual=screen.get_rgba_visual()
        if visual:self.window.set_visual(visual)
        self.window.set_app_paintable(True)
        self.area=Gtk.DrawingArea();self.area.set_size_request(300,44)
        # Transparent surface room for the ambient shadow, outside the content.
        self.frame=Gtk.Box();self.frame.pack_start(self.area,True,True,0)
        self.area.set_margin_start(24);self.area.set_margin_end(24)
        self.area.set_margin_top(12);self.area.set_margin_bottom(32)
        self.window.add(self.frame)
        self.frame.connect('draw',self.draw_surface)
        provider=Gtk.CssProvider()
        provider.load_from_data(b'.glyphos-island-window, .glyphos-island-frame { background-color: transparent; background-image: none; border: none; box-shadow: none; } .glyphos-island-surface { background-color: #000000; border-radius: 28px; border: 1px solid transparent; box-shadow: 0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.08); transition: box-shadow 180ms ease; }')
        self.area.get_style_context().add_provider(provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for widget,klass in [(self.window,'glyphos-island-window'),(self.frame,'glyphos-island-frame')]:
            widget.get_style_context().add_provider(provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            widget.get_style_context().add_class(klass)
        self.area.get_style_context().add_class('glyphos-island-surface')
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.ENTER_NOTIFY_MASK|Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.LEAVE_NOTIFY_MASK|Gdk.EventMask.SCROLL_MASK)
        self.area.connect('draw',self.draw);self.area.connect('button-press-event',self.click);self.area.connect('enter-notify-event',self.hover);self.area.connect('motion-notify-event',self.motion)
        self.area.connect('leave-notify-event',self.leave);self.area.connect('scroll-event',self.scroll_lyrics)
        self.window.connect('delete-event',lambda *_:True)
        self.path=Path(os.environ['XDG_RUNTIME_DIR'])/'glyphos-island.sock'
        self.path.unlink(missing_ok=True);self.ipc=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);self.ipc.bind(str(self.path));os.chmod(self.path,0o600);self.ipc.setblocking(False)
        GLib.io_add_watch(self.ipc.fileno(),GLib.IO_IN,self.message)
        GLib.timeout_add(100,self.tick)
    def toast(self,key,title,icon):
        self.queue.put(key,kind=key,title=title,icon=icon,priority=80,until=time.monotonic()+5,brief=True)
        self.index=0;self.cycle_at=time.monotonic();self.refresh()
    def collect(self):
        rows=[]
        def attempt(fn):
            try:return fn()
            except Exception:return None
        media=read(STATE/'island-media.json',{})
        if media.get('status') in ('Playing','Paused') and time.time()-media.get('updated',0)<5:
            length=media.get('duration',0);pos=media.get('position',0)
            progress=min(1,pos/length) if length>0 else 0
            rows.append(('media',dict(kind='media',title=media.get('title') or 'Music',subtitle=media.get('artist',''),status=media['status'],icon='♫',priority=20,progress=progress,art=Path(read(STATE/'island-art.json',{}).get('art')).as_uri() if read(STATE/'island-art.json',{}).get('art') else media.get('art'),player=media.get('player',''),duration=length)))
        jobs=HOME/'.config/eww/config/app-jobs'
        catalog=read(HOME/'.config/eww/store/apps.json',[]);names={r['id']:r['name'] for r in catalog}
        for path in jobs.glob('*.json'):
            job=read(path,{})
            if job.get('state') not in ('queued','working') or job.get('action')!='install':continue
            pid=job.get('pid',0)
            if not isinstance(pid,int) or pid<=1:continue
            try:os.kill(pid,0)
            except OSError:continue
            rows.append(('install:'+path.stem,dict(kind='install',title=names.get(path.stem,path.stem),subtitle=job.get('detail','Installing…'),icon='↓',priority=70,progress=job.get('progress'),pid=pid,app_id=path.stem)))
        focus=read(STATE/'focus.json',{})
        if focus.get('enabled'):rows.append(('focus',dict(kind='focus',title='Focus',subtitle=focus.get('app','Focused application'),icon='◉',priority=40)))
        battery=self.battery()
        bt=None
        if time.monotonic()-getattr(self,'bt_checked',0)>=5:
            self.bt_checked=time.monotonic()
            bt=attempt(lambda:call('bluetoothctl','--timeout','2','devices','Connected',timeout=3))
        GLib.idle_add(self.receive,rows,battery,bt)
    def battery(self):
        for p in Path('/sys/class/power_supply').glob('*'):
            if (p/'type').exists() and (p/'type').read_text().strip()=='Battery':
                try:
                    cap=int((p/'capacity').read_text());status=(p/'status').read_text().strip();remaining=''
                    for energy,rate in [('energy_now','power_now'),('charge_now','current_now')]:
                        if (p/energy).exists() and (p/rate).exists():
                            value=float((p/energy).read_text());speed=float((p/rate).read_text())
                            if status=='Charging':value=float((p/(energy.replace('_now','_full'))).read_text())-value
                            if speed>0:remaining=f'About {round(value/speed*60)} min '+('to full' if status=='Charging' else 'remaining')
                            break
                    return dict(kind='battery',title=f'{cap}% battery',subtitle=status+(' · '+remaining if remaining else ''),icon='ϟ',priority=90,capacity=cap,status=status)
                except (OSError,ValueError):pass
        return None
    def receive(self,rows,battery,bt):
        if time.monotonic()<self.fixture_until:return False
        persistent={key for key,_ in rows}
        for key in list(self.queue.rows):
            if self.queue.rows[key].get('kind') in ('media','focus','install') and key not in persistent:self.queue.rows.pop(key)
        for key,row in rows:self.queue.put(key,**row)
        if battery:
            changed=self.last_charge is not None and self.last_charge!=battery['status'];self.last_charge=battery['status']
            if battery['capacity']<15 or changed:
                if battery['capacity']>=15:battery['until']=time.monotonic()+8
                self.queue.put('battery',**battery)
            elif self.queue.rows.get('battery',{}).get('capacity',0)<15:self.queue.rows.pop('battery',None)
        if bt is not None:
            devices={line.split(' ',2)[1]:line.split(' ',2)[2] for line in bt.splitlines() if len(line.split(' ',2))==3}
            if self.last_bt is not None:
                for key in devices.keys()-self.last_bt.keys():self.toast('bluetooth','Connected: '+devices[key],'ᛒ')
                for key in self.last_bt.keys()-devices.keys():self.toast('bluetooth','Disconnected: '+self.last_bt[key],'ᛒ')
            self.last_bt=devices
        self.refresh();return False
    def current(self):
        rows=self.queue.active()
        if self.expanded:return next((r for r in rows if r['key']==self.selected),None)
        return rows[self.index%len(rows)] if rows else None
    def refresh(self):
        row=self.current()
        if self.expanded and row is None:self.expand(False);row=self.current()
        # Compact activity/context and synchronized lyrics live in the Eww bar.
        # This surface is only the optional expanded activity panel.
        if not row or (not self.expanded and self.amount == 0):self.window.hide();return
        self.window.show_all();self.area.queue_draw()
        uri=row.get('art')
        if row.get('kind')=='media' and (self.expanded or self.amount>0):self.update_lyrics()
        if uri!=self.art_uri:
            self.art_uri=uri;self.art=None
            if uri and urlparse(uri).scheme in ('file','https','http'):
                # Bounded local/remote artwork loading stays off GTK's thread.
                def load():
                    try:
                        if urlparse(uri).scheme=='file':pix=GdkPixbuf.Pixbuf.new_from_file_at_scale(unquote(urlparse(uri).path),600,600,True)
                        else:
                            with urlopen(uri,timeout=3) as response:raw=response.read(2_000_001)
                            if len(raw)>2_000_000:return
                            loader=GdkPixbuf.PixbufLoader.new();loader.set_size(600,600);loader.write(raw);loader.close();pix=loader.get_pixbuf()
                    except Exception:return
                    GLib.idle_add(self.set_art,uri,pix)
                self.submit('island-art',load)
    def set_art(self,uri,pix):
        if self.art_uri==uri:self.art=pix;self.area.queue_draw()
        return False
    def expand(self,value):
        if value:
            row=next((r for r in self.queue.active() if r.get('kind')=='media'),self.queue.newest())
            if not row or row.get('brief'):return
            self.selected=row['key'];self.hovered=False
            if row.get('kind')=='media':
                self.lyric_index=max(0,read(STATE/'island-render.json',{}).get('line',0));self.lyric_scroll=float(self.lyric_index)
        self.expanded=value;self.interacted=time.monotonic();self.animation_samples=[];self.start_amount=self.amount;self.target=1. if value else 0.;self.started=time.monotonic()
        if self.anim is None:self.anim=GLib.timeout_add(16,self.animate)
        self.refresh()
    def animate(self):
        t=(time.monotonic()-self.started)/.3;self.amount=self.start_amount+(self.target-self.start_amount)*ease(t)
        width=round(300+180*self.amount);height=round(44+(428 if self.current() and self.current().get('kind')=='media' else 168)*self.amount)
        self.area.set_size_request(width,height);self.window.resize(width+48,height+44);self.area.queue_draw()
        self.animation_samples.append({'time':round(time.monotonic(),3),'width':width,'height':height});self.animation_samples=self.animation_samples[-80:]
        if t>=1:self.amount=self.target;self.anim=None;return False
        return True
    def hover(self,*_):
        self.hovered=True
        if not self.expanded:self.expand(True)
        return False
    def leave(self,*_):self.hovered=False;self.interacted=time.monotonic();return False
    def scroll_lyrics(self,_,event):
        if not self.expanded:return False
        self.interacted=time.monotonic();self.manual_until=time.monotonic()+4
        delta=1 if event.direction==Gdk.ScrollDirection.DOWN else -1
        self.lyric_scroll=max(0,min(max(0,len(self.lyrics)-1),self.lyric_scroll+delta));self.area.queue_draw();return True
    def update_lyrics(self):
        data=read(STATE/'island-render.json',{});self.lyrics=data.get('lyrics',[])
        index=max(0,data.get('line',0));now=time.monotonic()
        if self.manual_until and now>=self.manual_until:self.manual_until=0;self.lyric_index=-1
        if self.lyric_index!=index and now>=self.manual_until:
            self.lyric_index=index;self.lyric_from=self.lyric_scroll;self.lyric_started=now
            if self.lyric_anim is None:self.lyric_anim=GLib.timeout_add(16,self.animate_lyrics)
    def animate_lyrics(self):
        t=min(1,(time.monotonic()-self.lyric_started)/DURATION);p=t*t*t*(t*(6*t-15)+10)
        self.lyric_scroll=self.lyric_from+(self.lyric_index-self.lyric_from)*p;self.area.queue_draw()
        if t>=1:self.lyric_anim=None;return False
        return True
    def seek_to(self,x):
        row=self.current()
        if not row or row.get('kind')!='media':return
        now=time.monotonic()
        if now-getattr(self,'last_seek',0)<.08:return
        self.last_seek=now;w=self.area.get_allocated_width();target=max(0,min(1,(x-26)/(w-52)))*row.get('duration',0)
        player=row.get('player','').removeprefix('org.mpris.MediaPlayer2.')
        self.submit('island-seek',lambda:call('playerctl','--player='+player,'position',str(target),check=False))
    def motion(self,_,event):
        self.interacted=time.monotonic()
        if event.state&Gdk.ModifierType.BUTTON1_MASK and 105<=event.y<=135:self.seek_to(event.x)
        return False
    def click(self,_,event):
        self.interacted=time.monotonic()
        if not self.expanded:self.expand(True);return True
        row=self.current();w=self.area.get_allocated_width();h=self.area.get_allocated_height()
        if event.y<35 and event.x>w-65:self.expand(False);return True
        if row and row['kind']=='media' and 105<=event.y<=135:self.seek_to(event.x);return True
        if event.y>h-65 and row:
            kind=row['kind']
            if kind=='media':
                action='previous' if event.x<w*.36 else 'next' if event.x>w*.64 else 'play-pause'
                player=row.get('player','').removeprefix('org.mpris.MediaPlayer2.')
                self.submit('island-control',lambda:call('playerctl',*(['--player='+player] if player else []),action,check=False))
            elif kind=='focus':
                def end():
                    from focus_mode import action
                    if read(STATE/'focus.json',{}).get('enabled'):action('toggle')
                self.submit('island-control',end)
            elif kind=='install':self.submit('island-control',lambda:self.cancel(row))
        return True
    def cancel(self,row):
        pid=row.get('pid',0)
        try:
            command=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            if str(HOME/'.config/eww/scripts/app-service.py').encode() in command and b'worker' in command and row['app_id'].encode() in command:os.kill(pid,signal.SIGTERM)
        except OSError:pass
    def tick(self):
        now=time.monotonic()
        if self.expanded and not self.hovered and now-self.interacted>=2:self.expand(False)
        elif not self.expanded and now-self.cycle_at>=3.5:self.index+=1;self.cycle_at=now;self.refresh()
        self.refresh()
        row=self.current()
        if now-self.health_at<2:return True
        self.health_at=now
        write(STATE/'island-health.json',dict(expanded=self.expanded,activity=row['key'] if row else None,queue=[r['key'] for r in self.queue.active()],keyboard_mode='none',accept_focus=self.window.get_accept_focus(),amount=self.amount,samples=self.animation_samples,updated=time.time()))
        return True
    def message(self,*_):
        try:
            data=json.loads(self.ipc.recv(4096));op=data.get('op')
            if op=='expand':self.expand(True)
            elif op=='collapse':self.expand(False)
            elif op=='outside' and self.expanded:self.submit('island-outside',self.outside)
            elif op=='verify-fixture':
                self.fixture_until=time.monotonic()+22
                self.queue.put('verify-media',kind='media',title='Luminous Flow',subtitle='Night Drive · verification',status='Playing',icon='♫',priority=20,progress=.4,until=self.fixture_until)
                GLib.timeout_add(600,self.verify_install)
                self.refresh()
        except (OSError,ValueError):pass
        return True
    def verify_install(self):
        self.queue.put('verify-install',kind='install',title='Test App',subtitle='Simulated install · no packages changed',icon='↓',priority=70,progress=42,until=self.fixture_until)
        self.cycle_at=time.monotonic();self.index=0;self.refresh();return False
    def outside(self):
        if time.monotonic()-self.interacted<2:return
        cursor=hypr('cursorpos');layers=hypr('layers');inside=False
        for monitor in layers.values():
            for rows in monitor.get('levels',{}).values():
                for r in rows:
                    if r.get('namespace')=='glyphos-dynamic-island' and r['x']<=cursor['x']<r['x']+r['w'] and r['y']<=cursor['y']<r['y']+r['h']:inside=True
        if not inside:GLib.idle_add(lambda:(self.expand(False),False)[1])
    def draw_surface(self,frame,c):
        w=self.area.get_allocated_width();h=self.area.get_allocated_height()
        Gtk.render_background(self.area.get_style_context(),c,24,12,w,h)
        row=self.current()
        if self.art and row and row.get('kind')=='media':
            c.save();c.translate(24,12);r=min(28,h/2)
            c.new_sub_path();c.arc(w-r,r,r,-math.pi/2,0);c.arc(w-r,h-r,r,0,math.pi/2);c.arc(r,h-r,r,math.pi/2,math.pi);c.arc(r,r,r,math.pi,math.pi*1.5);c.close_path();c.clip()
            c.save();scale=max(w/self.art.get_width(),h/self.art.get_height());c.translate((w-self.art.get_width()*scale)/2,(h-self.art.get_height()*scale)/2);c.scale(scale,scale)
            Gdk.cairo_set_source_pixbuf(c,self.art,0,0);c.paint();c.restore()
            c.set_source_rgba(0,0,0,.20);c.rectangle(0,0,w,h);c.fill();c.restore()
        Gtk.render_frame(self.area.get_style_context(),c,24,12,w,h)
        return False
    def draw(self,area,c):
        w=area.get_allocated_width();h=area.get_allocated_height();r=min(28,h/2)
        row=self.current()
        if not row:return False
        def text(value,x,y,size=16,color=(1,1,1),center=False):
            layout=PangoCairo.create_layout(c);font=Pango.FontDescription('Sans');font.set_absolute_size(size*Pango.SCALE);font.set_weight(Pango.Weight.SEMIBOLD);layout.set_font_description(font)
            layout.set_text(str(value),-1);layout.set_width(int((w-40 if center else w-x-20)*Pango.SCALE));layout.set_ellipsize(Pango.EllipsizeMode.END)
            if center:layout.set_alignment(Pango.Alignment.CENTER)
            c.move_to(x,y-size);c.set_source_rgb(*color);PangoCairo.show_layout(c,layout);c.new_path()
        def icon(kind,x,y,size=18):
            c.set_source_rgb(1,1,1);c.set_line_width(1.8);c.set_line_cap(1)
            if kind=='media':
                c.move_to(x+size*.3,y-size*.65);c.line_to(x+size*.3,y);c.line_to(x+size*.75,y-size*.12);c.move_to(x+size*.3,y-size*.65);c.line_to(x+size*.8,y-size*.85);c.line_to(x+size*.8,y-size*.2);c.stroke()
                c.arc(x+size*.17,y,3,0,7);c.fill();c.arc(x+size*.67,y-size*.12,3,0,7);c.fill()
            elif kind=='install':
                c.move_to(x+size/2,y-size);c.line_to(x+size/2,y-3);c.move_to(x+3,y-8);c.line_to(x+size/2,y-2);c.line_to(x+size-3,y-8);c.move_to(x,y+3);c.line_to(x+size,y+3);c.stroke()
            else:c.arc(x+size/2,y-size/3,size/3,0,7);c.stroke()
        if self.amount<.5:
            compact=row['title'][:28] if row.get('brief') else ' '.join(row['title'].split()[:2])[:24]
            if row['kind']=='install':compact+=' '+(str(row.get('progress'))+'%' if row.get('progress') is not None else '…')
            icon(row['kind'],18,h/2+6);text(compact,50,h/2+5,16)
        else:
            c.set_source_rgb(.6,.6,.6);c.set_line_width(1.5);c.move_to(w-39,17);c.line_to(w-33,23);c.line_to(w-27,17);c.stroke()
            if self.art and row['kind']=='media':pass
            else:
                c.set_source_rgb(.2,.2,.2);c.rectangle(24,32,64,64);c.fill();icon(row['kind'],43,77,26)
            text(row['title'][:30],106,57,20);text(row.get('subtitle','')[:42],106,82,13,(.6,.6,.6))
            progress=row.get('progress')
            if row['kind'] in ('media','install'):
                c.set_line_width(4);c.set_line_cap(1);c.set_source_rgb(.24,.24,.24);c.move_to(26,120);c.line_to(w-26,120);c.stroke()
                fraction=(progress/100 if row['kind']=='install' else progress) if progress is not None else (.2+.15*math.sin(time.monotonic()*3))
                c.set_source_rgb(1,1,1);c.move_to(26,120);c.line_to(26+(w-52)*max(0,min(1,fraction)),120);c.stroke()
                c.new_path();c.arc(26+(w-52)*max(0,min(1,fraction)),120,5,0,math.tau);c.fill()
            if row['kind']=='media':
                c.save();c.rectangle(20,145,w-40,h-225);c.clip()
                if self.lyrics:
                    center=145+(h-225)/2
                    for i,item in enumerate(self.lyrics):
                        y=center+(i-self.lyric_scroll)*38
                        if 125<=y<=h-65:
                            emphasis=1-min(1,abs(i-self.lyric_scroll));shade=.4+.6*emphasis
                            text(item[1],20,y,18,(shade,shade,shade),True)
                else:text('Looking up lyrics…',20,190,16,(.6,.6,.6),True)
                c.restore()
                c.new_path();c.set_source_rgb(1,1,1);c.arc(w/2,h-37,23,0,7);c.fill()
                c.set_source_rgb(.1,.1,.1)
                if row.get('status')=='Playing':c.rectangle(w/2-7,h-45,4,16);c.rectangle(w/2+3,h-45,4,16);c.fill()
                else:c.move_to(w/2-5,h-46);c.line_to(w/2+8,h-37);c.line_to(w/2-5,h-28);c.close_path();c.fill()
                c.set_source_rgb(.95,.95,.95);c.set_line_width(2)
                for x,d in [(w*.25,-1),(w*.75,1)]:
                    c.move_to(x-5*d,h-45);c.line_to(x+5*d,h-37);c.line_to(x-5*d,h-29);c.stroke()
            elif row['kind']=='install':text('Cancel install',w/2-50,h-28,15)
            elif row['kind']=='focus':text('End Focus',w/2-38,h-28,15)
        return False

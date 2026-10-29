#!/usr/bin/env python3
"""Visible-only, asynchronous VLC queue panel shared by desktop and Island."""
import sys,concurrent.futures,json,os,socket,time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
gi.require_version('GtkLayerShell','0.1')
from gi.repository import Gtk,GLib,Gio,Gdk,GtkLayerShell
from media_queue import Backend

class QueueApp(Gtk.Application):
 def __init__(self):
  super().__init__(application_id='org.glyphos.MediaQueue',flags=Gio.ApplicationFlags.FLAGS_NONE)
  self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.backend=Backend();self.busy=False;self.window=None;self.generation=0
 def do_activate(self):
  if self.window:self.window.present();return
  self.window=Gtk.ApplicationWindow(application=self,title='GlyphOS · Queue')
  self.window.set_decorated(False);self.window.set_resizable(False);self.window.set_accept_focus(False);self.window.set_focus_on_map(False)
  GtkLayerShell.init_for_window(self.window);GtkLayerShell.set_namespace(self.window,'glyphos-island-queue')
  GtkLayerShell.set_layer(self.window,GtkLayerShell.Layer.OVERLAY);GtkLayerShell.set_anchor(self.window,GtkLayerShell.Edge.TOP,True)
  GtkLayerShell.set_keyboard_mode(self.window,GtkLayerShell.KeyboardMode.NONE);GtkLayerShell.set_exclusive_zone(self.window,0)
  display=Gdk.Display.get_default();monitor=display.get_monitor(0)
  if monitor:GtkLayerShell.set_monitor(self.window,monitor)
  height=monitor.get_geometry().height if monitor else 900
  self.window.set_default_size(420,max(150,min(250,height-510)))
  GtkLayerShell.set_margin(self.window,GtkLayerShell.Edge.TOP,498)
  self.window.connect('destroy',self.closed)
  self.window.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK|Gdk.EventMask.LEAVE_NOTIFY_MASK)
  self.window.connect('enter-notify-event',lambda *_:self.island('queue-hold'))
  self.window.connect('leave-notify-event',lambda *_:self.island('queue-hold'))
  self.opened_at=time.monotonic()
  self.island('expand');self.island('queue-hold')
  self.follow_timer=GLib.timeout_add(250,self.follow_island)
  css=Gtk.CssProvider();css.load_from_data(b'window {background:#e9e9e4;color:#171b1b;border:1px solid rgba(255,255,255,.65);border-radius:16px;} .queue-root {padding:16px;} button {border-radius:10px; padding:10px; background:rgba(255,255,255,.45); color:#171b1b; border:1px solid rgba(255,255,255,.65);} .current {background:rgba(90,90,80,.16);} .queue-title {font-size:20px; font-weight:600;}')
  Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);root.get_style_context().add_class('queue-root');self.window.add(root)
  header=Gtk.Box(spacing=10);title=Gtk.Label(label='Queue',xalign=0);title.get_style_context().add_class('queue-title');header.pack_start(title,True,True,0)
  refresh=Gtk.Button(label='Refresh');refresh.connect('clicked',lambda *_:self.refresh());header.pack_end(refresh,False,False,0);close=Gtk.Button(label='×');close.connect('clicked',lambda *_:self.window.destroy());header.pack_end(close,False,False,0);root.pack_start(header,False,False,0)
  self.status=Gtk.Label(label='Loading VLC playlist…',xalign=0);self.status.set_line_wrap(True);root.pack_start(self.status,False,False,0)
  scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.rows=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);scroll.add(self.rows);root.pack_start(scroll,True,True,0)
  self.window.show_all();self.refresh();self.timer=GLib.timeout_add_seconds(3,self.refresh)
 def island(self,op):
  try:
   with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as ipc:
    ipc.sendto(json.dumps({'op':op}).encode(),str(Path(os.environ['XDG_RUNTIME_DIR'])/'glyphos-island.sock'))
  except OSError:pass
  return False
 def follow_island(self):
  if not self.window:return False
  try:
   health=json.loads((Path.home()/'.local/state/glyphos/island-health.json').read_text())
   if time.monotonic()-self.opened_at>3 and time.time()-health.get('updated',0)<4 and not health.get('expanded'):
    self.window.destroy();return False
  except (OSError,ValueError):pass
  self.island('queue-hold')
  return True
 def closed(self,*_):
  self.island("queue-release")
  self.window=None;self.generation+=1
  if getattr(self,"follow_timer",None):GLib.source_remove(self.follow_timer);self.follow_timer=None
  if getattr(self,'timer',None):GLib.source_remove(self.timer);self.timer=None
 def refresh(self):
  if not self.window:return False
  if self.busy:return True
  self.busy=True;generation=self.generation
  future=self.pool.submit(self.backend.snapshot)
  future.add_done_callback(lambda f:GLib.idle_add(self.render,f,generation));return True
 def render(self,future,generation):
  self.busy=False
  if not self.window or generation!=self.generation:return False
  try:snapshot=future.result()
  except Exception:
   self.status.set_text('Cannot read VLC’s playlist. Ensure VLC is running with MPRIS enabled.');return False
  self.status.set_text(snapshot['message'])
  identity=(snapshot['player'],snapshot['rows'])
  if identity==getattr(self,'last',None):return False
  self.last=identity
  for child in self.rows.get_children():child.destroy()
  for item in snapshot['rows']:
   button=Gtk.Button();label=Gtk.Label(xalign=0);label.set_ellipsize(3);label.set_max_width_chars(38)
   label.set_text(('▶  ' if item['current'] else '')+item['title']+ ('\n'+item['artist'] if item['artist'] else ''))
   button.add(label);button.set_tooltip_text(item['title']);button.get_style_context().add_class('current' if item['current'] else 'queued')
   button.connect('clicked',lambda _,name=snapshot['player'],track=item['id']:self.select(name,track));self.rows.pack_start(button,False,False,0)
  self.rows.show_all();return False
 def select(self,name,track):
  if self.busy:return
  self.busy=True;self.status.set_text('Switching track…')
  future=self.pool.submit(self.backend.select,name,track)
  future.add_done_callback(lambda f:GLib.idle_add(self.selected,f))
 def selected(self,future):
  self.busy=False
  if not self.window:return False
  try:future.result()
  except Exception as error:self.status.set_text(str(error));return False
  self.refresh();return False
if __name__=='__main__':QueueApp().run(sys.argv)

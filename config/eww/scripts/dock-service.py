#!/usr/bin/env python3
"""Persistent dock items and compact context menus; no shell-built app commands."""
import fcntl,json,os,re,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
STATE=Path.home()/'.config/glyphos/dock.json'
DEFAULTS=[{'id':key,'name':name,'icon':icon,'builtin':key} for key,name,icon in [('home','Glyph App Store','glyphos.svg'),('files','Files','files.svg'),('chat','WhatsApp','whatsapp.svg'),('ai','Gemini','ai.svg'),('browser','Browser','browser.svg'),('settings','Settings','settings.svg'),('music','Music','music.svg'),('photos','Photos','photos.svg')]]
def load():
 try:
  value=json.loads(STATE.read_text())
  assert isinstance(value.get('items'),list)
  return value
 except (OSError,ValueError,AssertionError):return dict(items=[dict(i) for i in DEFAULTS],hidden=False,color='')
def save(value):
 STATE.parent.mkdir(parents=True,exist_ok=True)
 target=STATE.with_suffix('.tmp');target.write_text(json.dumps(value));target.replace(STATE)
def valid_id(value):return bool(re.fullmatch(r'(?:home|files|chat|ai|browser|settings|music|photos|app-[0-9a-f]{24})',value))
def item(key):return next((i for i in load()['items'] if i['id']==key),None)
def eww(*args):return subprocess.run(['eww','--no-daemonize',*args],capture_output=True,text=True,timeout=4)
def snapshot(value,icons=None):
 rows=[]
 for entry in value['items']:
  if not valid_id(entry.get('id','')):continue
  icon=entry.get('icon','')
  if entry.get('builtin'):
   icon=entry.get('icon','files.svg')
   icon=str(BASE/'assets'/icon)
  elif icons:icon=icons(icon)
  if not icon or not Path(icon).is_file():icon=str(BASE/'assets/files.svg')
  rows.append(dict(id=entry['id'],name=entry.get('name','Application'),icon=icon))
 color=value.get('color','')
 if color and not re.fullmatch(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',color):color=''
 if len(color)==9:color='rgba('+','.join(str(int(color[i:i+2],16)) for i in (1,3,5))+','+str(round(int(color[7:9],16)/255,4))+')'
 return dict(items=rows,hidden=bool(value.get('hidden')),style='background-color:'+color+'; background-image:none;' if color else '')
def launch(key):
 entry=item(key)
 if not entry:return
 builtin=entry.get('builtin')
 commands={'home':[str(Path.home()/'.local/bin/glyph-store')],'files':[str(Path.home()/'.local/bin/glyphos-files')],'chat':['brave','--app=https://web.whatsapp.com'],'ai':[str(Path.home()/'.config/glyphos/scripts/launch-gemini.sh')],'browser':['brave'],'settings':[sys.executable,str(BASE/'scripts/settings-display.py'),'fullscreen'],'music':['spotify'],'photos':[str(Path.home()/'.local/bin/glyphos-files'),str(Path.home()/'Pictures')]}
 if builtin:subprocess.Popen(commands[builtin],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 else:
  from gi.repository import Gio
  app=Gio.DesktopAppInfo.new(entry['desktop'])
  if app:app.launch([],None)
def listen():
 import gi
 gi.require_version('Gtk','3.0')
 from gi.repository import Gtk
 theme=Gtk.IconTheme.get_default()
 def icon(name):
  if Path(name).is_file():return name
  info=theme.lookup_icon(name,48,0) if theme else None
  return info.get_filename() if info else ''
 previous=None
 while True:
  result=json.dumps(snapshot(load(),icon))
  if result!=previous:print(result,flush=True);previous=result
  time.sleep(.4)
def notify(text):subprocess.Popen(['notify-send','Dock',text])
def native_package(entry):
 if not entry or not entry.get('desktop'):return ''
 from gi.repository import Gio
 app=Gio.DesktopAppInfo.new(entry['desktop'])
 if not app or not app.get_filename():return ''
 try:
  result=subprocess.run(['pacman','-Qoq',app.get_filename()],capture_output=True,text=True,timeout=3)
 except (OSError,subprocess.TimeoutExpired):return ''
 package=result.stdout.strip()
 protected={'hyprland','hyprlock','eww','python','gtk3','gtk4','systemd','pacman','plasma-login-manager','sddm','linux','linux-lts'}
 return package if result.returncode==0 and re.fullmatch(r'[a-zA-Z0-9@._+:-]+',package) and package not in protected else ''
def ui(mode,key=''):
 import gi
 gi.require_version('Gtk','3.0');gi.require_version('GtkLayerShell','0.1')
 from gi.repository import Gtk,Gdk,Gio,GLib,GtkLayerShell
 value=load();window=Gtk.Window(title='GlyphOS Dock');window.set_decorated(False);window.set_resizable(False)
 GtkLayerShell.init_for_window(window);GtkLayerShell.set_namespace(window,'glyphos-dock-menu');GtkLayerShell.set_layer(window,GtkLayerShell.Layer.OVERLAY);GtkLayerShell.set_keyboard_mode(window,GtkLayerShell.KeyboardMode.ON_DEMAND);GtkLayerShell.set_exclusive_zone(window,-1)
 GtkLayerShell.set_anchor(window,GtkLayerShell.Edge.BOTTOM,True);GtkLayerShell.set_margin(window,GtkLayerShell.Edge.BOTTOM,100)
 window.set_default_size(280,-1);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);box.set_border_width(12);window.add(box)
 css=Gtk.CssProvider();css.load_from_data(b'window {background:#e9e9e4;color:#171b1b;border:1px solid rgba(255,255,255,.65);border-radius:14px;} button {background:transparent;color:#171b1b;border:none;box-shadow:none;border-radius:8px;padding:8px;} button:hover {background:rgba(80,80,70,.12);} .heading {font-weight:600;padding:5px;}')
 Gtk.StyleContext.add_provider_for_screen(window.get_screen(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
 window.connect('destroy',lambda *_:Gtk.main_quit())
 dialog_open=[False]
 # Layer surfaces can report focus-out immediately on map; dismiss only a real outside click.
 import socket
 runtime=Path(os.environ['XDG_RUNTIME_DIR']);guard=(runtime/'glyphos-dock-menu.lock').open('w')
 try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return
 sockpath=runtime/'glyphos-dock-menu.sock';sockpath.unlink(missing_ok=True)
 ipc=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);ipc.bind(str(sockpath));ipc.setblocking(False)
 def outside(*_):
  try:ipc.recv(128)
  except BlockingIOError:return True
  if dialog_open[0]:return True
  cursor=json.loads(subprocess.check_output(['hyprctl','cursorpos','-j'],text=True,timeout=2))
  layers=json.loads(subprocess.check_output(['hyprctl','layers','-j'],text=True,timeout=2))
  surfaces=[s for m in layers.values() for group in m.get('levels',{}).values() for s in group if s.get('namespace')=='glyphos-dock-menu']
  if surfaces and not any(s['x']<=cursor['x']<s['x']+s['w'] and s['y']<=cursor['y']<s['y']+s['h'] for s in surfaces):window.destroy();return False
  return True
 GLib.io_add_watch(ipc.fileno(),GLib.IO_IN,outside)
 def clear():
  for child in box.get_children():child.destroy()
 def title(text):
  label=Gtk.Label(label=text,xalign=0);label.get_style_context().add_class('heading');box.pack_start(label,False,False,0)
 def button(text,fn,enabled=True):
  b=Gtk.Button(label=text);b.set_sensitive(enabled);b.connect('clicked',lambda *_:fn());box.pack_start(b,False,False,0);return b
 def finish(fn):fn();window.destroy()
 def remove():
  current=load();current['items']=[i for i in current['items'] if i['id']!=key];save(current)
 def hide():
  current=load();current['hidden']=True;save(current);eww('close','dock')
 def show():
  current=load();current['hidden']=False;save(current);eww('open','dock')
 def color():
  dialog_open[0]=True
  dialog=Gtk.ColorChooserDialog(title='Dock background',transient_for=window);rgba=Gdk.RGBA();chosen=load().get('color') or '#e9e9e4';chosen='rgba('+','.join(str(int(chosen[i:i+2],16)) for i in (1,3,5))+','+str(int(chosen[7:9],16)/255)+')' if len(chosen)==9 else chosen;rgba.parse(chosen);dialog.set_rgba(rgba);dialog.set_use_alpha(True)
  if dialog.run()==Gtk.ResponseType.OK:
   c=dialog.get_rgba();current=load();current['color']='#'+''.join(f'{round(v*255):02x}' for v in [c.red,c.green,c.blue,c.alpha]);save(current)
  dialog.destroy();dialog_open[0]=False
 def rearrange():
  clear();title('Rearrange Dock')
  current=load()
  def move(key,delta):
   data=load();i=next(i for i,r in enumerate(data['items']) if r['id']==key);j=i+delta
   if 0<=j<len(data['items']):data['items'][i],data['items'][j]=data['items'][j],data['items'][i];save(data)
   rearrange()
  for index,entry in enumerate(current['items']):
   row=Gtk.Box(spacing=4);label=Gtk.Label(label=entry['name'],xalign=0);label.set_ellipsize(3);label.set_max_width_chars(20);row.pack_start(label,True,True,0)
   for text,delta in [('↑',-1),('↓',1)]:
    b=Gtk.Button(label=text);b.set_sensitive(0<=index+delta<len(current['items']));b.connect('clicked',lambda _,k=entry['id'],d=delta:move(k,d));row.pack_start(b,False,False,0)
   box.pack_start(row,False,False,0)
  button('Back',settings);window.show_all()
 def add():
  clear();title('Add Application to Dock');search=Gtk.SearchEntry();box.pack_start(search,False,False,0)
  scroll=Gtk.ScrolledWindow();scroll.set_min_content_height(220);scroll.set_max_content_height(300);scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);rows=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);scroll.add(rows);box.pack_start(scroll,True,True,0)
  apps=sorted([a for a in Gio.AppInfo.get_all() if isinstance(a,Gio.DesktopAppInfo) and a.should_show()],key=lambda a:a.get_name().casefold())
  def populate(*_):
   for child in rows.get_children():child.destroy()
   query=search.get_text().casefold()
   for app in apps:
    if query not in app.get_name().casefold():continue
    b=Gtk.Button(label=app.get_name());b.connect('clicked',lambda _,a=app:choose(a));rows.pack_start(b,False,False,0)
   rows.show_all()
  def choose(app):
   from app_service import register
   entry=register({'desktop':app.get_id(),'name':app.get_name(),'flatpak':app.get_string('X-Flatpak') or '', 'icon_name':app.get_string('Icon') or ''})
   current=load()
   if not any(i['id']==entry['key'] for i in current['items']):current['items'].append(dict(id=entry['key'],name=entry['name'],icon=entry['icon_name'],desktop=entry['desktop']))
   current['hidden']=False;save(current);eww('open','dock');settings()
  search.connect('search-changed',populate);populate();button('Back',settings);window.show_all()
 def reset_color():
  current=load();current['color']='';save(current)
 def settings():
  clear();title('Dock Options');button('Rearrange Dock',rearrange);button('Show Dock' if load().get('hidden') else 'Hide Dock',lambda:finish(show if load().get('hidden') else hide));button('Change Background Color',color);button('Restore Original Background',lambda:finish(reset_color));button('Add Application to Dock',add);button('Close',window.destroy);window.show_all()
 if mode=='context':
  entry=item(key)
  if not entry:return
  title(entry['name']);button('Remove from Dock',lambda:finish(remove))
  from app_service import resolve,entry as registered,installed
  app=registered(key) if key.startswith('app-') else resolve({'class':{'browser':'brave','files':'org.glyphos.Files','home':'app-store.py','music':'spotify'}.get(key,'')})
  flatpak=bool(app and app.get('flatpak') and app['flatpak'] in installed())
  package=native_package(app) if not flatpak and (not entry.get('builtin') or key in ('browser','music')) else ''
  def uninstall():
   if flatpak:
    subprocess.Popen([str(BASE/'scripts/app-service.py'),'confirm',app['key']],start_new_session=True);window.destroy();return
   if package:
    clear();title('Uninstall '+app['name']+'?')
    label=Gtk.Label(label='Remove package '+package+'?\nThe package manager will request authentication\nand check dependencies before removal.');label.set_line_wrap(True);box.pack_start(label,False,False,0)
    def execute():
     import shutil
     if not shutil.which('kitty'):notify('Kitty is required to open the authenticated package removal prompt.');return
     subprocess.Popen(['kitty','--title','Uninstall '+app['name'],'-e','sudo','pacman','-R','--',package],start_new_session=True);window.destroy()
    button('Continue to Uninstall',execute);button('Cancel',window.destroy);window.show_all()
  b=button('Uninstall Application',uninstall,flatpak or bool(package))
  if not flatpak and not package:b.set_tooltip_text('This shortcut has no removable app package, or is a protected desktop component.')
  button('Close',window.destroy)
 else:settings()
 window.show_all();Gtk.main()
def context_at_cursor():
 cursor=json.loads(subprocess.check_output(['hyprctl','cursorpos','-j'],text=True));layers=json.loads(subprocess.check_output(['hyprctl','layers','-j'],text=True))
 dock=next((s for m in layers.values() for group in m.get('levels',{}).values() for s in group if s.get('namespace')=='glyphos-dock'),None)
 if dock:
  x=cursor['x']-dock['x']-38;y=cursor['y']-dock['y']-24
  index=int(x//77)
  rows=load()['items']
  if x>=0 and 8<=y<72 and x%77<60 and index<len(rows):ui('context',rows[index]['id']);return
 ui('menu')
if __name__=='__main__':
 arguments=sys.argv[1:]
 detached=bool(arguments and arguments[0]=='--ui')
 if detached:arguments=arguments[1:]
 command=arguments[0] if arguments else 'menu'
 if command in ('menu','context','settings') and not detached:
  subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--ui',*arguments],start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  raise SystemExit(0)
 sys.argv=[sys.argv[0],*arguments]
 if command=='listen':listen()
 elif command=='launch' and len(sys.argv)>2 and valid_id(sys.argv[2]):launch(sys.argv[2])
 elif command=='menu':context_at_cursor()
 elif command=='settings':ui('menu')
 elif command=='context' and len(sys.argv)>2 and valid_id(sys.argv[2]):ui('context',sys.argv[2])

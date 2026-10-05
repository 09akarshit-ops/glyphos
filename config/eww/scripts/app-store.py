#!/usr/bin/python3
"""Glyph App Store: reference-inspired GTK glass cards with background Flatpak jobs."""
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf
from app_service import BASE, CATALOG, installed, job, start_job, valid_id

CSS = b'''
window { background-color: #d7dfe0; color: #202625; font-family: "Roboto Condensed", Sans; }
.store-frame { background-color: rgba(220,227,227,0.93); border: 1px solid #f8fcfb; border-radius: 24px; padding: 20px; box-shadow: 0 10px 24px rgba(26,38,38,0.22); }
.store-header { background-color: rgba(247,251,250,0.72); border-radius: 20px; padding: 15px 20px; }
.dot-title { font-family: "Ndot"; font-size: 42px; color: #151b19; }
.section-title { font-family: "Ndot"; font-size: 31px; }
.sidebar-title { font-family: "Ndot"; font-size: 25px; }
.featured, .sidebar-card { background-color: rgba(244,248,248,0.6); border-radius: 22px; padding: 18px; }
.app-card { background-color: rgba(241,247,247,0.9); border: 1px solid rgba(255,255,255,0.7); border-radius: 20px; padding: 14px; box-shadow: 0 8px 14px rgba(41,55,55,0.17); }
.app-name { font-size: 19px; font-weight: bold; }
.app-detail { font-size: 13px; color: #63716b; }
button { background-image: none; box-shadow: none; border: 0; border-radius: 13px; padding: 8px 15px; background-color: rgba(255,255,255,0.7); color: #202625; }
button:hover { background-color: #ffffff; }
button:disabled { opacity: 0.65; }
button.install { background-color: #e5b8b6; color: #70232c; }
button.open { background-color: #c7dec9; color: #254d30; }
button.category-active { background-color: #c7d3d2; }
entry { border-radius: 22px; padding: 12px 16px; background-color: #eff5f3; border: 1px solid #e8c2bf; box-shadow: 0 0 13px rgba(212,80,80,0.3); font-size: 20px; color: #27312c; }
.chart { border-radius: 8px; padding: 9px 12px; color: #27312c; font-size: 18px; }
.chart-red { background-color: #e6c8c5; border-left: 5px solid #d62b3e; }
.chart-yellow { background-color: #e8e2b9; border-left: 5px solid #dcbd2b; }
.chart-green { background-color: #c4dfca; border-left: 5px solid #37b25e; }
.status { color: #70423f; font-size: 13px; }
.store-disclaimer { background-color: rgba(233,233,228,0.82); border: 1px solid rgba(255,255,255,0.7); border-radius: 14px; padding: 10px 14px; color: #626761; font-size: 13px; }
progressbar trough { background-color: #d4dedd; border-radius: 8px; min-height: 5px; }
progressbar progress { background-color: #bc686c; border-radius: 8px; min-height: 5px; }
.custom-titlebar { padding: 5px 12px; background-color: #e9eeec; }
.control { padding: 0; background-color: transparent; }
'''

def label(text,css=None):
 w=Gtk.Label(label=text,xalign=0)
 if css:w.get_style_context().add_class(css)
 if css in ('dot-title','section-title','sidebar-title'):
  w.set_markup('<span font_family="Ndot">'+GLib.markup_escape_text(text)+'</span>')
 return w

def box(vertical=True,spacing=12,css=None):
 w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
 if css:w.get_style_context().add_class(css)
 return w

class Store(Gtk.Application):
 def __init__(self):
  super().__init__(application_id='org.glyphos.AppStore',flags=Gio.ApplicationFlags.FLAGS_NONE)
  self.cards={};self.present_ids=set();self.category='All';self.search='';self.last_states={};self.refreshing=False
  self.connect('activate',self.activate)

 def activate(self,*_):
  if self.get_active_window():self.get_active_window().present();return
  provider=Gtk.CssProvider();provider.load_from_data(CSS)
  # Native GTK callbacks keep CSS updates on the GUI's main thread.
  self.theme_mode=None
  def refresh_theme():
   try:
    state=json.loads((Path.home()/'.local/state/glyphos/theme.json').read_text())
    mode=state.get('mode','light')
    if mode!=self.theme_mode:
     data=CSS.decode()
     if mode=='dark':
      import re
      glyph_scripts=str(Path.home()/'.config/glyphos/scripts')
      if glyph_scripts not in sys.path:sys.path.append(glyph_scripts)
      from theme import neutral_hex,neutral_rgba
      data=re.sub(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b',neutral_hex,data)
      data=re.sub(r'\b(rgb|rgba)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[.\d]+)?\)',neutral_rgba,data)
     provider.load_from_data(data.encode());self.theme_mode=mode
   except (OSError,ValueError):pass
   return True
  refresh_theme();GLib.timeout_add_seconds(5,refresh_theme)
  Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.window=Gtk.ApplicationWindow(application=self);self.window.set_title('Glyph App Store');self.window.set_wmclass('glyphos-app-store','GlyphOS App Store')
  self.window.set_default_size(1050,700);self.window.set_decorated(False)
  outer=box(spacing=0);self.window.add(outer)
  titlebar=box(False,8,'custom-titlebar');titlebar.pack_start(label('GLYPHOS  /  APP STORE'),True,True,0)
  for name,callback in [('close',lambda *_:self.window.close()),('minimize',lambda *_:self.window.iconify()),('maximize',self.maximize)]:
   b=Gtk.Button();b.get_style_context().add_class('control');b.set_tooltip_text(name.title())
   b.set_image(Gtk.Image.new_from_file(str(BASE/'assets'/f'control-{name}.svg')));b.connect('clicked',callback);titlebar.pack_start(b,False,False,0)
  outer.pack_start(titlebar,False,False,0)
  surround=box(False);surround.set_margin_top(24);surround.set_margin_bottom(24);surround.set_margin_start(24);surround.set_margin_end(24)
  outer.pack_start(surround,True,True,0)
  frame=box(spacing=16,css='store-frame');frame.set_hexpand(True);surround.pack_start(frame,True,True,0)
  frame.connect_after('draw',self.draw_dots)
  header=box(False,20,'store-header');header.pack_start(label('Glyph App Store','dot-title'),True,True,0)
  search=Gtk.SearchEntry();search.set_placeholder_text('Search Glyph apps…');search.set_size_request(310,-1);search.connect('search-changed',self.search_changed)
  header.pack_end(search,False,False,0);frame.pack_start(header,False,False,0)
  scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
  frame.pack_start(scroll,True,True,0)
  body=box(False,16);scroll.add(body)
  featured=box(spacing=16,css='featured');body.pack_start(featured,True,True,0)
  featured.pack_start(label('Featured\nGLYPH APPS','section-title'),False,False,0)
  self.grid=Gtk.Grid(column_spacing=16,row_spacing=18);self.grid.set_column_homogeneous(True);featured.pack_start(self.grid,True,True,0)
  sidebar=box(spacing=16);sidebar.set_size_request(235,-1);body.pack_end(sidebar,False,False,0)
  charts=box(css='sidebar-card');charts.pack_start(label('TOP PICKS','sidebar-title'),False,False,0)
  # Curated picks are labelled honestly; there is no fabricated live ranking.
  for name,color,app_id in [('Spotify','red','com.spotify.Client'),('Discord','yellow','com.discordapp.Discord'),('VS Code','green','com.visualstudio.code')]:
   b=Gtk.Button(label=name);b.get_style_context().add_class('chart');b.get_style_context().add_class('chart-'+color)
   b.connect('clicked',lambda _,n=name:search.set_text(n));charts.pack_start(b,False,False,0)
  charts.pack_start(label('Curated on Flathub','app-detail'),False,False,0);sidebar.pack_start(charts,False,False,0)
  categories=box(css='sidebar-card');categories.pack_start(label('CATEGORY','sidebar-title'),False,False,0)
  self.category_buttons={}
  for name in ['All','Utilities','Creation','Sound','Games']:
   b=Gtk.Button(label=name);b.connect('clicked',self.select_category,name);categories.pack_start(b,False,False,0);self.category_buttons[name]=b
  sidebar.pack_start(categories,False,False,0)
  footer=box(css='sidebar-card');footer.pack_start(label('glyph-store v1.1','sidebar-title'),True,True,0)
  footer.pack_start(label('User installs · Flathub','app-detail'),False,False,0);sidebar.pack_start(footer,True,True,0)
  self.notice=label('','status');self.notice.set_line_wrap(True);frame.pack_start(self.notice,False,False,0)
  banner=box(spacing=0,css='store-disclaimer')
  self.disclaimer=label('This App Store is currently under active development. Expect bugs; more apps will be added soon! :)')
  self.disclaimer.set_line_wrap(True);self.disclaimer.set_max_width_chars(100)
  banner.pack_start(self.disclaimer,True,True,0);frame.pack_end(banner,False,False,0)
  self.render(CATALOG);self.select_category(None,'All')
  self.window.show_all();search.grab_focus();self.tick();self.refresh_installed();GLib.timeout_add(400,self.tick)
  GLib.timeout_add(250,lambda: (scroll.get_vadjustment().set_value(0),False)[1])
  if not shutil.which('flatpak'):self.notice.set_text('Flatpak setup required. Install Flatpak once to enable user-only app installation.')

 def draw_dots(self,widget,cr):
  w,h=widget.get_allocated_width(),widget.get_allocated_height();cr.set_source_rgba(1,1,1,.9)
  for x in range(10,w-10,7):
   for y in (10,h-10):cr.arc(x,y,1.1,0,6.283);cr.fill()
  for y in range(17,h-10,7):
   for x in (10,w-10):cr.arc(x,y,1.1,0,6.283);cr.fill()
  return False

 def maximize(self,*_):
  if self.window.is_maximized():self.window.unmaximize()
  else:self.window.maximize()

 def render(self,apps):
  for child in self.grid.get_children():self.grid.remove(child)
  self.cards={}
  for index,app in enumerate(apps):
   card=box(spacing=6,css='app-card');card.set_size_request(185,220)
   image=Gtk.Image();path={'com.spotify.Client':'store-spotify.svg','com.rtosta.zapzap':'whatsapp.svg','com.discordapp.Discord':'store-discord.svg'}.get(app['id'],app.get('fallback','glyphos.svg'))
   local=BASE/'assets'/app.get('icon',app['id'])
   icon=Gtk.IconTheme.get_default().lookup_icon(app.get('icon',app['id']),88,0)
   filename=str(BASE/'assets/whatsapp.svg') if app['id']=='com.rtosta.zapzap' else (str(local) if local.is_file() else icon.get_filename() if icon else str(BASE/'assets'/path))
   try:image.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(filename,88,88,True))
   except GLib.Error:image.set_from_icon_name('application-x-executable',Gtk.IconSize.DIALOG)
   card.pack_start(image,False,False,4);card.pack_start(label(app['name'],'app-name'),False,False,0)
   detail=label(app.get('description','Flathub application'),'app-detail');detail.set_line_wrap(True);detail.set_max_width_chars(25);card.pack_start(detail,True,True,0)
   progress=Gtk.ProgressBar();progress.set_no_show_all(True);card.pack_start(progress,False,False,0)
   button=Gtk.Button(label='Install');button.get_style_context().add_class('install');button.connect('clicked',self.install_or_open,app)
   card.pack_start(button,False,False,0)
   status=label('','app-detail');status.set_no_show_all(True);status.set_line_wrap(True);status.set_max_width_chars(24);card.pack_start(status,False,False,0)
   self.grid.attach(card,index%3,index//3,1,1);self.cards[app['id']]={'button':button,'progress':progress,'status':status}
  self.grid.show_all();self.tick()

 def refresh_installed(self):
  if self.refreshing:return
  self.refreshing=True
  def worker():
   try:ids=installed();error=''
   except Exception as e:ids=self.present_ids;error=str(e)
   GLib.idle_add(self.receive_installed,ids,error)
  threading.Thread(target=worker,daemon=True).start()

 def receive_installed(self,ids,error):
  self.present_ids=ids;self.refreshing=False
  if error:self.notice.set_text(error)
  return False

 def tick(self):
  for app_id,widgets in self.cards.items():
   state=job(app_id);busy=state.get('state') in ('queued','working');button=widgets['button'];progress=widgets['progress']
   button.set_sensitive(not busy and bool(shutil.which('flatpak')))
   is_installed=app_id in self.present_ids
   button.set_label(('Installing...' if state.get('action')=='install' else 'Uninstalling...') if busy else 'Open' if is_installed else 'Install')
   button.get_style_context().remove_class('open' if not is_installed else 'install');button.get_style_context().add_class('open' if is_installed else 'install')
   progress.set_visible(busy)
   if busy:
    if state.get('progress') is None:progress.pulse()
    else:progress.set_fraction(state['progress']/100)
   error=state.get('detail','') if state.get('state')=='error' else ''
   widgets['status'].set_text(error[:150]);widgets['status'].set_tooltip_text(error);widgets['status'].set_visible(bool(error))
   token=(state.get('state'),state.get('updated'))
   if state.get('state') in ('done','error') and self.last_states.get(app_id)!=token:self.refresh_installed()
   self.last_states[app_id]=token
  return True

 def install_or_open(self,button,app):
  if app['id'] in self.present_ids:
   subprocess.Popen(['flatpak','run',valid_id(app['id'])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  else:
   # Show immediate feedback while the detached worker starts.
   button.set_label('Installing...');button.set_sensitive(False)
   try:start_job('install',app['id'])
   except Exception as error:
    self.notice.set_text(str(error));button.set_label('Install');button.set_sensitive(True)

 def select_category(self,_,name):
  self.category=name
  for n,b in self.category_buttons.items():
   if n==name:b.get_style_context().add_class('category-active')
   else:b.get_style_context().remove_class('category-active')
  self.filter_apps()

 def search_changed(self,entry):
  self.search=entry.get_text().strip().lower();self.filter_apps()

 def filter_apps(self):
  apps=[a for a in CATALOG if (self.category=='All' or a['category']==self.category) and (not self.search or self.search in (a['name']+' '+a['id']+' '+a['description']).lower())]
  self.render(apps)

if __name__=='__main__':
 app=Store();sys.exit(app.run(sys.argv))

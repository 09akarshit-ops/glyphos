#!/usr/bin/env python3
"""GlyphOS Files: virtualized GTK4 navigation, bounded previews and KDE Connect mesh."""
from collections import OrderedDict
from mobile_sftp import PROFILE,MOUNT,KEY,save_profile
from file_transfer import transfer
import concurrent.futures
from datetime import datetime
import json
import mimetypes
import os
from pathlib import Path
import shutil
import stat as statmod
import subprocess
import sys
import threading
os.environ.setdefault('GSK_RENDERER','cairo')
import gi
gi.require_version('Gtk','4.0');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk,Gdk,GdkPixbuf,Gio,GLib,GObject
from phone_mesh import SNAPSHOT,read,send

HOME=Path.home();BASE=HOME/'.config/glyphos'
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=4,thread_name_prefix='glyphos-files')
THUMBS=concurrent.futures.ThreadPoolExecutor(max_workers=2,thread_name_prefix='glyphos-thumbnails')
THUMB_CACHE=OrderedDict();THUMB_PENDING=set()


def size_text(value):
    if value is None:return '—'
    for suffix in ['B','KB','MB','GB','TB']:
        if value<1024 or suffix=='TB':return f'{value:.0f} {suffix}' if suffix=='B' else f'{value:.1f} {suffix}'
        value/=1024


def scan(path,hidden,cancel):
    rows=[]
    with os.scandir(path) as entries:
        for entry in entries:
            if cancel.is_set():return []
            if not hidden and entry.name.startswith('.'):continue
            try:
                stat=entry.stat(follow_symlinks=False)
                directory=entry.is_dir(follow_symlinks=True)
                rows.append((entry.name,entry.path,directory,stat.st_size,stat.st_mtime,stat.st_mode))
            except OSError:rows.append((entry.name,entry.path,False,None,None,0))
    return sorted(rows,key=lambda row:(not row[2],row[0].casefold()))


def search(path,pattern,hidden,cancel):
    if not shutil.which('fd'):raise RuntimeError('Install fd to enable recursive search.')
    args=['fd','--color','never','--print0','--absolute-path','--max-results','500','--fixed-strings','--exclude','.git','--search-path',str(path)]
    if hidden:args.append('--hidden')
    result=subprocess.run(args+['--',pattern],capture_output=True,timeout=8,check=True)
    rows=[]
    for raw in result.stdout.split(b'\0'):
        if not raw or cancel.is_set():continue
        item=Path(os.fsdecode(raw))
        try:stat=item.stat();rows.append((str(item.relative_to(path)),str(item),item.is_dir(),stat.st_size,stat.st_mtime,stat.st_mode))
        except (OSError,ValueError):continue
    return sorted(rows,key=lambda row:(not row[2],row[0].casefold()))


class FileRow(GObject.Object):
    def __init__(self,row):
        super().__init__();self.name,self.path,self.directory,self.size,self.mtime=row[:5];self.mode=row[5] if len(row)>5 else 0


def label(text='',css=None,xalign=0):
    widget=Gtk.Label(label=text,xalign=xalign)
    if css:widget.add_css_class(css)
    return widget


def button(text,callback,css=None):
    widget=Gtk.Button(label=text);widget.connect('clicked',lambda *_:callback())
    if css:widget.add_css_class(css)
    return widget


class Files(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.glyphos.Files',flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.pending_open=None;self.window=None;self.path=HOME;self.history=[];self.future_history=[];self.hidden=False;self.generation=0
        self.cancel=threading.Event();self.search_timer=None;self.clipboard=None;self.preview=None
        self.mesh_state=None;self.pair_dialogs={};self.monitor=None;self.watch_timer=None
    def do_open(self,files,n_files,hint):
        self.do_activate()
        if files and files[0].get_path():
            path=Path(files[0].get_path())
            if path.is_dir():self.navigate(path)
            else:
                self.pending_open=str(path);self.hidden=self.hidden or path.name.startswith('.')
                self.navigate(path.parent)
    def do_activate(self):
        if self.window:self.window.present();return
        Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',False)
        provider=Gtk.CssProvider();provider.load_from_path(str(BASE/'file_manager/style.css'))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window=Gtk.ApplicationWindow(application=self,title='GlyphOS Files')
        self.window.set_default_size(960,540);self.window.set_decorated(False);self.window.add_css_class('glyphos-files')
        root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.window.set_child(root)
        header=Gtk.Box(spacing=4);header.add_css_class('files-header');root.append(header)
        spacer=Gtk.Box();spacer.set_hexpand(True);header.append(spacer)
        for text,callback in [('−',lambda:self.window.minimize()),('□',lambda:self.window.unmaximize() if self.window.is_maximized() else self.window.maximize()),('×',self.window.close)]:
            header.append(button(text,callback,'window-control'))
        def drag_window(gesture,n,x,y):
            if n==2:
                self.window.unmaximize() if self.window.is_maximized() else self.window.maximize();return
            device=gesture.get_current_event_device()
            if device:self.window.get_surface().begin_move(device,1,x,y,gesture.get_current_event_time())
        gesture=Gtk.GestureClick();gesture.set_button(1);gesture.connect('pressed',drag_window);spacer.add_controller(gesture)
        toolbar=Gtk.Box(spacing=8);toolbar.add_css_class('files-navigation');root.append(toolbar)
        toolbar.append(button('‹',self.back,'nav-button'));toolbar.append(button('›',self.forward,'nav-button'))
        folder=button('',lambda:self.navigate(self.path.parent),'nav-button');folder.set_child(self.icon('folder'));toolbar.append(folder)
        self.breadcrumb=label('','dot-breadcrumb');self.breadcrumb.set_ellipsize(3);self.breadcrumb.set_hexpand(True);self.breadcrumb.add_css_class('path-pill');toolbar.append(self.breadcrumb)
        self.search_entry=Gtk.SearchEntry(placeholder_text='Search (/)');self.search_entry.set_size_request(170,-1);self.search_entry.connect('search-changed',self.search_changed);toolbar.append(self.search_entry)
        body=Gtk.Box();body.set_vexpand(True);root.append(body)
        side_scroll=Gtk.ScrolledWindow();side_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);side_scroll.set_size_request(222,-1)
        self.sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2);self.sidebar.add_css_class('files-sidebar');side_scroll.set_child(self.sidebar);body.append(side_scroll)
        main=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0);main.add_css_class('files-main');main.set_hexpand(True);body.append(main)
        self.store=Gio.ListStore.new(FileRow);self.selection=Gtk.SingleSelection.new(self.store);self.selection.set_autoselect(False)
        self.view=Gtk.ColumnView.new(self.selection);self.view.set_show_row_separators(False);self.view.connect('activate',lambda _,position:self.open_row(self.store.get_item(position)))
        for title,key,expand in [('Name','name',True),('Size','size',False),('Modified','date',False),('Permissions','permissions',False),('Type','type',False)]:
            factory=Gtk.SignalListItemFactory()
            factory.connect('setup',lambda _,item,key=key:self.setup_cell(item,key))
            factory.connect('bind',lambda _,item,key=key:self.bind_cell(item,key))
            column=Gtk.ColumnViewColumn.new(title,factory);column.set_expand(expand);column.set_resizable(True);
            if not expand:column.set_fixed_width({'size':78,'date':142,'permissions':105,'type':80}[key])
            self.view.append_column(column)
        scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.set_child(self.view);main.append(scroll)
        footer=Gtk.Box(spacing=14);self.status=label('');self.status.set_hexpand(True);footer.append(self.status)
        self.capacity=label('','dot-capacity');footer.append(self.capacity);main.append(footer)
        self.metrics=label('');footer.append(self.metrics)
        self.selection.connect('notify::selected',lambda *_:self.selection_status())
        context=Gtk.GestureClick();context.set_button(3);context.connect('pressed',self.context_menu);self.view.add_controller(context)
        GLib.timeout_add_seconds(2,self.update_metrics)
        keys=Gtk.EventControllerKey();keys.connect('key-pressed',self.key);self.window.add_controller(keys)
        self.add_drop_target(self.view,lambda:self.path)
        self.volumes=Gio.VolumeMonitor.get()
        for signal in ['mount-added','mount-removed','mount-changed']:self.volumes.connect(signal,lambda *_:self.rebuild_sidebar())
        self.rebuild_sidebar();self.navigate(HOME,remember=False);self.window.present()
        GLib.timeout_add(1000,self.mesh_tick)
    def icon(self,name):
        return Gtk.Image.new_from_file(str(BASE/'file_manager/icons'/f'{name}.svg'))
    def setup_cell(self,item,key):
        cell=label();cell.set_ellipsize(3);cell.add_css_class('file-cell')
        if key=='name':
            box=Gtk.Box(spacing=8);box.add_css_class('name-cell');image=Gtk.Image();image.set_pixel_size(23);box.append(image);box.append(cell);item.set_child(box)
        else:item.set_child(cell)
        child=item.get_child()
        drag=Gtk.DragSource();drag.set_actions(Gdk.DragAction.COPY|Gdk.DragAction.MOVE)
        drag.connect('prepare',lambda *_:self.drag_file(child));child.add_controller(drag)
        self.add_drop_target(child,lambda:Path(child.glyphos_row.path) if getattr(child,'glyphos_row',None) and child.glyphos_row.directory else None)
    def drag_file(self,child):
        row=getattr(child,'glyphos_row',None)
        return Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path(row.path)])) if row else None
    def add_drop_target(self,widget,destination):
        target=Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY|Gdk.DragAction.MOVE)
        def dropped(controller,files,x,y):
            directory=destination();paths=[f.get_path() for f in files.get_files()]
            if directory is None or not paths or any(p is None for p in paths):return False
            drop=controller.get_current_drop();drag=drop.get_drag() if drop else None
            move=bool(drag and drag.get_selected_action()==Gdk.DragAction.MOVE)
            self.perform(lambda:transfer(paths,directory,move));return True
        target.connect('drop',dropped);widget.add_controller(target)
    def thumbnail(self,child,row):
        key=(row.path,row.mtime,row.size)
        cached=THUMB_CACHE.get(key)
        if cached:child.get_first_child().set_from_paintable(cached);THUMB_CACHE.move_to_end(key);return
        if key in THUMB_PENDING or len(THUMB_PENDING)>=64:return
        THUMB_PENDING.add(key)
        def work():
            with open(row.path,'rb') as stream:data=stream.read(8*1024*1024+1)
            if len(data)>8*1024*1024:return None
            return GdkPixbuf.Pixbuf.new_from_stream_at_scale(Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data)),48,48,True,None)
        future=THUMBS.submit(work)
        def ready():
            try:
                pix=future.result()
                if pix is None:return False
                texture=Gdk.Texture.new_for_pixbuf(pix);THUMB_CACHE[key]=texture
                while len(THUMB_CACHE)>64:THUMB_CACHE.popitem(last=False)
                if getattr(child,'glyphos_row',None) is row:child.get_first_child().set_from_paintable(texture)
            except (OSError,GLib.Error):pass
            finally:THUMB_PENDING.discard(key)
            return False
        future.add_done_callback(lambda _:GLib.idle_add(ready))
    def bind_cell(self,item,key):
        row=item.get_item();child=item.get_child()
        child.glyphos_row=row
        if key=='name':
            mime=mimetypes.guess_type(row.path)[0] or ''
            name='folder' if row.directory else 'music' if mime.startswith('audio/') else 'picture' if mime.startswith('image/') else 'document'
            child.get_first_child().set_from_file(str(BASE/'file_manager/icons'/f'{name}.svg'))
            cell=child.get_last_child();text=row.name
            if mime.startswith('image/') and not row.directory:self.thumbnail(child,row)
        else:
            cell=child
            if key=='size':text='' if row.directory else size_text(row.size)
            elif key=='permissions':text=statmod.filemode(row.mode) if row.mode else '—'
            elif key=='type':text='Folder' if row.directory else {'.py':'Python','.yuck':'Yuck Config','.md':'Markdown'}.get(Path(row.path).suffix.lower(),Path(row.path).suffix.lstrip('.').upper() or 'File')
            else:text=datetime.fromtimestamp(row.mtime).strftime('%d %b %y %H:%M') if row.mtime else '—'
        cell.set_text(text);cell.set_tooltip_text(row.path if key=='name' else text)
    def selection_status(self):
        row=self.selected()
        self.status.set_text('[ 1 Item Selected ]' if row else f'[ {getattr(self,"item_count",0)} Items ]')
    def update_metrics(self):
        if not self.window:return False
        try:
            rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            self.metrics.set_text(f'[ RAM: {size_text(rss)} ]')
        except (OSError,ValueError):pass
        return True
    def context_menu(self,gesture,n,x,y):
        target=self.view.pick(x,y,Gtk.PickFlags.DEFAULT)
        while target and target is not self.view:
            row=getattr(target,'glyphos_row',None)
            if row is not None:
                for i in range(self.store.get_n_items()):
                    if self.store.get_item(i) is row:self.selection.set_selected(i);break
                break
            target=target.get_parent()
        opening='Open with VLC Media Player' if self.audio_row(self.selected()) else 'Open'
        pop=Gtk.Popover();pop.set_parent(self.view);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);pop.set_child(box)
        for text,callback in [(opening,lambda:self.open_row(self.selected())),('Preview · Space',self.open_preview),('New Folder',self.new_folder),('Copy · Ctrl+C',self.copy),('Paste · Ctrl+V',self.paste),('Rename · F2',self.rename),('Move to Trash',self.trash)]:
            box.append(button(text,lambda callback=callback:(pop.popdown(),callback())))
        rectangle=Gdk.Rectangle();rectangle.x=int(x);rectangle.y=int(y);rectangle.width=1;rectangle.height=1;pop.set_pointing_to(rectangle)
        pop.connect('closed',lambda *_:pop.unparent());pop.popup()
    def selected(self):return self.selection.get_selected_item()
    def key(self,controller,keyval,keycode,state):
        editing=isinstance(self.window.get_focus(),Gtk.Editable)
        ctrl=bool(state&Gdk.ModifierType.CONTROL_MASK)
        if keyval==Gdk.KEY_slash and not editing:self.search_entry.grab_focus();return True
        if keyval==Gdk.KEY_Escape:
            if self.preview:self.preview.close();return True
            self.search_entry.set_text('');self.view.grab_focus();return True
        if editing:return False
        actions={Gdk.KEY_Return:lambda:self.open_row(self.selected()),Gdk.KEY_KP_Enter:lambda:self.open_row(self.selected()),Gdk.KEY_space:self.open_preview,Gdk.KEY_F2:self.rename,Gdk.KEY_Delete:self.trash}
        if keyval in actions:actions[keyval]();return True
        if ctrl:
            fn={Gdk.KEY_c:self.copy,Gdk.KEY_v:self.paste,Gdk.KEY_h:self.toggle_hidden,Gdk.KEY_l:self.path_dialog}.get(keyval)
            if fn:fn();return True
        if keyval==Gdk.KEY_BackSpace:self.back();return True
        return False
    def toggle_hidden(self):self.hidden=not self.hidden;self.navigate(self.path,remember=False)
    def path_dialog(self):self.prompt('Go to folder',str(self.path),lambda value:self.navigate(Path(os.path.expanduser(value))))
    def back(self):
        if self.history:
            self.future_history.append(self.path);self.navigate(self.history.pop(),remember=False)
    def forward(self):
        if self.future_history:
            self.history.append(self.path);self.navigate(self.future_history.pop(),remember=False)
    def search_changed(self,*_):
        if self.search_timer:GLib.source_remove(self.search_timer)
        self.search_timer=GLib.timeout_add(180,self.search_now)
    def search_now(self):
        self.search_timer=None;self.load(self.search_entry.get_text().strip());return False
    def navigate(self,path,remember=True):
        path=Path(os.path.abspath(os.path.expanduser(str(path))))
        if remember and path!=self.path:self.history.append(self.path);self.future_history.clear()
        self.path=path;self.breadcrumb.set_text(str(path)+('/' if str(path)!='/' else ''))
        if self.search_timer:GLib.source_remove(self.search_timer);self.search_timer=None
        self.search_entry.set_text('');self.load('')
        if self.monitor:self.monitor.cancel();self.monitor=None
        # Remote FUSE metadata must never be queried on the GTK main thread.
        if path==MOUNT or MOUNT in path.parents:return
        try:
            self.monitor=Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.NONE,None)
            self.monitor.connect('changed',self.directory_changed)
        except GLib.Error:pass
    def directory_changed(self,*_):
        if self.watch_timer:GLib.source_remove(self.watch_timer)
        self.watch_timer=GLib.timeout_add(300,self.watch_refresh)
    def watch_refresh(self):self.watch_timer=None;self.load(self.search_entry.get_text().strip());return False
    def load(self,pattern):
        self.generation+=1;generation=self.generation;self.cancel.set();self.cancel=threading.Event()
        self.status.set_text('Searching…' if pattern else 'Loading…');self.store.remove_all();path=self.path;cancel=self.cancel
        def work():
            rows=search(path,pattern,self.hidden,cancel) if pattern else scan(path,self.hidden,cancel)
            try:disk=shutil.disk_usage(path);capacity=f'[ Disk: {size_text(disk.total)} / {size_text(disk.free)} Free ]'
            except OSError:capacity=''
            return rows,capacity
        future=POOL.submit(work)
        def ready():
            if generation!=self.generation:return False
            try:rows,capacity=future.result()
            except Exception as error:self.status.set_text(str(error));return False
            self.capacity.set_text(capacity);iterator=iter(rows);count=0
            def append():
                nonlocal count
                if generation!=self.generation:return False
                batch=[]
                for _ in range(180):
                    try:batch.append(FileRow(next(iterator)))
                    except StopIteration:break
                self.store.splice(self.store.get_n_items(),0,batch);count+=len(batch)
                if len(batch)<180:
                    self.item_count=count;self.selection_status()
                    pending=self.pending_open;self.pending_open=None
                    if pending:
                        for i in range(self.store.get_n_items()):
                            row=self.store.get_item(i)
                            if row.path==pending:self.selection.set_selected(i);self.open_row(row);break
                    return False
                return True
            GLib.idle_add(append);return False
        future.add_done_callback(lambda _:GLib.idle_add(ready))
    @staticmethod
    def audio_row(row):
        if not row or row.directory:return False
        mime=mimetypes.guess_type(row.path)[0] or ''
        return mime.startswith('audio/') or Path(row.path).suffix.lower() in {'.mp3','.flac','.wav','.ogg','.opus','.m4a','.aac','.aiff','.wma'}
    def open_row(self,row):
        if not row:return
        if row.directory:self.navigate(Path(row.path))
        elif self.audio_row(row) or (mimetypes.guess_type(row.path)[0] or '').startswith('video/'):
            try:
                subprocess.Popen(['vlc','--',row.path],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except OSError as error:self.status.set_text('Unable to open VLC: '+str(error))
        elif (mimetypes.guess_type(row.path)[0] or '').startswith('image/'):
            self.open_preview()
        else:
            Gio.AppInfo.launch_default_for_uri_async(Gio.File.new_for_path(row.path).get_uri(),None,None,self.open_finished,None)
    def open_finished(self,obj,result,data):
        try:Gio.AppInfo.launch_default_for_uri_finish(result)
        except GLib.Error as error:self.status.set_text(str(error))
    def place(self,text,icon,callback):
        widget=button('',callback,'sidebar-place');box=Gtk.Box(spacing=10);box.append(self.icon(icon));box.append(label(text));widget.set_child(box);return widget
    def rebuild_sidebar(self):
        child=self.sidebar.get_first_child()
        while child:
            next_child=child.get_next_sibling();self.sidebar.remove(child);child=next_child
        self.sidebar.append(label('QUICK ACCESS','sidebar-heading'))
        for name,path in [('Home',HOME),('Documents',HOME/'Documents'),('Downloads',HOME/'Downloads'),('Music',HOME/'Music'),('Pictures',HOME/'Pictures')]:
            self.sidebar.append(self.place(name,{'Home':'home','Documents':'document','Downloads':'download','Music':'music','Pictures':'picture'}[name],lambda path=path:self.navigate(path)))
        self.sidebar.append(label('NETWORK & MESH','sidebar-heading'))
        self.mobile_card()
        self.sidebar.append(self.place('Discover Phones','phone',lambda:self.mesh_action('refresh')))
        self.sidebar.append(self.place('Local Share','network',lambda:self.navigate(HOME/'Public')))
        snapshot=read(SNAPSHOT,{'devices':[],'error':'Phone mesh is starting.'})
        if not snapshot.get('devices'):self.sidebar.append(label('No phones connected','sidebar-note'))
        for device in snapshot.get('devices',[]):
            card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);card.add_css_class('phone-card');self.sidebar.append(card)
            card.append(label(device['name']))
            card.append(label('● Connected' if device.get('online') else '○ Offline','device-status'))
            id=device['id']
            if device.get('mounted'):
                card.append(button('Browse Storage',lambda path=device['mount']:self.navigate(Path(path))))
                card.append(button('Unmount / Kill Switch',lambda id=id:self.mesh_action('disconnect',id)))
            elif device.get('paired'):
                if device.get('online') and not device.get('sftp_supported'):
                    note=label('Phone storage sharing is not enabled.','sidebar-note');note.set_wrap(True);card.append(note)
                card.append(button('Connect Storage',lambda id=id:self.mesh_action('connect',id)))
                card.append(button('Kill Switch',lambda id=id:self.mesh_action('disconnect',id)))
            elif device.get('online'):card.append(button('Pair Device',lambda device=device:self.pair(device)))
            if device.get('message'):
                note=label(device['message'],'sidebar-note');note.set_wrap(True);card.append(note)
        if snapshot.get('error'):
            note=label(snapshot['error'],'sidebar-note');note.set_wrap(True);self.sidebar.append(note)
        self.sidebar.append(label('STORAGE DISKS','sidebar-heading'));self.sidebar.append(self.place('System Root (/)', 'disk',lambda:self.navigate(Path('/'))))
        for mount in self.volumes.get_mounts():
            path=mount.get_root().get_path()
            if path and not mount.is_shadowed():self.sidebar.append(self.place(mount.get_name(),'disk',lambda path=path:self.navigate(Path(path))))
    def mobile_card(self):
        mobile=read(SNAPSHOT,{}).get('mobile',{});state=mobile.get('status','disconnected')
        card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);card.add_css_class('phone-card');self.sidebar.append(card)
        heading=Gtk.Box(spacing=8);image=self.icon('phone');image.set_opacity(1 if state=='connected' else .45);heading.append(image);heading.append(label('Mobile Storage'));card.append(heading)
        if state=='connecting':
            spinner=Gtk.Spinner();spinner.start();heading.append(spinner);card.append(label('Connecting…','sidebar-note'))
        elif state=='connected':
            dot=label('●','mobile-connected');heading.append(dot)
            total=mobile.get('total',0);available=mobile.get('available',0)
            if total:
                bar=Gtk.ProgressBar();bar.set_fraction(max(0,min(1,1-available/total)));card.append(bar)
                card.append(label(f'{size_text(available)} free / {size_text(total)}','sidebar-note'))
            card.append(button('Browse Storage',lambda:self.navigate(MOUNT)));self.add_drop_target(card,lambda:MOUNT)
            card.append(button('Eject / Disconnect',lambda:self.mesh_action('sftp-disconnect')))
        else:card.append(button('Connect Phone',self.connect_mobile))
        note=mobile.get('message','')
        if note:
            text=label(note,'sidebar-note');text.set_wrap(True);card.append(text)
        gesture=Gtk.GestureClick();gesture.set_button(3)
        def context(*args):
            pop=Gtk.Popover();pop.set_parent(card);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);pop.set_child(box)
            box.append(button('Eject / Disconnect Device',lambda:(pop.popdown(),self.mesh_action('sftp-disconnect'))))
            box.append(button('Configure Phone',lambda:(pop.popdown(),self.configure_mobile())))
            pop.connect('closed',lambda *_:pop.unparent());pop.popup()
        gesture.connect('pressed',context);card.add_controller(gesture)
    def connect_mobile(self):
        profile=read(PROFILE,{})
        if not profile.get('user') or not profile.get('host'):self.configure_mobile();return
        mobile=read(SNAPSHOT,{}).get('mobile',{})
        if mobile.get('fingerprint'):
            win,box=self.dialog('Verify Phone SSH Host',600,260);text=label(mobile['fingerprint']);text.set_selectable(True);text.set_wrap(True);box.append(text)
            guide=label('Compare this fingerprint with the phone’s SSH host key. Trust only when they match.');guide.set_wrap(True);box.append(guide)
            box.append(button('Trust Host & Connect',lambda:(self.mesh_action('sftp-trust-connect'),win.close())));box.append(button('Cancel',win.close));win.present()
        elif (BASE/'keys/phone_known_hosts').is_file():self.mesh_action('sftp-connect')
        else:self.mesh_action('sftp-probe')
    def configure_mobile(self):
        profile=read(PROFILE,{});win,box=self.dialog('Connect Phone · SFTP',620,420);entries={}
        for title,name,default in [('Wi-Fi IP','host',''),('SSH username','user',''),('SSH port','port',8022),('Remote folder','remote','/storage/emulated/0')]:
            row=Gtk.Box(spacing=10);row.append(label(title));entry=Gtk.Entry(text=str(profile.get(name,default)));entry.set_hexpand(True);row.append(entry);entries[name]=entry;box.append(row)
        note=label('On the phone: enable storage access and start its SSH server. Authorize this PC’s public key in ~/.ssh/authorized_keys.');note.set_wrap(True);box.append(note)
        def generate():
            def work():
                KEY.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                if not KEY.exists():subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(KEY)],timeout=10,check=True)
            self.perform(work)
        box.append(button('Generate PC SSH Key',generate))
        def copy_key():
            try:subprocess.run(['wl-copy'],input=KEY.with_suffix('.pub').read_bytes(),timeout=2);note.set_text('Public key copied. Add it to the phone’s authorized_keys file.')
            except OSError:note.set_text('Generate the key first; wl-copy must be installed.')
        box.append(button('Copy Public Key',copy_key))
        def save():
            try:save_profile({name:e.get_text() for name,e in entries.items()});self.mesh_action('sftp-probe');win.close()
            except ValueError as e:note.set_text(str(e))
        box.append(button('Save & Inspect SSH Host',save));box.append(button('Cancel',win.close));win.present()
    def mesh_tick(self):
        state=read(SNAPSHOT,{})
        comparable=json.dumps({'devices':state.get('devices',[]),'error':state.get('error',''),'mobile':state.get('mobile',{})},sort_keys=True)
        if comparable!=self.mesh_state:
            self.mesh_state=comparable;self.rebuild_sidebar()
            if state.get('mobile',{}).get('status')!='connected' and (self.path==MOUNT or MOUNT in self.path.parents):self.navigate(HOME,remember=False)
            for device in state.get('devices',[]):
                dialog=self.pair_dialogs.get(device['id'])
                if dialog:
                    info,accept=dialog[1:]
                    info.set_text('Paired successfully.' if device.get('paired') else self.pair_text(device))
                    accept.set_visible(bool(device.get('incoming')))
        return self.window is not None
    def mesh_action(self,command,id=''):
        try:send(command,id);self.status.set_text('Phone action requested.');self.mesh_state=None
        except OSError:self.status.set_text('Phone mesh is not running. Start glyphos-phone-mesh.service.')
    def pair_text(self,device):
        verification=device.get('verification') or device.get('encryption') or 'Waiting for KDE Connect verification details…'
        return 'Open KDE Connect on your phone and compare its verification details before accepting.\n\n'+verification
    def pair(self,device):
        existing=self.pair_dialogs.get(device['id'])
        if existing:existing[0].present();return
        win,box=self.dialog('Pair Device',620,350)
        info=label(self.pair_text(device));info.set_wrap(True);info.set_selectable(True);box.append(info)
        actions=Gtk.Box(spacing=8);box.append(actions)
        actions.append(button('Request Pairing',lambda:self.mesh_action('pair',device['id'])))
        accept=button('Accept Matching Request',lambda:self.mesh_action('accept',device['id']));accept.set_visible(bool(device.get('incoming')));actions.append(accept)
        actions.append(button('Cancel',lambda:(self.mesh_action('cancel',device['id']),win.close())))
        self.pair_dialogs[device['id']]=(win,info,accept)
        def closed(*_):
            self.pair_dialogs.pop(device['id'],None);return False
        win.connect('close-request',closed)
        win.present()
    def dialog(self,title,width=520,height=180):
        win=Gtk.Window(title=title,transient_for=self.window,modal=True);win.set_default_size(width,height);win.add_css_class('glyphos-files')
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);box.add_css_class('files-dialog');win.set_child(box);box.append(label(title,'dot-section'));return win,box
    def prompt(self,title,initial,callback):
        win,box=self.dialog(title);entry=Gtk.Entry(text=initial);box.append(entry)
        def accept(*_):
            value=entry.get_text().strip()
            if value:callback(value);win.close()
        entry.connect('activate',accept);box.append(button('Apply',accept));box.append(button('Cancel',win.close));win.present();entry.grab_focus()
    def perform(self,job):
        self.status.set_text('Working…');future=POOL.submit(job)
        def ready():
            try:future.result();self.load(self.search_entry.get_text().strip())
            except Exception as error:self.status.set_text(str(error))
            return False
        future.add_done_callback(lambda _:GLib.idle_add(ready))
    def new_folder(self):
        parent=self.path
        def create(name):
            if Path(name).name!=name or name in ('.','..'):self.status.set_text('Enter a folder name without slashes.');return
            self.perform(lambda:(parent/name).mkdir())
        self.prompt('New Folder','',create)
    def rename(self):
        row=self.selected()
        if not row:return
        source=Path(row.path)
        def change(name):
            if Path(name).name!=name or name in ('.','..'):self.status.set_text('Enter a name without slashes.');return
            def work():
                destination=source.with_name(name)
                Gio.File.new_for_path(str(source)).move(Gio.File.new_for_path(str(destination)),Gio.FileCopyFlags.NONE,None,None,None)
            self.perform(work)
        self.prompt('Rename',source.name,change)
    def copy(self):
        row=self.selected()
        if row:self.clipboard=row.path;self.status.set_text('Ready to copy '+Path(row.path).name)
    def paste(self):
        if not self.clipboard:return
        source=Path(self.clipboard);destination=self.path/source.name
        def work():
            if destination.exists():raise FileExistsError('A file with that name already exists.')
            if source.is_dir():
                if destination==source or source in destination.parents:raise ValueError('Cannot copy a folder into itself.')
                shutil.copytree(source,destination,symlinks=True)
            else:Gio.File.new_for_path(str(source)).copy(Gio.File.new_for_path(str(destination)),Gio.FileCopyFlags.NONE,None,None,None)
        self.perform(work)
    def trash(self):
        row=self.selected()
        if not row:return
        remote=Path(row.path)==MOUNT or MOUNT in Path(row.path).parents
        win,box=self.dialog('Permanently Delete from Phone' if remote else 'Move to Trash');name=label(Path(row.path).name);name.set_wrap(True);box.append(name)
        if remote:
            source=Path(row.path)
            box.append(button('Permanently Delete',lambda:(self.perform(lambda:shutil.rmtree(source) if source.is_dir() and not source.is_symlink() else source.unlink()),win.close())))
            box.append(button('Cancel',win.close));win.present();return
        box.append(button('Move to Trash',lambda:(self.perform(lambda:Gio.File.new_for_path(row.path).trash(None)),win.close())))
        box.append(button('Cancel',win.close));win.present()
    def open_preview(self):
        row=self.selected()
        if not row:return
        if self.preview:self.preview.close()
        win=Gtk.Window(title='Preview',transient_for=self.window);win.set_default_size(700,480);win.add_css_class('glyphos-files');self.preview=win
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.add_css_class('files-dialog');win.set_child(box)
        title=label(Path(row.path).name,'dot-section');title.set_ellipsize(3);box.append(title)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);body.set_vexpand(True);box.append(body)
        box.append(button('Close',win.close));stream=None
        mime=mimetypes.guess_type(row.path)[0] or ''
        if mime.startswith('audio/'):
            stream=Gtk.MediaFile.new_for_filename(row.path);controls=Gtk.MediaControls.new(stream);body.append(controls)
            note=label('Press Play to preview audio.');body.append(note)
            stream.connect('notify::error',lambda *_:note.set_text(str(stream.get_error()) if stream.get_error() else 'Press Play to preview audio.'))
        else:
            body.append(label('Loading preview…'))
            def work():
                if row.directory:return ('text',f'Folder\n{row.path}')
                with open(row.path,'rb') as file:data=file.read(32*1024*1024+1 if mime.startswith('image/') else 256*1024+1)
                if mime.startswith('image/'):
                    if len(data)>32*1024*1024:raise ValueError('Image exceeds 32 MB preview limit.')
                    pixbuf=GdkPixbuf.Pixbuf.new_from_stream_at_scale(Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(data)),1024,768,True,None)
                    return 'image',Gdk.Texture.new_for_pixbuf(pixbuf)
                if b'\0' in data:return 'text','No text preview for this file.\n'+row.path
                return 'text',data[:256*1024].decode('utf-8',errors='replace')+('\n[Preview limited to 256 KB]' if len(data)>256*1024 else '')
            future=POOL.submit(work)
            def ready():
                if self.preview!=win:return False
                body.remove(body.get_first_child())
                try:kind,value=future.result()
                except Exception as error:body.append(label(str(error)));return False
                if kind=='image':
                    picture=Gtk.Picture.new_for_paintable(value);picture.set_can_shrink(True);picture.set_vexpand(True);body.append(picture)
                else:
                    text=Gtk.TextView(editable=False,wrap_mode=Gtk.WrapMode.WORD_CHAR);text.get_buffer().set_text(value)
                    scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.set_child(text);body.append(scroll)
                return False
            future.add_done_callback(lambda _:GLib.idle_add(ready))
        def closed(*_):
            if stream:stream.pause()
            if self.preview==win:self.preview=None
            return False
        win.connect('close-request',closed)
        keys=Gtk.EventControllerKey();keys.connect('key-pressed',lambda _,key,*args:(win.close() or True) if key in (Gdk.KEY_space,Gdk.KEY_Escape) else False);win.add_controller(keys);win.present()
    def do_shutdown(self):
        self.cancel.set()
        if self.monitor:self.monitor.cancel()
        POOL.shutdown(wait=False,cancel_futures=True)
        Gtk.Application.do_shutdown(self)


if __name__=='__main__':
    app=Files()
    raise SystemExit(app.run(sys.argv))

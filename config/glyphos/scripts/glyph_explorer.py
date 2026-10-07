#!/usr/bin/env python3
"""GlyphOS Explorer launcher and isolated portal picker mode."""
import json,sys,os,fnmatch,mimetypes
from pathlib import Path
import file_manager as fm
from file_manager import Files,Gtk,Gio,GLib,Gdk,button,label

def decode_path(value):
 if isinstance(value,(list,bytes)):return os.fsdecode(bytes(value).rstrip(b'\0'))
 return value or ''
def matches(path,filter_):
 if not filter_:return True
 mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
 return any(fnmatch.fnmatchcase(Path(path).name,pattern) if kind==0 else Gio.content_type_is_a(mime,pattern) or fnmatch.fnmatchcase(mime,pattern) for kind,pattern in filter_[1])
class Picker(Files):
 def __init__(self,request):
  super().__init__();self.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
  self.request=request;self.options=request.get('options',{});self.done=False;self.filters=self.options.get('filters',[]);self.active_filter=self.options.get('current_filter',self.filters[0] if self.filters else None)
  self.choice_widgets=[];self.filename=None
 def do_activate(self):
  super().do_activate();self.window.set_title(self.request.get('title','Select files'));self.window.connect('close-request',lambda *_:self.finish(1,{}))
  if self.options.get('multiple') and self.request['method']=='OpenFile':
   self.selection=Gtk.MultiSelection.new(self.store);self.view.set_model(self.selection);self.selection.connect('selection-changed',lambda *_:self.selection_status())
  root=self.window.get_child();bar=Gtk.Box(spacing=10);bar.set_margin_start(12);bar.set_margin_end(12);bar.set_margin_top(8);bar.set_margin_bottom(8)
  if self.request['method']=='SaveFile':
   bar.append(label('File name'));self.filename=Gtk.Entry(text=self.options.get('current_name','Untitled'));self.filename.set_hexpand(True);bar.append(self.filename)
  if self.filters:
   combo=Gtk.DropDown.new_from_strings([f[0] for f in self.filters]);combo.set_selected(next((i for i,f in enumerate(self.filters) if f==self.active_filter),0))
   combo.connect('notify::selected',lambda c,*_:(setattr(self,'active_filter',self.filters[c.get_selected()]),self.load(self.search_entry.get_text().strip())));bar.append(combo)
  for ident,title,choices,current in self.options.get('choices',[]):
   bar.append(label(title))
   if choices:
    widget=Gtk.DropDown.new_from_strings([x[1] for x in choices]);widget.set_selected(next((i for i,x in enumerate(choices) if x[0]==current),0))
   else:widget=Gtk.CheckButton(active=current=='true')
   self.choice_widgets.append((ident,widget,choices));bar.append(widget)
  spacer=Gtk.Box();spacer.set_hexpand(True);bar.append(spacer);bar.append(button('Cancel',lambda:self.finish(1,{})));bar.append(button(self.options.get('accept_label','Save' if self.request['method']!='OpenFile' else 'Open').replace('_',''),self.accept));root.append(bar)
  folder=decode_path(self.options.get('current_folder'))
  current=decode_path(self.options.get('current_file'))
  if current:
   folder=str(Path(current).parent)
   if self.filename:self.filename.set_text(Path(current).name)
  self.navigate(Path(folder) if folder and Path(folder).is_dir() else fm.HOME,remember=False)
 def selected(self):
  if isinstance(self.selection,Gtk.MultiSelection):
   bits=self.selection.get_selection();return self.store.get_item(bits.get_minimum()) if not bits.is_empty() else None
  return super().selected()
 def selection_status(self):
  row=self.selected();self.status.set_text(row.name if row else 'Select a file or folder')
 def context_menu(self,*_):pass
 def key(self,controller,keyval,keycode,state):
  if keyval==Gdk.KEY_Escape:self.finish(1,{});return True
  if keyval in (Gdk.KEY_Delete,Gdk.KEY_F2):return True
  return super().key(controller,keyval,keycode,state)
 def open_row(self,row):
  if row and row.directory:self.navigate(Path(row.path))
  elif row and self.request['method']=='SaveFile':self.filename.set_text(row.name)
  elif row:self.accept()
 def finish(self,code,result):
  if self.done:return False
  self.done=True;print(json.dumps({'response':code,'results':result}),flush=True);self.quit();return False
 def accept(self):
  method=self.request['method'];directory=self.options.get('directory',False) or method=='SaveFiles';row=self.selected()
  if method=='SaveFile':
   name=self.filename.get_text().strip()
   if not name or Path(name).name!=name or name in ('.','..'):self.status.set_text('Enter a file name without slashes.');return
   path=self.path/name
   if path.exists():
    win,box=self.dialog('Replace existing file?');box.append(label(name));box.append(button('Cancel',win.close));box.append(button('Replace',lambda:(win.close(),self.complete([path]))));return
   self.complete([path]);return
  if directory:
   folder=Path(row.path) if row and row.directory else self.path
   if method=='SaveFiles':
    paths=[]
    for raw in self.options.get('files',[]):
     name=Path(decode_path(raw)).name
     if not name or name in ('.','..'):self.status.set_text('Invalid file name.');return
     p=folder/name;i=1
     while p.exists() or p in paths:p=folder/f'{Path(name).stem} ({i}){Path(name).suffix}';i+=1
     paths.append(p)
    self.complete(paths)
   else:self.complete([folder])
   return
  if isinstance(self.selection,Gtk.MultiSelection):paths=[Path(self.store.get_item(i).path) for i in range(self.store.get_n_items()) if self.selection.is_selected(i) and not self.store.get_item(i).directory]
  else:paths=[Path(row.path)] if row and not row.directory else []
  if not paths:self.status.set_text('Select at least one file.');return
  if any(not p.is_file() or not matches(p,self.active_filter) for p in paths):self.status.set_text('Select files matching the active filter.');return
  self.complete(paths)
 def complete(self,paths):
  result={'uris':[p.absolute().as_uri() for p in paths],'choices':[(ident,choices[w.get_selected()][0] if choices else ('true' if w.get_active() else 'false')) for ident,w,choices in self.choice_widgets]}
  if self.active_filter:result['current_filter']=self.active_filter
  self.finish(0,result)
if __name__=='__main__':
 if '--picker' in sys.argv:
  request=json.load(sys.stdin);app=Picker(request)
  for name in ('scan','search'):
   original=getattr(fm,name)
   def filtered(*args,_original=original):return [r for r in _original(*args) if r[2] or (not app.options.get('directory') and matches(r[1],app.active_filter))]
   setattr(fm,name,filtered)
  app.run([sys.argv[0]])
  if not app.done:app.finish(1,{})
 else:raise SystemExit(Files().run(sys.argv))

#!/usr/bin/env python3
"""Asynchronous XDG FileChooser backend for GlyphOS Explorer."""
import json,os,subprocess,threading
from pathlib import Path
from gi.repository import Gio,GLib
NAME='org.freedesktop.impl.portal.desktop.glyphos'
INTERFACE='org.freedesktop.impl.portal.FileChooser'
ARGS='<arg type="o" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="in"/><arg type="u" direction="out"/><arg type="a{sv}" direction="out"/>'
XML='<node><interface name="'+INTERFACE+'">'+''.join('<method name="'+m+'">'+ARGS+'</method>' for m in ['OpenFile','SaveFile','SaveFiles'])+'<property name="version" type="u" access="read"/></interface></node>'
REQUEST=Gio.DBusNodeInfo.new_for_xml('<node><interface name="org.freedesktop.impl.portal.Request"><method name="Close"/></interface></node>').interfaces[0]
class Portal:
 def __init__(self):self.pending={};self.connection=None
 def export(self,connection,*_):
  self.connection=connection
  connection.register_object('/org/freedesktop/portal/desktop',Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],self.call,lambda *_:GLib.Variant('u',3),None)
 def call(self,connection,sender,path,interface,method,params,invocation):
  handle,app,parent,title,options=params.unpack()
  if handle in self.pending:invocation.return_dbus_error('org.freedesktop.portal.Error.InvalidArgument','Duplicate request');return
  if len(self.pending)>=8:invocation.return_dbus_error('org.freedesktop.portal.Error.Failed','Too many file chooser requests');return
  try:
   proc=subprocess.Popen(['/usr/bin/python3',str(Path.home()/'.config/glyphos/scripts/glyph_explorer.py'),'--picker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=None,text=True,start_new_session=True)
   registration=connection.register_object(handle,REQUEST,lambda *args:self.close(handle,*args))
   self.pending[handle]=(proc,invocation,registration,sender)
   payload=json.dumps({'method':method,'title':title,'parent':parent,'options':options})
  except Exception as e:invocation.return_dbus_error('org.freedesktop.portal.Error.Failed',str(e));return
  def worker():
   try:
    output,_=proc.communicate(payload,timeout=1800);result=json.loads(output) if output.strip() else {'response':1,'results':{}}
   except Exception:
    proc.kill();proc.wait();result={'response':2,'results':{}}
   GLib.idle_add(self.finish,handle,result)
  threading.Thread(target=worker,daemon=True).start()
 def close(self,handle,connection,sender,path,interface,method,params,invocation):
  record=self.pending.get(handle)
  if record and sender!=record[3]:invocation.return_dbus_error('org.freedesktop.portal.Error.NotAllowed','Request owner mismatch');return
  invocation.return_value(GLib.Variant('()',()))
  if record:record[0].terminate();self.finish(handle,{'response':1,'results':{}})
 def finish(self,handle,result):
  record=self.pending.pop(handle,None)
  if not record:return False
  _,invocation,registration,_=record;self.connection.unregister_object(registration)
  values={};data=result.get('results',{});code=int(result.get('response',2))
  if code==0:
   uris=data.get('uris',[])
   if not uris or any(not isinstance(u,str) or not u.startswith('file:///') for u in uris):code=2
   else:
    values['uris']=GLib.Variant('as',uris)
    if 'choices' in data:values['choices']=GLib.Variant('a(ss)',[tuple(x) for x in data['choices']])
    if data.get('current_filter'):
     name,patterns=data['current_filter'];values['current_filter']=GLib.Variant('(sa(us))',(name,[(int(k),p) for k,p in patterns]))
  invocation.return_value(GLib.Variant('(ua{sv})',(code,values)));return False
if __name__=='__main__':
 portal=Portal();loop=GLib.MainLoop()
 Gio.bus_own_name(Gio.BusType.SESSION,NAME,Gio.BusNameOwnerFlags.NONE,portal.export,None,lambda *_:loop.quit())
 loop.run()

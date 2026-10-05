#!/usr/bin/python3
"""User-only Flatpak jobs and persistent taskbar application identities."""
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'config'
PINS = DATA / 'pinned_apps.json'
REGISTRY = DATA / 'applications.json'
JOBS = DATA / 'app-jobs'
CATALOG_PATH = BASE / 'store/apps.json'

def load_catalog():
 items=json.loads(CATALOG_PATH.read_text())
 if not isinstance(items,list):raise ValueError('App catalog must be a JSON array')
 seen=set()
 for app in items:
  app_id=app.get('id','')
  if not re.fullmatch(r'[A-Za-z][\w-]*(?:\.[A-Za-z_][\w-]*){2,}',app_id) or app_id in seen:
   raise ValueError('Invalid or duplicate catalog app ID: '+app_id)
  if not all(isinstance(app.get(key),str) and app[key] for key in ('name','category','description','icon','fallback')):
   raise ValueError('Incomplete catalog entry: '+app_id)
  if app_id=='com.rtosta.zapzap':app['name']='WhatsApp'
  seen.add(app_id)
 return items

CATALOG = load_catalog()

def read(path,default):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return default

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
 temp.write_text(json.dumps(value,ensure_ascii=False));temp.replace(path)

def mutate(path,fn,default):
 DATA.mkdir(parents=True,exist_ok=True)
 with path.with_suffix('.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  data=read(path,default);fn(data);write(path,data)

def valid_id(app_id):
 if not re.fullmatch(r'[A-Za-z][\w-]*(?:\.[A-Za-z_][\w-]*){2,}',app_id):raise ValueError('Invalid application ID')
 return app_id

def call(*args,timeout=30):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError(p.stderr.strip() or p.stdout.strip() or 'Command failed')
 return p.stdout

def installed():
 if not shutil.which('flatpak'):return set()
 return set(call('flatpak','list','--user','--app','--columns=application').splitlines())

def desktop_apps():
 import gi
 from gi.repository import Gio
 return [a for a in Gio.AppInfo.get_all() if isinstance(a,Gio.DesktopAppInfo)]

def branded(entry):
 entry=dict(entry)
 if entry.get('flatpak')=='com.rtosta.zapzap' or 'zapzap' in entry.get('desktop','').lower():
  entry.update(name='WhatsApp',icon_name=str(BASE/'assets/whatsapp.svg'))
 return entry

def register(entry):
 entry=branded(entry)
 key='app-'+hashlib.sha256(entry['desktop'].encode()).hexdigest()[:24]
 entry=dict(entry,key=key)
 if read(REGISTRY,{}).get(key)==entry:return entry
 def add(data):data[key]=entry
 mutate(REGISTRY,add,{})
 return entry

def resolve(client):
 identity={str(client.get(k,'')).lower() for k in ('class','initialClass')}
 if 'app-store.py' in identity or 'org.glyphos.appstore' in identity:
  return register({'desktop':str(DATA/'glyphos-app-store.desktop'),'name':'Glyph App Store','flatpak':'','icon_name':str(BASE/'assets/glyphos.svg')})
 candidates=desktop_apps()
 app=None
 # Flatpak exports have an unambiguous application ID in their desktop file.
 for a in candidates:
  keys={a.get_id().removesuffix('.desktop').lower(),(a.get_startup_wm_class() or '').lower()}
  if identity & (keys-{''}):app=a;break
 if app is None:
  # Chromium web-app classes share their browser desktop launcher.
  for a in candidates:
   executable=Path(a.get_executable() or '').name.lower()
   if executable and any(x==executable or x.startswith(executable+'-') for x in identity):app=a;break
 if app is None:return None
 return register({'desktop':app.get_id(),'name':app.get_name(),'flatpak':app.get_string('X-Flatpak') or '', 'icon_name':app.get_string('Icon') or ''})

def entry(key):
 if not re.fullmatch(r'app-[0-9a-f]{24}',key):raise ValueError('No launchable desktop application was found for this item')
 value=read(REGISTRY,{}).get(key)
 if not value:raise ValueError('Application entry is no longer available')
 return branded(value)

def pins():return [branded(value) for value in read(PINS,[])]

def pin(key,enabled):
 value=entry(key)
 def edit(items):
  items[:]=[i for i in items if i['key']!=key]
  if enabled:items.append(value)
 mutate(PINS,edit,[])

def launch(key):
 import gi
 from gi.repository import Gio
 value=entry(key);app=Gio.DesktopAppInfo.new_from_filename(value['desktop']) if Path(value['desktop']).is_absolute() else Gio.DesktopAppInfo.new(value['desktop'])
 if app:app.launch([],None)
 elif value['flatpak']:subprocess.Popen(['flatpak','run',valid_id(value['flatpak'])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 else:raise ValueError('The desktop launcher is no longer installed')

def running(app_id):
 rows=call('flatpak','ps','--columns=application').splitlines()
 if app_id in rows:return True
 # Also check mapped windows before allowing a destructive operation.
 clients=json.loads(call('hyprctl','clients','-j'))
 for client in clients:
  value=resolve(client)
  if value and value['flatpak']==app_id:return True
 return False

def job(app_id):return read(JOBS/(valid_id(app_id)+'.json'),{})

def start_job(action,app_id):
 valid_id(app_id)
 if action not in ('install','uninstall'):raise ValueError('Unknown app operation')
 JOBS.mkdir(parents=True,exist_ok=True)
 with (JOBS/(app_id+'.enqueue.lock')).open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  previous=job(app_id)
  if previous.get('state') in ('queued','working') and previous.get('pid'):
   try:os.kill(previous['pid'],0);return
   except ProcessLookupError:pass
  path=JOBS/(app_id+'.json')
  write(path,{'state':'queued','action':action,'detail':'Preparing…','progress':None,'updated':time.time()})
  try:
   process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',action,app_id],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
   queued=read(path,{})
   queued['pid']=process.pid
   write(path,queued)
  except OSError as error:
   write(path,{'state':'error','action':action,'detail':str(error),'updated':time.time()})
   raise

def worker(action,app_id):
 valid_id(app_id);JOBS.mkdir(parents=True,exist_ok=True)
 # Wait until the launcher has published the queued worker PID.
 with (JOBS/(app_id+'.enqueue.lock')).open('w') as enqueue:
  fcntl.flock(enqueue,fcntl.LOCK_EX)
 with (JOBS/(app_id+'.lock')).open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  path=JOBS/(app_id+'.json')
  def status(state,detail='',progress=None):write(path,{'state':state,'action':action,'detail':detail,'progress':progress,'updated':time.time(),'pid':os.getpid()})
  p=None
  def terminate(*_):
   if p is not None and p.poll() is None:
    try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   status('cancelled','Cancelled');raise SystemExit(0)
  import signal
  signal.signal(signal.SIGTERM,terminate)
  try:
   if not shutil.which('flatpak'):raise RuntimeError('Flatpak is not installed. Install the Flatpak backend to continue.')
   status('working','Preparing…')
   if action=='install':
    call('flatpak','remote-add','--user','--if-not-exists','flathub','https://dl.flathub.org/repo/flathub.flatpakrepo',timeout=120)
    args=['flatpak','install','--user','-y','--noninteractive','flathub',app_id]
   else:
    if app_id not in installed():raise ValueError('Only user-installed Flatpak applications can be removed here.')
    if running(app_id):raise ValueError('Close this application before uninstalling it.')
    args=['flatpak','uninstall','--user','-y','--noninteractive','--delete-data',app_id]
   # No terminal and no shell. The GUI pulses when Flatpak omits numeric progress.
   with (JOBS/(app_id+'.log')).open('w') as log:
    p=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
    for line in p.stdout:
     log.write(line);log.flush()
     clean=re.sub(r'\x1b\[[0-9;?]*[A-Za-z]','',line).strip()
     match=re.search(r'(\d{1,3})%',clean)
     status('working',clean[-180:],min(100,int(match[1])) if match else None)
    if p.wait():raise RuntimeError((JOBS/(app_id+'.log')).read_text()[-1000:] or 'Flatpak operation failed')
   present=app_id in installed()
   if present!=(action=='install'):raise RuntimeError('Flatpak did not reach the requested installation state')
   if action=='uninstall':
    mutate(PINS,lambda items:items.__setitem__(slice(None),[i for i in items if i.get('flatpak')!=app_id]),[])
   status('done','Installed' if present else 'Uninstalled',100)
  except Exception as error:status('error',str(error))

def eww(*args):call('eww','--no-daemonize','--config',str(BASE),*args)

def context(key,address=''):
 if key=='unsupported':
  value={'key':key,'name':'Application','flatpak':''}
 else:value=entry(key)
 value=dict(value,pinned=any(i['key']==key for i in pins()),supported=key!='unsupported',can_uninstall=bool(value.get('flatpak')),error='',address=address)
 eww('update','app-context='+json.dumps(value))
 cursor=json.loads(call('hyprctl','cursorpos','-j'))
 monitors=json.loads(call('hyprctl','monitors','-j'))
 monitor=next((m for m in monitors if m['x']<=cursor['x']<m['x']+m['width']/m['scale'] and m['y']<=cursor['y']<m['y']+m['height']/m['scale']),next(m for m in monitors if m['focused']))
 width,height=monitor['width']/monitor['scale'],monitor['height']/monitor['scale']
 layers=json.loads(call('hyprctl','layers','-j')).get(monitor['name'],{}).get('levels',{})
 surfaces=[s for rows in layers.values() for s in rows]
 source=next((s for s in surfaces if s.get('namespace') in ('glyphos-top-bar','glyphos-dock') and s['x']<=cursor['x']<s['x']+s['w'] and s['y']<=cursor['y']<s['y']+s['h']),None)
 x=max(8,min(cursor['x']-monitor['x']-140,width-288))
 # Eww top/left margins start at the compositor's reserved work area.
 top=source['y']-monitor['y'] if source else cursor['y']-monitor['y']
 bottom=top+source['h'] if source else top
 y=bottom+8 if top<height/2 else max(8,top-250-8)
 reserved=monitor.get('reserved',[0,0,0,0])
 if any(line.startswith('taskbar-context:') for line in call('eww','--no-daemonize','--config',str(BASE),'active-windows').splitlines()):
  eww('close','taskbar-context')
 eww('open','taskbar-context','--arg',f'context-monitor={monitor["id"]}','--arg',f'context-x={round(x-reserved[0])}','--arg',f'context-y={round(y-reserved[1])}')

def dismiss_context():
 # Observe a non-consuming mouse binding; never create an input surface.
 layers=json.loads(call('hyprctl','layers','-j'))
 menu=next((s for m in layers.values() for rows in m.get('levels',{}).values() for s in rows if s.get('namespace')=='glyphos-taskbar-context'),None)
 if menu is None:return
 cursor=json.loads(call('hyprctl','cursorpos','-j'))
 if not (menu['x']<=cursor['x']<menu['x']+menu['w'] and menu['y']<=cursor['y']<menu['y']+menu['h']):
  eww('close','taskbar-context')

def context_icon(icon):
 classes={'files':'org.kde.dolphin','browser':'brave','chat':'brave','ai':'brave','home':'app-store.py'}
 value=resolve({'class':classes.get(icon,'')})
 context(value['key'] if value else 'unsupported')

def confirm(key):
 value=entry(key)
 value=dict(value,key=key,pinned=False,supported=True,can_uninstall=bool(value['flatpak']),error='')
 if not value['flatpak']:raise ValueError('Only user Flatpak applications can be uninstalled here')
 eww('close','taskbar-context');eww('update','app-context='+json.dumps(value));eww('open','app-uninstall-confirm')

def context_action(action,key):
 if action in ('pin','unpin'):
  pin(key,action=='pin');eww('close','taskbar-context')
 elif action=='confirm':confirm(key)
 elif action=='uninstall':
  value=entry(key);start_job('uninstall',value['flatpak']);eww('close','app-uninstall-confirm');eww('open','app-operation-status')

def operation_status():
 selected=read(DATA/'selected-operation.json',{})
 return job(selected['id']) if selected.get('id') else {'state':'','detail':''}

if __name__=='__main__':
 try:
  command=sys.argv[1]
  if command=='worker':worker(sys.argv[2],sys.argv[3])
  elif command=='context':context(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else '')
  elif command=='context-icon':context_icon(sys.argv[2])
  elif command=='dismiss-context':dismiss_context()
  elif command=='launch':launch(sys.argv[2])
  elif command=='status':print(json.dumps(operation_status()))
  elif command in ('pin','unpin','confirm','uninstall'):
   if command=='uninstall':write(DATA/'selected-operation.json',{'id':entry(sys.argv[2])['flatpak']})
   context_action(command,sys.argv[2])
 except Exception as error:
  print(f'app-service: {error}',file=sys.stderr)
  try:
   value=json.loads(call('eww','--no-daemonize','--config',str(BASE),'get','app-context'))
   value['error']=str(error);eww('update','app-context='+json.dumps(value))
  except Exception:pass
  sys.exit(1)

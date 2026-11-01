#!/usr/bin/env python3
"""F11 uses compositor fullscreen for Spotify; forward F11 unchanged elsewhere."""
import fcntl,json,os,re,subprocess
from pathlib import Path
RUNTIME=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))
STATE=RUNTIME/'glyphos-spotify-fullscreen.json'
def is_spotify(client):return any(str(client.get(k,'')).lower() in ('spotify','com.spotify.client') for k in ('class','initialClass'))
def query(what):return json.loads(subprocess.check_output(['hyprctl',what,'-j'],text=True,timeout=3))
def dispatch(action,value):subprocess.run(['hyprctl','dispatch',action,value],check=True,capture_output=True,text=True,timeout=3)
def handle(read=query,send=dispatch,path=STATE):
 client=read('activewindow');address=client.get('address','')
 if not re.fullmatch(r'0x[0-9a-fA-F]+',address):return
 if not is_spotify(client):send('sendshortcut',',F11,address:'+address);return
 try:saved=json.loads(path.read_text())
 except (OSError,ValueError):saved={}
 identity=[address,client.get('pid')]
 if client.get('fullscreen')==2:
  restore=saved.get('restore',1) if saved.get('identity')==identity else 1
  target=restore if restore in (0,1) else 1
 else:
  saved={'identity':identity,'restore':1 if client.get('fullscreen')==1 else 0}
  temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(saved));temporary.replace(path);target=2
 # Do not send a fullscreen request into Spotify's own XWayland playback UI.
 if read('activewindow').get('address')==address:send('fullscreenstate',f'{target} 0')
if __name__=='__main__':
 with STATE.with_suffix('.lock').open('w') as guard:
  fcntl.flock(guard,fcntl.LOCK_EX);handle()

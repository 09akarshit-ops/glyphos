"""F11 routing fixtures: no player or compositor control during these tests."""
import importlib.util,tempfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'config/glyphos/scripts/spotify_fullscreen.py'
spec=importlib.util.spec_from_file_location('spotify_fs',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
client=dict(address='0x123',pid=10,**{'class':'Spotify'},fullscreen=1,fullscreenClient=0);calls=[]
def read(_):return dict(client)
with tempfile.TemporaryDirectory() as folder:
 state=Path(folder)/'state.json'
 m.handle(read,lambda *a:calls.append(a),state);assert calls[-1]==('fullscreenstate','2 0')
 client['fullscreen']=2;m.handle(read,lambda *a:calls.append(a),state);assert calls[-1]==('fullscreenstate','1 0')
 client.update(fullscreen=0);m.handle(read,lambda *a:calls.append(a),state);client['fullscreen']=2;m.handle(read,lambda *a:calls.append(a),state);assert calls[-1]==('fullscreenstate','0 0')
 client['class']='brave-browser';m.handle(read,lambda *a:calls.append(a),state);assert calls[-1]==('sendshortcut',',F11,address:0x123')
 client['class']='Spotify';counter=[0]
 def changed(_):
  counter[0]+=1;return dict(client,address='0x123' if counter[0]==1 else '0x456')
 count=len(calls);m.handle(changed,lambda *a:calls.append(a),state);assert len(calls)==count
print('PASS: Spotify true fullscreen, previous-state restoration, other-app F11 forwarding and focus-race guard.')

import sys,tempfile,threading,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config/glyphos/scripts'))
import file_manager as files
import phone_mesh as mesh
with tempfile.TemporaryDirectory() as d:
 root=Path(d);(root/'folder').mkdir();(root/'note.txt').write_text('Preview text\n');(root/'.hidden').write_text('hidden')
 rows=files.scan(root,False,threading.Event());assert [r[0] for r in rows]==['folder','note.txt']
 assert len(files.scan(root,True,threading.Event()))==3
 assert any(r[0]=='note.txt' for r in files.search(root,'note',False,threading.Event()))
 cancel=threading.Event();cancel.set();assert not files.scan(root,True,cancel)
print('PASS: directory-first navigation, hidden toggle, fd search, scan cancellation.')
a='aa'*32;b='bb'*32
info='Local '+':'.join(a[i:i+2] for i in range(0,64,2))+'\nRemote '+':'.join(b[i:i+2] for i in range(0,64,2))
assert mesh.fingerprint(info)==b
assert mesh.trusted(None,b,True)
assert not mesh.trusted(None,b,False)
assert not mesh.trusted({'fingerprint':a},b,True)
for id in ['../phone','phone; rm -rf','phone/path','']:
 try:mesh.valid_id(id)
 except ValueError:pass
 else:raise AssertionError(id)
class Backend:
 def __init__(self):self.mounts=0;self.unmounts=0;self.current=b;self.paired=True;self.mounted=False
 def devices(self):return ['phone']
 def properties(self,id):return {'type':'phone','name':'Test phone','isReachable':True,'isPaired':self.paired,'supportedPlugins':['kdeconnect_sftp']}
 def device(self,id,method):return info if method=='encryptionInfo' else ''
 def sftp(self,id,method,**kwargs):
  if method=='isMounted':return self.mounted
  if method=='mountAndWait':self.mounts+=1;self.mounted=True;return True
  if method=='unmount':self.unmounts+=1;self.mounted=False;return
  if method=='mountPoint':return d
  return ''
with tempfile.TemporaryDirectory() as d,patch.object(mesh,'TRUST',Path(d)/'trust.json'),patch.object(mesh,'SNAPSHOT',Path(d)/'devices.json'):
 backend=Backend();bridge=mesh.Mesh(backend)
 bridge.scan();assert backend.mounts==1 and bridge.snapshot['devices'][0]['trusted']
 bridge.enqueue('disconnect','phone');assert bridge.trust['phone']['auto_mount'] is False
 bridge.action('disconnect','phone');bridge.scan();assert not backend.mounted and backend.mounts==1
 bridge.action('connect','phone');bridge.scan();assert backend.mounts==2
 bridge.trust['phone']['fingerprint']=a;bridge.scan();assert not backend.mounted and not bridge.snapshot['devices'][0]['trusted']
 backend.paired=False;bridge.trust={};bridge.scan();assert backend.mounts==2
print('PASS: backend fingerprint extraction, paired-only mount, persistent kill switch, explicit reconnect and certificate-change rejection.')

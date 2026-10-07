#!/usr/bin/env python3
"""Private LAN SSHFS mount with explicit host-key trust and bounded probes."""
import base64,hashlib,ipaddress,json,os,re,shutil,subprocess,time
from pathlib import Path
BASE=Path.home()/'.config/glyphos';MOUNT=BASE/'mesh/phone';PROFILE=BASE/'mesh/phone.json';KEY=BASE/'keys/phone_key';KNOWN=BASE/'keys/phone_known_hosts'

def validate(data):
 host=str(data.get('host','')).strip();ip=ipaddress.ip_address(host)
 if not ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_unspecified:raise ValueError('Use the phone’s local Wi-Fi IP address.')
 user=str(data.get('user','')).strip()
 if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}',user):raise ValueError('Enter a valid SSH username.')
 port=int(data.get('port',8022))
 if not 1<=port<=65535:raise ValueError('Invalid SSH port.')
 remote=str(data.get('remote','/storage/emulated/0'))
 if not remote.startswith('/') or any(c in remote for c in '\n\r,\0') or '..' in Path(remote).parts:raise ValueError('Enter an absolute remote storage path.')
 return dict(host=host,user=user,port=port,remote=remote)
def save_profile(data):
 data=validate(data);PROFILE.parent.mkdir(mode=0o700,parents=True,exist_ok=True);temp=PROFILE.with_suffix('.tmp')
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f)
 temp.replace(PROFILE)
def load_profile():
 try:return validate(json.loads(PROFILE.read_text()))
 except (OSError,ValueError,TypeError):return None

def mounted():
 # Read mount metadata without touching an unresponsive FUSE filesystem.
 encoded=str(MOUNT).replace('\\','\\134').replace(' ','\\040')
 return any(len(parts)>4 and parts[4]==encoded for parts in (line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()))
def command(profile):
 host='['+profile['host']+']' if ':' in profile['host'] else profile['host']
 return ['sshfs',f"{profile['user']}@{host}:{profile['remote']}",str(MOUNT),'-p',str(profile['port']),'-o',f'IdentityFile={KEY}', '-o',f'UserKnownHostsFile={KNOWN}','-o','StrictHostKeyChecking=yes,BatchMode=yes,reconnect,ConnectTimeout=5,ServerAliveInterval=15,ServerAliveCountMax=3']
class MobileStorage:
 def __init__(self):
  self.state={'status':'disconnected','mount':str(MOUNT),'message':'Configure the phone’s SSH server to connect.','total':0,'available':0};self.probe=None;self.cancel=False
 def emit(self,publish):publish(dict(self.state))
 def disconnect(self,lost=False):
  if mounted():
   tool=shutil.which('fusermount3') or shutil.which('fusermount')
   if not tool:raise RuntimeError('FUSE unmount tool is missing.')
   try:
    result=subprocess.run([tool,'-u',str(MOUNT)],capture_output=True,text=True,timeout=5);force=bool(result.returncode)
   except subprocess.TimeoutExpired:force=True
   if force:subprocess.run([tool,'-uz',str(MOUNT)],capture_output=True,timeout=5,check=True)
  self.state.update(status='disconnected',total=0,available=0,message='Mobile connection lost' if lost else 'Storage disconnected.')
  if lost:subprocess.Popen(['notify-send','GlyphOS','Mobile connection lost'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 def action(self,action,publish):
  try:
   if action=='disconnect':self.cancel=True;self.disconnect();return
   profile=load_profile()
   if not profile:raise ValueError('Set the phone IP address, SSH username and port first.')
   if action=='probe':
    self.state.update(status='connecting',message='Reading SSH host fingerprint…');self.emit(publish)
    result=subprocess.run(['ssh-keyscan','-T','4','-p',str(profile['port']),'-t','ed25519,rsa',profile['host']],capture_output=True,text=True,timeout=7)
    lines=[line for line in result.stdout.splitlines() if line and not line.startswith('#')]
    if not lines:raise RuntimeError('The phone SSH server did not respond.')
    line=next((s for s in lines if ' ssh-ed25519 ' in s),lines[0]);parts=line.split()
    digest='SHA256:'+base64.b64encode(hashlib.sha256(base64.b64decode(parts[2])).digest()).decode().rstrip('=')
    self.probe=(profile,line,time.monotonic());self.state.update(status='disconnected',fingerprint=digest,message='Compare this SSH fingerprint on the phone before trusting it.');return
   if action=='trust-connect':
    if not self.probe or self.probe[0]!=profile or time.monotonic()-self.probe[2]>120:raise ValueError('Inspect the host again before trusting it.')
    KEY.parent.mkdir(mode=0o700,parents=True,exist_ok=True);KNOWN.write_text(self.probe[1]+'\n');KNOWN.chmod(0o600)
   if action not in ('connect','trust-connect'):raise ValueError('Unknown storage action.')
   if not shutil.which('sshfs'):raise RuntimeError('Install SSHFS: sudo pacman -S --needed sshfs')
   if not KEY.is_file():raise RuntimeError('Create ~/.config/glyphos/keys/phone_key and authorize its public key on your phone.')
   if not KNOWN.is_file():raise RuntimeError('Inspect and trust the phone SSH fingerprint first.')
   if mounted():self.health();return
   if self.cancel:raise RuntimeError('Connection cancelled by eject.')
   MOUNT.mkdir(mode=0o700,parents=True,exist_ok=True);KEY.chmod(0o600)
   self.state.update(status='connecting',message='Connecting phone storage…');self.emit(publish)
   result=subprocess.run(command(profile),capture_output=True,text=True,timeout=12)
   if result.returncode:raise RuntimeError(result.stderr.strip()[:220] or 'SSHFS mount failed.')
   if self.cancel:self.disconnect();return
   if not mounted():raise RuntimeError('SSHFS did not create a mounted filesystem.')
   self.state.update(status='connected',message='Encrypted SFTP connected.');self.health()
  except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:self.state.update(status='disconnected',message=str(error)[:240])
  finally:self.emit(publish)
 def health(self):
  if not mounted():
   if self.state['status']=='connected':self.disconnect(lost=True)
   return
  try:
   code='import os,json,sys; s=os.statvfs(sys.argv[1]); print(json.dumps([s.f_blocks*s.f_frsize,s.f_bavail*s.f_frsize]))'
   result=subprocess.run(['/usr/bin/python3','-c',code,str(MOUNT)],capture_output=True,text=True,timeout=4,check=True)
   total,available=json.loads(result.stdout);self.state.update(status='connected',total=total,available=available)
  except (OSError,ValueError,subprocess.SubprocessError):
   try:self.disconnect(lost=True)
   except Exception as error:self.state.update(status='disconnected',message='Mobile connection lost; eject failed: '+str(error)[:120])

#!/usr/bin/env python3
"""Bounded live verification. Fixtures expire; never install or start audible media."""
import json,os,socket,subprocess,time
from pathlib import Path
state=Path.home()/'.local/state/glyphos/island-health.json'
def health():return json.loads(state.read_text())
def send(op):
 with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:s.sendto(json.dumps({'op':op}).encode(),os.environ['XDG_RUNTIME_DIR']+'/glyphos-island.sock')
def wait(fn,timeout=3):
 for _ in range(int(timeout/.1)):
  if fn():return
  time.sleep(.1)
 raise AssertionError('Timed out')
def active():return json.loads(subprocess.check_output(['hyprctl','activewindow','-j']))
original=active().get('address');results=[]
for _ in range(30):
 try:send('verify-fixture');break
 except (ConnectionRefusedError,FileNotFoundError):time.sleep(.1)
else:raise AssertionError('Island IPC not ready')
wait(lambda:'verify-install' in health()['queue'])
assert health()['keyboard_mode']=='none' and not health()['accept_focus'];results.append('GTK keyboard mode NONE and accept_focus false')
seen=set()
for _ in range(80):
 seen.add(health()['activity']);time.sleep(.1)
assert {'verify-install','verify-media'}<=seen;results.append('Media then simulated install: compact queue cycles between both')
original=active().get('address')
send('expand');wait(lambda:health()['expanded']);wait(lambda:health()['amount']==1)
samples=health()['samples'];assert len({r['width'] for r in samples})>=8
assert .25<=samples[-1]['time']-samples[0]['time']<=.5;results.append('Expansion has >=8 intermediate sizes over about 300ms')
assert health()['activity']=='verify-install';results.append('Expanded view selects most recently activated install')
assert active().get('address')==original;results.append('Active application unchanged across expansion; compact keyboard focus is disabled')
start=time.monotonic();wait(lambda:not health()['expanded'],5)
assert 3.3<=time.monotonic()-start<=4.3;wait(lambda:health()['amount']==0)
results.append('Auto-collapse after about four idle seconds, animated back to compact')
send('expand');wait(lambda:health()['expanded']);send('outside');wait(lambda:health()['amount']==0 and not health()['expanded']);results.append('Non-grabbing outside-click dismissal animates to compact')
assert not subprocess.check_output(['hyprctl','configerrors'],text=True).strip();results.append('Hyprland has no configuration errors')
report={'passed':results,'limitations':['Activity fixtures simulate media and install data; no package installation or audible playback','Focus retention checked with compositor address and keyboard-mode properties; physical typing must be checked by user'],'time':time.time()}
path=state.with_name('island-verification.json');path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

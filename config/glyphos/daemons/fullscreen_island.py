"""Swap the ordinary bars for an Island-only overlay in true fullscreen."""
from common import call,hypr
BARS=('top-bar','app-titlebar')
def is_fullscreen(client):return client.get('fullscreen')==2 or client.get('fullscreenClient')==2
class FullscreenIsland:
 def __init__(self):self.enabled=False;self.restore=set(BARS)
 def apply(self):
  active=hypr('activewindow');fullscreen=is_fullscreen(active)
  opened={line.split(':',1)[0] for line in call('eww','active-windows').splitlines() if ':' in line}
  if fullscreen:
   if not self.enabled:self.restore=opened.intersection(BARS);self.enabled=True
   if 'fullscreen-island' not in opened:call('eww','open','fullscreen-island',check=True)
   close=[name for name in BARS if name in opened]
   if close:call('eww','close',*close,check=False)
  elif self.enabled or 'fullscreen-island' in opened:
   for name in BARS:
    if name in self.restore and name not in opened:call('eww','open',name,check=True)
   if 'fullscreen-island' in opened:call('eww','close','fullscreen-island',check=False)
   self.enabled=False

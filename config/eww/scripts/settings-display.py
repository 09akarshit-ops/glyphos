#!/usr/bin/env python3
"""Validated Hyprland display controls and installed settings launchers."""
import json, subprocess, sys, shutil
from pathlib import Path

def run(*args):
 return subprocess.check_output(args,text=True,timeout=5).strip()
def monitors():
 try:return json.loads(run('hyprctl','monitors','-j'))
 except (OSError,ValueError,subprocess.SubprocessError):return []
def notify(text):subprocess.run(['notify-send','Glyph Control Center',text],timeout=3)
def state():
 rows=monitors();m=next((r for r in rows if r.get('focused')),rows[0] if rows else {})
 mode=f"{m.get('width',0)}x{m.get('height',0)}@{m.get('refreshRate',60):.2f}Hz"
 modes=list(dict.fromkeys([mode]+m.get('availableModes',[]))) if m else []
 return dict(scales=list(dict.fromkeys([f"{round(m.get('scale',1)*100)}%", "100%", "125%", "150%", "175%", "200%"])),scale=f"{round(m.get('scale',1)*100)}%",mode=mode,modes=modes,summary=' · '.join(r['name'] for r in rows)+' — '+str(len(rows))+' connected display'+('s' if len(rows)!=1 else ''))
def refresh():subprocess.run(['eww','--no-daemonize','update','settings-display='+json.dumps(state())],timeout=5)
def launch(candidates):
 for args in candidates:
  if shutil.which(args[0]):subprocess.Popen(args,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return
 notify('No compatible control panel is installed for this section.')
if __name__=='__main__':
 action=sys.argv[1] if len(sys.argv)>1 else 'state'
 if action=='state':print(json.dumps(state()))
 elif action in ('scale','mode'):
  rows=monitors();m=next((r for r in rows if r.get('focused')),rows[0] if rows else None)
  if not m:sys.exit(1)
  value=sys.argv[2];current=state()
  if action=='scale':
   if value not in ['100%','125%','150%','175%','200%']:sys.exit(2)
   scale=int(value[:-1])/100;mode=current['mode']
  else:
   if value not in current['modes']:sys.exit(2)
   scale=m['scale'];mode=value
  if scale != m['scale'] or mode != current['mode']:
   run('hyprctl','keyword','monitor',f"{m['name']},{mode},{m['x']}x{m['y']},{scale}")
  refresh()
 elif action=='graphics':notify('Graphics are managed by Hyprland. Blur and animations follow your active GlyphOS theme.')
 elif action=='advanced':launch([['nwg-displays'],['wdisplays']])
 elif action=='section':
  section=sys.argv[2]
  options={'Devices':[['blueman-manager'],['pavucontrol']], 'Network & Mesh':[['nm-connection-editor'],['kdeconnect-settings']], 'Apps':[[str(Path.home()/'.config/eww/scripts/app-store.py')]],'Accounts':[['gnome-control-center','user-accounts']], 'Time & Language':[['gnome-control-center','region']], 'Gaming':[['steam']], 'Accessibility':[['gnome-control-center','universal-access']], 'Privacy & Security':[['gnome-control-center','privacy']]}
  if section=='GLYPH Update':
   launch([['kitty','--title','GLYPH Update','sh','-c','pacman -Qu; printf "\\nReview the packages above. To install updates, run: sudo pacman -Syu\\n\\nPress Enter to close."; read answer']])
  elif section=='Personalization':
   if shutil.which('rofi'):
    choice=subprocess.run(['rofi','-dmenu','-p','GlyphOS Theme'],input='Light\nDark',text=True,capture_output=True,timeout=120).stdout.strip().lower()
    if choice in ('light','dark'):launch([[str(Path.home()/'.config/glyphos/scripts/theme.py'),choice]])
   else:notify('Install Rofi to use the theme chooser.')
  else:launch(options.get(section,[]))

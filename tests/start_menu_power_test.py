"""Power submenu toggles inline; no session or power commands are executed."""
import importlib.util
from pathlib import Path
path=Path(__file__).resolve().parents[1]/'config/eww/scripts/modal.py'
spec=importlib.util.spec_from_file_location('modal',path);modal=importlib.util.module_from_spec(spec);spec.loader.exec_module(modal)
opened={'app-launcher'};power_open=False;calls=[]
def eww(*args):
 global power_open
 calls.append(args)
 if args==('get','launcher-power-open'):return str(power_open).lower()
 if args[0]=='update':power_open=args[1].endswith('=true')
 if args[0]=='close':opened.difference_update(args[1:])
 if args[0]=='open':opened.add(args[1])
 return ''
modal.eww=eww;modal.active=lambda:set(opened)
modal.power();assert opened=={'app-launcher'} and power_open
modal.power();assert opened=={'app-launcher'} and not power_open
modal.power();modal.launcher_close();assert not opened and not power_open
modal.launcher_toggle();assert opened=={'app-launcher'} and not power_open
assert not any(c[0] in ('shutdown','reboot','logout') for c in calls)
print('PASS: inline power toggle, launcher persistence, closing/reset and reopening.')

"""System controls target Settings layers rather than the application underneath."""
import sys,importlib.util,copy
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'config/eww/scripts'))
p=root/'config/eww/scripts/window-management.py';spec=importlib.util.spec_from_file_location('wm',p);wm=importlib.util.module_from_spec(spec);spec.loader.exec_module(wm)
state={'desktop':{},'panels':{},'maximized':[]};calls=[]
layers={'LVDS-1':{'levels':{'3':[{'namespace':'glyphos-settings-app-max'}]}}}
def query(what):
 if what=='layers':return layers
 if what=='monitors':return [dict(width=1600,height=900,scale=1,focused=True,reserved=[0,96,0,0])]
 raise AssertionError('Underlying native client was queried: '+what)
wm.query=query;wm.run=lambda *args:calls.append(args);wm.load=lambda:copy.deepcopy(state)
wm.save=lambda value:state.update(value)
wm.dispatch=lambda *_:(_ for _ in ()).throw(AssertionError('Must never act on underlying app'))
wm.native('close','active');assert calls[-1]==('eww','--no-daemonize','close','settings-app-max')
wm.native('maximize','active');assert calls[-1]==('eww','--no-daemonize','open','settings-app')
wm.native('minimize','active');assert 'settings-app-max' in state['panels']
wm.panel('restore','settings-app-max');assert calls[-1][4:6]==('--size','1600x804')
print('PASS: system close/maximize/minimize route to Settings; restore respects taskbar bounds.')

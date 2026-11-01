"""Window/desktop matching fixtures; no live apps are launched."""
import importlib.util
from pathlib import Path
path=Path(__file__).resolve().parents[1]/'config/eww/scripts/dock-service.py'
spec=importlib.util.spec_from_file_location('dock',path);dock=importlib.util.module_from_spec(spec);spec.loader.exec_module(dock)
def entry(key):return next(i for i in dock.DEFAULTS if i['id']==key)
def client(cls,title='',mapped=True):return {'class':cls,'initialClass':cls,'title':title,'mapped':mapped}
clients=[client('brave-browser','WhatsApp'),client('brave-browser','Google Gemini'),client('spotify','Track'),client('org.glyphos.Files','Files')]
for key in ['chat','ai','music','files','photos']:assert dock.running(entry(key),clients),key
assert not dock.running(entry('browser'),clients),'Web apps must not claim a separate ordinary browser window'
assert dock.running(entry('browser'),clients+[client('brave-browser','Browser')])
assert not dock.running(entry('music'),[client('spotify',mapped=False)])
assert dock.running(entry('settings'),[],[{'namespace':'glyphos-settings-app-max'}])
assert not dock.running(entry('settings'),[],[])
custom={'id':'app-'+'a'*24,'desktop':'org.example.Editor.desktop'}
assert dock.running(custom,[client('Editor')],extra_classes=['Editor'])
assert not dock.running(custom,[client('Unrelated')],extra_classes=['Editor'])
print('PASS: running-app matching, separate browser web apps, layer Settings and custom desktop identities.')

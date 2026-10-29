import ast,re
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1]
source=(root/'config/glyphos/scripts/actions.py').read_text().replace("HOME/'.config/eww/eww.yuck'","CONFIG")
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='dismiss')
class Socket:
 def __enter__(self):return self
 def __exit__(self,*_):pass
 def sendto(self,*_):pass
socket=SimpleNamespace(socket=lambda *_:Socket(),AF_UNIX=1,SOCK_DGRAM=2)
base=__builtins__.__dict__.copy();original=base['__import__'];base['__import__']=lambda name,*args:socket if name=='socket' else original(name,*args)
closed=[];cursor={'x':950,'y':25}
layers={'monitor':{'levels':{'2':[{'namespace':'glyphos-top-bar','x':0,'y':0,'w':1000,'h':50}],'3':[{'namespace':'glyphos-wifi','x':600,'y':60,'w':340,'h':330}]}}}
ns={'CONFIG':root/'config/eww/eww.yuck','__builtins__':base,'Path':Path,'HOME':Path.home(),'os':SimpleNamespace(environ={'XDG_RUNTIME_DIR':'/tmp'}),'re':re,'hypr':lambda key:cursor if key=='cursorpos' else layers,'call':lambda *args,**kwargs:closed.append(args)}
exec(compile(ast.Module(body=[node],type_ignores=[]),'dismiss','exec'),ns)
ns['dismiss']();assert not closed,'Opening click dismissed its own menu'
cursor.update(x=700,y=150);ns['dismiss']();assert not closed,'Inside click dismissed menu'
cursor.update(x=100,y=500);ns['dismiss']();assert ('eww','close','wifi-menu') in closed
print('Opening taskbar click, inside click, and outside dismissal checks passed.')

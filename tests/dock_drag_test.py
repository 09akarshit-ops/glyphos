"""Dock geometry, ordering, click suppression and persistence without live apps."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('drag',Path(__file__).resolve().parents[1]/'config/eww/scripts/dock-drag.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
layer={'x':300,'y':772,'w':1000,'h':128}
assert d.hit({'x':338,'y':812},layer,5)==0
assert d.hit({'x':415,'y':812},layer,5)==1
assert d.hit({'x':399,'y':812},layer,5) is None
assert d.hit({'x':500,'y':600},layer,5,False) is None
rows=[{'id':k} for k in ['a','b','c','d']]
assert [r['id'] for r in d.reordered(rows,'a','c')]==['b','c','a','d']
assert [r['id'] for r in d.reordered(rows,'d','b')]==['a','d','b','c']
assert d.reordered(rows,'missing','a')==rows
assert [r['id'] for r in rows]==['a','b','c','d']
with TemporaryDirectory() as folder:
 root=Path(folder);d.RUNTIME=root;d.STATE=root/'drag.json';d.RELEASE=root/'release.json';d.PREFS=root/'prefs.json'
 d.write(d.PREFS,{'items':rows,'hidden':False,'color':'#123456'})
 cursor=iter([{'x':338,'y':812},{'x':500,'y':812}])
 def query(name):
  if name=='layers':return {'screen':{'levels':{'2':[dict(layer,namespace='glyphos-dock')]}}}
  return next(cursor)
 real_read=d.read
 def read(path,default):
  if path==d.RELEASE:return {'at':d.time.time()+1}
  return real_read(path,default)
 with patch.object(d,'query',side_effect=query),patch.object(d,'read',side_effect=read),patch.object(d,'feedback'):
  d.begin()
 result=real_read(d.PREFS,{})
 assert [r['id'] for r in result['items']]==['b','c','a','d']
 assert result['color']=='#123456'
 assert d.blocked('a') and not d.blocked('b')
 # Ordinary clicks never suppress launch.
 d.write(d.STATE,{'source':'a','dragged':False,'expires':d.time.time()+1})
 assert not d.blocked('a')
print('PASS: hit regions, both reorder directions, outside cancellation, persisted preferences and drag-only launch suppression')

"""Offline snap partition and hit-region checks; no compositor or desktop mutations."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'config/glyphos/scripts/snap_engine.py'
spec=importlib.util.spec_from_file_location('snap',path)
snap=importlib.util.module_from_spec(spec);spec.loader.exec_module(snap)
for rect in [(0,84,1600,816),(-1920,40,1920,1040),(0,50,1001,701)]:
 for preset in snap.PRESETS:
  slots=snap.cells(preset,rect)
  assert sum(w*h for x,y,w,h in slots)==rect[2]*rect[3]
  for zone in range(len(slots)):
   for count in [1,2,4,7]:
    windows=[{'address':hex(i+1),'focusHistoryID':i} for i in range(count)]
    result=snap.plan(preset,zone,rect,windows,'0x1')
    assert len(result)==count and result[0][1]==slots[zone]
    for i,(_, (x,y,w,h)) in enumerate(result):
     assert rect[0]<=x<x+w<=rect[0]+rect[2] and rect[1]<=y<y+h<=rect[1]+rect[3]
     for _,(x2,y2,w2,h2) in result[i+1:]:
      assert min(x+w,x2+w2)<=max(x,x2) or min(y+h,y2+h2)<=max(y,y2)
monitor={'x':0,'y':0,'width':1600,'height':900,'scale':1,'reserved':[0,84,0,0]}
assert snap.area(monitor)==(0,84,1600,816)
assert snap.area(dict(monitor,width=1800,height=3200,scale=2,transform=1))==(0,84,1600,816)
picker={'x':440,'y':96}
for i,(preset,regions) in enumerate(snap.PRESETS.items()):
 for zone,(a,b,c,d) in enumerate(regions):
  cursor={'x':picker['x']+27+i*174+(a+c/2)*138,'y':picker['y']+18+(b+d/2)*76}
  assert snap.hit(cursor,monitor,picker)==(preset,zone)
assert snap.hit({'x':0,'y':0},monitor,picker) is None
# Releasing outside every destination must not dispatch window changes.
engine=snap.Engine(lambda *args:None);engine.open=True;engine.picker=picker
engine.drag={'monitor':monitor,'window':{'address':'0x1'}}
with patch.object(snap,'query',return_value={'x':0,'y':0}),patch.object(snap,'ipc') as ipc,patch.object(snap,'run'):
 engine.release();ipc.assert_not_called();assert engine.drag is None
print('PASS: exact partitions, no overlaps, scaled/rotated monitors, all hover regions and outside-drop cancellation.')

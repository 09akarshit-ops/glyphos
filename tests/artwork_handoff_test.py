"""Deterministic artwork handoff tests; no live players, network or image decoding."""
import importlib.util
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'config/eww/scripts/island-art.py'
spec=importlib.util.spec_from_file_location('island_art',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Future:
 def __init__(self):self.value=None
 def done(self):return self.value is not None
 def result(self):return self.value
jobs=[]
def submit(state):
 future=Future();jobs.append((state,future));return future
presenter=module.ArtworkPresenter(submit)
def state(title):return dict(url=title,title=title,artist='Artist',art='',status='Playing',updated=100)
def tick(title,now):return presenter.tick(state(title),now=now,wall=100)
tick('A',0);jobs[-1][1].value=('/tmp/a.jpg','/tmp/a-blur.jpg');a=tick('A',.2)
assert a['art']=='/tmp/a.jpg' and a['dock']
b=tick('B',1);assert b['dock']==a['dock'] and b['art']==a['art'],'Track handoff must retain the current image'
jobs[-1][1].value=('/tmp/b.jpg','');b=tick('B',1.2)
assert b['art']=='/tmp/b.jpg' and b['dock']==a['dock'],'Temporary blur failure must keep the previous blur'
count=len(jobs);tick('B',3.3);assert len(jobs)==count+1,'Blur must retry even with a sharp cover'
jobs[-1][1].value=('/tmp/b.jpg','/tmp/b-blur.jpg');b=tick('B',3.5);assert 'b-blur.jpg' in b['dock']
tick('C',4);count=len(jobs);tick('D',4.1);assert len(jobs)==count,'Only one resolver job may be in flight'
jobs[-1][1].value=('/tmp/c.jpg','/tmp/c-blur.jpg');d=tick('D',4.2);assert 'c-blur.jpg' not in d['dock'],'Stale result must not replace the current artwork'
assert jobs[-1][0]['title']=='D'
jobs[-1][1].value=('/tmp/d.jpg','/tmp/d-blur.jpg');d=tick('D',4.4)
assert presenter.tick({},now=5,wall=100)['dock']==d['dock'],'Brief metadata gaps must not clear the dock'
assert presenter.tick({},now=7.1,wall=100)['dock']=='','Actual stop must restore the fallback'
print('PASS: seamless handoff, blur retry, stale result rejection, bounded jobs and stop fallback.')

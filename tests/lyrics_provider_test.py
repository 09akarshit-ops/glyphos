import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config/glyphos/scripts'))
import lyrics as m
from unittest.mock import patch
import lyrics_web
# Provider fixtures must never make live web requests.
_original_lookup = m.lookup
def offline_lookup(*args, **kwargs):
 with patch.object(lyrics_web, "web_lyrics", return_value=("", "")):
  return _original_lookup(*args, **kwargs)
m.lookup = offline_lookup

def record(id=1,title='Hello',artist='Adele',raw='[00:01]First\n[00:02]Second',plain=''):
 return dict(id=id,trackName=title,artistName=artist,duration=10,syncedLyrics=raw,plainLyrics=plain)

def check(name,lr,ne,expected,key=('Helo','Adele','',10,'')):
 with tempfile.TemporaryDirectory() as d,patch.object(m,'CACHE',Path(d)),patch.object(m,'request',side_effect=lr),patch.object(m,'netease_request',side_effect=ne):
  found=m.lookup(key)
  assert found['mode']==expected[0] and found['source'].startswith(expected[1]),found
  assert found['rows'],found
  print(name+': PASS')

def unavailable(*args,**kwargs):raise OSError('Provider unavailable')
def fuzzy(path,params,*args):
 if path=='get':raise OSError('404')
 assert 'q' in params
 return [record(2,'Unrelated','Different'),record(1)]
check('404 to ranked q search; misspelling recovered; unrelated result rejected',fuzzy,unavailable,('synced','LRCLIB:1'))

def lrplain(path,params,*args):return record(raw='',plain='First\nSecond') if path=='get' else [record(raw='',plain='First\nSecond')]
def nesync(path,params,*args,**kwargs):
 if path.startswith('search'):
  return {'result':{'songs':[{'id':7,'name':'Hello','artists':[{'name':'Adele'}],'duration':10000}]}}
 return {'lrc':{'lyric':'[00:01]First\n[00:02]Second'}}
check('NetEase timed result beats LRCLIB plain result',lrplain,nesync,('synced','NetEase:7'),('Hello','Adele','',10,''))
check('Plain lyrics retained after provider failure',lrplain,unavailable,('plain','LRCLIB'),('Hello','Adele','',10,''))
def neplain(path,params,*args,**kwargs):
 if path.startswith('search'):return nesync(path,params,*args,**kwargs)
 return {'lrc':{'lyric':'First\nSecond'}}
check('NetEase plain-only duration fallback',unavailable,neplain,('plain','NetEase'),('Hello','Adele','',10,''))
with tempfile.TemporaryDirectory() as d,patch.object(m,'CACHE',Path(d)/'cache'),patch.object(m,'request',side_effect=unavailable),patch.object(m,'netease_request',side_effect=unavailable):
 audio=Path(d)/'Artist - Song.mp3';audio.touch();audio.with_suffix('.txt').write_text('First\nSecond')
 found=m.lookup(('Song','Artist','',8,audio.as_uri()))
 assert found['mode']=='plain' and found['rows']==[(0.,'First'),(4.,'Second')]
 print('Local plain text survives all provider failures: PASS')
for raw in ['Artist feat. Guest - Song Title','Artist - Song Title (Prod. by Producer)','Song Title | Artist [4K]']:
 found=m.normalize(raw)
 assert (found['title'],found['artist'])==('Song Title','Artist'),found
print('Feature credits, production credits, pipe delimiters: PASS')

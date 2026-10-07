#!/usr/bin/env python3
"""Resolve artwork for any MPRIS player in a worker; lyric rendering never waits for network."""
import concurrent.futures,hashlib,json,subprocess,time,sys,re
from pathlib import Path
from urllib.parse import urlparse,unquote,urlencode
from urllib.request import Request,urlopen
HOME=Path.home();CACHE=HOME/'.cache/glyphos/island-art';CACHE.mkdir(parents=True,exist_ok=True)
POOL=concurrent.futures.ThreadPoolExecutor(max_workers=1)
def valid_image(path):
 try:
  import gi;gi.require_version('GdkPixbuf','2.0')
  from gi.repository import GdkPixbuf
  info=GdkPixbuf.Pixbuf.get_file_info(str(path))
  return bool(info[0] and 0<info[1]<=16384 and 0<info[2]<=16384 and info[0].get_name()!='svg')
 except (OSError,ValueError):return False

def download(url,target):
 if urlparse(url).scheme not in ('https','http'):return ''
 temporary=target.with_name(target.name+'.download')
 try:
  with urlopen(Request(url,headers={'User-Agent':'GlyphOS/1.0'}),timeout=5) as response:
   if urlparse(response.geturl()).scheme not in ('http','https'):return ''
   data=response.read(4_000_001)
  if not data or len(data)>4_000_000:return ''
  temporary.write_bytes(data)
  if not valid_image(temporary):return ''
  temporary.replace(target);return str(target)
 except Exception:return ''
 finally:temporary.unlink(missing_ok=True)

def fetch(state):
 parsed=urlparse(state.get('url',''));path=Path(unquote(parsed.path)) if parsed.scheme=='file' else None
 identity=str(path) if path else json.dumps([state.get(k,'') for k in ('url','title','artist','art')])
 key=hashlib.sha256(identity.encode()).hexdigest();target=CACHE/(key+'.jpg')
 # Player-supplied artwork is preferred: Spotify covers and browser thumbnails.
 art=state.get('art','');art_uri=urlparse(art)
 if art_uri.scheme=='file':
  cover=Path(unquote(art_uri.path))
  if cover.is_file() and valid_image(cover):return str(cover)
 if target.exists() and valid_image(target):return str(target)
 if art_uri.scheme in ('http','https'):
  cover=download(art,target)
  if cover:return cover
 temp=CACHE/(key+'.tmp.jpg')
 try:
  if path and path.is_file():
   r=subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-map','0:v:0','-frames:v','1','-y',str(temp)],capture_output=True,timeout=6)
   if r.returncode==0 and temp.exists() and valid_image(temp):temp.replace(target);return str(target)
   for name in [path.with_suffix('.jpg'),path.with_suffix('.png'),path.parent/'cover.jpg',path.parent/'folder.jpg']:
    if name.is_file() and valid_image(name):return str(name)
  title=state.get('title','');artist=state.get('artist','')
  if not title or not artist:return ''
  query=(artist+' '+title).strip()
  sys.path.insert(0,str(HOME/'.config/glyphos/scripts'));from lyrics import similarity
  requests=[('itunes', 'https://itunes.apple.com/search?'+urlencode({'term':query,'entity':'song','limit':25})),
            ('itunes', 'https://itunes.apple.com/search?'+urlencode({'term':query,'entity':'song','limit':25,'country':'IN'})),
            ('deezer', 'https://api.deezer.com/search?'+urlencode({'q':query,'limit':25}))]
  for provider,address in requests:
   try:
    with urlopen(address,timeout=5) as response:payload=json.load(response)
    rows=payload.get('results',[]) if provider=='itunes' else [dict(trackName=r.get('title',''),artistName=r.get('artist',{}).get('name',''),artworkUrl100=r.get('album',{}).get('cover_big','')) for r in payload.get('data',[])]
    rows=[r for r in rows if similarity(title,r.get('trackName',''))>=.65 and similarity(artist,r.get('artistName',''))>=.5]
    if not rows:continue
    row=max(rows,key=lambda r:similarity(title,r.get('trackName',''))+similarity(artist,r.get('artistName','')))
    cover=download(row.get('artworkUrl100','').replace('100x100bb','600x600bb'),target)
    if cover:return cover
   except Exception:continue
  return ''

 except Exception:return ''
 finally:temp.unlink(missing_ok=True)

def style(path):
 if not path:return 'background-color:#000000; background-image:none;'
 return 'background-color:#000000; background-image:linear-gradient(rgba(0,0,0,0.10),rgba(0,0,0,0.10)),url("'+Path(path).as_uri()+'");'
if __name__=='__main__':
 if '--prepare' in sys.argv:
  sys.path.insert(0,str(HOME/'.config/glyphos/scripts'));from lyrics import normalize
  paths=[p for p in (HOME/'Music').iterdir() if p.suffix.lower() in ('.mp3','.flac','.m4a','.ogg','.wav')]
  def prepare(path):
   try:
    raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format_tags=title,artist,album','-of','json',str(path)],timeout=4,text=True)
    tags=json.loads(raw).get('format',{}).get('tags',{})
    state=normalize(tags.get('title',path.stem),tags.get('artist',''),tags.get('album',''),path.as_uri())
    state['title']=re.sub(r'(?i)\bOfficial\s+(?:Music\s+)?(?:Video|Audio)\b','',state['title']).strip()
    return bool(fetch(state))
   except Exception:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   results=list(pool.map(prepare,paths))
  print(json.dumps({'tracks_checked':len(paths),'artwork_available':sum(results),'black_fallback':len(paths)-sum(results)}),flush=True)
  raise SystemExit(0)
 previous=None;key=None;future=None;pane=0;styles=[style(''),style('')];shown='';retry_at=0
 while True:
  try:state=json.loads((HOME/'.local/state/glyphos/island-media.json').read_text())
  except (OSError,ValueError):state={}
  current=(state.get('url',''),state.get('title',''),state.get('artist',''),state.get('art','')) if state.get('status') in ('Playing','Paused') and time.time()-state.get('updated',0)<5 else None
  if current!=key:
   key=current;future=POOL.submit(fetch,dict(state)) if current else None;retry_at=time.monotonic()+30
   if shown:shown='';pane=1-pane;styles[pane]=style('')
  if current and not shown and future is None and time.monotonic()>=retry_at:
   future=POOL.submit(fetch,dict(state));retry_at=time.monotonic()+30
  if future and future.done():
   path=future.result();future=None
   if path!=shown:shown=path;pane=1-pane;styles[pane]=style(path)
  output=json.dumps(dict(a=styles[0],b=styles[1],pane=pane,art=shown))
  if output!=previous:
   snapshot=HOME/'.local/state/glyphos/island-art.json';tmp=snapshot.with_suffix('.tmp');tmp.write_text(output);tmp.replace(snapshot)
   print(output,flush=True);previous=output
  time.sleep(.2)

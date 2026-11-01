#!/usr/bin/env python3
"""Resolve artwork for any MPRIS player in a worker; lyric rendering never waits for network."""
import concurrent.futures,hashlib,json,subprocess,time,sys,re
from pathlib import Path
from urllib.parse import urlparse,unquote,urlencode
from urllib.request import Request,urlopen
HOME=Path.home();CACHE=HOME/'.cache/glyphos/island-art';CACHE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'glyphos/scripts'))
from media_policy import excluded_media
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
 if excluded_media(state.get('player',''),state):return ''
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
    def score(row):
     pairs=[(title,artist)]
     # Untagged local downloads can use either Artist - Song or Song - Artist.
     if path:pairs.append((artist,title))
     scores=[]
     for track,performer in pairs:
      ts=similarity(track,row.get('trackName',''));ars=similarity(performer,row.get('artistName',''))
      if ts>=.65 and ars>=.5:scores.append(ts+ars)
     return max(scores,default=0)
    rows=[r for r in rows if score(r)>0]
    if not rows:continue
    row=max(rows,key=score)
    cover=download(row.get('artworkUrl100','').replace('100x100bb','600x600bb'),target)
    if cover:return cover
   except Exception:continue
  return ''

 except Exception:return ''
 finally:temp.unlink(missing_ok=True)

def blurred_cover(path):
 if not path:return ''
 try:
  source=Path(path);info=source.stat()
  key=hashlib.sha256((str(source)+str(info.st_mtime_ns)+str(info.st_size)+'dock-blur-v1').encode()).hexdigest()
  target=CACHE/(key+'.dock.jpg')
  if target.exists() and valid_image(target):return str(target)
  temporary=target.with_name(target.stem+'.tmp.jpg')
  try:
   # Prefer bounded in-process work; spawning FFmpeg can exceed its timeout on a busy desktop.
   try:
    from PIL import Image,ImageOps,ImageFilter
    with Image.open(source) as image:
     if image.width*image.height>32_000_000:return ''
     image=ImageOps.fit(image.convert('RGB'),(256,256)).filter(ImageFilter.GaussianBlur(14))
     image.save(temporary,'JPEG',quality=88)
    temporary.replace(target);return str(target)
   except (ImportError,OSError,ValueError):pass
   result=subprocess.run(['ffmpeg','-v','error','-nostdin','-threads','1','-filter_threads','1','-i',str(source),'-vf','scale=256:256:force_original_aspect_ratio=increase,crop=256:256,gblur=sigma=14','-frames:v','1','-y',str(temporary)],capture_output=True,timeout=8)
   if result.returncode==0 and valid_image(temporary):temporary.replace(target);return str(target)
  finally:temporary.unlink(missing_ok=True)
 except (OSError,subprocess.SubprocessError):pass
 return ''
def resolve(state):
 cover=fetch(state)
 return cover,blurred_cover(cover)
def dock_style(path):
 if not path:return ''
 return 'background-color:#e9e9e4; background-image:linear-gradient(rgba(0,0,0,0.22),rgba(0,0,0,0.22)),url("'+Path(path).as_uri()+'");'

def style(path):
 if not path:return 'background-color:#181a1d; background-image:linear-gradient(135deg,#263e59,#181a1d);'
 return 'background-color:#181a1d; background-image:linear-gradient(rgba(0,0,0,0.10),rgba(0,0,0,0.10)),url("'+Path(path).as_uri()+'");'
class ArtworkPresenter:
 """Keep the last good cover during handoff; one worker and explicit blur retries."""
 def __init__(self,submit):
  self.submit=submit;self.key=None;self.state={};self.future=None;self.job_key=None
  self.resolved_key=None;self.blur_key=None;self.shown='';self.dock='';self.pane=0
  self.styles=[style(''),style('')];self.retry_at=0;self.changed=0;self.inactive_at=None
 def tick(self,state,now=None,wall=None):
  now=time.monotonic() if now is None else now;wall=time.time() if wall is None else wall
  excluded=excluded_media(state.get('player',''),state)
  current=tuple(state.get(k,'') for k in ('url','title','artist','art')) if not excluded and state.get('status') in ('Playing','Paused') and wall-state.get('updated',0)<15 else None
  if excluded:self.inactive_at=now-2
  if current is None:
   if self.inactive_at is None:self.inactive_at=now
   if now-self.inactive_at<2:current=self.key
  else:self.inactive_at=None
  if current!=self.key:
   self.key=current;self.changed=now;self.retry_at=now
   if current:self.state=dict(state)
   else:
    self.shown='';self.dock='';self.pane=1-self.pane;self.styles[self.pane]=style('')
    self.resolved_key=None;self.blur_key=None
  if self.future and self.future.done():
   try:path,blurred=self.future.result()
   except Exception:path,blurred='',''
   self.future=None
   if self.job_key==self.key and self.key is not None:
    if path:
     self.resolved_key=self.key
     if path!=self.shown:self.shown=path;self.pane=1-self.pane;self.styles[self.pane]=style(path)
    if blurred:self.dock=dock_style(blurred);self.blur_key=self.key
    self.retry_at=now+(2 if path and not blurred else 5)
  # A missing blur must retry even when a sharp cover is already available.
  if self.key is not None and self.future is None and now>=self.retry_at and (self.resolved_key!=self.key or self.blur_key!=self.key):
   self.job_key=self.key;self.future=self.submit(dict(self.state))
  if self.key is not None and now-self.changed>30:
   if self.resolved_key!=self.key and self.shown:self.shown='';self.pane=1-self.pane;self.styles[self.pane]=style('')
   if self.blur_key!=self.key:self.dock=''
  return dict(a=self.styles[0],b=self.styles[1],pane=self.pane,art=self.shown,dock=self.dock)

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
 previous=None;presenter=ArtworkPresenter(lambda state:POOL.submit(resolve,state))
 while True:
  try:state=json.loads((HOME/'.local/state/glyphos/island-media.json').read_text())
  except (OSError,ValueError):state={}
  output=json.dumps(presenter.tick(state))
  if output!=previous:
   snapshot=HOME/'.local/state/glyphos/island-art.json';tmp=snapshot.with_suffix('.tmp');tmp.write_text(output);tmp.replace(snapshot)
   print(output,flush=True);previous=output
  time.sleep(.2)

import sys,json,tempfile,time,importlib.util
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config/glyphos/scripts'))
import lyrics as m
import lyrics_web as web
html='<nav>Not lyrics</nav><div data-lyrics-container="true"><div class="LyricsHeader">Header</div>First test line<br/>Second <a>test</a> line<button>Not lyrics</button></div><div data-lyrics-container="true">Third test line<script>Ignored</script></div>'
p=web.LyricsHTML();p.feed(html);plain=''.join(p.parts)
assert 'First test line' in plain and 'Second test line' in plain and 'Third test line' in plain
assert 'Not lyrics' not in plain and 'Ignored' not in plain and 'Header' not in plain
print('HTML lyric-only extraction and line breaks: PASS')

def fail(*args,**kwargs):raise OSError('Provider unavailable')
def genius(url,deadline):
 if '/api/search/multi?' in url:
  return json.dumps({'response':{'sections':[{'hits':[{'result':{'title':'Song','primary_artist':{'name':'Artist'},'url':'https://genius.com/Artist-song-lyrics'}}]}]}})
 if url=='https://genius.com/Artist-song-lyrics':return html
 raise AssertionError(url)
with tempfile.TemporaryDirectory() as folder,patch.object(m,'CACHE',Path(folder)),patch.object(m,'request',side_effect=fail),patch.object(m,'netease_request',side_effect=fail),patch.object(web,'fetch',side_effect=genius):
 found=m.lookup(('Song','Artist','',9,''))
 assert found['mode']=='plain' and found['source'].startswith('Genius:')
 assert len(found['rows'])==3 and found['rows'][1][0]==3
 print('Genius fallback after timed-provider failures; estimated duration scrolling: PASS')

def google(url,deadline):
 if '/api/search/multi?' in url:raise OSError('Public search unavailable')
 if 'google.com/search?' in url:return '<a href="/url?q=https%3A%2F%2Fgenius.com%2FArtist-song-lyrics">song</a><a href="https://example.com/lyrics">ignore</a>'
 if url=='https://genius.com/Artist-song-lyrics':return html
 raise AssertionError(url)
with patch.object(web,'fetch',side_effect=google):
 plain,source=web.web_lyrics('Song','Artist',9,time.monotonic()+10,m.ranked)
 assert 'First test line' in plain and source.startswith('Genius:')
 print('Google link discovery; actual lyric page fetched instead of search snippets: PASS')
with tempfile.TemporaryDirectory() as folder,patch.object(m,'CACHE',Path(folder)),patch.object(m,'request',side_effect=fail),patch.object(m,'netease_request',side_effect=fail),patch.object(web,'fetch',side_effect=fail):
 found=m.lookup(('Missing Song','Unknown','',60,''))
 assert found['mode']=='none' and not found['rows']
 print('All providers unavailable: bounded, safe result for marquee/retry: PASS')
spec=importlib.util.spec_from_file_location('island',str(Path(__file__).resolve().parents[1]/'config/eww/scripts/island-lyrics.py'));island=importlib.util.module_from_spec(spec);spec.loader.exec_module(island)
title='A long track title with artist information that exceeds the pill width'
assert island.scroll_text(title,0)!=island.scroll_text(title,5)
assert len(island.scroll_text(title,5))==32
assert m.normalize('Artist - Song Audio 320kbps.mp3 [Official HD]')['title']=='Song'
print('Fallback marquee movement and additional noise cleanup: PASS')

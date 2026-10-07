import base64,importlib.util,json,tempfile
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('island_art',Path(__file__).resolve().parents[1]/'config/eww/scripts/island-art.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Real PNG bytes let the image validator run without showing a window.
import gi;gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf
pix=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,True,8,2,2);pix.fill(0x556677ff)
success,data=pix.save_to_bufferv('png',[],[]);assert success

class Response:
 def __enter__(self):return self
 def __exit__(self,*_):pass
 def read(self,*_):return data
 def geturl(self):return 'https://i.scdn.co/image/test'
with tempfile.TemporaryDirectory() as folder,patch.object(m,'CACHE',Path(folder)):
 spotify=dict(url='spotify:track:test',title='Song',artist='Artist',art='https://i.scdn.co/image/test')
 with patch.object(m,'urlopen',return_value=Response()) as network:
  first=m.fetch(spotify);assert first and Path(first).is_file();assert m.valid_image(first)
  assert m.fetch(spotify)==first;assert network.call_count==1
 browser=dict(url='https://youtube.com/watch?v=test',title='Song',artist='Artist',art='https://example.com/thumb.png')
 with patch.object(m,'urlopen',return_value=Response()):assert m.fetch(browser)
 cover=Path(folder)/'local.png';cover.write_bytes(data)
 assert m.fetch(dict(url='nonfile:track',art=cover.as_uri()))==str(cover)
 assert m.fetch(dict(url='spotify:track:no-art'))==''
 assert 'background-image:none' in m.style('')
 with patch.object(m,'urlopen',side_effect=OSError('offline')):assert m.fetch(dict(url='spotify:track:offline',art='https://example.com/offline'))==''
print('Passed Spotify/browser artwork, local art URI, cache reuse, missing-art and offline fallback checks.')

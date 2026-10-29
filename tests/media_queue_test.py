"""Fake MPRIS calls only: never connect to a live player."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config/glyphos/scripts'))
from media_queue import Backend,TRACKLIST,PLAYER
NAME='org.mpris.MediaPlayer2.vlc';ids=['/track/one','/track/two','/track/three'];calls=[]
def fake(name,interface,method,args):
 calls.append((name,interface,method,args.unpack()))
 if method=='Get':
  iface,key=args.unpack()
  return ({'Tracks':ids,'Metadata':{'mpris:trackid':ids[1]},'Shuffle':False}[key],)
 if method=='GetTracksMetadata':return ([{'xesam:title':'Track '+str(ids.index(i)+1),'xesam:artist':['Artist']} for i in args.unpack()[0]],)
 if method=='GoTo':return ()
 raise AssertionError(method)
backend=Backend(call=fake,active=lambda:NAME)
snapshot=backend.snapshot();assert [r['id'] for r in snapshot['rows']]==ids[1:];assert snapshot['rows'][0]['current']
assert not any(c[2]=='GoTo' for c in calls)
backend.select(NAME,ids[2]);assert calls[-1][2:] == ('GoTo',(ids[2],))
for name,track in [('org.mpris.MediaPlayer2.spotify',ids[1]),(NAME,'/missing')]:
 try:backend.select(name,track);raise AssertionError('Selection should fail')
 except ValueError:pass
unsupported=Backend(call=lambda *_:(_ for _ in ()).throw(AssertionError('No Spotify calls')),active=lambda:'org.mpris.MediaPlayer2.spotify').snapshot()
assert not unsupported['rows'] and 'deferred' in unsupported['message']
print('Queue order, selection, stale entry/player guards and Spotify deferral passed (mocked).')

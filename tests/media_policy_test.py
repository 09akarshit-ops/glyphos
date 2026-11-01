"""Social/video exclusions must never start lyric/artwork work or hide real music."""
import sys,importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'config/glyphos/scripts'))
from media_policy import excluded_media,eligible_candidates
for url in ['https://www.youtube.com/watch?v=123','https://youtu.be/123','https://m.youtube.com/shorts/123','https://music.youtube.com/watch?v=123','https://www.instagram.com/reel/123','https://instagram.com/p/123']:
 assert excluded_media('org.mpris.MediaPlayer2.chromium',{'xesam:url':url}),url
assert excluded_media('org.mpris.MediaPlayer2.firefox',{'mpris:artUrl':'https://i.ytimg.com/vi/id/default.jpg'})
assert excluded_media('org.mpris.MediaPlayer2.chromium',{'mpris:artUrl':'https://scontent.cdninstagram.com/image.jpg'})
assert excluded_media('org.mpris.MediaPlayer2.brave.instance2730',{'xesam:url':'','mpris:artUrl':'file:///tmp/.org.chromium.Chromium.icon','xesam:title':'YouTube'})
assert not excluded_media('org.mpris.MediaPlayer2.brave',{'xesam:url':'https://open.spotify.com/track/id','mpris:artUrl':'file:///tmp/cover'})
for player,meta in [('vlc',{'url':'file:///Music/YouTube Song.mp3'}),('spotify',{'url':'https://open.spotify.com/track/id','art':'https://i.scdn.co/image/id'}),('chromium',{'url':'https://youtube.com.example.org/video'})]:
 assert not excluded_media(player,meta),(player,meta)
def candidate(name,url,status='Playing'):return (name,{'PlaybackStatus':status,'Metadata':{'xesam:url':url}},0)
youtube=candidate('chromium','https://youtube.com/watch?v=123')
spotify=candidate('spotify','https://open.spotify.com/track/id');paused=candidate('spotify',spotify[1]['Metadata']['xesam:url'],'Paused')
assert eligible_candidates([youtube])==[]
assert eligible_candidates([youtube,paused])==[]
assert eligible_candidates([youtube,spotify])==[spotify]
assert eligible_candidates([paused])==[paused]
spec=importlib.util.spec_from_file_location('art',root/'config/eww/scripts/island-art.py');art=importlib.util.module_from_spec(spec);spec.loader.exec_module(art)
blocked={'player':'chromium','url':'https://youtube.com/watch?v=123','status':'Playing','updated':100}
assert art.fetch(blocked)=='','Excluded artwork must return before network or image work'
presenter=art.ArtworkPresenter(lambda *_:(_ for _ in ()).throw(AssertionError('Excluded video submitted to artwork worker')))
assert presenter.tick(blocked,now=0,wall=100)['dock']==''
print('PASS: YouTube/Instagram URL and thumbnail exclusions, music preservation, paused fallback and no artwork jobs.')

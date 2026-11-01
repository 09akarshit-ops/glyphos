"""Keep social/video browser playback out of desktop music surfaces."""
from urllib.parse import urlparse
SITES=('youtube.com','youtu.be','youtube-nocookie.com','instagram.com')
VIDEO_ART=('ytimg.com','googlevideo.com','cdninstagram.com','instagram.com')
def host(value):
 try:return (urlparse(str(value or '')).hostname or '').lower().rstrip('.')
 except ValueError:return ''
def matches(name,domains):return any(name==domain or name.endswith('.'+domain) for domain in domains)
def excluded_media(player,metadata):
 url=metadata.get('xesam:url',metadata.get('url',''))
 if matches(host(url),SITES):return True
 # Chromium/Firefox may omit the page URL but still expose its video thumbnail.
 browser=any(token in str(player).lower() for token in ('chromium','chrome','brave','firefox'))
 # Unknown browser origins can be social video plus a browser favicon. Fail closed.
 if browser and not host(url):return True
 art=metadata.get('mpris:artUrl',metadata.get('art',''))
 return browser and matches(host(art),VIDEO_ART)
def eligible_candidates(candidates,preferred=''):
 ignored_playing=any(props.get('PlaybackStatus')=='Playing' and excluded_media(name,props.get('Metadata',{})) for name,props,_ in candidates)
 allowed=[row for row in candidates if not excluded_media(row[0],row[1].get('Metadata',{}))]
 if ignored_playing:allowed=[row for row in allowed if row[1].get('PlaybackStatus')=='Playing']
 return sorted(allowed,key=lambda row:(row[1].get('PlaybackStatus')!='Playing',row[0]!=preferred))

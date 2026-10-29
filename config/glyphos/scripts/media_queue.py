#!/usr/bin/env python3
"""VLC's real MPRIS playlist. No directory guessing or playback during refresh."""
import json,time
from pathlib import Path
from urllib.parse import unquote,urlparse
from gi.repository import Gio,GLib
PREFIX='org.mpris.MediaPlayer2.'
TRACKLIST=PREFIX+'TrackList'
PLAYER=PREFIX+'Player'
OBJECT='/org/mpris/MediaPlayer2'

def active_player():
 try:
  state=json.loads((Path.home()/'.local/state/glyphos/island-media.json').read_text())
 except (OSError,ValueError):return ''
 if time.time()-state.get('updated',0)>10 or state.get('status') not in ('Playing','Paused'):return ''
 name=state.get('player','')
 return name if name.startswith(PREFIX) else PREFIX+name if name else ''

class Backend:
 def __init__(self,call=None,active=None):self._call=call or self.dbus;self.active=active or active_player;self.bus=None
 def dbus(self,name,interface,method,args):
  if self.bus is None:self.bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
  return self.bus.call_sync(name,OBJECT,interface,method,args,None,Gio.DBusCallFlags.NONE,2500,None).unpack()
 def get(self,name,interface,key):
  value=self._call(name,'org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',(interface,key)))[0]
  return value.unpack() if isinstance(value,GLib.Variant) else value
 def snapshot(self):
  name=self.active()
  if not name:return dict(player='',rows=[],message='No active media player.')
  if not name.removeprefix(PREFIX).lower().startswith('vlc'):return dict(player=name,rows=[],message='Queue currently supports VLC. Spotify queue support is deferred.')
  tracks=list(self.get(name,TRACKLIST,'Tracks'))
  metadata=self.get(name,PLAYER,'Metadata');current=metadata.get('mpris:trackid','')
  current=current.unpack() if isinstance(current,GLib.Variant) else current
  shuffle=bool(self.get(name,PLAYER,'Shuffle'))
  # Retain the player-provided order; a shuffled future order is not exposed by MPRIS.
  start=tracks.index(current) if current in tracks else 0
  visible=tracks[start:start+200]
  rows=[]
  for offset in range(0,len(visible),40):
   batch=visible[offset:offset+40]
   metas=self._call(name,TRACKLIST,'GetTracksMetadata',GLib.Variant('(ao)',(batch,)))[0]
   for track,meta in zip(batch,metas):
    meta={k:v.unpack() if isinstance(v,GLib.Variant) else v for k,v in meta.items()}
    title=meta.get('xesam:title') or Path(unquote(urlparse(meta.get('xesam:url','')).path)).name or 'Untitled track'
    artist=meta.get('xesam:artist',[])
    rows.append(dict(id=track,title=title,artist=', '.join(artist) if isinstance(artist,(list,tuple)) else str(artist),current=track==current))
  return dict(player=name,rows=rows,message='Shuffle is on · playlist order shown' if shuffle else ('Now playing and up next' if rows else 'VLC playlist is empty.'))
 def select(self,name,track):
  if self.active()!=name:raise ValueError('The active player changed. Refresh the queue.')
  if track not in self.get(name,TRACKLIST,'Tracks'):raise ValueError('This track is no longer in VLC’s playlist.')
  self._call(name,TRACKLIST,'GoTo',GLib.Variant('(o)',(track,)))

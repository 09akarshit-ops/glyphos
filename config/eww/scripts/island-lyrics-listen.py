#!/usr/bin/env python3
"""Read lyric state; animate only the short handoff, never playback position."""
import json,time
from functools import lru_cache
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo
layout=Pango.Layout.new(PangoCairo.FontMap.get_default().create_context())
layout.set_font_description(Pango.FontDescription("Roboto Semi-Bold 18px"))

@lru_cache(maxsize=512)
def fit_line(text):
 text=str(text).replace("\n", " ")
 def width(value):
  layout.set_text(value,-1)
  return layout.get_pixel_size()[0]
 if width(text)<=360:return text
 lo,hi=0,len(text)
 while lo<hi:
  mid=(lo+hi+1)//2
  if width(text[:mid]+"…")<=360:lo=mid
  else:hi=mid-1
 return text[:lo].rstrip()+"…"

from pathlib import Path
from lyric_animation import transition,frame,settled,identity
path=Path.home()/'.local/state/glyphos/island-render.json'
previous_raw=None;previous_output=None;state=None;change=None;started=0
while True:
 try:
  raw=path.read_text()
  if raw!=previous_raw:
   incoming=json.loads(raw)
   if state is None or identity(incoming)!=identity(state) or incoming.get('marquee')!=state.get('marquee'):
    change=transition(state,incoming);started=time.monotonic()
   state=incoming;previous_raw=raw
  if state:
   output=dict(state);output.pop('lyrics',None);output.update(frame(change,time.monotonic()-started) if change else settled())
   if change and not output['lyric_animating']:change=None;output.update(settled())
   for field in ("active", "next", "lyric_old", "lyric_promoted"):
    if field in output:output[field]=fit_line(output[field])
   encoded=json.dumps(output,ensure_ascii=False)
   if encoded!=previous_output:print(encoded,flush=True);previous_output=encoded
 except (OSError,ValueError):pass
 except (BrokenPipeError,KeyboardInterrupt):break
 time.sleep(1/60 if change else .05)

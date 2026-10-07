#!/usr/bin/env python3
"""Read lyric state; animate only the short handoff, never playback position."""
import json,time
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
   encoded=json.dumps(output,ensure_ascii=False)
   if encoded!=previous_output:print(encoded,flush=True);previous_output=encoded
 except (OSError,ValueError):pass
 except (BrokenPipeError,KeyboardInterrupt):break
 time.sleep(1/60 if change else .05)

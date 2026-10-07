"""Offline fullscreen routing regression checks."""
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'config/glyphos/daemons'),str(ROOT/'config/glyphos/scripts')]
import fullscreen_island as f
router=f.FullscreenIsland()
with patch.object(f,'hypr',return_value={'fullscreen':2}),patch.object(f,'call',side_effect=['top-bar: top-bar\napp-titlebar: app-titlebar','','']) as calls:
 router.apply();assert router.enabled
 assert calls.call_args_list[1].args[-1]=='fullscreen-island'
 assert calls.call_args_list[2].args[-2:]==('top-bar','app-titlebar')
with patch.object(f,'hypr',return_value={'fullscreen':0}),patch.object(f,'call',side_effect=['fullscreen-island: fullscreen-island','','','']) as calls:
 router.apply();assert not router.enabled
 assert [c.args[-1] for c in calls.call_args_list[1:]]==['top-bar','app-titlebar','fullscreen-island']
assert not f.is_fullscreen({'fullscreen':1})
print('PASS: Island-only fullscreen, ordered restoration and maximized-window exclusion.')

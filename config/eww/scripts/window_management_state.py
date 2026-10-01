import json, os, re
from pathlib import Path

def minimized_panels():
    session=re.sub(r'[^\w-]', '_', os.environ.get('HYPRLAND_INSTANCE_SIGNATURE','default'))
    path=Path('/tmp')/f'glyphos-window-management-{os.getuid()}-{session}.json'
    try: panels=json.loads(path.read_text()).get('panels',{})
    except FileNotFoundError: return []
    return [{'address':'eww:'+name,'icon':str(Path(__file__).resolve().parent.parent/'assets/glyphos-dark.svg'),'style':'taskbar-button minimized','tooltip':title+' — click to restore'} for name,title in panels.items()]

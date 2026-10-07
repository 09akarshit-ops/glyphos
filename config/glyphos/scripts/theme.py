#!/usr/bin/env python3
import configparser, datetime, re, sys
from common import HOME, BASE, STATE, call, read, write
EWW=HOME/'.config/eww'
def neutral_hex(match):
    token=match.group(0);color=token[1:]
    if len(color)==3:color=''.join(c*2 for c in color)
    if color.lower()=='e9e9e4':return '#121212'
    rgb=[int(color[i:i+2],16) for i in (0,2,4)]
    if max(rgb)-min(rgb)>30:return token
    avg=sum(rgb)//3;new=255 if avg<40 else max(18,255-avg)
    return '#'+('%02x'%new)*3
def neutral_rgba(match):
    mode=match.group(1);rgb=[int(match.group(i)) for i in (2,3,4)]
    if max(rgb)-min(rgb)>30:return match.group(0)
    avg=sum(rgb)//3
    if avg<40 and match.group(5) and float(match.group(5).lstrip(', '))<.35:return match.group(0)
    value=255 if avg<40 else max(18,255-avg)
    return f'{mode}({value}, {value}, {value}'+(match.group(5) or '')+')'
def apply(mode='auto',force=False):
    if mode=='auto':
        preference=read(STATE/'theme.json',{}).get('preference','auto')
        mode=preference if preference in ('light','dark') else ('dark' if datetime.datetime.now().hour>=18 or datetime.datetime.now().hour<6 else 'light')
    if not force and read(STATE/'theme.json',{}).get('mode')==mode:return
    source=BASE/'themes/light.scss'
    if not source.exists():source.write_text((EWW/'eww.scss').read_text())
    css=source.read_text()
    if mode=='dark':
        css=re.sub(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b',neutral_hex,css)
        css=re.sub(r'\b(rgb|rgba)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[.\d]+)?\)',neutral_rgba,css)
        css+='\n/* Night palette covers cards and nested system text. */\nwindow { color: #ffffff; }\n'
    # The black Island and white lyrics retain their contrast in both themes.
    stable=BASE/'themes/island-dock.scss'
    if stable.exists():css+='\n'+stable.read_text()
    (EWW/'eww.scss').write_text(css)
    bg='#121212ed' if mode=='dark' else '#e9e9e4ed';fg='#ffffff' if mode=='dark' else '#111111'
    rofi=f'''* {{ font: "Ndot 55 13"; background-color: transparent; text-color: {fg}; }}
window {{ width: 640px; border: 1px; border-color: {fg}; border-radius: 24px; background-color: {bg}; padding: 20px; }}
mainbox {{ children: [inputbar, listview]; spacing: 14px; }}
inputbar {{ children: [prompt, entry]; spacing: 10px; }}
listview {{ lines: 10; scrollbar: false; }}
element {{ padding: 10px; border-radius: 12px; }}
element selected {{ background-color: #007aff; text-color: #ffffff; }}
'''
    (BASE/'themes/current.rasi').write_text(rofi)
    gtk='Adwaita-dark' if mode=='dark' else 'Adwaita'
    for version in ('gtk-3.0','gtk-4.0'):
        path=HOME/'.config'/version/'settings.ini';path.parent.mkdir(parents=True,exist_ok=True)
        cfg=configparser.ConfigParser();cfg.read(path)
        if not cfg.has_section('Settings'):cfg.add_section('Settings')
        cfg.set('Settings','gtk-theme-name',gtk);cfg.set('Settings','gtk-application-prefer-dark-theme','true' if mode=='dark' else 'false')
        with path.open('w') as f:cfg.write(f)
    call('gsettings','set','org.gnome.desktop.interface','gtk-theme',gtk,check=False)
    call('gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-dark' if mode=='dark' else 'prefer-light',check=False)
    border='ffffffff' if mode=='dark' else '111111ff'
    (BASE/'themes/hyprland.conf').write_text('general {\n    col.active_border = rgba('+border+')\n    col.inactive_border = rgba('+('ffffff66' if mode=='dark' else '11111166')+')\n}\n')
    call('hyprctl','keyword','general:col.active_border','rgba('+border+')',check=False)
    call('hyprctl','keyword','general:col.inactive_border','rgba('+('ffffff66' if mode=='dark' else '11111166')+')',check=False)
    # Generate inverted neutral SVG assets in a separate directory.
    assets=EWW/'assets';dest=BASE/'themes/dark-assets';dest.mkdir(exist_ok=True)
    if mode=='dark':
        for path in assets.glob('*.svg'):
            data=re.sub(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b',neutral_hex,path.read_text())
            data=re.sub(r'(["\'])black\1',r'\1white\1',data)
            (dest/path.name).write_text(data)
    write(STATE/'theme.json',dict(read(STATE/'theme.json',{}),mode=mode))
    call('eww','reload',check=False)
    from common import update
    update(glyph_dark=mode=='dark',glyph_assets=str(BASE/'themes/dark-assets') if mode=='dark' else 'assets')
if __name__=='__main__':apply(sys.argv[1] if len(sys.argv)>1 else 'auto',force=True)

#!/usr/bin/env python3
"""Refresh per-user backend discovery after installation/package changes."""
from pathlib import Path
HOME=Path.home();CONFIG=HOME/'.config';DATA=HOME/'.local/share'
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
folder=DATA/'xdg-desktop-portal/portals';folder.mkdir(parents=True,exist_ok=True)
for source in Path('/usr/share/xdg-desktop-portal/portals').glob('*.portal'):
 target=folder/source.name
 if not target.exists() and not target.is_symlink():target.symlink_to(source)
write(folder/'glyphos.portal','[portal]\nDBusName=org.freedesktop.impl.portal.desktop.glyphos\nInterfaces=org.freedesktop.impl.portal.FileChooser;\nUseIn=Hyprland;GlyphOS;\n')
write(DATA/'dbus-1/services/org.freedesktop.impl.portal.desktop.glyphos.service','[D-BUS Service]\nName=org.freedesktop.impl.portal.desktop.glyphos\nExec=/usr/bin/python3 '+str(CONFIG/'glyphos/scripts/file_portal.py')+'\nSystemdService=glyphos-file-portal.service\n')
write(CONFIG/'systemd/user/xdg-desktop-portal.service.d/glyphos.conf','[Service]\nEnvironment=XDG_DESKTOP_PORTAL_DIR=%h/.local/share/xdg-desktop-portal/portals\n')
for name in ['portals.conf','hyprland-portals.conf']:
 source=CONFIG/'xdg-desktop-portal'/name
 if source.exists():write(DATA/'xdg-desktop-portal'/name,source.read_text())

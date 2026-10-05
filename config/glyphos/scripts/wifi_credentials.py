#!/usr/bin/env python3
"""Nonmodal, bounded Wi-Fi credential prompt; NetworkManager receives stdin."""
import subprocess, sys, threading
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib
from common import BASE, STATE, read, notify
key=sys.argv[1]
row=next((r for r in read(STATE/'wifi-rows.json',[]) if r['id']==key),None)
if not row:sys.exit(1)
window=Gtk.Window(title='GlyphOS · Wi-Fi credentials');window.set_default_size(380,180)
window.set_resizable(False);window.connect('destroy',lambda *_:Gtk.main_quit())
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);box.set_border_width(20);window.add(box)
box.pack_start(Gtk.Label(label='Connect to '+row['value']),False,False,0)
entry=Gtk.Entry();entry.set_visibility(False);entry.set_placeholder_text('Wi-Fi password');box.pack_start(entry,False,False,0)
button=Gtk.Button(label='Connect');box.pack_start(button,False,False,0)
def connect(*_):
    password=entry.get_text();entry.set_text('');button.set_sensitive(False)
    def worker():
        try:
            p=subprocess.run(['nmcli','--ask','--wait','12','device','wifi','connect',row['value']],input=password+'\n',capture_output=True,text=True,timeout=15)
            text='Connected to '+row['value'] if p.returncode==0 else 'Wi-Fi connection failed · check password and network availability'
        except subprocess.SubprocessError:text='Wi-Fi connection timed out'
        GLib.idle_add(lambda:(notify(text),window.destroy(),False)[2])
    threading.Thread(target=worker,daemon=True).start()
button.connect('clicked',connect);entry.connect('activate',connect)
GLib.timeout_add_seconds(60,lambda:(window.destroy(),False)[1])
window.show_all();entry.grab_focus();Gtk.main()

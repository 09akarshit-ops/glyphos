#!/usr/bin/env python3
"""Normal Wayland picker: closes on focus loss; never grabs input."""
import json, sys
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, Gdk, GLib
from common import STATE, read
GLib.set_prgname('glyphos-palette')
payload=json.load(sys.stdin);choices=payload.get('choices',[]);custom=payload.get('custom',False)
window=Gtk.Window(title='GlyphOS Palette');window.set_default_size(640,480);window.set_decorated(False)
window.set_resizable(False);focused=[False];done=[False];visible=[]
dark=read(STATE/'theme.json',{}).get('mode')=='dark'
provider=Gtk.CssProvider()
provider.load_from_data(('''window { background-color: %s; color: %s; border: 1px solid %s; border-radius: 24px; }
box.picker { padding: 20px; } label, entry { font-family: "Ndot 55"; font-size: 15px; }
entry { padding: 12px; border-radius: 14px; background: transparent; color: %s; }
list, row { background: transparent; color: %s; } row { padding: 10px; border-radius: 12px; }
row:selected { background: rgba(128,128,128,0.2); }''' % (('rgba(18,18,18,0.95)','#ffffff','#ffffff','#ffffff','#ffffff') if dark else ('rgba(233,233,228,0.96)','#111111','#111111','#111111','#111111'))).encode())
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);box.get_style_context().add_class('picker');window.add(box)
title=Gtk.Label(label=payload.get('prompt','GLYPHOS'));title.set_xalign(0);box.pack_start(title,False,False,0)
entry=Gtk.SearchEntry();entry.set_placeholder_text('Search…');box.pack_start(entry,False,False,0)
scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);box.pack_start(scroll,True,True,0)
listing=Gtk.ListBox();listing.set_selection_mode(Gtk.SelectionMode.SINGLE);scroll.add(listing)
def finish(value=''):
    if done[0]:return
    done[0]=True
    if value:print(value,flush=True)
    window.destroy()
def refresh(*_):
    for child in listing.get_children():listing.remove(child)
    query=entry.get_text().casefold();visible[:]=[item for item in choices if query in item.casefold()][:40]
    for item in visible:
        row=Gtk.ListBoxRow();label=Gtk.Label(label=item);label.set_xalign(0);label.set_ellipsize(3);row.add(label);listing.add(row)
    listing.show_all()
    rows=listing.get_children()
    if rows:listing.select_row(rows[0])
def activate(*_):
    row=listing.get_selected_row()
    if row:finish(visible[row.get_index()])
    elif custom:finish(entry.get_text())
def keypress(_,event):
    if event.keyval==Gdk.KEY_Escape:finish();return True
    if event.keyval in (Gdk.KEY_Down,Gdk.KEY_Up):
        row=listing.get_selected_row();index=row.get_index() if row else 0
        next_index=max(0,min(len(visible)-1,index+(1 if event.keyval==Gdk.KEY_Down else -1)))
        if visible:listing.select_row(listing.get_row_at_index(next_index))
        return True
    return False
def focus_in(*_):focused[0]=True;return False
def focus_out(*_):
    if focused[0]:finish()
    return False
window.connect('destroy',lambda *_:Gtk.main_quit());window.connect('key-press-event',keypress)
window.connect('focus-in-event',focus_in);window.connect('focus-out-event',focus_out)
entry.connect('search-changed',refresh);entry.connect('activate',activate)
listing.connect('row-activated',lambda _,row:finish(visible[row.get_index()]))
GLib.timeout_add_seconds(120,lambda:(finish(),False)[1])
refresh();window.show_all();entry.grab_focus();Gtk.main()

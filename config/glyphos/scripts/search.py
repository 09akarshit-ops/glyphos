#!/usr/bin/env python3
"""Bounded local full-text search, with safe desktop application launching."""
import os, re, sqlite3, sys, time
from gi.repository import Gio
from common import HOME, BASE, STATE, call, update, read, write
DB = STATE/'files.sqlite3'
ROOTS=[HOME/name for name in ('Desktop','Documents','Downloads')]
TEXT={'.txt','.md','.rst','.csv','.json','.yaml','.yml','.py','.sh','.html','.log'}
def index():
    db=sqlite3.connect(DB); db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS files USING fts5(path UNINDEXED, name, content)')
    db.execute('DELETE FROM files'); count=0; start=time.monotonic()
    for root in ROOTS:
        for folder, dirs, names in os.walk(root):
            dirs[:]=[d for d in dirs if not d.startswith('.') and d not in ('node_modules','venv') and not (Path(folder)/d).is_symlink()]
            for name in names:
                path=Path(folder)/name
                if path.is_symlink(): continue
                try:
                    content=path.read_text(errors='replace')[:100000] if path.suffix.lower() in TEXT and path.stat().st_size<=1000000 else ''
                    db.execute('INSERT INTO files VALUES (?,?,?)',(str(path),name,content)); count+=1
                except OSError: continue
                if count>=12000 or time.monotonic()-start>20: break
            if count>=12000 or time.monotonic()-start>20: break
        if count>=12000 or time.monotonic()-start>20: break
    db.commit(); db.close(); return count
from pathlib import Path
def results(query):
    query=query.strip(); out=[]
    if not query: return out
    for app in Gio.AppInfo.get_all():
        if app.should_show() and query.casefold() in (app.get_display_name()+' '+(app.get_description() or '')).casefold():
            out.append({'kind':'app','label':app.get_display_name(),'id':app.get_id()})
    if DB.exists():
        db=sqlite3.connect(DB)
        terms=re.findall(r'\w+',query)[:12]
        if terms:
            match=' OR '.join('"'+t+'"*' for t in terms)
            try:
                for path,name in db.execute('SELECT path,name FROM files WHERE files MATCH ? ORDER BY rank LIMIT 10',(match,)):
                    if Path(path).exists(): out.append({'kind':'file','label':name+' · '+str(Path(path).parent),'id':path})
            except sqlite3.Error: pass
        db.close()
    return out[:12]
def launch(item):
    if item['kind']=='app':
        app=Gio.DesktopAppInfo.new(item['id'])
        if app: app.launch([],None)
    else: Gio.AppInfo.launch_default_for_uri(Path(item['id']).as_uri(),None)
def worker(query):
    time.sleep(.35)
    if read(STATE/'search-request.json',{}).get('query')!=query:return
    found=results(query)
    preview='\n'.join(item['label'] for item in found)
    if query and not found:
        from gemini import answer
        preview=answer(query)
    if read(STATE/'search-request.json',{}).get('query')==query:
        write(STATE/'search-results.json',found); update(search_preview=preview)
if __name__=='__main__':
    action=sys.argv[1]
    if action=='index':print(index())
    elif action=='worker':worker(sys.argv[2])
    elif action=='launch':
        found=results(sys.argv[2])
        if found: launch(found[0])

#!/usr/bin/env python3
"""Event-driven kernel inotify watcher with paired rename cookies."""
import configparser, ctypes, fcntl, json, os, signal, struct, sys, time
from pathlib import Path
from urllib.parse import unquote
from gi.repository import GLib
sys.path.insert(0,str(Path.home()/'.config/glyphos/scripts'))
from common import HOME, STATE, read, write
LOG=Path('/tmp/glyph_file_undo.log')
TRASH=HOME/'.local/share/Trash'
MASK=0x40|0x80|0x100|0x200|0x8
class Watcher:
    def __init__(self):
        self.lib=ctypes.CDLL(None,use_errno=True)
        self.fd=self.lib.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        if self.fd<0:raise OSError(ctypes.get_errno(),'inotify_init1')
        self.watches={};self.moves={};self.buffer=b''
        for root in [HOME/n for n in ('Desktop','Documents','Downloads')]+[TRASH/'files',TRASH/'info']:
            root.mkdir(parents=True,exist_ok=True)
            self.tree(root)
        GLib.io_add_watch(self.fd,GLib.IO_IN,self.ready)
        GLib.timeout_add_seconds(5,self.expire)
    def tree(self,root):
        for path,dirs,_ in os.walk(root):
            dirs[:]=[d for d in dirs if not d.startswith('.') and d not in ('node_modules','venv') and not (Path(path)/d).is_symlink()]
            if len(self.watches)>=3000:break
            wd=self.lib.inotify_add_watch(self.fd,os.fsencode(path),MASK)
            if wd>=0:self.watches[wd]=Path(path)
    def record(self,row):
        ignore=read(STATE/'undo-ignore.json',{})
        if time.time()<ignore.get('until',0) and any(row.get(k) in ignore.get('paths',[]) for k in ('from','to')):return
        with (STATE/'undo.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            rows=read(LOG,[])
            if row.get('kind')=='trash':rows=[r for r in rows if not (r.get('from')==row['from'] and r.get('to')==row['to'])]
            row['time']=time.time(); rows.append(row);write(LOG,rows[-100:])
    def trash_info(self,path):
        try:
            cfg=configparser.ConfigParser(interpolation=None);cfg.read(path)
            original=unquote(cfg['Trash Info']['Path']);source=TRASH/'files'/path.name.removesuffix('.trashinfo')
            if source.exists() and Path(original).is_absolute() and any(Path(original).is_relative_to(HOME/n) for n in ('Desktop','Documents','Downloads')):
                self.record({'kind':'trash','from':original,'to':str(source),'info':str(path)})
        except (OSError,KeyError,configparser.Error):pass
    def ready(self,fd,condition):
        try:data=os.read(fd,65536)
        except BlockingIOError:return True
        self.buffer+=data
        # At most 4096 events per callback; kernel reads above are bounded.
        for _ in range(4096):
            if len(self.buffer)<16:break
            wd,mask,cookie,size=struct.unpack_from('iIII',self.buffer)
            if len(self.buffer)<16+size:break
            name=os.fsdecode(self.buffer[16:16+size].split(b'\0',1)[0]);self.buffer=self.buffer[16+size:]
            if mask&0x4000:
                print('inotify queue overflow; some operations cannot be undone',flush=True);continue
            root=self.watches.get(wd)
            if not root:continue
            path=root/name
            if mask&0x40000000 and mask&(0x100|0x80):self.tree(path)
            if mask&0x40:self.moves[cookie]=(str(path),time.time())
            if mask&0x80 and cookie in self.moves:
                source,_=self.moves.pop(cookie)
                if not path.is_relative_to(TRASH):self.record({'kind':'move','from':source,'to':str(path)})
                # Update watched subtree paths after directory renames.
                for key,folder in list(self.watches.items()):
                    if folder.is_relative_to(source):self.watches[key]=path/folder.relative_to(source)
            if path.parent==TRASH/'info' and path.suffix=='.trashinfo' and mask&(0x8|0x80):
                GLib.timeout_add(150,lambda p=path:(self.trash_info(p),False)[1])
        return True
    def expire(self):
        now=time.time();self.moves={k:v for k,v in self.moves.items() if now-v[1]<10};return True
if __name__=='__main__':
    os.umask(0o077)
    # Refuse an unrelated or symlinked shared /tmp state path.
    if LOG.is_symlink() or (LOG.exists() and LOG.stat().st_uid!=os.getuid()):raise RuntimeError('Unsafe undo log path')
    Watcher();loop=GLib.MainLoop()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,lambda:(loop.quit(),False)[1])
    loop.run()

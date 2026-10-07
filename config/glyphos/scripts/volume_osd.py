#!/usr/bin/env python3
"""One lazy IPC worker for volume feedback, hover timers and mute hold detection."""
import fcntl
import json
import math
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path.home()/'.local/state/glyphos/volume-osd'
SOCKET = ROOT/'control.sock'


def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL,timeout=2).strip()


def eww(*args):
    return run('eww','--no-daemonize',*args)


def read_volume(raw):
    words = raw.split()
    volume = round(float(words[1])*100)
    muted = '[MUTED]' in raw
    icon = '󰖁' if muted or volume == 0 else '󰕿' if volume < 34 else '󰖀' if volume < 67 else '󰕾'
    return volume,muted,icon


class OSD:
    def __init__(self):
        self.visible=False;self.hover=False;self.hide_at=None;self.close_at=None
        self.hold_at=None;self.pressed=False;self.last_volume=None;self.poll_at=0
        self.pending_set=None;self.set_at=0

    def refresh(self):
        value=read_volume(run('wpctl','get-volume','@DEFAULT_AUDIO_SINK@'))
        if value!=self.last_volume:
            volume,muted,icon=value
            eww('update',f'osd-volume={min(100,max(0,volume))}',f'osd-muted={str(muted).lower()}',f'osd-icon={icon}')
            self.last_volume=value
        self.poll_at=time.monotonic()+0.25

    def show(self,now):
        self.refresh()
        eww('update','osd-reveal=true')
        if not self.visible:
            eww('open','volume-osd');self.visible=True
        self.close_at=None
        self.hide_at=None if self.hover else now+2

    def command(self,command,value=None,now=None):
        now=time.monotonic() if now is None else now
        if command in ('raise','lower'):
            run('wpctl','set-volume','-l','1.0','@DEFAULT_AUDIO_SINK@','5%+' if command=='raise' else '5%-')
            self.show(now)
        elif command=='mute-press':
            if not self.pressed:
                self.pressed=True;self.hold_at=now+3
                run('wpctl','set-mute','@DEFAULT_AUDIO_SINK@','toggle');self.show(now)
        elif command=='mute-release':
            self.pressed=False;self.hold_at=None
        elif command=='mute':
            run('wpctl','set-mute','@DEFAULT_AUDIO_SINK@','toggle');self.show(now)
        elif command=='show':self.show(now)
        elif command=='hover':
            self.hover=True;self.hide_at=None;self.close_at=None
            if self.visible:eww('update','osd-reveal=true')
        elif command=='leave':
            self.hover=False
            if self.visible:self.hide_at=now+2
        elif command=='set':
            number=float(value)
            if not math.isfinite(number):raise ValueError('Invalid volume')
            if self.pending_set is None:self.set_at=now+0.025
            self.pending_set=max(0,min(100,number))
            if self.visible:self.hide_at=None if self.hover else now+2
        elif command=='mixer':self.mixer()
        else:raise ValueError('Unknown OSD command')

    def mixer(self):
        binary=shutil.which('pavucontrol') or shutil.which('qpwgraph')
        if binary:subprocess.Popen([binary],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

    def tick(self,now):
        if self.pending_set is not None and now>=self.set_at:
            value=self.pending_set;self.pending_set=None
            run('wpctl','set-volume','-l','1.0','@DEFAULT_AUDIO_SINK@',f'{value}%')
            self.refresh()
        if self.hold_at is not None and now>=self.hold_at:
            self.hold_at=None
            if self.pressed:self.mixer()
        if self.visible and now>=self.poll_at:self.refresh()
        if self.hide_at is not None and now>=self.hide_at and not self.hover:
            self.hide_at=None;eww('update','osd-reveal=false');self.close_at=now+0.22
        if self.close_at is not None and now>=self.close_at and not self.hover:
            eww('close','volume-osd');self.visible=False;self.close_at=None;self.hover=False


def daemon():
    with (ROOT/'worker.lock').open('w') as guard:
        try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        SOCKET.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as server:
            server.bind(str(SOCKET));os.chmod(SOCKET,0o600)
            osd=OSD()
            try:
                while True:
                    # Idle workers block; visible widgets alone refresh volume.
                    due=[d for d in (osd.hide_at,osd.close_at,osd.hold_at,
                         osd.set_at if osd.pending_set is not None else None,
                         osd.poll_at if osd.visible else None) if d is not None]
                    timeout=max(0,min(due)-time.monotonic()) if due else None
                    if select.select([server],[],[],timeout)[0]:
                        try:
                            message=json.loads(server.recv(1024));osd.command(message['command'],message.get('value'))
                        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:print(error,file=sys.stderr,flush=True)
                    try:osd.tick(time.monotonic())
                    except (OSError,ValueError,subprocess.SubprocessError) as error:
                        print(error,file=sys.stderr,flush=True);osd.poll_at=time.monotonic()+1
            finally:SOCKET.unlink(missing_ok=True)


def main():
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    args=sys.argv[1:] or ['show']
    if args[0]=='--daemon':daemon();return
    payload=json.dumps({'command':args[0],'value':args[1] if len(args)>1 else None}).encode()
    def send():
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
            client.settimeout(0.15)
            client.sendto(payload,str(SOCKET))
    try:send();return
    except OSError:pass
    with (ROOT/'start.lock').open('w') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        try:send();return
        except OSError:pass
        with (ROOT/'worker.log').open('a') as log:
            subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--daemon'],stdout=log,stderr=log,start_new_session=True)
        for _ in range(30):
            try:send();return
            except OSError:time.sleep(0.02)
    raise SystemExit('Volume OSD worker did not start')


if __name__=='__main__':main()

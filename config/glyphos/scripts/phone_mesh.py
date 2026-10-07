#!/usr/bin/env python3
"""KDE Connect trust/mount bridge. Backend owns LAN discovery, TLS and SSH keys."""
import fcntl
import json
import os
from pathlib import Path
import queue
import re
import socket
import threading
import time
import sys
from mobile_sftp import MobileStorage
import gi
from gi.repository import Gio,GLib

ROOT=Path.home()/'.local/state/glyphos/phone-mesh'
SNAPSHOT=ROOT/'devices.json';TRUST=ROOT/'trust.json';CONTROL=ROOT/'control.sock'
SERVICE='org.kde.kdeconnect';BASE='/modules/kdeconnect'
DEVICE='org.kde.kdeconnect.device';SFTP=DEVICE+'.sftp'


def valid_id(device):
    if not isinstance(device,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',device):raise ValueError('Invalid device identifier')
    return device


def read(path,default):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return default


def write(path,value):
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temp.open('w') as file:
        os.chmod(temp,0o600);json.dump(value,file,ensure_ascii=False)
    temp.replace(path)


def fingerprint(info):
    # Backend supplies local then remote certificate SHA-256, independent of locale.
    matches=re.findall(r'(?i)\b(?:[0-9a-f]{2}:){31}[0-9a-f]{2}\b',info)
    return matches[1].replace(':','').lower() if len(matches)>=2 else ''


def trusted(old,current,paired):
    return bool(paired and re.fullmatch(r'[0-9a-f]{64}',current or '')
                and (not old or not old.get('fingerprint') or old.get('fingerprint')==current))


class Backend:
    def __init__(self):self.bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    def call(self,path,interface,method,params=None,timeout=3000,cancellable=None):
        reply=self.bus.call_sync(SERVICE,path,interface,method,params,None,Gio.DBusCallFlags.NONE,timeout,cancellable)
        values=reply.unpack();return values[0] if len(values)==1 else values
    def devices(self):return self.call(BASE,'org.kde.kdeconnect.daemon','devices',GLib.Variant('(bb)',(False,False)))
    def properties(self,device):return self.call(BASE+'/devices/'+valid_id(device),'org.freedesktop.DBus.Properties','GetAll',GLib.Variant('(s)',(DEVICE,)))
    def device(self,device,method):return self.call(BASE+'/devices/'+valid_id(device),DEVICE,method)
    def sftp(self,device,method,**kwargs):return self.call(BASE+'/devices/'+valid_id(device)+'/sftp',SFTP,method,**kwargs)
    def refresh(self):self.call(BASE,'org.kde.kdeconnect.daemon','forceOnNetworkChange')


class Mesh:
    def __init__(self,backend):
        self.backend=backend;self.jobs=queue.PriorityQueue();self.serial=0;self.lock=threading.RLock()
        self.trust=read(TRUST,{});self.messages={};self.snapshot={'devices':[],'error':''}
        self.last_mount={};self.cancellable=None;self.mounting=None;self.mobile=MobileStorage()
    def enqueue(self,command,device=''):
        if command.startswith('sftp-'):
            if command not in ('sftp-connect','sftp-disconnect','sftp-probe','sftp-trust-connect'):raise ValueError('Unknown SFTP action')
            if command=='sftp-disconnect':self.mobile.cancel=True
            elif command in ('sftp-connect','sftp-trust-connect'):self.mobile.cancel=False
            with self.lock:self.serial+=1;self.jobs.put((0 if command=='sftp-disconnect' else 1,self.serial,command,''))
            return
        if command not in ('scan','refresh','pair','accept','cancel','connect','disconnect','forget'):raise ValueError('Unknown mesh action')
        if command not in ('refresh','scan'):valid_id(device)
        with self.lock:
            if command in ('disconnect','forget'):
                self.trust.setdefault(device,{})['auto_mount']=False;write(TRUST,self.trust)
                if self.mounting==device and self.cancellable:self.cancellable.cancel()
            self.serial+=1;self.jobs.put((0 if command in ('disconnect','forget') else 1,self.serial,command,device))
    def inspect(self,device):
        props=self.backend.properties(device)
        if props.get('type') not in ('phone','tablet'):return None
        online=bool(props.get('isReachable'));paired=bool(props.get('isPaired'))
        info=self.backend.device(device,'encryptionInfo') if online or paired else ''
        digest=fingerprint(info)
        with self.lock:
            old=self.trust.get(device)
            secure=trusted(old,digest,paired)
            if secure and (not old or not old.get('fingerprint')):
                self.trust[device]={'fingerprint':digest,'auto_mount':old.get('auto_mount',True) if old else True};write(TRUST,self.trust)
                old=self.trust[device]
            auto=bool(old and old.get('auto_mount',False))
        mismatch=bool(paired and digest and old and old.get('fingerprint') and not secure)
        plugin='kdeconnect_sftp' in props.get('supportedPlugins',[])
        mounted=False;mount=''
        if online and paired and not secure and plugin:
            try:self.backend.sftp(device,'unmount')
            except GLib.Error:pass
        if online and paired and secure and plugin:
            mounted=bool(self.backend.sftp(device,'isMounted'))
            if not auto and mounted:
                self.backend.sftp(device,'unmount');mounted=False
            if auto and not mounted and time.monotonic()-self.last_mount.get(device,-60)>30:
                self.last_mount[device]=time.monotonic()
                with self.lock:self.cancellable=Gio.Cancellable();self.mounting=device;cancel=self.cancellable
                try:
                    mounted=bool(self.backend.sftp(device,'mountAndWait',timeout=12000,cancellable=cancel))
                    if not mounted:self.messages[device]=str(self.backend.sftp(device,'getMountError')) or 'Phone storage is not available.'
                finally:
                    with self.lock:self.cancellable=None;self.mounting=None
                # A kill switch queued during mounting must still prevent exposure.
                with self.lock:auto=bool(self.trust.get(device,{}).get('auto_mount',False))
                if mounted and not auto:self.backend.sftp(device,'unmount');mounted=False
            if mounted:
                candidate=str(self.backend.sftp(device,'mountPoint'))
                # Never let a peer-supplied path become an arbitrary unmount command.
                if candidate.startswith('/') and Path(candidate).is_dir():mount=candidate
        if mismatch:self.messages[device]='Certificate changed. Disconnect and pair again before browsing.'
        key=str(props.get('verificationKey',''))
        if not key and props.get('isPairRequestedByPeer'):
            try:key=str(self.backend.device(device,'verificationKey'))
            except GLib.Error:pass
        return {'id':device,'name':str(props.get('name','Phone'))[:100], 'online':online,'paired':paired,
                'incoming':bool(props.get('isPairRequestedByPeer')),'pending':bool(props.get('isPairRequested')),
                'verification':key,'fingerprint':digest,'encryption':info,'trusted':secure,'auto_mount':auto,
                'sftp_supported':plugin,'mount':mount,'mounted':bool(mount),'message':self.messages.get(device,'')}
    def publish_mobile(self,state):
        self.snapshot['mobile']=state;write(SNAPSHOT,self.snapshot)
    def scan(self):
        self.mobile.health()
        rows=[];error=''
        try:
            for device in self.backend.devices():
                try:
                    row=self.inspect(valid_id(device))
                    if row:rows.append(row)
                except (GLib.Error,OSError,ValueError) as problem:
                    rows.append({'id':device,'name':'Phone','online':False,'paired':False,'mounted':False,'mount':'','message':str(problem)[:180]})
        except GLib.Error as problem:error='KDE Connect unavailable: '+str(problem)[:180]
        self.snapshot={'devices':rows,'mobile':dict(self.mobile.state),'error':error,'updated':time.time()};write(SNAPSHOT,self.snapshot)
    def action(self,command,device):
        if command.startswith('sftp-'):
            self.mobile.action(command[5:],self.publish_mobile);return
        try:
            if command=='refresh':self.backend.refresh()
            elif command=='scan':pass
            elif command in ('pair','accept','cancel'):
                self.backend.device(device,{'pair':'requestPairing','accept':'acceptPairing','cancel':'cancelPairing'}[command])
                self.messages[device]='Confirm the pairing request on your phone.' if command=='pair' else ''
            elif command=='connect':
                props=self.backend.properties(device)
                digest=fingerprint(self.backend.device(device,'encryptionInfo'))
                with self.lock:
                    if not trusted(self.trust.get(device),digest,props.get('isPaired')):raise ValueError('Pair and verify the device before mounting storage.')
                    self.trust.setdefault(device,{'fingerprint':digest})['auto_mount']=True;write(TRUST,self.trust)
                self.last_mount.pop(device,None);self.messages[device]=''
            elif command in ('disconnect','forget'):
                try:self.backend.sftp(device,'unmount')
                except GLib.Error as problem:self.messages[device]='Storage disconnect failed: '+str(problem)[:100];return
                self.messages[device]='Storage disconnected; automatic mounting paused.'
                if command=='forget':
                    self.backend.device(device,'unpair')
                    with self.lock:self.trust.pop(device,None);write(TRUST,self.trust)
        except (GLib.Error,OSError,ValueError) as problem:self.messages[device]=str(problem)[:180]
    def worker(self):
        while True:
            try:_,_,command,device=self.jobs.get(timeout=10);self.action(command,device)
            except queue.Empty:pass
            self.scan()


def send(command,device=''):
    valid_id(device) if device else None
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
        client.settimeout(.2);client.sendto(json.dumps({'command':command,'device':device}).encode(),str(CONTROL))


def daemon():
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (ROOT/'daemon.lock').open('w') as guard:
        try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        backend=Backend();mesh=Mesh(backend)
        backend.bus.signal_subscribe(SERVICE,None,None,None,None,Gio.DBusSignalFlags.NONE,lambda *args: mesh.enqueue('scan') if mesh.jobs.empty() else None)
        CONTROL.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as control:
            control.bind(str(CONTROL));os.chmod(CONTROL,0o600)
            def receive():
                while True:
                    try:
                        data=json.loads(control.recv(2048));mesh.enqueue(data['command'],data.get('device',''))
                    except (OSError,ValueError,KeyError) as error:print(error,file=sys.stderr,flush=True)
            threading.Thread(target=receive,daemon=True).start();threading.Thread(target=mesh.worker,daemon=True).start()
            mesh.enqueue('refresh');GLib.MainLoop().run()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--daemon':daemon()
    elif len(sys.argv)>1:send(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else '')
    else:print(json.dumps(read(SNAPSHOT,{'devices':[],'error':'Phone mesh is starting.'})))

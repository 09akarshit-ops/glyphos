import json, os, subprocess, threading
from pathlib import Path
HOME = Path.home()
BASE = HOME / '.config/glyphos'
STATE = HOME / '.local/state/glyphos'
STATE.mkdir(parents=True, exist_ok=True)
EWW_LOCK=threading.RLock()
def call(*args, timeout=4, input=None, check=True):
    if args and args[0]=='eww':
        with EWW_LOCK:
            return call('/usr/bin/eww','--no-daemonize','--config',str(HOME/'.config/eww'),*args[1:],timeout=timeout,input=input,check=check)
    if args and args[0]=='wl-copy':
        # wl-copy's detached clipboard owner inherits pipes unless redirected.
        # Capturing them would keep communicate() waiting after its parent exits.
        p=subprocess.run(args,input=input,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True,timeout=timeout)
        if check and p.returncode:raise RuntimeError('Clipboard copy failed')
        return ''
    p = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or 'Command failed')
    return p.stdout.strip()
def read(path, default):
    try: return json.loads(Path(path).read_text())
    except (OSError, ValueError): return default
def write(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False)); tmp.chmod(0o600); tmp.replace(path)
def update(**values):
    call('eww', 'update', *[k.replace('_','-')+'='+(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)) for k,v in values.items()], check=False)
def notify(text): call('notify-send', 'GlyphOS', text, check=False)
def hypr(what): return json.loads(call('hyprctl', what, '-j'))

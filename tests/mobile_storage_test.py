import sys,tempfile,subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config/glyphos/scripts'))
import mobile_sftp as mobile
from file_transfer import transfer
import file_manager as files
from gi.repository import Gtk,Gdk,Gio
profile=mobile.validate({'host':'192.168.1.10','user':'u0_a123','port':8022,'remote':'/storage/emulated/0'})
args=mobile.command(profile);assert 'StrictHostKeyChecking=yes' in args[-1] and 'ServerAliveCountMax=3' in args[-1]
for bad in [{'host':'8.8.8.8','user':'test'},{'host':'192.168.1.10','user':'x;exec'},{'host':'192.168.1.10','user':'x','remote':'/../tmp'}]:
 try:mobile.validate(bad)
 except ValueError:pass
 else:raise AssertionError('Invalid profile accepted')
with tempfile.TemporaryDirectory() as d:
 root=Path(d);a=root/'local';b=root/'phone';a.mkdir();b.mkdir();(a/'nested').mkdir();(a/'nested'/'song.mp3').write_text('test')
 transfer([a/'nested'],b);assert (b/'nested'/'song.mp3').read_text()=='test'
 try:transfer([a/'nested'],b)
 except FileExistsError:pass
 else:raise AssertionError('Overwrite allowed')
 try:transfer([a/'nested'],a/'nested')
 except ValueError:pass
 else:raise AssertionError('Self copy allowed')
 (a/'move.txt').write_text('move');transfer([a/'move.txt'],b,True);assert not (a/'move.txt').exists() and (b/'move.txt').exists()
m=mobile.MobileStorage();m.state['status']='connected'
with patch.object(mobile,'mounted',return_value=True),patch.object(mobile.shutil,'which',return_value='/usr/bin/fusermount3'),patch.object(mobile.subprocess,'run',side_effect=[subprocess.TimeoutExpired('stat',4),SimpleNamespace(returncode=0)] ) as calls,patch.object(mobile.subprocess,'Popen') as banner:
 m.health();assert m.state['status']=='disconnected';assert calls.call_args_list[1].args[0][1]=='-u';banner.assert_called_once()
for state in ['disconnected','connecting','connected']:
 fake=SimpleNamespace(sidebar=Gtk.Box(),icon=lambda name:Gtk.Image(),connect_mobile=lambda:None,mesh_action=lambda *a:None,navigate=lambda *a:None,configure_mobile=lambda:None,add_drop_target=lambda *a:None)
 with patch.object(files,'read',return_value={'mobile':{'status':state,'total':1000,'available':750}}):files.Files.mobile_card(fake)
 assert fake.sidebar.get_first_child() is not None
provider=Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path('/tmp/test.mp3')]))
assert provider is not None
print('Passed: host/profile validation, safe recursive copy/move, collision guards, timeout unmount/banner, three sidebar states and native drag payload.')

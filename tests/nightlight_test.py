import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("nightlight",Path(__file__).resolve().parents[1]/"config/glyphos/scripts/nightlight.py")
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
assert n.strength(-20)==0 and n.strength(130)==100
assert "0.807000, 0.651000" in n.shader(50)
assert "1.000000, 1.000000" in n.shader(0)
with TemporaryDirectory() as folder:
 n.CACHE=Path(folder)/"cache";n.STATE=Path(folder)/"state.json"
 calls=[];n.hypr=lambda *args:calls.append(args)
 data={"intensity":50,"previous":""}
 target=n.apply({"action":"set","value":75},data,"custom.frag")
 assert data["previous"]=="custom.frag" and Path(target).exists()
 n.apply({"action":"set","value":75},data,target)
 assert len(calls)==1,"Identical settings must not recompile the shader"
 restored=n.apply({"action":"off"},data,target)
 assert restored=="custom.frag"
 target=n.apply({"action":"on"},data,restored)
 assert n.apply({"action":"set","value":0},data,target)=="custom.frag"
 assert data["intensity"]==0
 n.apply({"action":"on"},data,"custom.frag")
 assert data["intensity"]==50
print("PASS: intensity bounds, shader defaults, previous shader restoration, zero/off, and redundant update suppression")

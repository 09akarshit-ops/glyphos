#!/usr/bin/env python3
"""Debounced native Hyprland Night Light controller; Eww owns the listener."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

STATE = Path.home() / ".local/state/glyphos/nightlight.json"
CACHE = Path.home() / ".cache/glyphos/nightlight"
SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/glyphos-{os.getuid()}")) / "glyphos-nightlight.sock"
LEGACY = str(Path.home() / ".config/eww/shaders/nightlight.frag")

def strength(value):
    return max(0, min(100, round(float(value))))

def shader(value):
    amount = strength(value) / 100
    return """#version 300 es
precision mediump float;
in vec2 v_texcoord;
layout(location=0) out vec4 fragColor;
uniform sampler2D tex;
void main() {
    vec4 pixel = texture(tex, v_texcoord);
    fragColor = vec4(pixel.rgb * vec3(1.0, %.6f, %.6f), pixel.a);
}
""" % (1 - .386 * amount, 1 - .698 * amount)

def hypr(*args):
    result = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=3, check=True)
    return result.stdout.strip()

def current():
    value = json.loads(hypr("getoption", "decoration:screen_shader", "-j")).get("str", "")
    return "" if value == "[[EMPTY]]" else value

def owned(path):
    return path == LEGACY or str(path).startswith(str(CACHE) + "/strength-")

def load():
    try:
        data = json.loads(STATE.read_text())
        return {"intensity": strength(data.get("intensity", 50)), "previous": str(data.get("previous", ""))}
    except (OSError, ValueError, TypeError):
        return {"intensity": 50, "previous": ""}

def apply(command, data, active):
    action = command.get("action")
    enabled = owned(active)
    value = strength(command.get("value", data["intensity"]))
    if action == "set":
        data["intensity"] = value
        enable = value > 0
    elif action in ("toggle", "on", "off"):
        enable = not enabled if action == "toggle" else action == "on"
        if enable and value == 0:
            data["intensity"] = value = 50
    else:
        raise ValueError("Unknown action")
    if enable:
        if not enabled:
            data["previous"] = active
        elif active == LEGACY and not data.get("previous"):
            legacy_previous = Path.home() / ".config/eww/.nightlight-previous"
            if legacy_previous.exists():
                data["previous"] = legacy_previous.read_text().replace("[[EMPTY]]", "")
        CACHE.mkdir(parents=True, exist_ok=True)
        path = CACHE / f"strength-{value:03}.frag"
        content = shader(value)
        if not path.exists() or path.read_text() != content:
            path.write_text(content)
        target = str(path)
    else:
        target = data.get("previous", "") if enabled else active
        if owned(target):
            target = ""
    if target != active:
        hypr("keyword", "decoration:screen_shader", target)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.replace(STATE)
    return target

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("state", "set", "toggle", "on", "off", "status"), nargs="?", default="toggle")
    parser.add_argument("value", nargs="?", type=float)
    args = parser.parse_args()
    if args.action in ("status", "state"):
        enabled = owned(current())
        if args.action == "status":
            print("true" if enabled else "false")
        else:
            print(json.dumps({"enabled": enabled, "intensity": load()["intensity"]}))
        return
    if args.action == "set" and args.value is None:
        parser.error("set requires an intensity from 0 to 100")
    command = {"action": args.action}
    if args.value is not None:
        command["value"] = strength(args.value)
    SOCKET.parent.mkdir(parents=True, exist_ok=True)
    request = SOCKET.with_suffix(".request")
    if args.action == "set":
        # Every slider event replaces the pending value atomically. Only the
        # process holding the worker lock applies it; waiting events coalesce.
        temporary = request.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(command))
        temporary.replace(request)
    with open(str(SOCKET) + ".apply.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "set":
            time.sleep(.08)
            try:
                command = json.loads(request.read_text())
                request.unlink(missing_ok=True)
            except FileNotFoundError:
                return
        apply(command, load(), current())

if __name__ == "__main__":
    main()

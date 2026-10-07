#!/usr/bin/env python3
"""One bounded MPRIS reader and one lyrics worker; never block Eww or GTK."""
import bisect
import concurrent.futures
import json
import os
import re
import threading
import time
from pathlib import Path

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

CONTEXT = Path.home() / '.local/state/glyphos/island-context.json'
SNAPSHOT = CONTEXT.with_name('island-media.json')
RENDER = CONTEXT.with_name('island-render.json')
PLAYER = 'org.mpris.MediaPlayer2.Player'
PATH = '/org/mpris/MediaPlayer2'


import sys
sys.path.insert(0, str(Path.home() / '.config/glyphos/scripts'))
from lyrics import normalize, parse_lrc, lookup, offset_ms, lyric_position


def unpack(value):
    if isinstance(value, GLib.Variant):
        return unpack(value.unpack())
    if isinstance(value, dict):
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [unpack(v) for v in value]
    return value


def scroll_text(text, elapsed, width=32):
    if len(text) <= width:
        return text
    # Briefly hold the start, then move one character at a time. This uses the
    # non-revealing fallback labels, avoiding fade/reveal flicker on every step.
    cycle = text + '     '
    start = int(max(0, elapsed - 2) / .35) % len(cycle)
    return (cycle + cycle)[start:start + width]


class Reader:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {}
        self.preferred = ''
        self.wake = threading.Event()
        self.position_wake = threading.Event()

    def changed(self, bus, sender, path, interface, signal, params, _):
        if signal == 'Seeked':
            with self.lock:
                self.state['position'] = params.unpack()[0] / 1e6
                self.state['sampled'] = time.monotonic()
        self.wake.set()
        self.position_wake.set()

    def poll_position(self):
        # Direct property queries run off Eww/GTK's thread on every 100ms tick.
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        while True:
            started = time.monotonic()
            with self.lock:
                player = self.state.get('player')
                track = self.state.get('track')
            if player:
                try:
                    value = unpack(bus.call_sync(player, PATH,
                        'org.freedesktop.DBus.Properties', 'Get',
                        GLib.Variant('(ss)', (PLAYER, 'Position')), None,
                        Gio.DBusCallFlags.NONE, 80, None))[0] / 1e6
                    with self.lock:
                        if self.state.get('player') == player and self.state.get('track') == track:
                            self.state.update(position=value, sampled=time.monotonic(), position_valid=True)
                except GLib.Error:
                    with self.lock:
                        if self.state.get('player') == player:
                            self.state['position_valid'] = False
            self.position_wake.wait(max(.01, .1 - (time.monotonic() - started)))
            self.position_wake.clear()

    def run(self):
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        subscriptions = []
        while True:
            started = time.monotonic()
            try:
                names = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                    'org.freedesktop.DBus', 'ListNames', None, None,
                    Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
                candidates = []
                for name in sorted(n for n in names if n.startswith('org.mpris.MediaPlayer2.'))[:12]:
                    try:
                        props = unpack(bus.call_sync(name, PATH, 'org.freedesktop.DBus.Properties',
                            'GetAll', GLib.Variant('(s)', (PLAYER,)), None,
                            Gio.DBusCallFlags.NONE, 250, None))[0]
                        if props.get('PlaybackStatus') in ('Playing', 'Paused'):
                            candidates.append((name, props, time.monotonic()))
                    except GLib.Error:
                        continue
                candidates.sort(key=lambda row: (row[1].get('PlaybackStatus') != 'Playing', row[0] != self.preferred))
                state = {}
                if candidates:
                    name, props, sampled = candidates[0]
                    self.preferred = name
                    if getattr(self, 'subscribed', None) != name:
                        for subscription in subscriptions:
                            bus.signal_unsubscribe(subscription)
                        subscriptions = [bus.signal_subscribe(name, interface, member, PATH, None,
                            Gio.DBusSignalFlags.NONE, self.changed, None)
                            for interface, member in [(PLAYER, 'Seeked'),
                                ('org.freedesktop.DBus.Properties', 'PropertiesChanged')]]
                        self.subscribed = name
                    meta = props.get('Metadata', {})
                    artists = meta.get('xesam:artist', [])
                    state = dict(player=name, title=meta.get('xesam:title', ''),
                        artist=', '.join(artists) if isinstance(artists, list) else str(artists),
                        album=meta.get('xesam:album', ''), duration=meta.get('mpris:length', 0) / 1e6,
                        track=meta.get('mpris:trackid', ''), status=props.get('PlaybackStatus'),
                        art=meta.get('mpris:artUrl', ''), url=meta.get('xesam:url', ''),
                        position=props.get('Position', 0) / 1e6, sampled=sampled,
                        position_valid='Position' in props,
                        rate=props.get('Rate', 1))
                with self.lock:
                    # A newer direct Position response wins over a slower
                    # metadata refresh for the same track and player.
                    if state.get('player') == self.state.get('player') and state.get('track') == self.state.get('track') and self.state.get('sampled', 0) > state.get('sampled', 0):
                        for field in ('position', 'sampled', 'position_valid'):
                            state[field] = self.state[field]
                    self.state = state
            except GLib.Error:
                with self.lock:
                    self.state = {}
            self.wake.wait(max(.1, 1 - (time.monotonic() - started)))
            self.wake.clear()


def main():
    reader = Reader()
    threading.Thread(target=reader.run, daemon=True).start()
    threading.Thread(target=reader.poll_position, daemon=True).start()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    key = None
    pending = None
    pending_key = None
    rows = []
    times = []
    lyrics_mode = 'none'
    lyrics_source = ''
    lookup_at = 0
    retry_delay = 15
    attempts = 0
    fallback_started = time.monotonic()
    previous = None
    panes = [{'active': 'GlyphOS', 'next': 'Live activities'} for _ in range(2)]
    pane = 0
    shown = None
    reveal_at = 0
    snapshot_at = 0
    while True:
        context_loop = GLib.MainContext.default()
        while context_loop.pending():
            context_loop.iteration(False)
        with reader.lock:
            state = dict(reader.state)
        metadata = normalize(state.get('title', ''), state.get('artist', ''), state.get('album', ''), state.get('url', ''))
        state.update(title=metadata['title'], artist=metadata['artist'], album=metadata['album'])
        new_key = (metadata['title'], metadata['artist'], metadata['album'], state.get('duration', 0), metadata['url'])
        if new_key != key:
            key = new_key
            rows, times = [], []
            lyrics_mode, lyrics_source = 'none', ''
            attempts, retry_delay = 0, 15
            fallback_started = time.monotonic()
        if pending and pending.done():
            try:
                result = pending.result()
            except Exception:
                result = dict(rows=[], mode='none', source='Lookup failed; retrying')
            if pending_key == key:
                rows = result['rows']
                lyrics_mode, lyrics_source = result['mode'], result['source']
                times = [row[0] for row in rows]
                lookup_at = time.monotonic()
                if not rows:
                    attempts += 1
                    retry_delay = min(120, 15 * 2 ** min(attempts - 1, 3))
            pending = None
        if pending is None and (key != pending_key or (not rows and time.monotonic() - lookup_at >= retry_delay)):
            pending_key = key
            lookup_at = time.monotonic()
            pending = pool.submit(lookup, key)
        try:
            context = json.loads(CONTEXT.read_text()).get('title', 'GlyphOS')
        except (OSError, ValueError):
            context = 'GlyphOS'
        active = state.get('status') in ('Playing', 'Paused')
        position = state.get('position', 0)
        # Never advance lyrics using an independent timer. If Position queries
        # fail, hold the last measured position until the player responds again.
        timing_offset = offset_ms(state.get('url', ''))
        adjusted_position = lyric_position(position, timing_offset)
        index = bisect.bisect_right(times, adjusted_position) - 1
        current = rows[index][1] if index >= 0 and rows else ''
        following = rows[index + 1][1] if rows and index + 1 < len(rows) else ''
        marquee = active and not rows
        elapsed = time.monotonic() - fallback_started
        output = dict(active=current or (state.get('title') if active else context) or 'GlyphOS',
            next=following or (state.get('artist', '') if active else 'Live activities'),
            marquee=marquee, lookup_pending=pending is not None, retry_delay_seconds=retry_delay,
            synced=lyrics_mode == 'synced', lyrics_mode=lyrics_mode, lyrics_source=lyrics_source,
            current_lyric=current, next_lyric=following, lyric_count=len(rows), lyrics=rows[:1000],
            lyrics_description='Synchronized lyrics' if lyrics_mode == 'synced' else 'Plain lyrics · approximate timing' if lyrics_mode == 'plain' else 'Looking up lyrics',
            position=round(position), playing=state.get('status') == 'Playing', player=state.get('player', ''),
            lyric_offset_ms=timing_offset, position_poll_ms=100,
            position_valid=state.get('position_valid', False),
            line=index, title=state.get('title') or 'Nothing Playing',
            artist=state.get('artist') or 'No Artist', status=state.get('status', 'Stopped'),
            progress=round(max(0, min(100, position / state['duration'] * 100))) if state.get('duration', 0) > 0 else 0)
        if marquee:
            output['active'] = scroll_text(state.get('title') or 'Playing media', elapsed)
            output['next'] = scroll_text(state.get('artist') or 'Searching lyrics…', elapsed, 40)
        if time.monotonic() - snapshot_at >= 1:
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            temporary = SNAPSHOT.with_suffix(f'.{os.getpid()}.tmp')
            temporary.write_text(json.dumps(dict(state, updated=time.time(), lyrics_mode=lyrics_mode, lyrics_source=lyrics_source, lyric_count=len(rows), lyric_index=index, lyric_offset_ms=timing_offset, adjusted_position=adjusted_position, position_poll_ms=100)))
            temporary.replace(SNAPSHOT)
            snapshot_at = time.monotonic()
        if not active:
            output['active'] = re.sub(r'^\[\s*[!.·]\s*\]\s*(?:Action Required\s*\|\s*)?', '', output['active'])
        output['active'] = output['active'][:300].replace('\\', '\\\\')
        output['next'] = output['next'][:300].replace('\\', '\\\\')
        text = {'active': output['active'], 'next': output['next']}
        if text != shown:
            pane = 1 - pane
            reveal_at = time.monotonic() + .18
            panes[pane] = text
            shown = text
        output.update(pane=pane, a=panes[0], b=panes[1],
            reveal_a=pane == 0 and time.monotonic() >= reveal_at,
            reveal_b=pane == 1 and time.monotonic() >= reveal_at)
        if output != previous:
            raw = json.dumps(output, ensure_ascii=False)
            if '--service' in sys.argv:
                RENDER.parent.mkdir(parents=True, exist_ok=True)
                temporary = RENDER.with_suffix(f'.{os.getpid()}.tmp')
                temporary.write_text(raw)
                temporary.replace(RENDER)
            else:
                print(raw, flush=True)
            previous = output
        time.sleep(.1)


if __name__ == '__main__':
    try:
        main()
    except (BrokenPipeError, KeyboardInterrupt):
        pass

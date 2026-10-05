"""Sanitize MPRIS/file metadata and resolve bounded local/API lyric lookups."""
import hashlib
import json
import os
import difflib
from pathlib import Path
import re
import time
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen

CACHE = Path.home() / '.cache/glyphos/lyrics-v4'
LYRIC_OFFSET_MS = -500  # Negative offsets delay lyric changes.
TIMING = Path.home() / '.config/glyphos/lyrics-timing.json'


def offset_ms():
    try:
        value = json.loads(TIMING.read_text())['offset_ms']
        return max(-10000, min(10000, int(value)))
    except (OSError, ValueError, KeyError, TypeError):
        return LYRIC_OFFSET_MS


def lyric_position(position, offset):
    return position + offset / 1000


def clean(value):
    value = re.sub(r'\.(mp3|mp4|m4a|flac|ogg|opus|wav|webm)$', '', value, flags=re.I)
    value = re.sub(r'[\[(][^\])]*(?:official|lyrics?|visualizer|audio|video|full\s+song|remaster|\bfeat\b|\bft\b|\bprod\b|\b4k\b|\bhd\b|\bhq\b|kbps)[^\])]*[\])]', '', value, flags=re.I)
    value = re.sub(r'\b\d+\s*kbps\b|\b(?:HQ|HD|4K)\b', '', value, flags=re.I)
    value = re.sub(r'\b(?:\d{4}\s+)?remastered?(?:\s+\d{4})?\b', '', value, flags=re.I)
    value = re.sub(r'\s*\b(?:feat\.?|ft\.?|prod\.?\s*(?:by)?)\s+[^|]*', '', value, flags=re.I)
    value = re.sub(r'\b(?:latest|new)\s+(?:punjabi\s+)?songs?(?:\s+\d{4})?.*$', '', value, flags=re.I)
    value = re.sub(r'\s*[-–]\s*(?:topic|vevo|official channel)\s*$', '', value, flags=re.I)
    value = re.sub(r'\s*(?:VEVO|Official YouTube Channel|Official Channel)\s*$', '', value, flags=re.I)
    value = re.sub(r'\bAudio\b|\.(mp3|mp4|m4a|flac|ogg|opus|wav|webm)\b', '', value, flags=re.I)
    return re.sub(r'\s+', ' ', value).strip(' -–_|')


def casing(value):
    if value and value == value.upper():
        return ' '.join(word if len(word) <= 2 else word.title() for word in value.split())
    return value


def normalize(title, artist='', album='', url=''):
    local = unquote(urlparse(url).path) if urlparse(url).scheme == 'file' else ''
    raw = title.strip() or (Path(local).stem if local else '')
    # Common download filename: SONG (Official Video) ARTIST Latest Songs 2025.
    marker = re.search(r'[\[(]\s*official\s+(?:music\s+)?(?:video|audio)\s*[\])]', raw, re.I)
    if not artist.strip() and marker:
        before, after = clean(raw[:marker.start()]), clean(raw[marker.end():])
        if before and after:
            raw, artist = before, after
    # Split before removing feature/production credits, which may occur in
    # the artist segment and must not consume the song on the other side.
    if re.search(r'\s[-–]\s', raw):
        left, right = re.split(r'\s[-–]\s', raw, maxsplit=1)
        if not artist.strip() or identity(clean(left)) == identity(clean(artist)):
            raw, artist = right, artist or left
    title, artist = clean(raw), clean(artist)
    if '|' in title:
        parts = [clean(part) for part in title.split('|') if clean(part)]
        if len(parts) >= 2:
            title = parts[0]
            if not artist:
                artist = parts[1]
            elif identity(parts[0]) == identity(artist):
                title = parts[1]
        elif parts:
            title = parts[0]
    if artist:
        title = re.sub(r'^' + re.escape(artist) + r'\s*[-–:]\s*', '', title, flags=re.I)
        title = re.sub(r'\s*[-–:]\s*' + re.escape(artist) + '$', '', title, flags=re.I)
    elif re.search(r'\s[-–]\s', title):
        artist, title = re.split(r'\s[-–]\s', title, maxsplit=1)
    return dict(title=casing(title), artist=casing(artist), album=clean(album), local=local, url=url)


def parse_lrc(raw):
    offset = re.search(r'\[offset:([+-]?\d+)\]', raw, re.I)
    offset = int(offset.group(1)) / 1000 if offset else 0
    rows = []
    for line in raw.splitlines():
        stamps = re.findall(r'\[(\d+):(\d+(?:[.,]\d+)?)\]', line)
        text = re.sub(r'\[[^]]*\]', '', line).strip()
        for minute, second in stamps:
            rows.append((max(0, int(minute) * 60 + float(second.replace(',', '.')) + offset), text))
    return sorted(rows, key=lambda row: row[0])


def result(raw, plain, source, duration):
    rows = parse_lrc(raw or '')
    if rows:
        return dict(rows=rows, mode='synced', source=source)
    lines = [line.strip() for line in (plain or raw or '').splitlines()
             if line.strip() and not re.fullmatch(r'\[[^]]*\]', line.strip())]
    if lines:
        # Plain lyrics have no real timestamps. Estimate line timing from track
        # duration and follow Position so pause and seek still behave correctly.
        step = duration / len(lines) if duration > 0 else 4
        return dict(rows=[(i * step, line) for i, line in enumerate(lines)], mode='plain', source=source)
    return dict(rows=[], mode='none', source=source)


def json_request(base, path, params, deadline=None, post=False):
    remaining = deadline - time.monotonic() if deadline else 4
    if remaining <= 0:
        raise TimeoutError('Lyrics lookup time budget exhausted')
    encoded = urlencode(params)
    req = Request(base + path + ('' if post else '?' + encoded),
                  data=encoded.encode() if post else None,
                  headers={'User-Agent': 'GlyphOS-Lyrics/3.0', 'Accept': 'application/json',
                           'Referer': 'https://music.163.com/'})
    with urlopen(req, timeout=min(4, remaining)) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Lyrics response too large')
    return json.loads(raw)


def request(path, params, deadline=None):
    return json_request('https://lrclib.net/api/', path, params, deadline)


def netease_request(path, params, deadline=None, post=False):
    return json_request('https://music.163.com/api/', path, params, deadline, post)


def identity(value):
    return re.sub(r'[^\w]', '', value.casefold())


def similarity(left, right):
    left, right = identity(clean(left)), identity(clean(right))
    if not left or not right:
        return 0
    if left == right:
        return 1
    return difflib.SequenceMatcher(None, left, right).ratio()


def ranked(matches, title, artist, duration):
    scored = []
    for row in matches:
        title_score = similarity(title, row.get('trackName', ''))
        artist_score = similarity(artist, row.get('artistName', '')) if artist else 1
        # Allow misspellings and collaborations, but exclude unrelated songs.
        if title_score < .65 or (artist and artist_score < .45):
            continue
        difference = abs(float(row.get('duration') or 0) - duration) if duration else 0
        score = .72 * title_score + .2 * artist_score + .08 * max(0, 1 - difference / 30)
        scored.append((score, row))
    return [row for _, row in sorted(scored, key=lambda pair: pair[0], reverse=True)[:8]]


def netease(title, artist, duration, deadline):
    params = dict(s=(title + ' ' + artist).strip(), type=1, limit=12, offset=0)
    try:
        response = netease_request('search/get/', params, deadline, post=True)
    except Exception:
        # Some network gateways block POST while allowing the public GET API.
        response = netease_request('search/get', params, deadline)
    songs = response.get('result', {}).get('songs', [])
    candidates = []
    for song in songs:
        candidates.append(dict(id=song['id'], trackName=song.get('name', ''),
            artistName=', '.join(a.get('name', '') for a in song.get('artists', song.get('ar', []))),
            duration=float(song.get('duration', song.get('dt', 0))) / 1000))
    plain = None
    for song in ranked(candidates, title, artist, duration)[:3]:
        try:
            payload = netease_request('song/lyric', dict(id=song['id'], lv=-1, kv=-1, tv=-1), deadline)
            raw = payload.get('lrc', {}).get('lyric', '')
            candidate = result(raw, '', 'NetEase:' + str(song['id']), duration)
            if candidate['mode'] == 'synced':
                return candidate
            if candidate['rows'] and plain is None:
                plain = candidate
        except Exception:
            continue
    return plain


def lookup(key):
    title, artist, album, duration, url = key
    local = unquote(urlparse(url).path) if urlparse(url).scheme == 'file' else ''
    paths = []
    plain_fallback = None
    if local:
        audio = Path(local)
        paths.append(audio.with_suffix('.lrc'))
        for suffix in ('.lrc', '.txt'):
            for stem in (title, artist + ' - ' + title):
                if '/' not in stem:
                    paths.append(audio.parent / (stem + suffix))
    for path in paths:
        try:
            if path.stat().st_size > 1_000_000:
                continue
            raw = path.read_text(encoding='utf-8-sig')
            found = result(raw, '', 'local:' + str(path), duration)
            if found['mode'] == 'synced':
                return found
            if found['rows'] and plain_fallback is None:
                plain_fallback = found
        except (OSError, UnicodeError):
            pass
    if not title:
        return result('', '', '', duration)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(json.dumps(key).encode()).hexdigest() + '.json')
    try:
        cached = json.loads(path.read_text())
        ttl = 86400 * 30 if cached.get('mode') == 'synced' else 3600 if cached['rows'] else 10
        if time.time() - cached['at'] < ttl:
            return cached
    except (OSError, ValueError, KeyError):
        pass
    found = result('', '', 'LRCLIB', duration)
    deadline = time.monotonic() + 30
    lrclib_deadline = min(deadline, time.monotonic() + 10)
    params = dict(track_name=title, artist_name=artist)
    if duration > 0:
        params['duration'] = round(duration)
    if album:
        params['album_name'] = album
    try:
        if artist:
            exact = request('get', params, lrclib_deadline)
            found = result(exact.get('syncedLyrics'), exact.get('plainLyrics'), 'LRCLIB:' + str(exact['id']), duration)
            if found['mode'] == 'plain' and plain_fallback is None:
                plain_fallback = found
    except Exception:
        pass
    if found['mode'] != 'synced':
        # Broad q search recovers misspellings and inconsistent artist tags.
        for query in dict.fromkeys([(title + ' ' + artist).strip(), title]):
            try:
                hits = request('search', dict(q=query), lrclib_deadline)
                matches = ranked(hits, title, artist, duration)
                if not matches and query == title and duration:
                    # A browser uploader may not be the recording artist.
                    matches = [row for row in ranked(hits, title, '', duration)
                        if similarity(title, row.get('trackName', '')) >= .85
                        and abs(float(row.get('duration') or 0) - duration) <= 15]
                for row in matches:
                    candidate = result(row.get('syncedLyrics'), row.get('plainLyrics'), 'LRCLIB:' + str(row['id']), duration)
                    if candidate['mode'] == 'synced':
                        found = candidate
                        break
                    if candidate['rows'] and plain_fallback is None:
                        plain_fallback = candidate
                if found['mode'] == 'synced':
                    break
            except Exception:
                continue
    if found['mode'] != 'synced':
        try:
            alternative = netease(title, artist, duration, min(deadline, time.monotonic() + 8))
            if alternative and alternative['mode'] == 'synced':
                found = alternative
            elif alternative and plain_fallback is None:
                plain_fallback = alternative
        except Exception:
            pass
    if found['mode'] != 'synced' and plain_fallback is None:
        try:
            from lyrics_web import web_lyrics
            plain, source = web_lyrics(title, artist, duration, deadline, ranked)
            if plain:
                plain_fallback = result('', plain, source, duration)
        except Exception:
            pass
    if found['mode'] != 'synced' and plain_fallback:
        found = plain_fallback
    found.update(at=time.time())
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(found, ensure_ascii=False))
    temporary.replace(path)
    return found

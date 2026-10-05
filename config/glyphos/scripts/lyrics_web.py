"""Bounded public-page lookup; search snippets are never treated as lyrics."""
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen


def fetch(url, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Web lyrics budget exhausted')
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; GlyphOS-Lyrics/4.0)',
                                   'Accept': 'text/html,application/json'})
    with urlopen(request, timeout=min(3, remaining)) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Web lyrics response too large')
    return raw.decode('utf-8', errors='replace')


class LyricsHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.excluded = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.depth:
            if tag == 'br':
                self.parts.append('\n')
            if tag not in ('br', 'img', 'hr', 'input', 'meta', 'link', 'wbr'):
                self.depth += 1
                if self.excluded:
                    self.excluded += 1
                elif attrs.get('data-exclude-from-selection') == 'true' or tag in ('script', 'style', 'button') or 'LyricsHeader' in attrs.get('class', ''):
                    self.excluded = 1
        elif attrs.get('data-lyrics-container') == 'true' or 'lyrics' in attrs.get('class', '').split():
            self.depth = 1

    def handle_startendtag(self, tag, attrs):
        if tag == 'br' and self.depth:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.depth and tag not in ('br', 'img', 'hr', 'input', 'meta', 'link', 'wbr'):
            self.depth -= 1
            if self.excluded:
                self.excluded -= 1
            if not self.depth:
                self.parts.append('\n')

    def handle_data(self, text):
        if self.depth and not self.excluded:
            self.parts.append(text)


class LinksHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        href = dict(attrs).get('href', '')
        if href.startswith('/url?'):
            params = parse_qs(urlparse(href).query)
            href = (params.get('q') or params.get('url') or [''])[0]
        self.links.append(href)


def web_lyrics(title, artist, duration, deadline, rank):
    urls = []
    try:
        query = urlencode({'q': (title + ' ' + artist).strip(), 'per_page': 5})
        response = json.loads(fetch('https://genius.com/api/search/multi?' + query, deadline))
        candidates = []
        for section in response.get('response', {}).get('sections', []):
            for hit in section.get('hits', []):
                song = hit.get('result', {})
                if song.get('title') and song.get('url'):
                    candidates.append(dict(trackName=song['title'], artistName=song.get('primary_artist', {}).get('name', ''), duration=duration, url=song['url']))
        urls = [row['url'] for row in rank(candidates, title, artist, duration)]
    except Exception:
        pass
    if not urls:
        try:
            query = urlencode({'q': f'{title} {artist} lyrics site:genius.com', 'num': 5})
            links = LinksHTML()
            links.feed(fetch('https://www.google.com/search?' + query, deadline))
            identity = lambda text: re.sub(r'[^\w]', '', text.casefold())
            for link in links.links:
                path = identity(urlparse(link).path)
                if identity(title) in path and (not artist or identity(artist) in path):
                    urls.append(link)
        except Exception:
            pass
    for url in list(dict.fromkeys(urls))[:2]:
        parsed = urlparse(url)
        # Only public Genius song pages. Never follow arbitrary result URLs.
        if parsed.scheme != 'https' or parsed.hostname not in ('genius.com', 'www.genius.com') or not parsed.path.endswith('-lyrics'):
            continue
        try:
            parser = LyricsHTML()
            parser.feed(fetch(url, deadline))
            plain = ''.join(parser.parts).strip()
            if plain:
                return plain, 'Genius:' + url
        except Exception:
            continue
    if artist:
        try:
            url = 'https://api.lyrics.ovh/v1/' + quote(artist, safe='') + '/' + quote(title, safe='')
            plain = json.loads(fetch(url, deadline)).get('lyrics', '')
            if plain.strip():
                return plain, 'lyrics.ovh'
        except Exception:
            pass
    return '', 'Web lookup pending'

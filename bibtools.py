#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers shared by update_bib.py and check_iris.py: lossless parsing and
editing of raw BibTeX entries (BibDesk style), and title/author matching."""

import os
import re
import json
import time
import html
import difflib
import hashlib
import unicodedata
from datetime import datetime

import requests

PREPRINT_VENUES = ('arxiv', 'techrxiv', 'preprints')
UNTRACKED_FIELDS = ('keywords', 'date-added', 'date-modified', 'abstract')


# --------------------------------------------------------------------------
# raw BibTeX parsing / editing
# --------------------------------------------------------------------------

def _match_brace(text, i):
    """Index just past the brace that closes the one at text[i]."""
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def iter_raw_entries(text):
    """Yield (start, end, raw_text) for each @type{key, ...} entry in `text`,
    skipping @comment/@preamble/@string blocks."""
    for m in re.finditer(r'^@(\w+)\s*\{', text, re.MULTILINE):
        if m.group(1).lower() in ('comment', 'preamble', 'string'):
            continue
        end = _match_brace(text, m.end() - 1)
        if end is not None:
            yield m.start(), end, text[m.start():end]


class Entry:
    """A BibTeX entry whose field values are kept verbatim (including their
    delimiters), so that untouched fields are written back unchanged."""

    def __init__(self, raw):
        self.raw = raw
        m = re.match(r'@(\w+)\s*\{\s*([^,\s]+)\s*,', raw)
        self.type, self.key = m.group(1), m.group(2)
        self.fields = []  # list of [name, raw_value]
        body, i = raw[m.end():len(raw) - 1], 0
        while True:
            fm = re.compile(r'\s*([\w\-:.]+)\s*=\s*').match(body, i)
            if not fm:
                break
            i = j = fm.end()
            depth, in_quotes = 0, False
            while j < len(body):
                c = body[j]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                elif c == '"' and depth == 0:
                    in_quotes = not in_quotes
                elif c == ',' and depth == 0 and not in_quotes:
                    break
                j += 1
            self.fields.append([fm.group(1), body[i:j].strip()])
            i = j + 1
        self.modified = False

    def get(self, name, default=''):
        """Field value with outer delimiters stripped."""
        for n, v in self.fields:
            if n.lower() == name.lower():
                if (v.startswith('{') and v.endswith('}')) or \
                        (v.startswith('"') and v.endswith('"')):
                    return v[1:-1]
                return v
        return default

    def has(self, name):
        return bool(self.get(name).strip())

    def set(self, name, value):
        """Set `name` to `value` (wrapped in braces). New fields are inserted
        in alphabetical order before the bdsk-* fields, as BibDesk does."""
        if name.lower() == 'keywords':
            raise ValueError('refusing to modify the keywords field')
        value = '{%s}' % value
        for f in self.fields:
            if f[0].lower() == name.lower():
                if f[1] != value:
                    f[1] = value
                    self.modified = True
                return
        pos = len(self.fields)
        for idx, (n, _) in enumerate(self.fields):
            if n.lower().startswith('bdsk-') or n.lower() > name.lower():
                pos = idx
                break
        self.fields.insert(pos, [name, value])
        self.modified = True

    def remove(self, name):
        if name.lower() == 'keywords':
            raise ValueError('refusing to modify the keywords field')
        n_before = len(self.fields)
        self.fields = [f for f in self.fields if f[0].lower() != name.lower()]
        self.modified |= len(self.fields) != n_before

    def set_type(self, etype):
        if etype != self.type:
            self.type = etype
            self.modified = True

    def touch(self):
        """Update BibDesk's date-modified field, if the entry has one."""
        if self.has('date-modified'):
            now = datetime.now().astimezone()
            self.set('date-modified', now.strftime('%Y-%m-%d %H:%M:%S %z'))

    def fingerprint(self):
        """Hash of the entry content, ignoring the fields that change without
        the publication changing (keywords, BibDesk bookkeeping)."""
        fields = sorted((n.lower(), ' '.join(self.get(n).split()))
                        for n, _ in self.fields
                        if n.lower() not in UNTRACKED_FIELDS
                        and not n.lower().startswith('bdsk-'))
        data = json.dumps([self.type.lower(), fields])
        return hashlib.sha1(data.encode('utf8')).hexdigest()[:16]

    def to_bibtex(self):
        if not self.modified:
            return self.raw
        lines = ['\t%s = %s' % (n, v) for n, v in self.fields]
        return '@%s{%s,\n%s}' % (self.type, self.key, ',\n'.join(lines))


def load_entries(path):
    """Return (text, [(start, end, Entry), ...]) for the .bib file `path`."""
    with open(path, encoding='utf8') as f:
        text = f.read()
    return text, [(s, e, Entry(raw)) for s, e, raw in iter_raw_entries(text)]


def save_entries(text, spans, path):
    """Write `text` to `path`, replacing the spans of modified entries."""
    out, last = [], 0
    for start, end, entry in spans:
        out.append(text[last:start])
        out.append(entry.to_bibtex())
        last = end
    out.append(text[last:])
    with open(path, 'w', encoding='utf8') as f:
        f.write(''.join(out))


def state_path(bib_path, suffix):
    """Default state file for `bib_path`, e.g. biblio.update-state.json."""
    return re.sub(r'\.bib$', '', bib_path) + '.%s-state.json' % suffix


def load_state(path):
    if not os.path.isfile(path):
        return {}
    with open(path, encoding='utf8') as f:
        return json.load(f)


def save_state(state, path):
    with open(path, 'w', encoding='utf8') as f:
        json.dump(state, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write('\n')


def approve(entries, keys, checked):
    """Record `entries` (or only `keys`, if given) as checked in `checked`
    ({key: fingerprint}); returns the number of entries approved."""
    by_key = {e.key: e for e in entries}
    for key in set(keys or ()) - set(by_key):
        print('Warning: no entry "%s" to approve' % key)
    for key in (keys or by_key):
        if key in by_key:
            checked[key] = by_key[key].fingerprint()
    return len(set(keys or by_key) & set(by_key))


def is_preprint(entry):
    if entry.type.lower() != 'article':
        return False
    journal = entry.get('journal').lower()
    return any(v in journal for v in PREPRINT_VENUES)


def arxiv_id(entry):
    """arXiv identifier of a preprint entry (from its url or volume)."""
    for name in ('eprint', 'volume'):
        m = re.fullmatch(r'\s*(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?\s*',
                         entry.get(name), re.IGNORECASE)
        if m and 'arxiv' in entry.get('journal').lower():
            return m.group(1)
    for name in ('url', 'bdsk-url-1', 'doi'):
        m = re.search(r'arxiv(?:\.org/(?:abs|pdf)/|\.)(\d{4}\.\d{4,5})',
                      entry.get(name), re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def normalize_doi(doi):
    doi = doi.strip().lower()
    doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi)
    return re.sub(r'^doi:\s*', '', doi)


# --------------------------------------------------------------------------
# text normalization and matching
# --------------------------------------------------------------------------

def plain(text):
    """Strip LaTeX markup, HTML/MathML tags and accents; lowercase."""
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    text = re.sub(r'\\[`\'^"~=.]', '', text)    # accents: \'e
    text = re.sub(r'\\[a-zA-Z]+\s*', '', text)  # \emph, \v ...
    text = text.replace('{', '').replace('}', '').replace('$', '')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def norm_title(title):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', plain(title)).split())


def title_similarity(a, b):
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def surnames(author_field):
    """Normalized surnames from a BibTeX author field."""
    names = []
    for person in re.split(r'\s+and\s+', author_field.strip()):
        person = person.strip()
        if not person or person.lower() == 'others':
            continue
        last = person.split(',')[0] if ',' in person else person.split()[-1]
        names.append(re.sub(r'[^a-z]', '', plain(last)))
    return [n for n in names if n]


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Http:
    """requests.Session with a per-host minimum delay and retries on 429/5xx."""

    def __init__(self, user_agent, delays=None, timeout=30):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent
        self.delays = delays or {}
        self.timeout = timeout
        self._last = {}

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def request(self, method, url, retries=4, **kwargs):
        host = requests.utils.urlparse(url).netloc
        for attempt in range(retries):
            wait = self._last.get(host, 0) + self.delays.get(host, 0) \
                - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.time()
            try:
                r = self.session.request(method, url, timeout=self.timeout,
                                         **kwargs)
            except requests.RequestException:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get('Retry-After', 2 ** attempt + 1)))
                continue
            return r
        return None

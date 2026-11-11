#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update the entries of a BibTeX file with data from Crossref, arXiv and
Semantic Scholar:

 - pre-prints (arXiv, TechRxiv, ...) that have since been published are
   converted to the published version (entry type, journal/booktitle, DOI,
   volume, number, pages, year, url);
 - published entries get their missing DOI, volume, number and pages filled
   in (and the year updated when an early-access paper gets an issue).

Existing values of published entries are never overwritten (except the
year, as above), the KEYWORDS field is never touched, and entry keys are
kept unchanged. Unmodified entries are written back byte-for-byte."""

import os
import re
import sys
import html
import shutil
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime

from bibtools import (Http, load_entries, save_entries, is_preprint,
                      arxiv_id, normalize_doi, title_similarity, surnames,
                      plain, state_path, load_state, save_state, approve)
from html_report import write_html_report

CROSSREF = 'https://api.crossref.org/works'
ARXIV = 'https://export.arxiv.org/api/query'
S2_BATCH = 'https://api.semanticscholar.org/graph/v1/paper/batch'

# Crossref types we accept as "the published version", and the BibTeX entry
# type / venue field each one maps to
CROSSREF_TYPES = {
    'journal-article': ('article', 'journal'),
    'proceedings-article': ('inproceedings', 'booktitle'),
    'book-chapter': ('incollection', 'booktitle'),
}
VENUE_FIELDS = ('journal', 'booktitle')
SKIP_TYPES = ('proceedings', 'periodical', 'phdthesis', 'mastersthesis',
              'misc', 'unpublished', 'techreport', 'manual', 'booklet')
NON_CROSSREF_DOI = ('10.48550/',  # arXiv (DataCite)
                    '10.5281/')   # Zenodo (DataCite)
# pre-print servers that Crossref lists as journals
PREPRINT_DOI = ('10.2139/',   # SSRN
                '10.36227/',  # TechRxiv
                '10.20944/',  # Preprints.org
                '10.21203/')  # Research Square
PREPRINT_VENUE_RE = re.compile(r'ssrn|rxiv|preprint|research square', re.I)


def bib_escape(text):
    """Crossref strings -> BibTeX: drop markup, escape special chars."""
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'(?<!\\)([&%#_])', r'\\\1', text)


def date_year(item, *keys):
    for k in keys:
        parts = item.get(k, {}).get('date-parts', [[None]])
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return None


def crossref_record(item):
    """Normalize a Crossref work into the fields we may copy to BibTeX."""
    etype, venue_field = CROSSREF_TYPES.get(item.get('type'), (None, None))
    if item.get('type') == 'journal-article':
        year = date_year(item, 'published-print', 'issued')
    else:
        year = date_year(item, 'issued', 'published-print',
                         'published-online')
    pages = item.get('page') or ''
    # journals without page numbers (e.g. Springer) cite papers by article
    # number, which goes in the number field; Elsevier repeats it as page
    number = item.get('article-number') or ''
    if not number or number == pages:
        number = item.get('issue') or ''
    pages = re.sub(r'\s*[-–]+\s*', '--', pages)
    # Springer chapters list [series, book title]; LNCS ones are conferences
    container = item.get('container-title') or ['']
    series = container[0] if len(container) > 1 else ''
    if etype == 'incollection' and re.match(r'lecture notes', series, re.I):
        etype = 'inproceedings'
    # not a published version (type None is never used to convert pre-prints)
    if item.get('DOI', '').lower().startswith(PREPRINT_DOI) or \
            PREPRINT_VENUE_RE.search(container[-1]):
        etype = None
    return {
        'crossref_type': item.get('type'),
        'type': etype,
        'venue_field': venue_field,
        'venue': bib_escape(container[-1]),
        'series': bib_escape(series),
        'title': ': '.join(t[0] for t in (item.get('title'),
                                          item.get('subtitle')) if t),
        'surnames': [plain(a.get('family', '')) for a in
                     item.get('author', [])],
        'authors': [' '.join(filter(None, (a.get('given'), a.get('family'))))
                    or a.get('name', '') for a in item.get('author', [])],
        'doi': item.get('DOI', '').lower(),
        'volume': item.get('volume', ''),
        'number': number,
        'pages': pages,
        'year': year,
        'publisher': bib_escape(item.get('publisher', '')),
    }


class Finder:
    def __init__(self, http, min_sim, review_sim):
        self.http = http
        self.min_sim = min_sim
        self.review_sim = review_sim

    def by_doi(self, doi):
        r = self.http.get('%s/%s' % (CROSSREF, doi))
        if r is None or r.status_code != 200:
            return None
        return crossref_record(r.json()['message'])

    def search(self, entry):
        """Crossref bibliographic search by title (+ first author).
        Returns (records sorted by title similarity, desc) as (sim, rec)."""
        title = plain(entry.get('title'))
        params = {'query.bibliographic': title, 'rows': 10,
                  'filter': ','.join('type:' + t for t in CROSSREF_TYPES)}
        authors = surnames(entry.get('author'))
        if authors:
            params['query.author'] = authors[0]
        r = self.http.get(CROSSREF, params=params)
        if r is None or r.status_code != 200:
            return []
        found = []
        for item in r.json()['message']['items']:
            rec = crossref_record(item)
            sim = title_similarity(entry.get('title'), rec['title'])
            if sim >= self.review_sim and rec['type'] and \
                    self.authors_overlap(entry, rec) and \
                    not rec['doi'].startswith(NON_CROSSREF_DOI):
                found.append((sim, rec))
        return sorted(found, key=lambda x: -x[0])

    @staticmethod
    def authors_overlap(entry, rec):
        bib = set(surnames(entry.get('author')))
        return not bib or not rec['surnames'] or bool(bib & set(
            re.sub(r'[^a-z]', '', s) for s in rec['surnames']))


def arxiv_metadata(http, ids):
    """{arxiv_id: {'doi':..., 'journal_ref':...}} from the arXiv API."""
    out = {}
    ns = {'a': 'http://www.w3.org/2005/Atom',
          'x': 'http://arxiv.org/schemas/atom'}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        r = http.get(ARXIV, params={'id_list': ','.join(chunk),
                                    'max_results': len(chunk)})
        if r is None or r.status_code != 200:
            continue
        for e in ET.fromstring(r.content).findall('a:entry', ns):
            m = re.search(r'abs/(\d{4}\.\d{4,5})', e.findtext('a:id', '', ns))
            if m:
                out[m.group(1)] = {
                    'doi': e.findtext('x:doi', '', ns).strip(),
                    'journal_ref': e.findtext('x:journal_ref', '', ns).strip()}
    return out


def s2_metadata(http, ids, api_key=None):
    """{arxiv_id: {'doi', 'venue', 'year'}} from Semantic Scholar."""
    out = {}
    ids = sorted(set(ids))
    headers = {'x-api-key': api_key} if api_key else {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        r = http.post(S2_BATCH, params={
            'fields': 'externalIds,venue,publicationVenue,year'},
            json={'ids': ['arXiv:' + a for a in chunk]}, headers=headers)
        if r is None or r.status_code != 200:
            print('Warning: Semantic Scholar unavailable (%s); set '
                  'S2_API_KEY or use --no-s2'
                  % (r.status_code if r is not None else 'no response'))
            continue
        for aid, paper in zip(chunk, r.json()):
            if not paper:
                continue
            venue = (paper.get('publicationVenue') or {}).get('name') \
                or paper.get('venue') or ''
            out[aid] = {'doi': (paper.get('externalIds') or {}).get('DOI', ''),
                        'venue': venue, 'year': paper.get('year')}
    return out


def fill_missing(entry, rec, changes):
    """Fill in the missing fields of a published entry from `rec`."""
    def put(name, value):
        old = entry.get(name)
        entry.set(name, value)
        changes.append((name, old, value))

    had_volume = entry.has('volume')
    if not entry.has('doi') and rec['doi']:
        put('doi', rec['doi'])
    for name in ('volume', 'number', 'pages'):
        if name == 'number' and entry.type.lower() != 'article':
            continue
        # early-access articles have placeholder pages (e.g. 1--18)
        if name == 'pages' and entry.type.lower() == 'article' and \
                not rec['volume']:
            continue
        if not entry.has(name) and rec[name]:
            put(name, rec[name])
    # an early-access article that has now been assigned to an issue
    if entry.type.lower() == 'article' and not had_volume and \
            rec['volume'] and rec['year'] and rec['year'] != entry.get('year'):
        put('year', rec['year'])


def convert_preprint(entry, rec, changes):
    """Turn a pre-print entry into its published version `rec`."""
    def put(name, value):
        old = entry.get(name)
        entry.set(name, value)
        changes.append((name, old, value))

    def drop(name):
        if entry.has(name):
            changes.append((name, entry.get(name), None))
            entry.remove(name)

    if rec['type'] != entry.type.lower():
        changes.append(('@type', entry.type, rec['type']))
        entry.set_type(rec['type'])
    for f in VENUE_FIELDS:
        if f != rec['venue_field']:
            drop(f)
    put(rec['venue_field'], rec['venue'])
    for name in ('volume', 'number', 'pages'):
        if rec[name] and not (name == 'pages' and rec['type'] == 'article'
                              and not rec['volume']):
            put(name, rec[name])
        else:  # e.g. the arXiv id stored in the volume field
            drop(name)
    put('doi', rec['doi'])
    if rec['year']:
        put('year', rec['year'])
    put('url', 'https://doi.org/' + rec['doi'])
    for name in ('series', 'publisher'):
        if rec['type'] != 'article' and rec[name] and not entry.has(name):
            put(name, rec[name])


def is_final(entry):
    """True for papers published with all their final details, which are
    the only ones that can be approved. Pre-prints never are; articles need
    a volume and pages (or an article number), so early-access ones are
    re-checked until they get an issue; conference papers and chapters need
    pages or a DOI, unless they are 5+ years old (they will not get them)."""
    etype = entry.type.lower()
    if is_preprint(entry):
        return False
    if etype == 'article':
        return entry.has('volume') and \
            (entry.has('pages') or entry.has('number'))
    if etype in ('inproceedings', 'conference', 'incollection', 'inbook'):
        year = entry.get('year')
        return entry.has('pages') or entry.has('doi') or (
            year.isdigit() and int(year) <= datetime.now().year - 5)
    return True


def print_changes(entry, changes, note=''):
    print('\n[%s] %s' % (entry.key, entry.get('title')[:90]))
    for name, old, new in changes:
        if new is None:
            print('   - %-10s %s' % (name, old))
        elif old:
            print('   ~ %-10s %s  ->  %s' % (name, old, new))
        else:
            print('   + %-10s %s' % (name, new))
    if note:
        print(note)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('-i', '--input', metavar='BIB', default='biblio.bib',
                        help='input .bib file (default: biblio.bib)')
    parser.add_argument('-o', '--output', metavar='BIB',
                        help='output .bib file (default: <input>.updated.bib)')
    parser.add_argument('--in-place', action='store_true',
                        help='overwrite the input file (a .bak copy is kept)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='only report the changes, write nothing')
    parser.add_argument('-k', '--keys', nargs='+', metavar='KEY',
                        help='only process these entry keys')
    parser.add_argument('-x', '--exclude', nargs='+', metavar='KEY',
                        default=[], help='do not process these entry keys '
                                         '(e.g. wrong matches)')
    parser.add_argument('--report', metavar='HTML',
                        help='HTML report of the changes, to review them '
                             '(default: <input>.changes.html)')
    parser.add_argument('--preprints-only', action='store_true',
                        help='only look for published versions of '
                             'pre-prints')
    parser.add_argument('--min-sim', type=float, default=0.93,
                        help='title similarity required to apply a '
                             'Crossref search match (default: 0.93)')
    parser.add_argument('--review-sim', type=float, default=0.80,
                        help='matches above this similarity, but below '
                             '--min-sim, are only reported (default: 0.80)')
    parser.add_argument('--mailto', default=os.environ.get('CROSSREF_MAILTO'),
                        help='e-mail sent to Crossref to use its faster '
                             '"polite" pool (or set CROSSREF_MAILTO)')
    parser.add_argument('--no-s2', action='store_true',
                        help='do not query Semantic Scholar (set '
                             'S2_API_KEY to avoid its rate limits)')
    parser.add_argument('--incremental', action='store_true',
                        help='skip the entries approved with --approve and '
                             'not modified since (pre-prints and papers '
                             'without their final details are always '
                             're-checked)')
    parser.add_argument('--approve', nargs='*', metavar='KEY',
                        help='mark these entries (default: all) as checked '
                             'in the state file, and exit; only final papers '
                             'are approved')
    parser.add_argument('--state', metavar='JSON',
                        help='state file for --incremental/--approve '
                             '(default: <input>.update-state.json)')
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.exit('File "%s" does not exist.' % args.input)
    output = args.input if args.in_place else (
        args.output or re.sub(r'\.bib$', '', args.input) + '.updated.bib')

    state_file = args.state or state_path(args.input, 'update')
    state = load_state(state_file)
    checked = state.setdefault('checked', {})

    text, spans = load_entries(args.input)
    entries = [e for _, _, e in spans
               if e.type.lower() not in SKIP_TYPES
               and (not args.keys or e.key in args.keys)
               and e.key not in args.exclude]
    # only final papers can be approved: drop any that is not final anymore
    for _, _, e in spans:
        if e.key in checked and not is_final(e):
            del checked[e.key]
    if args.approve is not None:
        final = [e for e in entries if is_final(e)]
        not_final = [e.key for e in entries if not is_final(e)
                     and (not args.approve or e.key in args.approve)]
        n = approve(final, [k for k in args.approve if k not in not_final],
                    checked) if args.approve else approve(final, None, checked)
        save_state(state, state_file)
        print('%d entries approved in "%s".' % (n, state_file))
        if not_final:
            print('%d pre-prints / papers without their final details not '
                  'approved, they will be re-checked: %s'
                  % (len(not_final), ' '.join(not_final)))
        return
    if args.incremental:
        n_before = len(entries)
        entries = [e for e in entries if not is_final(e)
                   or checked.get(e.key) != e.fingerprint()]
        print('Incremental: skipping %d approved entries, checking %d.'
              % (n_before - len(entries), len(entries)))

    ua = 'bib2md-update/1.0 (https://github.com/battistabiggio/bib2md'
    ua += '; mailto:%s)' % args.mailto if args.mailto else ')'
    http = Http(ua, delays={'api.crossref.org': 0.2 if args.mailto else 1.0,
                            'export.arxiv.org': 3.0,
                            'api.semanticscholar.org': 1.1})
    finder = Finder(http, args.min_sim, args.review_sim)

    preprints = [e for e in entries if is_preprint(e)]
    if args.preprints_only:
        entries = preprints

    ids = [a for a in map(arxiv_id, preprints) if a]
    print('Querying arXiv for %d pre-prints...' % len(ids))
    arxiv = arxiv_metadata(http, ids)
    s2 = {}
    if not args.no_s2:
        print('Querying Semantic Scholar...')
        s2 = s2_metadata(http, ids, os.environ.get('S2_API_KEY'))

    updated, to_review, manual = [], [], []
    for i, entry in enumerate(entries, 1):
        print('\r(%d/%d) %-40s' % (i, len(entries), entry.key[:40]),
              end='', file=sys.stderr, flush=True)
        changes, match = [], None
        before = {'title': entry.get('title'), 'author': entry.get('author'),
                  'year': entry.get('year'),
                  'venue': entry.get('journal') or entry.get('booktitle'),
                  'arxiv': arxiv_id(entry) if is_preprint(entry) else None}
        if is_preprint(entry):
            aid = arxiv_id(entry)
            candidates = []
            # DOIs of the published version declared on arXiv / S2
            how = 'Crossref title search'
            for source, doi in (('arXiv', arxiv.get(aid, {}).get('doi')),
                                ('Semantic Scholar',
                                 s2.get(aid, {}).get('doi'))):
                if doi and not doi.lower().startswith(NON_CROSSREF_DOI):
                    rec = finder.by_doi(doi)
                    if rec and rec['type']:
                        sim = title_similarity(entry.get('title'),
                                               rec['title'])
                        # trust the declared DOI even if the title changed a bit
                        candidates.append(
                            (sim if sim < 0.5 else max(sim, args.min_sim),
                             rec))
                        how = 'DOI declared on %s' % source
                        break
            if not candidates:
                candidates = finder.search(entry)
            if candidates and candidates[0][0] >= args.min_sim:
                convert_preprint(entry, candidates[0][1], changes)
                match = (how, candidates[0][1])
            elif candidates:
                to_review.append((entry, candidates[0]))
            elif aid in s2 and s2[aid]['venue'] and \
                    not re.search(r'arxiv|rxiv|ssrn|preprint',
                                  s2[aid]['venue'], re.I):
                manual.append((entry, 'Semantic Scholar: %s (%s)'
                               % (s2[aid]['venue'], s2[aid]['year'])))
            elif aid in arxiv and arxiv[aid]['journal_ref']:
                manual.append((entry, 'arXiv journal-ref: %s'
                               % arxiv[aid]['journal_ref']))
        else:
            doi = normalize_doi(entry.get('doi'))
            if doi and not doi.startswith(NON_CROSSREF_DOI):
                if all(entry.has(f) for f in ('volume', 'pages')):
                    continue  # nothing to fill in
                rec = finder.by_doi(doi)
                if rec:
                    fill_missing(entry, rec, changes)
                    match = ('Crossref record of the entry DOI', rec)
            elif not doi:
                candidates = [(s, r) for s, r in finder.search(entry)
                              if not entry.get('year').isdigit()
                              or not r['year']
                              or abs(int(r['year']) -
                                     int(entry.get('year'))) <= 2]
                if candidates and candidates[0][0] >= args.min_sim:
                    fill_missing(entry, candidates[0][1], changes)
                    match = ('Crossref title search', candidates[0][1])
                elif candidates:
                    to_review.append((entry, candidates[0]))
        if changes:
            entry.touch()
            note = ''
            if any(c[0] == '@type' and c[2] == 'inproceedings'
                   for c in changes):
                note = '   ! now a conference paper: add TOP_CONF to ' \
                       'keywords if the venue is A* (ICORE)'
            print('\r' + ' ' * 50 + '\r', end='', file=sys.stderr)
            print_changes(entry, changes, note)
            updated.append({'entry': entry, 'before': before,
                            'changes': changes, 'how': match[0],
                            'rec': match[1], 'note': note.strip(' !')})
    print('\r' + ' ' * 50 + '\r', end='', file=sys.stderr)
    n_updated = len(updated)

    if to_review:
        print('\n\nPossible matches NOT applied (title similarity below '
              '%.2f), please check:' % args.min_sim)
        for entry, (sim, rec) in to_review:
            print('\n[%s] %s\n   %.2f  %s\n         %s, %s  https://doi.org/%s'
                  % (entry.key, entry.get('title'), sim, rec['title'],
                     rec['venue'], rec['year'], rec['doi']))
    if manual:
        print('\n\nPre-prints that seem published, but without a usable '
              'DOI (update manually):')
        for entry, info in manual:
            print('\n[%s] %s\n   %s' % (entry.key, entry.get('title'), info))

    print('\n%d entries updated.' % n_updated)
    report = args.report or re.sub(r'\.bib$', '', args.input) + \
        '.changes.html'
    write_html_report(report, updated, to_review, manual, args, output)
    print('Review the changes in "%s".' % report)
    if args.dry_run or not n_updated:
        return
    if args.in_place:
        shutil.copyfile(args.input, args.input + '.bak')
    save_entries(text, spans, output)
    print('Written to "%s"%s.' % (output, ' (backup in "%s.bak")'
                                  % args.input if args.in_place else ''))


if __name__ == '__main__':
    main()

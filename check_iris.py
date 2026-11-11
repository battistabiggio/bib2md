#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List the published entries of a BibTeX file (pre-prints excluded) that are
missing from an IRIS institutional archive (default: iris.unica.it).

The author's IRIS records are retrieved from the archive's search page,
filtered by the author's IRIS identifier (e.g. rp01234), and their DOIs from
the OAI-PMH interface. A BibTeX entry is considered archived if its DOI or
its title matches one of those records. Entries still unmatched are then
searched by title across the whole archive, to spot records that exist but
are not linked to the author's profile."""

import os
import re
import sys
import html
import argparse
from urllib.parse import urljoin

from bibtools import (Http, load_entries, is_preprint, normalize_doi,
                      norm_title, title_similarity, state_path, load_state,
                      save_state, approve)
from html_report import write_iris_report

SKIP_TYPES = ('misc', 'unpublished', 'techreport', 'manual', 'booklet')
OAI_ID = 'oai:{host}:{handle}'

ITEM_RE = re.compile(
    r'href="/handle/(\d+/\d+)"[^>]*>.*?<h5[^>]*>(.*?)</h5>.*?'
    r'<p class="mb-1">(.*?)</p>', re.DOTALL)
TOTAL_RE = re.compile(r'\d+\s*-\s*\d+\s+(?:di|of)\s+(\d+)')


def clean(text):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', text)).split())


def parse_results(page):
    items = []
    for handle, title, info in ITEM_RE.findall(page):
        info = clean(info)
        year = info[:4] if info[:4].isdigit() else ''
        items.append({'handle': handle, 'title': clean(title),
                      'year': year, 'authors': info[11:]})
    return items


def search(http, base, rpp=100, **params):
    """All the records returned by an IRIS (DSpace-CRIS) simple search."""
    items, start = [], 0
    while True:
        r = http.get(urljoin(base, '/simple-search'),
                     params=dict(params, rpp=rpp, start=start))
        if r is not None and r.status_code == 404:
            return items  # IRIS answers 404 when nothing is found
        if r is None or r.status_code != 200:
            sys.exit('IRIS search failed (%s)'
                     % (r.status_code if r is not None else 'no response'))
        page_items = parse_results(r.text)
        items += page_items
        m = TOTAL_RE.search(r.text)
        total = int(m.group(1)) if m else len(items)
        start += rpp
        if not page_items or start >= total:
            return items


def author_records(http, base, author_id):
    return search(http, base, query='', filtername='author',
                  filterquery=author_id, filtertype='authority',
                  sort_by='dc.date.issued_dt', order='desc')


def record_dois(http, base, handle):
    host = re.sub(r'^https?://', '', base).strip('/')
    r = http.get(urljoin(base, '/oai/request'), params={
        'verb': 'GetRecord', 'metadataPrefix': 'oai_dc',
        'identifier': OAI_ID.format(host=host, handle=handle)})
    if r is None or r.status_code != 200:
        return set()
    ids = re.findall(r'<dc:identifier>\s*([^<]+?)\s*</dc:identifier>', r.text)
    return {normalize_doi(i) for i in ids
            if re.match(r'(https?://(dx\.)?doi\.org/)?10\.', i.strip())}


def best_match(entry, records):
    """(similarity, record) of the IRIS record whose title is closest."""
    best = (0.0, None)
    title = norm_title(entry.get('title'))
    for rec in records:
        sim = title_similarity(entry.get('title'), rec['title'])
        # one title extends the other (e.g. a subtitle added / removed)
        other = norm_title(rec['title'])
        short, full = sorted((title, other), key=len)
        if len(short) >= 25 and full.startswith(short):
            sim = max(sim, 0.99)
        if sim > best[0]:
            best = (sim, rec)
    return best


def describe(entry):
    venue = entry.get('journal') or entry.get('booktitle') or \
        entry.get('publisher') or entry.get('school')
    doi = normalize_doi(entry.get('doi'))
    line = '[%s] %s (%s) %s. %s' % (entry.key, entry.type.lower(),
                                    entry.get('year'), entry.get('title'),
                                    venue)
    line = re.sub(r'[{}]', '', line)
    return line + ('  https://doi.org/%s' % doi if doi else '')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('-i', '--input', metavar='BIB', default='biblio.bib',
                        help='input .bib file (default: biblio.bib)')
    parser.add_argument('-a', '--author-id', required=True,
                        help='IRIS author identifier, as found in the '
                             'author facet of the IRIS search page, '
                             'e.g. rp01234')
    parser.add_argument('--base-url', default='https://iris.unica.it',
                        help='IRIS base url (default: https://iris.unica.it)')
    parser.add_argument('-o', '--output', metavar='MD',
                        help='also write the report to this markdown file')
    parser.add_argument('--html', metavar='HTML',
                        help='HTML version of the report, with a checkbox per '
                             'entry (default: <input>.missing-iris.html)')
    parser.add_argument('--min-sim', type=float, default=0.90,
                        help='title similarity to consider an entry archived '
                             '(default: 0.90)')
    parser.add_argument('--review-sim', type=float, default=0.75,
                        help='matches above this similarity, but below '
                             '--min-sim, are reported as possible matches '
                             '(default: 0.75)')
    parser.add_argument('--no-doi', action='store_true',
                        help='match by title only (skips one OAI-PMH request '
                             'per IRIS record)')
    parser.add_argument('--no-global-search', action='store_true',
                        help='do not search unmatched titles across the '
                             'whole archive')
    parser.add_argument('--skip-types', nargs='*', default=list(SKIP_TYPES),
                        help='BibTeX entry types to ignore (default: %s)'
                             % ' '.join(SKIP_TYPES))
    parser.add_argument('--incremental', action='store_true',
                        help='skip the entries already found in IRIS or '
                             'approved with --approve, and not modified '
                             'since; reuse the cached IRIS DOIs')
    parser.add_argument('--approve', nargs='*', metavar='KEY',
                        help='mark these entries (default: all) as checked, '
                             'e.g. those you will not upload, and exit')
    parser.add_argument('--state', metavar='JSON',
                        help='state file for --incremental/--approve '
                             '(default: <input>.iris-state.json)')
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.exit('File "%s" does not exist.' % args.input)

    _, spans = load_entries(args.input)
    skip = {t.lower() for t in args.skip_types}
    entries = [e for _, _, e in spans
               if not is_preprint(e) and e.type.lower() not in skip]
    n_published = len(entries)

    # checked: {key: fingerprint} of the entries found in IRIS or approved;
    # found: {key: IRIS handle}; dois: {IRIS handle: [DOIs]}
    state_file = args.state or state_path(args.input, 'iris')
    state = load_state(state_file)
    checked = state.setdefault('checked', {})
    found = state.setdefault('found', {})
    doi_cache = state.setdefault('dois', {})
    if args.approve is not None:
        n = approve(entries, args.approve, checked)
        save_state(state, state_file)
        print('%d entries approved in "%s".' % (n, state_file))
        return
    if args.incremental:
        entries = [e for e in entries
                   if checked.get(e.key) != e.fingerprint()]
        print('Incremental: skipping %d checked entries, checking %d.'
              % (n_published - len(entries), len(entries)))

    http = Http('bib2md-check-iris/1.0', delays={
        re.sub(r'^https?://', '', args.base_url).strip('/'): 0.3})
    print('Fetching IRIS records of author %s...' % args.author_id)
    records = author_records(http, args.base_url, args.author_id)
    print('%d IRIS records, %d published BibTeX entries.'
          % (len(records), n_published))
    doi_index = {}
    if not args.no_doi and entries:
        for i, rec in enumerate(records, 1):
            print('\rFetching DOIs from OAI-PMH (%d/%d)'
                  % (i, len(records)), end='', file=sys.stderr, flush=True)
            if not args.incremental or rec['handle'] not in doi_cache:
                doi_cache[rec['handle']] = sorted(
                    record_dois(http, args.base_url, rec['handle']))
            for doi in doi_cache[rec['handle']]:
                doi_index[doi] = rec
        print(file=sys.stderr)

    missing, possible, unlinked = [], [], []
    for i, entry in enumerate(entries, 1):
        doi = normalize_doi(entry.get('doi'))
        sim, rec = best_match(entry, records)
        if doi and doi in doi_index:
            sim, rec = 1.0, doi_index[doi]
        if sim >= args.min_sim:
            checked[entry.key] = entry.fingerprint()
            found[entry.key] = rec['handle']
            continue
        if not args.no_global_search:
            print('\rSearching unmatched titles in IRIS (%d/%d)'
                  % (i, len(entries)), end='', file=sys.stderr, flush=True)
            words = norm_title(entry.get('title')).split()[:12]
            hits = search(http, args.base_url, rpp=10, query=' '.join(words))
            g_sim, g_rec = best_match(entry, hits[:10])
            if g_sim >= args.min_sim:
                unlinked.append((entry, g_sim, g_rec))
                continue
            if g_sim > sim:
                sim, rec = g_sim, g_rec
        if sim >= args.review_sim:
            possible.append((entry, sim, rec))
        else:
            missing.append(entry)
    print('\r' + ' ' * 60 + '\r', end='', file=sys.stderr)
    save_state(state, state_file)

    def year(e):
        y = e.get('year')
        return int(y) if y.isdigit() else 0

    url = lambda rec: urljoin(args.base_url, '/handle/' + rec['handle'])
    lines = ['# Published entries missing from IRIS (%s)\n' % args.author_id,
             '%d of %d %spublished entries not found.\n'
             % (len(missing), len(entries),
                'new or modified ' if args.incremental else '')]
    for entry in sorted(missing, key=year, reverse=True):
        lines.append('- [ ] ' + describe(entry))
    if possible:
        lines.append('\n## Possible matches, please check\n')
        for entry, sim, rec in sorted(possible, key=lambda x: -year(x[0])):
            lines.append('- [ ] %s\n    - %.2f IRIS: %s (%s) %s'
                         % (describe(entry), sim, rec['title'],
                            rec['year'], url(rec)))
    if unlinked:
        lines.append('\n## In IRIS, but not linked to author %s\n'
                     % args.author_id)
        for entry, sim, rec in sorted(unlinked, key=lambda x: -year(x[0])):
            lines.append('- [ ] %s\n    - IRIS: %s (%s) %s'
                         % (describe(entry), rec['authors'], rec['year'],
                            url(rec)))
    report = '\n'.join(lines) + '\n'
    print('\n' + report)
    if args.output:
        with open(args.output, 'w', encoding='utf8') as f:
            f.write(report)
        print('Report written to "%s".' % args.output)
    html_path = args.html or re.sub(r'\.bib$', '', args.input) + \
        '.missing-iris.html'
    write_iris_report(html_path, missing, possible, unlinked, len(entries),
                      args)
    print('HTML report written to "%s".' % html_path)


if __name__ == '__main__':
    main()

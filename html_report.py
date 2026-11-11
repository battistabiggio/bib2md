#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-contained HTML report of the changes made by update_bib.py, to review
them one by one: each updated entry is shown next to the record it was
matched to, with its field changes, and can be marked as correct or wrong.
The page then builds the commands to apply the correct changes only and to
approve the reviewed entries."""

import re
import json
import unicodedata
from html import escape
from datetime import datetime

from bibtools import title_similarity

CSS = """
:root {
  --bg: #f6f7f9; --card: #ffffff; --text: #1d232b; --muted: #5c6773;
  --border: #dde2e8; --accent: #2f6fdf; --code: #eef1f5;
  --add-bg: #e6f5ea; --add: #1d7a3a; --del-bg: #fbe9e9; --del: #b42323;
  --mod-bg: #fff4dc; --mod: #8a5a00; --ok: #1d7a3a; --bad: #b42323;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12161b; --card: #1a2027; --text: #e3e8ee; --muted: #94a0ad;
    --border: #2c343e; --accent: #6b9bff; --code: #232b34;
    --add-bg: #15301e; --add: #6fd38f; --del-bg: #3a1a1a; --del: #ff8a8a;
    --mod-bg: #362a10; --mod: #f0c060; --ok: #6fd38f; --bad: #ff8a8a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
  Helvetica, Arial, sans-serif; padding-bottom: 170px; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 36px 0 12px; }
.meta { color: var(--muted); font-size: 13px; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin: 20px 0 12px; }
.toolbar input { flex: 1 1 220px; padding: 7px 10px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--card);
  color: var(--text); font: inherit; }
button { font: inherit; font-size: 13px; cursor: pointer; padding: 5px 11px;
  border-radius: 6px; border: 1px solid var(--border);
  background: var(--card); color: var(--text); }
button.on { border-color: var(--accent); color: var(--accent);
  font-weight: 600; }
.card { background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin: 0 0 12px; }
.card.correct { border-left: 4px solid var(--ok); }
.card.wrong { border-left: 4px solid var(--bad); }
.card-head { display: flex; gap: 12px; justify-content: space-between;
  align-items: flex-start; flex-wrap: wrap; }
.key { font-weight: 600; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 999px;
  background: var(--code); color: var(--muted); }
.badge.warn { background: var(--mod-bg); color: var(--mod); }
.verdict button.ok.on { border-color: var(--ok); color: var(--ok); }
.verdict button.bad.on { border-color: var(--bad); color: var(--bad); }
.title { margin: 6px 0 10px; font-weight: 500; }
.tables { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 760px) { .tables { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; font-size: 13px;
  table-layout: fixed; }
th, td { text-align: left; vertical-align: top; padding: 4px 6px;
  border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }
th { color: var(--muted); font-weight: 600; }
td.f { width: 78px; color: var(--muted); }
caption { text-align: left; font-size: 12px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .04em; padding-bottom: 4px; }
tr.add td.new { background: var(--add-bg); color: var(--add); }
tr.mod td.old, tr.del td.old { background: var(--del-bg); color: var(--del);
  text-decoration: line-through; }
tr.mod td.new { background: var(--mod-bg); color: var(--mod); }
.differs { color: var(--mod); font-weight: 600; }
.links { margin-top: 8px; font-size: 13px; display: flex; gap: 14px;
  flex-wrap: wrap; }
a { color: var(--accent); }
.note { margin-top: 8px; font-size: 13px; color: var(--mod); }
.hidden { display: none; }
.bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--card);
  border-top: 1px solid var(--border); padding: 10px 16px; }
.bar-inner { max-width: 1100px; margin: 0 auto; }
.cmd { display: flex; gap: 8px; align-items: center; margin-top: 6px; }
.cmd code { flex: 1; background: var(--code); padding: 5px 8px;
  border-radius: 6px; overflow-x: auto; white-space: nowrap; }
.cmd span { width: 150px; flex: none; font-size: 12px; color: var(--muted); }
@media (max-width: 760px) { .cmd span { width: 90px; } }
.empty { color: var(--muted); }
"""

JS = """
const KEY = 'bibreview:' + document.body.dataset.id;
let verdicts = {};
try { verdicts = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) {}
const cards = [...document.querySelectorAll('.card[data-key]')];
const inp = document.body.dataset.input, out = document.body.dataset.output;
let filter = 'all';

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(verdicts)); } catch (e) {}
}
function render() {
  const q = document.getElementById('q').value.toLowerCase();
  for (const c of cards) {
    const v = verdicts[c.dataset.key] || '';
    c.classList.toggle('correct', v === 'ok');
    c.classList.toggle('wrong', v === 'bad');
    c.querySelector('.ok').classList.toggle('on', v === 'ok');
    c.querySelector('.bad').classList.toggle('on', v === 'bad');
    const show = (filter === 'all' || (filter === 'todo' && !v) ||
                  filter === v) && c.textContent.toLowerCase().includes(q);
    c.classList.toggle('hidden', !show);
  }
  const keys = cards.map(c => c.dataset.key);
  const ok = keys.filter(k => verdicts[k] === 'ok');
  const bad = keys.filter(k => verdicts[k] === 'bad');
  document.getElementById('count').textContent =
    ok.length + ' correct, ' + bad.length + ' wrong, ' +
    (keys.length - ok.length - bad.length) + ' to review';
  const rerun = 'python update_bib.py -i ' + inp + ' --in-place' +
    (bad.length ? ' --exclude ' + bad.join(' ') : '');
  let apply;
  if (document.body.dataset.inplace === '1') {
    apply = bad.length ? 'cp ' + inp + '.bak ' + inp + ' && ' + rerun
                       : '(already applied in place)';
  } else {
    apply = bad.length || !out ? rerun : 'mv ' + out + ' ' + inp;
  }
  document.getElementById('apply').textContent = apply;
  document.getElementById('approve').textContent = ok.length + bad.length
    ? 'python update_bib.py -i ' + inp + ' --approve ' +
      ok.concat(bad).join(' ')
    : '(mark some entries first)';
}
for (const c of cards) {
  for (const [cls, v] of [['ok', 'ok'], ['bad', 'bad']]) {
    c.querySelector('.' + cls).addEventListener('click', () => {
      verdicts[c.dataset.key] = verdicts[c.dataset.key] === v ? '' : v;
      save(); render();
    });
  }
}
for (const b of document.querySelectorAll('[data-filter]')) {
  b.addEventListener('click', () => {
    filter = b.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(
      x => x.classList.toggle('on', x === b));
    render();
  });
}
document.getElementById('q').addEventListener('input', render);
for (const b of document.querySelectorAll('[data-copy]')) {
  b.addEventListener('click', () => {
    const t = document.getElementById(b.dataset.copy).textContent;
    navigator.clipboard.writeText(t).then(() => {
      b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200);
    });
  });
}
render();
"""


def authors_list(bib_author):
    return '; '.join(a.strip() for a in re.split(r'\s+and\s+', bib_author)
                     if a.strip())


def doi_link(doi):
    return '<a href="https://doi.org/%s" target="_blank">doi:%s</a>' % (
        escape(doi, True), escape(doi))


def match_table(before, rec):
    sim = title_similarity(before['title'], rec['title'])
    rows = [
        ('Title', before['title'], rec['title'], sim < 0.999),
        ('Authors', authors_list(before['author']),
         '; '.join(rec['authors']), False),
        ('Year', before['year'], rec['year'] or '',
         bool(rec['year']) and rec['year'] != before['year']),
        ('Venue', before['venue'], rec['venue'], False),
    ]
    out = ['<table><caption>Your entry vs. matched record</caption>',
           '<tr><th class="f"></th><th>Your entry (before)</th>'
           '<th>Matched record</th></tr>']
    for name, mine, theirs, differs in rows:
        out.append('<tr><td class="f">%s</td><td>%s</td><td%s>%s</td></tr>'
                   % (name, escape(mine or ''),
                      ' class="differs"' if differs else '',
                      escape(theirs or '')))
    out.append('</table>')
    return '\n'.join(out), sim


def changes_table(changes):
    out = ['<table><caption>Field changes</caption>',
           '<tr><th class="f">Field</th><th>Before</th><th>After</th></tr>']
    for name, old, new in changes:
        cls = 'del' if new is None else 'mod' if old else 'add'
        out.append('<tr class="%s"><td class="f mono">%s</td>'
                   '<td class="old">%s</td><td class="new">%s</td></tr>'
                   % (cls, escape(name), escape(old or ''),
                      escape(new or '')))
    out.append('</table>')
    return '\n'.join(out)


def entry_card(item):
    entry, before, rec = item['entry'], item['before'], item['rec']
    table, sim = match_table(before, rec)
    sim_cls = ' warn' if sim < 0.97 else ''
    badges = ['<span class="badge">@%s</span>' % escape(entry.type),
              '<span class="badge">%s</span>' % escape(item['how']),
              '<span class="badge%s">title similarity %.2f</span>'
              % (sim_cls, sim)]
    if before['arxiv']:
        badges.append('<span class="badge warn">pre-print &rarr; '
                      'published</span>')
    links = [doi_link(rec['doi']),
             '<a href="https://api.crossref.org/works/%s" target="_blank">'
             'Crossref record</a>' % escape(rec['doi'], True)]
    if before['arxiv']:
        links.append('<a href="https://arxiv.org/abs/%s" target="_blank">'
                     'arXiv:%s</a>' % (before['arxiv'], before['arxiv']))
    note = '<div class="note">%s</div>' % escape(item['note']) \
        if item['note'] else ''
    return """
<div class="card" data-key="%(key)s">
  <div class="card-head">
    <div><span class="key mono">%(key)s</span>
      <div class="badges">%(badges)s</div></div>
    <div class="verdict"><button class="ok">&#10003; Correct</button>
      <button class="bad">&#10007; Wrong</button></div>
  </div>
  <div class="title">%(title)s</div>
  <div class="tables"><div>%(match)s</div><div>%(changes)s</div></div>
  <div class="links">%(links)s</div>%(note)s
</div>""" % {'key': escape(entry.key, True), 'badges': ''.join(badges),
             'title': escape(before['title']), 'match': table,
             'changes': changes_table(item['changes']),
             'links': ''.join(links), 'note': note}


def write_html_report(path, updated, to_review, manual, args, output):
    now = datetime.now().astimezone()
    written = not args.dry_run and updated
    status = ('changes written to <code>%s</code>' % escape(output)
              if written else 'dry run: nothing written' if args.dry_run
              else 'nothing to write')
    body = ['<main>',
            '<h1>Bibliography changes</h1>',
            '<div class="meta">%s &middot; <code>%s</code> &middot; %s '
            '&middot; %d entries updated</div>'
            % (now.strftime('%Y-%m-%d %H:%M'), escape(args.input), status,
               len(updated)),
            '<div class="toolbar"><input id="q" type="search" '
            'placeholder="Filter by key, title, venue...">'
            '<button class="on" data-filter="all">All</button>'
            '<button data-filter="todo">To review</button>'
            '<button data-filter="ok">Correct</button>'
            '<button data-filter="bad">Wrong</button></div>']
    if updated:
        body += [entry_card(item) for item in updated]
    else:
        body.append('<p class="empty">No entry was updated.</p>')

    if to_review:
        body.append('<h2>Possible matches not applied</h2><div class="meta">'
                    'Title similarity below %.2f: update these by hand if '
                    'the match is right.</div>' % args.min_sim)
        for entry, (sim, rec) in to_review:
            body.append(
                '<div class="card"><span class="key mono">%s</span>'
                '<div class="title">%s</div><div class="meta">%.2f &rarr; '
                '%s. <i>%s</i>, %s. %s</div></div>'
                % (escape(entry.key), escape(entry.get('title')), sim,
                   escape(rec['title']), escape(rec['venue']),
                   escape(rec['year'] or ''), doi_link(rec['doi'])))
    if manual:
        body.append('<h2>Pre-prints that seem published, without a DOI</h2>'
                    '<div class="meta">Update these by hand.</div>')
        for entry, info in manual:
            body.append('<div class="card"><span class="key mono">%s</span>'
                        '<div class="title">%s</div><div class="meta">%s'
                        '</div></div>' % (escape(entry.key),
                                          escape(entry.get('title')),
                                          escape(info)))
    body.append('</main>')
    body.append("""
<div class="bar"><div class="bar-inner">
  <div class="meta"><b id="count"></b> &middot; marks are kept in this
    browser. Run the commands in this order:</div>
  <div class="cmd"><span>1. Apply correct ones</span><code id="apply"></code>
    <button data-copy="apply">Copy</button></div>
  <div class="cmd"><span>2. Approve reviewed</span><code id="approve"></code>
    <button data-copy="approve">Copy</button></div>
</div></div>""")

    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bibliography changes</title>
<style>%s</style></head>
<body data-id="%s" data-input="%s" data-output="%s" data-inplace="%s">
%s
<script>%s</script>
</body></html>
""" % (CSS, escape(json.dumps([args.input, now.isoformat()]), True),
       escape(args.input, True), escape(output if written else '', True),
       '1' if written and args.in_place else '0',
       '\n'.join(body), JS)
    with open(path, 'w', encoding='utf8') as f:
        f.write(page)


IRIS_CSS = """
.row { display: flex; gap: 12px; align-items: flex-start;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 14px; margin: 0 0 8px; }
.row.done { opacity: .55; }
.row.done .title { text-decoration: line-through; }
.row input { margin-top: 5px; width: 16px; height: 16px; flex: none; }
.row .title { margin: 2px 0; }
.year { font-weight: 600; margin-right: 6px; }
.sub { font-size: 13px; color: var(--muted); }
.iris { font-size: 13px; margin-top: 4px; }
.count { font-size: 13px; color: var(--muted); font-weight: 400; }
"""

IRIS_JS = """
const KEY = 'irisreview:' + document.body.dataset.id;
let done = {};
try { done = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) {}
const rows = [...document.querySelectorAll('.row[data-key]')];
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(done)); } catch (e) {}
}
function render() {
  const q = document.getElementById('q').value.toLowerCase();
  const hide = document.getElementById('hide').checked;
  for (const r of rows) {
    const d = !!done[r.dataset.key];
    r.querySelector('input').checked = d;
    r.classList.toggle('done', d);
    r.classList.toggle('hidden', (hide && d) ||
                       !r.textContent.toLowerCase().includes(q));
  }
  const keys = rows.map(r => r.dataset.key).filter(k => done[k]);
  document.getElementById('count').textContent =
    keys.length + ' of ' + rows.length + ' done';
  document.getElementById('approve').textContent = keys.length
    ? 'python check_iris.py -i ' + document.body.dataset.input + ' -a ' +
      document.body.dataset.author + ' --approve ' + keys.join(' ')
    : '(tick some entries first)';
}
for (const r of rows) {
  r.querySelector('input').addEventListener('change', e => {
    done[r.dataset.key] = e.target.checked; save(); render();
  });
}
document.getElementById('q').addEventListener('input', render);
document.getElementById('hide').addEventListener('change', render);
for (const b of document.querySelectorAll('[data-copy]')) {
  b.addEventListener('click', () => {
    const t = document.getElementById(b.dataset.copy).textContent;
    navigator.clipboard.writeText(t).then(() => {
      b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1200);
    });
  });
}
render();
"""

IRIS_GROUPS = [
    ('Journal papers', ('article',)),
    ('Conference papers', ('inproceedings', 'conference')),
    ('Books and book chapters', ('book', 'inbook', 'incollection')),
    ('Edited proceedings', ('proceedings',)),
]


ACCENTS = {"'": '\u0301', '`': '\u0300', '^': '\u0302', '"': '\u0308',
           '~': '\u0303', 'c': '\u0327', 'v': '\u030c'}


def _bib_text(text):
    """Strip the BibTeX braces, escapes and accent commands for display."""
    text = re.sub(r'[{}]', '', text or '')
    text = re.sub(r'\\([\'`^"~cv])\s*([A-Za-z])',
                  lambda m: m.group(2) + ACCENTS[m.group(1)], text)
    text = unicodedata.normalize('NFC', text)
    return re.sub(r'\\([&%#_])', r'\1', text)


def _year(entry):
    y = entry.get('year')
    return int(y) if y.isdigit() else 0


def _iris_row(entry, extra=''):
    venue = entry.get('journal') or entry.get('booktitle') or \
        entry.get('publisher') or entry.get('school')
    doi = entry.get('doi').strip()
    doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi)
    return """
<label class="row" data-key="%(key)s"><input type="checkbox">
  <div><div class="title"><span class="year">%(year)s</span>%(title)s</div>
  <div class="sub"><i>%(venue)s</i> &middot; <span class="mono">%(key)s</span>
  %(doi)s</div>%(extra)s</div></label>""" % {
        'key': escape(entry.key, True), 'year': escape(entry.get('year')),
        'title': escape(_bib_text(entry.get('title'))),
        'venue': escape(_bib_text(venue)),
        'doi': '&middot; ' + doi_link(doi) if doi else '', 'extra': extra}


def write_iris_report(path, missing, possible, unlinked, n_checked, args):
    """HTML version of check_iris.py's report: the published entries missing
    from IRIS, grouped by type, each with a checkbox to tick it off."""
    now = datetime.now().astimezone()
    base = args.base_url.rstrip('/')
    body = ['<main>', '<h1>Papers missing from IRIS</h1>',
            '<div class="meta">%s &middot; <code>%s</code> &middot; IRIS '
            'author <code>%s</code> &middot; %d of %d %spublished entries '
            'not found</div>'
            % (now.strftime('%Y-%m-%d %H:%M'), escape(args.input),
               escape(args.author_id), len(missing), n_checked,
               'new or modified ' if args.incremental else ''),
            '<div class="toolbar"><input id="q" type="search" '
            'placeholder="Filter by key, title, venue...">'
            '<label class="meta"><input id="hide" type="checkbox"> '
            'Hide ticked</label></div>']
    groups = [(name, [e for e in missing if e.type.lower() in types])
              for name, types in IRIS_GROUPS]
    grouped = {e.key for _, es in groups for e in es}
    groups.append(('Other', [e for e in missing if e.key not in grouped]))
    for name, entries in groups:
        if entries:
            body.append('<h2>%s <span class="count">(%d)</span></h2>'
                        % (name, len(entries)))
            body += [_iris_row(e) for e in sorted(entries, key=_year,
                                                  reverse=True)]
    if not missing:
        body.append('<p class="empty">All published entries are in IRIS.</p>')

    def iris_link(rec, text):
        return '<a href="%s/handle/%s" target="_blank">%s</a>' % (
            escape(base, True), escape(rec['handle'], True), escape(text))

    if possible:
        body.append('<h2>Possible matches, please check <span class="count">'
                    '(%d)</span></h2>' % len(possible))
        for entry, sim, rec in sorted(possible, key=lambda x: -_year(x[0])):
            body.append(_iris_row(entry, '<div class="iris">%.2f &rarr; IRIS: '
                                  '%s (%s)</div>' % (sim, iris_link(
                                      rec, rec['title']), escape(rec['year']))))
    if unlinked:
        body.append('<h2>In IRIS, but not linked to your profile '
                    '<span class="count">(%d)</span></h2>' % len(unlinked))
        for entry, sim, rec in sorted(unlinked, key=lambda x: -_year(x[0])):
            body.append(_iris_row(entry, '<div class="iris">IRIS: %s &middot; '
                                  '%s</div>' % (iris_link(rec, rec['handle']),
                                                escape(rec['authors']))))
    body.append('</main>')
    body.append("""
<div class="bar"><div class="bar-inner">
  <div class="meta"><b id="count"></b> &middot; ticks are kept in this
    browser. To stop reporting the ticked entries (e.g. papers you will not
    upload; uploaded ones are found automatically next time):</div>
  <div class="cmd"><code id="approve"></code>
    <button data-copy="approve">Copy</button></div>
</div></div>""")

    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Missing from IRIS</title>
<style>%s%s</style></head>
<body data-id="%s" data-input="%s" data-author="%s">
%s
<script>%s</script>
</body></html>
""" % (CSS, IRIS_CSS, escape(json.dumps([args.input, now.isoformat()]), True),
       escape(args.input, True), escape(args.author_id, True),
       '\n'.join(body), IRIS_JS)
    with open(path, 'w', encoding='utf8') as f:
        f.write(page)

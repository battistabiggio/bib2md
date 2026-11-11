#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copy the updated entries of a .bib file (e.g. biblio.bib, after
update_bib.py) back into the master .bib file it was extracted from.

Entries are matched by key, and only the entries that changed are replaced;
all the other entries, and everything else in the master file, are kept
byte-for-byte. If the version the update started from is given (--base, e.g.
biblio.bib.bak), an entry is replaced only if the master file still has that
version: entries edited in the master file in the meantime are reported as
conflicts and left untouched."""

import os
import sys
import shutil
import argparse

from bibtools import iter_raw_entries, Entry


def raw_by_key(path):
    with open(path, encoding='utf8') as f:
        text = f.read()
    entries = {}
    for start, end, raw in iter_raw_entries(text):
        entries.setdefault(Entry(raw).key, (start, end, raw))
    return text, entries


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('-i', '--input', metavar='BIB', default='biblio.bib',
                        help='updated .bib file (default: biblio.bib)')
    parser.add_argument('-m', '--master', metavar='BIB', required=True,
                        help='master .bib file to update')
    parser.add_argument('-b', '--base', metavar='BIB',
                        help='the input file before the update (e.g. '
                             'biblio.bib.bak), to detect conflicts')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='only report what would change')
    args = parser.parse_args()

    for path in (args.input, args.master, args.base):
        if path and not os.path.isfile(path):
            sys.exit('File "%s" does not exist.' % path)

    _, updated = raw_by_key(args.input)
    master_text, master = raw_by_key(args.master)
    base = raw_by_key(args.base)[1] if args.base else None

    replace, conflicts, missing = [], [], []
    for key, (_, _, raw) in updated.items():
        if key not in master:
            missing.append(key)
            continue
        current = master[key][2]
        if current == raw:
            continue  # already up to date
        if base is not None and (key not in base or base[key][2] != current):
            conflicts.append(key)
            continue
        replace.append(key)

    print('%d entries to update in "%s".' % (len(replace), args.master))
    for key in replace:
        print('   ~ %s' % key)
    if conflicts:
        print('\n%d conflicts: these entries were modified in the master '
              'file since the extraction, and are left untouched:'
              % len(conflicts))
        for key in conflicts:
            print('   ! %s' % key)
    if missing:
        print('\n%d entries are not in the master file (not added):'
              % len(missing))
        for key in missing:
            print('   ? %s' % key)
    if args.dry_run or not replace:
        return

    spans = sorted((master[k][0], master[k][1], updated[k][2])
                   for k in replace)
    out, last = [], 0
    for start, end, raw in spans:
        out += [master_text[last:start], raw]
        last = end
    out.append(master_text[last:])
    shutil.copyfile(args.master, args.master + '.bak')
    with open(args.master, 'w', encoding='utf8') as f:
        f.write(''.join(out))
    print('\nWritten "%s" (backup in "%s.bak").' % (args.master, args.master))


if __name__ == '__main__':
    main()

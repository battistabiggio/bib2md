#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- vim: set fileencoding=utf-8 -*-

import sys
import os
import re
import argparse

from pybtex.plugin import find_plugin
from pybtex import database, errors as bibtex_errors

from pybtex.style.formatting.unsrt import Style as UnsrtStyle
from pybtex.style.template import (field, sentence)
from pybtex.plugin import register_plugin as pybtex_register_plugin


class CustomStyle(UnsrtStyle):
    default_sorting_style = 'author_year_title'

    def format_title(self, e, which_field, as_sentence=True):
        # This avoids that title is capitalized (and then set all lowercase)
        formatted_title = field(which_field)
        if as_sentence:
            return sentence[formatted_title]
        else:
            return formatted_title


pybtex_register_plugin("pybtex.style.formatting", "custom", CustomStyle)

# front matter delimiter: dashes for YAML, pluses for TOML
FM_DELIM = '---'

# http://bib-it.sourceforge.net/help/fieldsAndEntryTypes.php#proceedings
# NOTE: title  is required for all entries, without exception
# NOTE: author is required for all entries except proceedings.
#       beware the script will fail for this entry
WHERE_FIELDS = ['booktitle', 'journal', 'school', 'institution']  # 'publisher'
BIB_FIELDS = {
    'article': {
        'req': ['journal', 'year'],
        'cus': ['doi', 'url', 'keywords', 'abstract'],  # TODO
        'opt': ['volume', 'number', 'pages', 'month', 'note'],
    },
    'inproceedings': {
        'req': ['booktitle', 'year'],
        'cus': ['doi', 'url', 'keywords', 'abstract'],  # TODO
        'opt': ['editor', 'volume', 'number',
                'series', 'pages', 'address',
                'month', 'organization', 'publisher', 'note'],
    },
    'book': {'req': [], 'opt': [], },
    'phdthesis': {'req': [], 'opt': [], },
    'mastersthesis': {'req': [], 'opt': [], },
    'techreport': {'req': [], 'opt': [], },
    'inbook': {'req': [], 'opt': [], },
    'incollection': {'req': [], 'opt': [], },
    'proceedings': {'req': [], 'opt': [], },
    'manual': {'req': [], 'opt': [], },
    'misc': {'req': [], 'opt': [], },
    'unpublished': {'req': [], 'opt': [], },
    'booklet': {'req': [], 'opt': [], },
}


def split_raw_entries(text):
    """Split raw BibTeX text into {key: raw_entry_text}, preserving the
    original formatting of each entry (including things like bdsk-file
    blobs) instead of re-serializing it through pybtex."""
    entries = {}
    for m in re.finditer(r'^@(\w+)\s*\{\s*([^,\s]+)\s*,', text, re.MULTILINE):
        key = m.group(2)
        start = m.start()
        brace_start = text.index('{', start)
        depth = 0
        end = None
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue  # malformed entry, unbalanced braces
        entries[key] = text[start:end]
    return entries


def entry_matches_author(entry, name):
    """True if `name` is a case-insensitive substring of any author's or
    editor's name on the entry."""
    name = name.lower()
    for role in ('author', 'editor'):
        for person in entry.persons.get(role, []):
            full_name = ' '.join(
                str(part) for part in
                person.last_names + person.first_names + person.middle_names)
            if name in full_name.lower():
                return True
    return False


def extract_author_entries(master_bib, author, output_bib):
    """Extract `author`'s entries from `master_bib` (a .bib file with
    entries from many people) into `output_bib`, preserving their
    original raw formatting. Returns the parsed pybtex database and the
    list of matched entry keys."""
    # a master .bib file shared/exported across many entries may reference
    # journal-name macros (e.g. IEEE_J_PAMI) that aren't defined in it;
    # don't let those (in all likelihood unrelated) entries abort the parse
    bibtex_errors.set_strict_mode(False)
    bib_data = database.parse_file(master_bib)
    with open(master_bib, encoding='utf8') as f:
        raw_entries = split_raw_entries(f.read())

    matched_keys = [key for key, entry in bib_data.entries.items()
                     if entry_matches_author(entry, author)]

    missing_keys = [k for k in matched_keys if k not in raw_entries]
    if missing_keys:
        print('Warning: could not recover raw text for keys: %s'
              % ', '.join(missing_keys))

    with open(output_bib, 'w', encoding='utf8') as f:
        for key in matched_keys:
            if key in raw_entries:
                f.write(raw_entries[key] + '\n\n')

    print('Extracted %d entries (of %d in "%s") matching author "%s" to "%s"'
          % (len(matched_keys), len(bib_data.entries), master_bib,
             author, output_bib))

    return bib_data, matched_keys


def print_entry(entry):
    title = entry.fields['title']
    url = None  # pick url or doi from bibtex
    if 'url' in entry.fields:
        url = entry.fields['url']
    elif 'doi' in entry.fields:
        url = entry.fields['doi']
        if url[0:4] != 'http':
            url = 'https://doi.org/' + url
    if url is None:
        entry.fields['title'] = '<b>{}</b>'.format(title)
    else:
        entry.fields['title'] = '<a href="{}"><b>{}</b></a>'.format(url, title)
    for place in WHERE_FIELDS:
        if place in entry.fields:
            where = entry.fields[place]
            entry.fields[place] = '<i>{}</i>'.format(where)
            break

    plain_backend = find_plugin('pybtex.backends', 'plaintext')
    plain_style = find_plugin(
        'pybtex.style.formatting', 'custom')(abbreviate_names=True)

    plain_entry = plain_style.format_entry(entry.type, entry)
    # title becomes lowercase after rendering...
    text = plain_entry.text.render(plain_backend('utf8')).split('URL:')[0]
    text = text.split('doi:')[0]
    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='A script to parse a single ' 
                    'BibTeX (.bib) file into Beautiful Hugo\'s publication ' 
                    'Markdown (.md) files')
    parser.add_argument('-i', '--input', metavar='BIB', type=str,
                        required=True,
                        help='master bibtex .bib file with entries from '
                             'many authors')
    parser.add_argument('-a', '--author', metavar='NAME', type=str,
                        required=True,
                        help='author/editor name to filter by, matched as '
                             'a case-insensitive substring')
    parser.add_argument('-o', '--output', metavar='BIB', type=str,
                        default='biggio.bib',
                        help='output .bib file with just the extracted '
                             'entries (default: biggio.bib)')
    parser.add_argument('-d', '--dir', metavar='DIR', type=str,
                        help='output dir to store .md files')
    args = parser.parse_args()

    if args.dir is None:
        args.dir = '.'
    if not os.path.isfile(args.input):
        print('File "' + args.input + '" does not exist.')
        sys.exit(1)

    # extract this author's entries from the master .bib file into args.output
    bib_data, matched_keys = extract_author_entries(
        args.input, args.author, args.output)

    # sort by year (more recent first)
    data = sorted(
        ((key, bib_data.entries[key]) for key in matched_keys),
        key=lambda e: e[1].fields['year'], reverse=True)
    _, entries = zip(*data)

    with open('pubs.md', 'w', encoding='utf8') as md:
        md.write('**Pre-prints**\n')
        pub_index = 0
        PREPRINT_VENUES = ('arxiv', 'techrxiv', 'preprints')
        for entry in entries:
            if entry.type != 'article':
                continue
            journal = entry.fields.get('journal', '').lower()
            if any(venue in journal for venue in PREPRINT_VENUES):
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Journal Papers**\n')
        pub_index = 0
        for entry in entries:
            if entry.type != 'article':
                continue
            journal = entry.fields.get('journal', '').lower()
            if not any(venue in journal for venue in PREPRINT_VENUES):
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Top-tier Conference Papers**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'conference' or \
                    entry.type == 'inproceedings':
                entry.type = 'inproceedings'  # override style
                keywords = entry.fields.get('keywords', '').upper()
                if "TOP_CONF" in keywords:
                    pub_index += 1
                    text = print_entry(entry)
                    md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Conference Papers**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'conference' or \
                    entry.type == 'inproceedings':
                entry.type = 'inproceedings'  # override style
                keywords = entry.fields.get('keywords', '').upper()
                if "TOP_CONF" not in keywords:
                    pub_index += 1
                    text = print_entry(entry)
                    md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Books**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'book':
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Book Chapters**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'incollection':
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Proceedings / Edited Books**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'proceedings':
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Miscellaneous**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'periodical':
                entry.type = 'article'  # override style
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**PhD Thesis**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'phdthesis':
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

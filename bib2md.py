#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- vim: set fileencoding=utf-8 -*-

import sys
import os
import argparse

from pybtex.plugin import find_plugin
from pybtex import database

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
                        help='input bibtex .bib file', required=True)
    parser.add_argument('-d', '--dir', metavar='DIR', type=str,
                        help='output dir to store .md files')
    args = parser.parse_args()

    if args.dir is None:
        args.dir = '.'
    if not os.path.isfile(args.input):
        print('File "' + args.input + '" does not exist.')
        sys.exit(1)

    # sort by year (more recent first)
    bib_data = database.parse_file(args.input)
    data = sorted(
        bib_data.entries.items(),
        key=lambda e: e[1].fields['year'], reverse=True)
    _, entries = zip(*data)

    with open('pubs.md', 'w', encoding='utf8') as md:
        md.write('**Pre-prints**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'article' and \
                    'arxiv' in entry.fields['journal'].lower():
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Journal Papers**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'article' and \
                    'arxiv' not in entry.fields['journal'].lower():
                pub_index += 1
                text = print_entry(entry)
                md.write('%s. %s\n' % (pub_index, text))

        md.write('\n**Conference Papers**\n')
        pub_index = 0
        for entry in entries:
            if entry.type == 'conference' or \
                    entry.type == 'inproceedings':
                entry.type = 'inproceedings'  # override style
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

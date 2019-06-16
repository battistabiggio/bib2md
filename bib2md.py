#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- vim: set fileencoding=utf-8 -*-
#
# author: jun 2019
# cassio batista - https://cassota.gitlab.io/

import sys
import os
import re
import argparse

from pybtex.plugin import find_plugin
from pybtex import database

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase

# front matter delimiter: dashes for YAML, pluses for TOML
FM_DELIM = '---' 

# http://bib-it.sourceforge.net/help/fieldsAndEntryTypes.php#proceedings
# NOTE: title  is required for all entries, without exception
# NOTE: author is required for all entries except proceedings. 
#       beware the script will fail for this entry
WHERE_FIELDS = ['booktitle', 'journal', 'school', 'institution'] # 'publisher'
BIB_FIELDS = {
    'article': {
        'req': ['journal', 'year'],
        'cus': ['doi', 'url', 'keywords', 'abstract'], # TODO
        'opt': ['volume', 'number', 'pages', 'month', 'note'],
    },
    'inproceedings': {
        'req': ['booktitle', 'year'],
        'cus': ['doi', 'url', 'keywords', 'abstract'], # TODO
        'opt': ['editor', 'volume', 'number', 
                'series', 'pages', 'address', 
                'month', 'organization', 'publisher', 'note'],
    },
    'book':          { 'req': [], 'opt': [], },
    'phdthesis':     { 'req': [], 'opt': [], },
    'mastersthesis': { 'req': [], 'opt': [], },
    'techreport':    { 'req': [], 'opt': [], },
    'inbook':        { 'req': [], 'opt': [], },
    'incollection':  { 'req': [], 'opt': [], },
    'proceedings':   { 'req': [], 'opt': [], },
    'manual':        { 'req': [], 'opt': [], },
    'misc':          { 'req': [], 'opt': [], },
    'unpublished':   { 'req': [], 'opt': [], },
    'booklet':       { 'req': [], 'opt': [], },
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to parse a single '\
                'BibTeX (.bib) file into Beautiful Hugo\'s publication '\
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

    plain_backend = find_plugin('pybtex.backends', 'plaintext')
    plain_style   = find_plugin('pybtex.style.formatting', 'plain')()

    bib_data = database.parse_file(args.input)

    # make title bold
    for bibkey in bib_data.entries:
        title = bib_data.entries[bibkey].fields['title']
        bib_data.entries[bibkey].fields['title'] = '<b>{}</b>'.format(title)
        for place in WHERE_FIELDS:
            if place in bib_data.entries[bibkey].fields:
                where = bib_data.entries[bibkey].fields[place]
                bib_data.entries[bibkey].fields[place] = '<i>{}</i>'.format(where)
                break

    for plainentry in plain_style.format_bibliography(bib_data):
        markdown  = os.path.join(args.dir, '{}.md'.format(plainentry.key))
        endnote = plainentry.text.render(plain_backend('utf8')).split('URL:')[0]
        tT = endnote[endnote.index('<b>')+3] # gambiarra master
        endnote = endnote.replace('<b>'+tT, '<b>'+tT.upper())
        authors, title, garbage = re.split('<b>|</b>', endnote)
        with open(markdown, 'w', encoding='utf8') as md:
            md.write(FM_DELIM + '\n')
            md.write('authors:\n')
            for author in authors.split(','):
                md.write('- %s\n' % author.strip().rstrip().rstrip('.').lstrip('and '))
            md.write('%-10s "%s"\n' % ('title:', title))
            md.write('%-10s "%s"\n' % ('endnote:', endnote))

    for bibentry in bib_data.entries.values():
        markdown = os.path.join(args.dir, '{}.md'.format(bibentry.key))
        with open(markdown, 'a', encoding='utf8') as md:
            md.write('%-10s "%s"\n' % ('pub_type:', bibentry.type))
            for field, value in bibentry.fields.items():
                if field in BIB_FIELDS[bibentry.type]['req']:
                    if field in WHERE_FIELDS:
                        value = re.sub('<i>|</i>', '', value)
                    md.write('%-10s "%s"\n' % (field+':', value))
            md.write('%-10s "%s-01-01"\n' % ('date:', bibentry.fields['year']))
            md.write(FM_DELIM + '\n\n')

            md.write('## Abstract\n')
            if 'abstract' in bibentry.fields:
                md.write(bibentry.fields['abstract'] + '\n')
            else:
                md.write('Unavailable :(' + '\n')
            md.write('\n')

    with open(args.input, encoding="utf8") as bibtex_file:
        bibtex_str = bibtex_file.read()
    bib_database = bibtexparser.loads(bibtex_str)
    for entry in bib_database.entries:
        markdown = os.path.join(args.dir, '{}.md'.format(entry['ID']))
        with open(markdown, 'a', encoding="utf8") as md:
            bibdb = BibDatabase()
            bibdb.entries = [entry]

            bibtw = BibTexWriter()
            bibtw.align_values = True # TOP CARALHO
            bibtw.indent = '    '

            md.write('## BibTeX Citation\n')
            md.write('{{< highlight bibtex >}}' + '\n') # FIXME bibtex supported?
            md.write(bibtw.write(bibdb).rstrip() + '\n')
            md.write('{{< /highlight >}}' + '\n')

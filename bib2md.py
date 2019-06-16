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

FM_DELIM = '---' # YAML

# http://bib-it.sourceforge.net/help/fieldsAndEntryTypes.php#proceedings
BIB_FIELDS = {
    'article': {
        'req': ['journal', 'year'],
        'opt': ['volume', 'number', 'pages', 
                'month', 'note'],
    },
    'inproceedings': {
        'req': ['booktitle', 'year'],
        'opt': ['editor', 'volume', 'number', 
                'series', 'pages', 'address', 
                'month', 'organization', 'publisher', 'note'],
    },
    'booklet':       { 'req': [], 'opt': [], },
    'inbook':        { 'req': [], 'opt': [], },
    'incollection':  { 'req': [], 'opt': [], },
    'misc':          { 'req': [], 'opt': [], },
    'book':          { 'req': [], 'opt': [], },
    'proceedings':   { 'req': [], 'opt': [], },
    'unpublished':   { 'req': [], 'opt': [], },
    'mastersthesis': { 'req': [], 'opt': [], },
    'phdthesis':     { 'req': [], 'opt': [], },
    'techreport':    { 'req': [], 'opt': [], },
    'manual':        { 'req': [], 'opt': [], },
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
        # TODO make 'booktitle' and 'journal' fields italic

    for plainentry in plain_style.format_bibliography(bib_data):
        markdown   = os.path.join(args.dir, '{}.md'.format(plainentry.key))
        plaintext  = re.split('<b>|</b>|URL:', 
                    plainentry.text.render(plain_backend('utf8')))
        endnote  = '{}\'<b>{}</b>\'{}'.format(plaintext[0], 
                    plaintext[1].capitalize(), plaintext[2].rstrip())
        authors  = plaintext[0].split(',')
        title    = plaintext[1].strip().rstrip().capitalize()
        with open(markdown, 'w', encoding='utf8') as md:
            md.write(FM_DELIM + '\n')
            md.write('authors:\n')
            for author in authors:
                md.write('- %s\n' % author.strip().rstrip().rstrip('.').lstrip('and '))
            md.write('%-10s "%s"\n' % ('title:', title))
            md.write('%-10s "%s"\n' % ('endnote:', endnote))

    for bibentry in bib_data.entries.values():
        markdown = os.path.join(args.dir, '{}.md'.format(bibentry.key))
        with open(markdown, 'a', encoding='utf8') as md:
            md.write('%-10s "%s"\n' % ('pub_type:', bibentry.type))
            for field, value in bibentry.fields.items():
                if field in BIB_FIELDS[bibentry.type]['req']:
                    md.write('%-10s "%s"\n' % (field+':', value))
            md.write('%-10s "%s-01-01"\n' % ('date:', bibentry.fields['year']))
            md.write(FM_DELIM + '\n\n')

            md.write('## Abstract\n')
            if 'abstract' in bibentry.fields:
                md.write('```' + '\n') # FIXME
                md.write(bibentry.fields['abstract'] + '\n')
                md.write('```' + '\n')
            else:
                md.write('unavailable :(' + '\n')
            md.write('\n')

            #md.write('# BibTeX Citation\n')
            #bd = database.BibliographyData()
            #bd.add_entry(bibentry.key, bibentry)
            #md.write(bd.to_string('bibtex').replace('\\textasciitilde ','~') + '\n')

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
            md.write('```bibtex' + '\n') # FIXME use shortcote highlight
            md.write(bibtw.write(bibdb))
            md.write('```' + '\n')

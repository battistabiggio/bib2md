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

YAML_FM_DELIM = '---'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to parse a single '\
                'BibTeX (.bib) file into Beautiful Hugo\'s publication '\
                'Markdown (.md) files')
    parser.add_argument('-i', '--input', metavar='BIB', type=str, 
                help='input bibtex .bib file', required=True)
    parser.add_argument('-d', '--dir', metavar='DIR', type=str, 
                help='output dir to store .md files')
    
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print('File "' + args.input + '" does not exist.')
        sys.exit(1)

    if args.dir is None:
        args.dir = '.'

    plain_backend = find_plugin('pybtex.backends', 'plaintext')
    plain_style   = find_plugin('pybtex.style.formatting', 'plain')()

    bib_data = database.parse_file(args.input)
    for bibkey in bib_data.entries:
        title = bib_data.entries[bibkey].fields['title']
        bib_data.entries[bibkey].fields['title'] = '**{}**'.format(title)

    for plainentry in plain_style.format_bibliography(bib_data):
        markdown = os.path.join(args.dir, '{}.md'.format(plainentry.key))
        endnote  = plainentry.text.render(plain_backend('utf8'))
        authors  = endnote.split('*')[0].split(',')
        title    = endnote.split('*')[2].strip().rstrip()
        #where    = endnote.split('*')[4].strip().rstrip()#.split(',')[0]
        endnote  = endnote.replace('**'+title[0], '**'+title[0].capitalize())
        if 'URL:' in endnote:
            endnote = endnote.split('URL:')[0].rstrip()
        with open(markdown, 'w', encoding='utf8') as md:
            md.write(YAML_FM_DELIM + '\n')
            md.write('endnote: "%s"\n' % endnote)
            md.write('title: "%s"\n'   % title.capitalize())
            md.write('authors:\n')
            for author in authors:
                md.write('- %s\n' % author.strip().rstrip().rstrip('.').lstrip('and '))

    for bibentry in bib_data.entries.values():
        markdown = os.path.join(args.dir, '{}.md'.format(bibentry.key))
        with open(markdown, 'a', encoding='utf8') as md:
            md.write('pub_type: "%s"\n' % bibentry.type)
            for field, value in bibentry.fields.items():
                if field != 'title':
                    md.write('%s: "%s"\n' % (field, value))
            md.write(YAML_FM_DELIM + '\n\n')

            md.write('# Abstract\n')
            if 'abstract' in bibentry.fields:
                md.write(bibentry.fields['abstract'] + '\n')
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

            md.write('# BibTeX Citation\n')
            md.write(bibtw.write(bibdb))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Receives a Bibtex file and produces the markdown files for academic-hugo theme

@author: Petros Aristidou
@contact: p.aristidou@ieee.org
@date: 19-10-2017
@version: alpha

Edited by Cassio Batista on Jun 2019
"""

import sys
import os
import re
import argparse

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase

YAML_FM_DELIM = '---'

def RepresentsInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def supetrim(string):
    out = re.sub('[\\\\{}]', '', string)
    return out.replace('\n',' ')


def month_string_to_number(string):
    m = {
        'jan':1,
        'feb':2,
        'mar':3,
        'apr':4,
        'may':5,
        'jun':6,
        'jul':7,
        'aug':8,
        'sep':9,
        'oct':10,
        'nov':11,
        'dec':12
        }
    s = string.strip()[:3].lower()

    try:
        out = m[s]
        return out
    except:
        raise ValueError('Not a month')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A script to parse a single '\
                'BibTeX (.bib) file into Beautiful Hugo\'s publication '\
                'Markdown (.md) files')
    parser.add_argument('-i', '--input', metavar='BIB', type=str, 
                help='input bibtex .bib file', required=True)
    parser.add_argument('-d', '--dir', metavar='DIR', type=str, 
                help='output dir to store .md files')
    
    args = parser.parse_args()

    try:
        with open(args.input, encoding="utf8") as bibtex_file:
            bibtex_str = bibtex_file.read()
    except EnvironmentError:  # parent of IOError, OSError *and* WindowsError where available
        print('File "' + args.input + '" not found or some other error...')
        sys.exit(3)

    # It takes the type of the bibtex entry and maps to a corresponding category of the academic theme
    pubtype_dict = {
        'PW': '"0"',
        'phdthesis': '"0"',
        'mastersthesis': '"0"',
        'Uncategorized': '"0"',
        'inproceedings': '"1"',
        'conference': '"1"',
        'article': '"2"',
        'submitted': '"3"',
        'techreport': '"4"',
        'book': '"5"',
        'incollection': '"6"',
    }
    
    bib_database = bibtexparser.loads(bibtex_str)
    for entry in bib_database.entries:
        filenm = os.path.join(args.dir, '{}.md'.format(entry['ID']))
        print(filenm)
        
        # TODO do something to avoid overwriting pubs but not repeating them as well
        with open(filenm, 'w', encoding="utf8") as the_file:
            the_file.write(YAML_FM_DELIM + '\n')
            the_file.write('title: "'+supetrim(entry['title'])+'"\n')
            #print('Parsing ' + entry['ID'])
            
            if 'year' in entry:
                date = entry['year']
                if 'month' in entry:
                    if RepresentsInt(entry['month']):
                        month = entry['month']
                    else:
                        month = str(month_string_to_number(entry['month']))
                    date = date+'-'+ month.zfill(2)
                else:
                    date = date+'-01'
                the_file.write('date: "' + date + '-01"\n')
                
            # Treating the authors
            if 'author' in entry:
                authors = entry['author'].split(' and ')
                the_file.write('authors: ' + '\n')
                authors_str = ''
                for author in authors:
                    author_strip = supetrim(author)
                    author_split = author_strip.split(',')
                    if len(author_split)==2:
                        author_strip = author_split[1].strip() + ' ' +author_split[0].strip()
                    author_split = author_strip.split(' ')
                    author_strip = author_split[0][0]+'. '+' '.join(map(str, author_split[1:]))
                    authors_str = authors_str+ '"'+author_strip+'",'
                the_file.write(authors_str[:-1]+']\n')
            
            # Treating the publication type
            if 'ENTRYTYPE' in entry:
                if 'booktitle' in entry and ('Seminar' in supetrim(entry['booktitle'])):
                    the_file.write('publication_types: ['+pubtype_dict['PW']+']\n')
                elif 'booktitle' in entry and ('Workshop' in supetrim(entry['booktitle'])):
                    the_file.write('publication_types: ['+pubtype_dict['conference']+']\n')
                elif 'note' in entry and ('review' in supetrim(entry['note'])):
                    the_file.write('publication_types: ['+pubtype_dict['submitted']+']\n')
                elif 'note' in entry and ('Conditional' in supetrim(entry['note'])):
                    the_file.write('publication_types: ['+pubtype_dict['submitted']+']\n')
                else:
                    the_file.write('publication_types: ['+pubtype_dict[entry['ENTRYTYPE']]+']\n')
            
            # Treating the publication journal, conference, etc.
            if 'booktitle' in entry:
                the_file.write('publication: "_'+supetrim(entry['booktitle'])+'_"\n')
            elif 'journal' in entry:
                the_file.write('publication: "_'+supetrim(entry['journal'])+'_"\n')
            elif 'school' in entry:
                the_file.write('publication: "_'+supetrim(entry['school'])+'_"\n')
            elif 'institution' in entry:
                the_file.write('publication: "_'+supetrim(entry['institution'])+'_"\n')
                
            # I never put the short version. In the future I will use a dictionary like the authors to set the acronyms of important conferences and journals
            the_file.write('publication_short: ""\n')
            
            # Add the abstract if it's available in the bibtex
            if 'abstract' in entry:
                the_file.write('abstract: "'+supetrim(entry['abstract'])+'"\n')
            
            # I add urls to the online version and the DOI
            if 'link' in entry:
                the_file.write('url_pdf: "'+supetrim(entry['link'])+'"\n')
            if 'doi' in entry:
                the_file.write('doi: "'+supetrim(entry['doi'])+'"\n')
            
            ## I put the individual .bib entry to a file with the same name as the .md to create the CITE option
            #db = BibDatabase()
            #db.entries =[entry]
            #writer = BibTexWriter()
            #with open('static/files/citations/'+supetrim(entry['ID']+'.bib'), 'w', encoding="utf8") as bibfile:
            #    bibfile.write(writer.write(db))

            the_file.write(YAML_FM_DELIM + '\n\n')
            
            # Any notes are copied to the main document
            if 'note' in entry:
                strTemp = supetrim(entry['note'])
                the_file.write(strTemp + "\n")

# parse_bib

This is a simple script that parses a bibtex file and generates the markdown
files for the [Hugo academic theme](https://github.com/gcushen/hugo-academic). 

The script relies on
[bibtexparser](https://github.com/sciunto-org/python-bibtexparser) to get the
individual entries from the bibtex file with your publications and then
generates a .md file for each one of them.
~~under */content/publications/* and a
.bib file with the same name under *static/files/citations/*.~~

## Usage

Simply download the script 
~~in your root website folder (e.g., next to the .toml file)~~, 
make sure that you have
[bibtexparser](https://github.com/sciunto-org/python-bibtexparser) **and** 
[pybtex](https://pybtex.org/) installed. Follow the argparse help message below
to run:

```
usage: bib2md.py [-h] -i BIB [-d DIR]

A script to parse a single BibTeX (.bib) file into Beautiful Hugo's
publication Markdown (.md) files

optional arguments:
  -h, --help           show this help message and exit
  -i BIB, --input BIB  input bibtex .bib file
  -d DIR, --dir DIR    output dir to store .md files
```
  
## Dependencies (Debian 9.9)
```
sudo -H pip3 install bibtexparser pybtex --upgrade

```

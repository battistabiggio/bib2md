# bib2md: BibTeX to Beautiful Hugo MarkDown (YAML?)

This is a simple script that parses a BibTeX file and generates the Markdown
files for the 
[Beautiful Hugo theme](https://github.com/halogenica/beautifulhugo/), especially
the section that goes into the front matter (which is pretty much YAML rather
than Mardown actually).

The script relies on `bibtexparser` and `pybtex` libs to get the individual
entries from the BibTeX file with your publications and then generates a .md
file for each one of them.

## Usage

Simply download the script make sure that you have
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

## BibTeX entries fully supported so far
- inproceedings
- article
  
## Dependencies (Debian 9.9)
```bash
sudo -H pip3 install --upgrade \
    bibtexparser pybtex 
```

## Credits
This project was forked and originally based on the work of Petros Aristidou
called [parse_bib](https://github.com/apetros/parse_bib) for Hugo Academic. 
However since I made it compatible to Beautiful Hugo theme apart from
including `pybtex` dependency, I think this project has followed its own path.

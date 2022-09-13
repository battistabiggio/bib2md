# bib2md: BibTeX to Markdown

This is a simple script that parses a BibTeX file and generates a Markdown
file containing the whole bibligraphy as shown at: https://battistabiggio.github.io/publications/

The script is a modification of that intially provided by Cassio Batista, and 
relies on `pybtex` to get the individual entries from the BibTeX file with your publications, 
and then generates a .md file containing the full bibliography, sorted by year (more recent to older),
and grouped by type.

## Usage

Simply download the script, make sure that you have
[pybtex](https://pybtex.org/) installed. 
Follow the argparse help message below to run:

```
usage: bib2md.py [-h] -i BIB [-d DIR]

A script to parse a single BibTeX (.bib) file into Beautiful Hugo's
publication Markdown (.md) files

optional arguments:
  -h, --help           show this help message and exit
  -i BIB, --input BIB  input bibtex .bib file
  -d DIR, --dir DIR    output dir to store .md file
```

## BibTeX entries fully supported so far
- inproceedings
- article
  

## Credits
This project was forked and originally based on the work of Petros Aristidou
called [parse_bib](https://github.com/apetros/parse_bib) for Hugo Academic. 
However since I made it compatible to Beautiful Hugo theme apart from
including the `pybtex` dependency, I think this project has followed its own
path. I kept @apetros' license, tho.

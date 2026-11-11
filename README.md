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
usage: bib2md.py [-h] -i BIB -a NAME [-o BIB] [-d DIR]

A script to parse a single BibTeX (.bib) file into Beautiful Hugo's
publication Markdown (.md) files

options:
  -h, --help            show this help message and exit
  -i BIB, --input BIB   master bibtex .bib file with entries from many authors
  -a NAME, --author NAME
                        author/editor name to filter by, matched as a case-
                        insensitive substring
  -o BIB, --output BIB  output .bib file with just the extracted entries
                        (default: biblio.bib)
  -d DIR, --dir DIR     output dir to store .md files
```

For example, `python bib2md.py -i master.bib -a Smith` extracts the entries
of author Smith from the master file `master.bib` into `biblio.bib`, and
writes `pubs.md`. Published papers link to their DOI (or to their `url`, if
they have no DOI), pre-prints to their `url` (e.g. on arXiv).

## Keeping the BibTeX file up to date

More scripts (they also need [requests](https://pypi.org/project/requests/))
help maintain the `.bib` file. Both keep BibDesk's formatting: entries that
are not modified are written back byte-for-byte.

### `update_bib.py`

Looks up every entry on Crossref (by DOI, or by title + first author),
arXiv and Semantic Scholar, and:

- converts pre-prints (arXiv, TechRxiv, Preprints) that have been published
  into the published version (entry type, journal/booktitle, DOI, volume,
  number, pages, year, url);
- fills in the missing DOI, volume, number and pages of published entries,
  and updates the year of early-access articles that got an issue.

Existing values are never overwritten, entry keys are kept, and the
`keywords` field (project acknowledgements, `TOP_CONF`) is never touched; when
a pre-print becomes a conference paper the report reminds you to add
`TOP_CONF` if needed. Uncertain matches and pre-prints published at venues
without a DOI (e.g. NeurIPS, ICLR) are only reported.

```
python update_bib.py -i biblio.bib -n           # dry run: report only
python update_bib.py -i biblio.bib              # writes biblio.updated.bib
python update_bib.py -i biblio.bib --in-place   # overwrites, keeps a .bak
```

Every run also writes an HTML report, `biblio.changes.html` (change it with
`--report`). Each updated entry is shown next to the record it was matched
to (title, authors, year, venue), with its field changes, and can be marked
as correct or wrong. From these marks the page builds the commands to apply
only the correct changes (re-running with `--exclude` on the wrong ones) and
to approve the reviewed entries.

Pass `--mailto you@example.org` (or set `CROSSREF_MAILTO`) to use Crossref's
faster polite pool, and set `S2_API_KEY` to avoid Semantic Scholar's rate
limits (or skip it with `--no-s2`).

### `sync_bib.py`

Copies the updated entries back into the master `.bib` file they were
extracted from (with `bib2md.py`), matching them by key. Only the changed
entries are replaced; all other entries are kept byte-for-byte. With
`--base`, the version before the update, entries edited in the master file
in the meantime are reported as conflicts and left untouched. A `.bak` copy
of the master file is kept.

```
python sync_bib.py -m master.bib -b biblio.bib.bak -n   # dry run
python sync_bib.py -m master.bib -b biblio.bib.bak
```

Close the master file in BibDesk first, so that BibDesk does not overwrite
the changes when it saves.

### `check_iris.py`

Lists the published entries (pre-prints excluded) that are missing from IRIS,
the institutional research repository (developed by Cineca) used by most
Italian universities to archive their researchers' publications. The default
archive is the one of the University of Cagliari (https://iris.unica.it); use
`--base-url` for another university's IRIS, e.g. `--base-url
https://iris.example.it`. Your IRIS records are retrieved by your IRIS author
id (the `rp...` id in the author facet of the IRIS search page) and matched by
DOI or title; unmatched titles are also searched across the whole archive, to
find records not linked to your profile.

```
python check_iris.py -i biblio.bib -a rp01234 -o missing.md
```

Besides printing the list, it writes an HTML version, `biblio.missing-iris.html`
(change it with `--html`), grouped by type and with a checkbox per entry to
tick off the papers as you upload them.

### Incremental runs

Both scripts can skip the entries that were already checked, keeping track
of them in a JSON state file next to the `.bib` (`biblio.update-state.json`,
`biblio.iris-state.json`; choose another one with `--state`). An entry is
checked again whenever its content changes; editing `keywords` does not count.

```
# once you have reviewed the update report and applied the changes
python update_bib.py --approve                 # approve all final papers
python update_bib.py --approve key1 key2       # ... or only some
python update_bib.py --incremental             # new/modified entries only

# entries found in IRIS are recorded automatically; approve those you
# will not upload (e.g. edited proceedings) to stop reporting them
python check_iris.py -a rp01234 --approve key1 key2
python check_iris.py -a rp01234 --incremental
```

`update_bib.py` only approves final papers, i.e. published with all their
details; the others are never approved and `--incremental` re-checks them on
every run, as they are expected to change:

- pre-prints (arXiv, TechRxiv, Preprints) are never final;
- journal articles are final once they have a volume and pages (or an
  article number, in `number`): early-access ones are re-checked until they
  are assigned to an issue;
- conference papers and book chapters are final once they have pages or a
  DOI, or when they are at least 5 years old (by then they will not get
  them anymore).

## BibTeX entries fully supported so far
- inproceedings
- article
  

## Credits
This project was forked and originally based on the work of Petros Aristidou
called [parse_bib](https://github.com/apetros/parse_bib) for Hugo Academic. 
However since I made it compatible to Beautiful Hugo theme apart from
including the `pybtex` dependency, I think this project has followed its own
path. I kept @apetros' license, tho.

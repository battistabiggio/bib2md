#!/usr/bin/env python3
from pybtex.plugin import find_plugin
from pybtex import database

output_backend = find_plugin('pybtex.backends', 'plaintext')
bib_data = database.parse_file('pubs.bib')
style = find_plugin('pybtex.style.formatting', 'plain')()

formatted_bibliography = style.format_bibliography(bib_data)
for e in formatted_bibliography.entries:
    print(e.text.render(output_backend('utf8')))

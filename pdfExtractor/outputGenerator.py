import codecs
import os
import re
import tempfile
from pathlib import Path

from fuzzywuzzy import fuzz
from yattag import Doc, indent

from pdfExtractor.dataStructure import Documents


def generate_html(output_path: str, docs: Documents, searchWord: str):
    # TODO: implement html generation
    doc, tag, text = Doc().tagtext()

    doc.asis('<!DOCTYPE html>')

    with tag('html'):
        with tag('body'):
            with tag('h1', id="heading"):
                text('Summary of search results')
            doc_index = 0
            for document in docs.docs:
                with tag('div', id=str(doc_index)):
                    doc_index += 1
                    with tag('h2'):
                        text("Found in document with location: " + str(document.path))
                    # output extracted paragraphs
                    for paragraph in document.paragraphs:
                        if fuzz.partial_token_set_ratio(paragraph, searchWord) > 70:
                            with tag('p'):
                                text(paragraph)
                    # output extracted tables
                    table_index = 0
                    for table in document.tables:
                        with tag('div', id="table" + str(table_index)):
                            table_index += 1
                            table.to_html(tempfile.gettempdir() + "/table")
                            with codecs.open(tempfile.gettempdir() + "/table", 'r') as table_file:
                                # replace \n in table to fix formating
                                tab = re.sub(r'\\n', '<br>', table_file.read())
                                doc.asis(tab)
                                os.remove(tempfile.gettempdir() + "/table")

    # write HTML to file
    # check if output path is a directory
    if not os.path.isdir(output_path):
        output_path = str(Path(output_path).parent)
    with open(output_path + "/summary.html", "w") as file:
        file.write(indent(doc.getvalue()))

import os
from pathlib import Path

from yattag import Doc, indent

from pdfExtractor.dataStructure import Documents


def generate_html(output_path: str, docs: Documents):
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
                    with tag('h2'):
                        text("Found in document with location: " + str(document.path))
                    for paragraph in document.paragraphs:
                        with tag('p'):
                            text(paragraph)

    # write HTML to file
    # check if output path is a directory
    if not os.path.isdir(output_path):
        output_path = str(Path(output_path).parent)
    with open(output_path + "/summary.html", "w") as file:
        file.write(indent(doc.getvalue()))

from yattag import Doc
from pdfExtractor.dataStructure import Document, Documents


def generate_html():
    # TODO: implement html generation
    doc, tag, text = Doc().tagtext()

    with tag('html'):
        with tag('body'):
            with tag('p', id='main'):
                text('some text')
            with tag('a', href='/my-url'):
                text('some link')

    result = doc.getvalue()

import logging
from io import StringIO

from PyPDF2 import PdfFileReader
from pdfminer.converter import PDFPageAggregator, TextConverter
from pdfminer.layout import LAParams, LTTextBoxHorizontal
from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from pdfExtractor.dataStructure import Document

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(formatter)
fileHandler = logging.FileHandler('pdfExtractor.log', 'w')
fileHandler.setLevel(logging.DEBUG)
fileHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logger.addHandler(fileHandler)
logger.info("Started")


# parses Document to PDFDocument
def get_pdf_object(document: Document):
    file = open(document.path, 'rb')
    parser = PDFParser(file)
    document.doc = PDFDocument(parser)
    parser.set_document(document.doc)

    # if document.doc.is_extractable():
    #     document.extractable = True


def extract_text(document: Document):
    output_string = StringIO()
    with open(document.path, 'rb') as in_file:
        parser = PDFParser(in_file)
        pdf = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(pdf):
            interpreter.process_page(page)

    return output_string.getvalue()


def extract_info(document: Document):
    with open(document.path, 'rb') as f:
        pdf = PdfFileReader(f, strict=False)
        # if pdf.isEncrypted():
        #     logger.error("Encrypted files are currently not supported")
        #     logger.error("Aborting")
        #     sys.exit(1)
        #     # TODO: Handle encrypted files
        info = pdf.getDocumentInfo()
        document.num_pages = pdf.getNumPages()
        document.author = info.author
        document.creator = info.creator
        document.producer = info.producer
        document.subject = info.subject
        document.title = info.title


# layout analysis for every page
def extract_page_layouts(document: Document):
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    page_aggregator = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, page_aggregator)
    for page in PDFPage.create_pages(document.doc):
        interpreter.process_page(page)
        document.page_layouts.append(page_aggregator.get_result())


def extract_table_of_contents(document: Document):
    try:
        for (level, title, dest, a, se) in document.doc.get_outlines():
            document.table_of_contents.append((level, title))
    except PDFNoOutlines:
        logger.warning("Could not get table of contents")


def extract_paragraphs(document: Document):
    for page_layout in document.page_layouts:
        for element in page_layout:
            if isinstance(element, LTTextBoxHorizontal):
                document.paragraphs.append(element.get_text())
            # TODO: Implement logic for other types


if __name__ == "__main__":
    import argparse

    argumentParser = argparse.ArgumentParser()
    argumentParser.add_argument('--path', help='path to pdf file', required=True)
    args = vars(argumentParser.parse_args())
    doc = Document(args["path"])
    print(extract_text(doc))

import logging
import ntpath
import os
import re
import sys
from io import StringIO
from typing import TYPE_CHECKING

import camelot
import cv2
import pytesseract
from PyPDF2 import PdfFileReader
from iso639 import languages
from langdetect import detect_langs
from pdf2image import pdf2image
from pdfminer.converter import PDFPageAggregator, TextConverter
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTImage
from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pytesseract import TesseractNotFoundError, TesseractError

from pdfExtractor.dataStructure import Document

# Set up logger
log_level = 20
if TYPE_CHECKING:
    from pdfExtractor.main import log_level
logger = logging.getLogger(__name__)
logger.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(log_level)
consoleHandler.setFormatter(formatter)
fileHandler = logging.FileHandler('pdfExtractor.log', 'w')
fileHandler.setLevel(log_level)
fileHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logger.addHandler(fileHandler)



# Get filename from path
def get_filename(document: Document):
    document.filename = os.path.splitext(ntpath.basename(document.path))[0]


# Convert document pages to jpg images
def pdf_to_image(document: Document):
    pages = pdf2image.convert_from_path(pdf_path=document.path, dpi=300)
    for i in range(len(pages)):
        pages[i].save(document.parent.path + document.filename + "_" + str(i) + ".jpg")


# Preprocess the images for OCR then extract them
def extract_text_ocr(document):
    for i in range(document.num_pages):
        img = cv2.imread(document.parent.path + document.filename + "_" + str(i) + ".jpg")
        # RGB to grayscale
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold
        img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        # Perform opening
        # img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        cv2.imwrite(document.parent.path + document.filename + "_" + str(i) + "cleaned.jpg", img)
        # Extract testing using OCR

        if i == 0:
            language = get_language(img)
        try:
            text = pytesseract.image_to_string(img, lang=language, config='--psm 1')
            # Remove lines with only whitespaces or newline
            lines = text.split("\n\n")
            out = []
            for line in lines:
                if re.search(r"\S+", line):
                    out.append(line + '\n')
            document.paragraphs = out
            document.text = "".join(out)
        except TesseractNotFoundError:
            logger.error("Tesseract is not installed. Exiting")
            sys.exit(1)
        except TesseractError as e:
            logger.error(e)
            sys.exit(1)


# get language from text
def get_language(img):
    # TODO: Implement input parameter for specifying possible languages. Slovene and english by default.
    config = r'-l eng+slv --psm 6'
    try:
        text = pytesseract.image_to_string(img, config=config)
    except TesseractNotFoundError:
        logger.error("Tesseract is not installed. Exiting")
        sys.exit(1)
    except TesseractError as e:
        logger.error(e)
        sys.exit(1)
    # Assume that all pages contain the same language
    # TODO: clean this up
    # Detect language from extracted text
    detected_languages = detect_langs(text)
    # Convert iso-639-2b to iso-639-2t
    language = languages.get(part1=detected_languages[0].lang)
    return language.part2t


# parses Document to PDFDocument
def get_pdf_object(document: Document):
    file = open(document.path, 'rb')
    parser = PDFParser(file)
    document.doc = PDFDocument(parser)
    parser.set_document(document.doc)

    if document.doc.is_extractable:
        document.extractable = True


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
        # TODO: Handle encrypted files
        # if pdf.isEncrypted:
        #     print(pdf.isEncrypted)
        #     logger.error("Encrypted files are currently not supported")
        #     logger.error("Aborting")
        #     sys.exit(1)

        document.num_pages = pdf.getNumPages()
        info = pdf.getDocumentInfo()
        if info is not None:
            document.author = "unknown" if not info.author else info.author
            document.creator = "unknown" if not info.creator else info.creator
            document.producer = "unknown" if not info.producer else info.producer
            document.subject = "unknown" if not info.subject else info.subject
            document.title = "unknown" if not info.title else info.title


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
        logger.warning("Could not get table of contents for document at path " + document.path)


def parse_layouts(document: Document):
    for page_layout in document.page_layouts:
        for element in page_layout:
            # TODO: improve efficiency
            # extract text and images if there is no table in that location
            for coordinates in document.tables_coordinates:
                if not (coordinates[0] < element.bbox[0] < coordinates[2] or coordinates[1] < element.bbox[1] <
                        coordinates[3]):
                    if isinstance(element, LTTextBoxHorizontal):
                        document.paragraphs.append(element.get_text())
                    elif isinstance(element, LTImage):
                        # Save image objects
                        document.images.append(element)
            # TODO: recursively interate over LTFigure to find images


def extract_tables(document: Document, output_path: str):
    tables = camelot.read_pdf(document.path, pages='1-' + str(document.num_pages), flavor='lattice')
    # find coordinates of table regions to exclude them from text extraction
    for table in tables:
        first_cell_coord = table.cells[0][0].lt
        last_cel_coord = table.cells[-1][-1].rb
        document.tables_coordinates.append(first_cell_coord + last_cel_coord)

    document.tables = tables


if __name__ == "__main__":
    import argparse

    argumentParser = argparse.ArgumentParser()
    argumentParser.add_argument('--path', help='path to pdf file', required=True)
    args = vars(argumentParser.parse_args())
    doc = Document(args["path"])
    print(extract_text(doc))

import logging
import ntpath
import os
import re
import sys
import tempfile
from io import StringIO
from typing import TYPE_CHECKING

import camelot
import cv2
import pytesseract
from PyPDF2 import PdfFileReader, PdfFileWriter
from iso639 import languages
from langdetect import detect_langs
import numpy as np
from pdf2image import pdf2image
from pdfminer.converter import PDFPageAggregator, TextConverter
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTImage
from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pytesseract import TesseractNotFoundError, TesseractError
from scipy.ndimage import interpolation as inter
from PDFScraper.dataStructure import Document

# Set up logger
log_level = 20
if TYPE_CHECKING:
    from PDFScraper.main import log_level
logger = logging.getLogger(__name__)
logger.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(log_level)
consoleHandler.setFormatter(formatter)
fileHandler = logging.FileHandler('PDFScraper.log', 'w')
fileHandler.setLevel(log_level)
fileHandler.setFormatter(formatter)
logger.addHandler(consoleHandler)
logger.addHandler(fileHandler)


# Get filename from path
def get_filename(document: Document):
    document.filename = os.path.splitext(ntpath.basename(document.path))[0]


# Convert document pages to jpg images
def pdf_to_image(document: Document):
    tempfile_path = tempfile.gettempdir() + "/PDFScraper"
    try:
        os.makedirs(tempfile_path)
    except FileExistsError:
        pass

    if document.isPDF:
        pages = pdf2image.convert_from_path(pdf_path=document.path, dpi=300)
        # TODO: implement saving to temp dir with mkstemp for better security
        for i in range(len(pages)):
            pages[i].save(tempfile_path + "/" + document.filename + "_" + str(i) + ".jpg")
    else:
        img = cv2.imread(document.path)
        cv2.imwrite(tempfile_path + "/" + document.filename + "_0.jpg", img)


# helper function for preserving aspect ration when resizing
def image_resize(image, width=None, height=None, inter=cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    dim = None
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation=inter)

    # return the resized image
    return resized


def preprocess_image(image):

    # Denoising
    image = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 15)
    # RGB to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Thresholding
    image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # Skew correction
    def determine_score(arr, angle):
        data = inter.rotate(arr, angle, reshape=False, order=0)
        histogram = np.sum(data, axis=1)
        score = np.sum((histogram[1:] - histogram[:-1]) ** 2)
        return histogram, score

    scores = []
    angles = np.arange(-5, 5 + 1, 1)
    for angle in angles:
        histogram, score = determine_score(image, angle)
        scores.append(score)
    best_angle = angles[scores.index(max(scores))]

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, best_angle, 1.0)
    image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, \
                           borderMode=cv2.BORDER_REPLICATE)

    return image


# Preprocess the images for OCR then extract them
def convert_to_pdf(document: Document, tessdata_location: str):
    pdf_pages = []
    for i in range(document.num_pages):
        img = cv2.imread(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # remove temporary image file
        os.remove(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # Resize imput image if not PDF
        if not document.isPDF:
            image = image_resize(image, width=1024)
        img = preprocess_image(img)

        # Extract testing using OCR

        # Extract language only from the first page
        if i == 0:
            language = get_language(img, tessdata_location)
        try:
            config_options = '--psm 1 --tessdata-dir ' + tessdata_location
            text = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang=language, config=config_options)
            with open(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".pdf",
                      'w+b') as f:
                f.write(text)
                pdf_pages.append(
                    tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".pdf")
        except TesseractNotFoundError:
            logger.error("Tesseract is not installed. Exiting")
            sys.exit(1)
        except TesseractError as e:
            logger.error(e)
            sys.exit(1)
    pdf_writer = PdfFileWriter()
    for filename in pdf_pages:
        pdf_file = open(filename, 'rb')
        pdf_reader = PdfFileReader(pdf_file)
        for i in range(pdf_reader.numPages):
            page = pdf_reader.getPage(i)
            pdf_writer.addPage(page)
    with open(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + ".pdf", 'w+b') as out:
        pdf_writer.write(out)
        out.close()
        document.ocr_path = tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + ".pdf"
    # cleanup temporary files
    for filename in pdf_pages:
        os.remove(filename)


# get language from text
def get_language(img, tessdata_location: str):
    # TODO: Implement input parameter for specifying possible languages. Slovene and english by default.
    config = r'-l eng+slv --psm 6' + ' --tessdata-dir ' + tessdata_location
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
    # use OCR file if available
    file = open(document.ocr_path, 'rb')
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
        codec = 'unicode'
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, codec=codec, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(pdf):
            interpreter.process_page(page)

    return output_string.getvalue()


def extract_info(document: Document):
    if document.isPDF:
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
    else:
        document.num_pages = 1
        document.author = "unknown"
        document.creator = "unknown"
        document.producer = "unknown"
        document.subject = "unknown"
        document.title = "unknown"


# layout analysis for every page
def extract_page_layouts(document: Document):
    resource_manager = PDFResourceManager()
    laparams = LAParams(line_margin=0.8)
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
            skip = False
            if len(document.tables_coordinates) > 0:
                for coordinates in document.tables_coordinates:
                    # skip if element is inside already detected table
                    if (coordinates[0] < element.bbox[0] < coordinates[2] or coordinates[1] < element.bbox[1] <
                            coordinates[3]):
                        skip = True
                        break
            if not skip:
                if isinstance(element, LTTextBoxHorizontal):
                    text = element.get_text()
                    # fix Slovene chars and other anomalies
                    text = re.sub(r'ˇs', "š", text)
                    text = re.sub(r"ˇc", "č", text)
                    text = re.sub(r"ˇz", "ž", text)
                    text = re.sub(r"-\s", "", text)

                    document.paragraphs.append(text)
                elif isinstance(element, LTImage):
                    # Save image objects
                    document.images.append(element)
                # TODO: recursively iterate over LTFigure to find images


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

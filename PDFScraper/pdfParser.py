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
import numpy as np
import pytesseract
from PyPDF2 import PdfFileReader, PdfFileWriter
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
from skimage import io
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks, rotate

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


# determine skew angle of image
def determine_skew(image):
    edges = canny(image, sigma=3.0)
    h, a, d = hough_line(edges)
    _, ap, _ = hough_line_peaks(h, a, d, num_peaks=20)

    if len(ap) == 0:
        return 0

    def calculate_deviation(angle):

        angle_in_degrees = np.abs(angle)
        deviation = np.abs(np.pi / 4 - angle_in_degrees)
        return deviation

    absolute_deviations = [calculate_deviation(k) for k in ap]
    average_deviation = np.mean(np.rad2deg(absolute_deviations))
    ap_deg = [np.rad2deg(x) for x in ap]

    bin_0_45 = []
    bin_45_90 = []
    bin_0_45n = []
    bin_45_90n = []

    def compare_sum(value):
        if 44 <= value <= 46:
            return True
        else:
            return False

    for ang in ap_deg:
        deviation_sum = int(90 - ang + average_deviation)
        if compare_sum(deviation_sum):
            bin_45_90.append(ang)
            continue

        deviation_sum = int(ang + average_deviation)
        if compare_sum(deviation_sum):
            bin_0_45.append(ang)
            continue

        deviation_sum = int(-ang + average_deviation)
        if compare_sum(deviation_sum):
            bin_0_45n.append(ang)
            continue

        deviation_sum = int(90 + ang + average_deviation)
        if compare_sum(deviation_sum):
            bin_45_90n.append(ang)

    angles = [bin_0_45, bin_45_90, bin_0_45n, bin_45_90n]
    lmax = 0

    for j in range(len(angles)):
        l = len(angles[j])
        if l > lmax:
            lmax = l
            maxi = j

    def get_max_freq_elem(arr):

        max_arr = []
        freqs = {}
        for i in arr:
            if i in freqs:
                freqs[i] += 1
            else:
                freqs[i] = 1

        sorted_keys = sorted(freqs, key=freqs.get, reverse=True)
        max_freq = freqs[sorted_keys[0]]

        for k in sorted_keys:
            if freqs[k] == max_freq:
                max_arr.append(k)

        return max_arr

    if lmax:
        ans_arr = get_max_freq_elem(angles[maxi])
        ans_res = np.mean(ans_arr)

    else:
        ans_arr = get_max_freq_elem(ap_deg)
        ans_res = np.mean(ans_arr)

    return ans_res


# Apply deskewing to the image
def deskew(image):
    angle = determine_skew(image)

    if 0 <= angle <= 90:
        rot_angle = angle - 90
    if -45 <= angle < 0:
        rot_angle = angle - 90
    if -90 <= angle < -45:
        rot_angle = 90 + angle

    return rotate(image, rot_angle, resize=True)


def preprocess_image(image):
    # Denoising
    image = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 15)
    # RGB to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Thresholding
    image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # save and reread to convert to scikit-image image type
    temp_image_path = tempfile.gettempdir() + "/PDFScraper" + "/" + "deskew.jpg"
    cv2.imwrite(temp_image_path, image)
    image = io.imread(temp_image_path)
    os.remove(temp_image_path)
    # perform deskewing
    image = deskew(image)
    image = image * 255
    io.imsave(temp_image_path, image.astype(np.uint8))
    image = cv2.imread(temp_image_path)
    os.remove(temp_image_path)
    return image


# Preprocess the images for OCR then extract them
def convert_to_pdf(document: Document, tessdata_location: str):
    pdf_pages = []
    for i in range(document.num_pages):
        img = cv2.imread(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # remove temporary image file
        os.remove(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # Resize imput image if not PDF
        # if not document.isPDF:
        #     img = image_resize(img, width=1024)
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


# Returns true if two rectangles(l1, r1)
# and (l2, r2) overlap
def doOverlap(l1, r1, l2, r2):
    # If one rectangle is on left side of other
    if l1[0] >= r2[0] or l2[0] >= r1[0]:
        return False

    # If one rectangle is above other
    if l1[1] <= r2[1] or l2[1] <= r1[1]:
        return False

    return True


def parse_layouts(document: Document):
    count = 1
    for page_layout in document.page_layouts:
        parse_elements(document, page_layout, count)
        count = count + 1


# Recursively iterate over all the elements
def parse_elements(document, page_layout, page):
    for element in page_layout:
        # TODO: improve efficiency
        # extract text and images if there is no table in that location
        skip = False
        if len(document.tables) > 0 and hasattr(element, "x0"):
            for table in document.tables:
                # skip if element is inside already detected table
                if (table.page == page and doOverlap((element.x0, element.y1), (element.x1, element.y0),
                                                     (table._bbox[0], table._bbox[3]),
                                                     (table._bbox[2], table._bbox[1]))):
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
        elif hasattr(element, '_objs'):
            for el in element._objs:
                if hasattr(el, '__iter__'):
                    parse_elements(document, el, page)


def extract_tables(document: Document, output_path: str):
    tables = camelot.read_pdf(document.path, pages='1-' + str(document.num_pages), flavor='lattice')
    document.tables = tables


if __name__ == "__main__":
    import argparse

    argumentParser = argparse.ArgumentParser()
    argumentParser.add_argument('--path', help='path to pdf file', required=True)
    args = vars(argumentParser.parse_args())
    doc = Document(args["path"])
    print(extract_text(doc))

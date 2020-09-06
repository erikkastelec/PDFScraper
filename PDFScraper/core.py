import logging
import ntpath
import os
import re
import sys
import tempfile
import uuid
from typing import TYPE_CHECKING

import camelot
import cv2
import numpy as np
import pytesseract
from PyPDF2 import PdfFileReader, PdfFileWriter
from fuzzywuzzy import fuzz, process
from iso639 import languages
from langdetect import detect_langs
from pdf2image import pdf2image
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTImage
from pdfminer.pdfdocument import PDFDocument, PDFNoOutlines
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFObject
from pytesseract import TesseractNotFoundError, TesseractError
from skimage import io
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks, rotate

from PDFScraper.dataStructure import Document

# Set up logger
log_level = 20
if TYPE_CHECKING:
    from PDFScraper.cli import log_level
logger = logging.getLogger("PDFScraper")
logger.setLevel(log_level)


def find_pdfs_in_path(path: str):
    pdfs = []
    if os.path.exists(path):
        if os.path.isdir(path):  # find PDFs in directory and add them to the list
            count = 0
            for f in os.listdir(path):
                count += 1
                pdfs = pdfs + find_pdfs_in_path(path + '/' + f)

        elif os.path.isfile(path) and (path.endswith(".pdf")):
            pdfs.append(Document(path, True))

        elif os.path.isfile(path) and (path.endswith(".bmp") or path.endswith(".jpg") or path.endswith(".pbm")
                                       or path.endswith(".pgm") or path.endswith(".ppm") or path.endswith(".jpeg")
                                       or path.endswith(".jpe") or path.endswith(".jp2") or path.endswith(".tiff")
                                       or path.endswith(".tif") or path.endswith(".png")):

            pdfs.append(Document(path, False))

    else:
        raise Exception("Provided path does not exist")
    return pdfs


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

    if document.is_pdf:
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
def determine_skew(image, sigma=3.0, num_peaks=20):
    edges = canny(image, sigma=sigma)
    h, a, d = hough_line(edges)
    _, ap, _ = hough_line_peaks(h, a, d, num_peaks=num_peaks)

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
    # image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    # save and reread to convert to scikit-image image type
    temp_image_path = tempfile.gettempdir() + "/PDFScraper" + "/" + str(uuid.uuid4()) + "deskew.jpg"
    cv2.imwrite(temp_image_path, image)
    image = io.imread(temp_image_path)
    os.remove(temp_image_path)
    image = deskew(image)
    image = image * 255
    io.imsave(temp_image_path, image.astype(np.uint8))
    image = cv2.imread(temp_image_path)
    os.remove(temp_image_path)
    return image


# Preprocess the images for OCR then extract them
def convert_to_pdf(document: Document, tessdata_location: str, config_options=""):
    pdf_pages = []
    for i in range(document.num_pages):
        img = cv2.imread(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # remove temporary image file
        os.remove(tempfile.gettempdir() + "/PDFScraper" + "/" + document.filename + "_" + str(i) + ".jpg")
        # Resize imput image if not PDF
        # if not document.isPDF:
        #     img = image_resize(img, width=1024)

        img = preprocess_image(img)

        # Extract language from the first page only
        if i == 0:
            language = get_language(img, tessdata_location)
            # if not english or slovene set to english
            if language != "eng" or language != "slv":
                language = "eng"

        try:
            # uses provided config if available
            if config_options == "":
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
    # Detect language from extracted text
    detected_languages = detect_langs(text)
    # Convert iso-639-2b to iso-639-2t
    language = languages.get(part1=detected_languages[0].lang)
    return language.part2t


# parses Document to PDFDocument
def get_pdf_object(document: Document):
    if document.filename is None:
        get_filename(document)
    # use OCR processed file if available
    file = open(document.ocr_path, 'rb')
    parser = PDFParser(file)
    pdf_object = PDFDocument(parser)
    parser.set_document(pdf_object)

    if pdf_object.is_extractable:
        document.extractable = True
    return pdf_object


def extract_info(document: Document):
    if document.filename is None:
        get_filename(document)
    if document.is_pdf:
        with open(document.path, 'rb') as f:
            pdf = PdfFileReader(f, strict=False)
            # TODO: Handle encrypted files

            document.num_pages = pdf.getNumPages()
            informations = pdf.getDocumentInfo()
            if informations is not None:
                document.info.author = "unknown" if not informations.author else informations.author
                document.info.creator = "unknown" if not informations.creator else informations.creator
                document.info.producer = "unknown" if not informations.producer else informations.producer
                document.info.subject = "unknown" if not informations.subject else informations.subject
                document.info.title = "unknown" if not informations.title else informations.title
    else:
        document.num_pages = 1
        document.info.author = "unknown"
        document.info.creator = "unknown"
        document.info.producer = "unknown"
        document.info.subject = "unknown"
        document.info.title = "unknown"


# layout analysis for every page
def extract_page_layouts(pdf_object: PDFObject, config_options="line_margin=0.8"):
    # converts config_options, which is a string to dictionary, so it can be passed as **kwargs to camelot
    args = dict(e.split('=') for e in config_options.split(','))
    for key in args:
        try:
            args[key] = float(args[key])
        except ValueError:
            pass
    resource_manager = PDFResourceManager()
    laparams = LAParams(**args)
    page_aggregator = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, page_aggregator)
    page_layouts = []
    for page in PDFPage.create_pages(pdf_object):
        interpreter.process_page(page)
        page_layouts.append(page_aggregator.get_result())
    return page_layouts


def extract_table_of_contents(document: Document, pdf_object):
    try:
        for (level, title, dest, a, se) in pdf_object.get_outlines():
            document.info.table_of_contents.append((level, title))
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


# extracts LTTextBoxHorizontal and LTImage from layouts
def parse_layouts(document: Document, page_layouts):
    count = 1
    for page_layout in page_layouts:
        parse_elements(document, page_layout, count)
        count = count + 1


# Recursively iterate over all the lt elements from pdfminer.six
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


def extract_tables(document: Document, config_options="pages=all,flavor=lattice,parallel=True"):
    # converts config_options, which is a string to dictionary, so it can be passed as **kwargs to camelot
    args = dict(e.split('=') for e in config_options.split(','))
    for key in args:
        try:
            args[key] = int(args[key])
        except ValueError:
            pass
    # use new OCR path if available
    tables = camelot.read_pdf(document.ocr_path, **args)
    # remove tables with bad accuracy
    tables = [table for table in tables if table.accuracy > 90]
    document.tables = tables


def find_words_paragraphs(paragraphs, search_mode, search_words, match_score):
    result = []
    for paragraph in paragraphs:
        # split paragraph into sentences.
        split = paragraph.split(".")
        for word in search_words:
            found = False
            for string in split:
                if (len(word) <= len(string)) and fuzz.partial_ratio(word, string) > match_score:
                    found = True
                    break
            # exit after finding first match when or mode is selected
            if found and not search_mode:
                break
            # exit if one of words was not Found in and mode
            if not found and search_mode:
                break
        if found:
            result.append(paragraph)
    return result


def find_words_tables(tables, search_mode, search_words, match_score):
    result = []
    for table in tables:
        table.df[0].str.strip('.!? \n\t')
        # perform fuzzy search over all columns
        found = False
        for i in range(0, table.shape[1]):
            if found:
                break
            for x in process.extract(search_words[0], table.df[i].astype(str).values.tolist(),
                                     scorer=fuzz.partial_ratio):
                if x[1] > 80:
                    found = True
                    break
            # exit after finding first match when or mode is selected
            if found and not search_mode:
                break
            # exit if one of words was not Found in and mode
            if not found and search_mode:
                break
        if found:
            result.append(table)
    return result


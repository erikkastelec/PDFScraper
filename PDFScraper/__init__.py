__version__ = "1.0.11"

import argparse
import logging
import os
import shutil
import signal
import sys
import tempfile

from PDFScraper.batchProcessing import find_pdfs_in_path
from PDFScraper.dataStructure import Documents
from PDFScraper.outputGenerator import generate_html
from PDFScraper.pdfParser import get_filename, pdf_to_image, convert_to_pdf, get_pdf_object, extract_page_layouts, \
    extract_tables, parse_layouts, extract_table_of_contents, extract_info


def version():
    return __version__


def main():
    # Define logger level helper
    logger_switcher = {
        'critical': 50,
        'error': 40,
        'warning': 30,
        'info': 20,
        'debug': 10
    }

    # boolean input helper for ArgumentParser
    def str2bool(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    # boolean input helper for search_mode
    def search_mode_helper(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('and', '&', 't', 'y', '1', 'true'):
            return True
        elif v.lower() in ('or', '|', 'f', 'n', '0', 'false'):
            return False
        else:
            raise argparse.ArgumentTypeError('"and" or "or" value expected')


    # Parse arguments from command line
    argumentParser = argparse.ArgumentParser()
    argumentParser.add_argument('--path', help='path to pdf folder or file', default=".")
    argumentParser.add_argument('--out', help='path to output file location', default=".")
    argumentParser.add_argument('--log_level', choices=['critical', 'error', 'warning', 'info', 'debug'], help='logger '
                                                                                                               'level to '
                                                                                                               'use ('
                                                                                                               'default: '
                                                                                                               'info)',
                                default='info')
    argumentParser.add_argument('--search', help='word to search for', default="default")
    argumentParser.add_argument('--tessdata', help='location of tesseract data files', default="/usr/share/tessdata")
    argumentParser.add_argument('--tables', type=str2bool, help='should tables be extracted and searched', default=True)
    # True -> and mode, False -> or mode
    argumentParser.add_argument('--search_mode', type=search_mode_helper, help='And or Or search, when multiple '
                                                                               'search words are provided',
                                default=True)

    args = vars(argumentParser.parse_args())
    output_path = args["out"]
    log_level = logger_switcher.get(args["log_level"])
    search_word = args["search"]
    tessdata_location = args["tessdata"]
    tables_extract = args["tables"]
    search_mode = args["search_mode"]

    # Set up logger
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
    logger.info("Started")

    # Define signal handlers
    def signal_handler(sign, frame):
        logger.info("Ctrl+C pressed")
        logger.info("Stopping")
        sys.exit(0)

    # Start signal handlers
    signal.signal(signal.SIGINT, signal_handler)

    # Read PDFs from path
    docs = Documents(path=os.path.abspath(args["path"]))
    logger.info('Finding PDFs in ' + docs.path)
    try:
        find_pdfs_in_path(docs, docs.path)
    except Exception as e:
        logger.error(e)
        sys.exit(1)
    logger.info('Found ' + str(docs.num_docs) + ' PDFs')

    logger.info('Parsing ' + str(docs.num_docs) + ' documents')
    # Extract information about PDFs
    progress_counter = 1
    for doc in docs.docs:
        extract_info(doc)
        if doc.isPDF:
            get_pdf_object(doc)
            if doc.extractable:
                #extract_info(doc)
                logger.debug('Document information:' + '\n' + doc.document_info_to_string())
                extract_table_of_contents(doc)
                logger.debug('Table of contents: \n' + doc.table_of_contents_to_string())
                extract_page_layouts(doc)
                # table extraction is possible only for text based PDFs
                if tables_extract:
                    extract_tables(doc, output_path)
                parse_layouts(doc)
                if len(doc.paragraphs) == 0:
                    logger.info("Regular text extraction is not possible. Trying to extract text using OCR")
                    get_filename(doc)
                    pdf_to_image(doc)
                    convert_to_pdf(doc, tessdata_location)
                    get_pdf_object(doc)
                    extract_page_layouts(doc)
                    if tables_extract:
                        extract_tables(doc, output_path)
                    parse_layouts(doc)

            else:
                logger.warning("Skipping parsing. Document is not extractable.")
            logger.info('Parsed ' + str(progress_counter) + ' out of ' + str(docs.num_docs) + ' documents')
            progress_counter += 1
        else:
            logger.info("Regular text extraction is not possible. Trying to extract text using OCR")
            get_filename(doc)
            pdf_to_image(doc)
            convert_to_pdf(doc, tessdata_location)
            get_pdf_object(doc)
            extract_page_layouts(doc)
            if tables_extract:
                extract_tables(doc, output_path)
            parse_layouts(doc)
        logger.debug('Paragraphs: \n' + '\n'.join(doc.paragraphs))
    logger.info('Done parsing PDFs')
    logger.info('Stopping')
    generate_html(output_path, docs, search_word, search_mode)
    # clean up temporary directory
    shutil.rmtree(tempfile.gettempdir() + "/PDFScraper", ignore_errors=True)
    sys.exit(0)



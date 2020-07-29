import argparse
import logging
import signal
import sys

from pdfExtractor.batchProcessing import find_pdfs_in_path
from pdfExtractor.dataStructure import Documents
from pdfExtractor.pdfParser import extract_info, extract_table_of_contents, get_pdf_object, extract_paragraphs, \
    extract_page_layouts, get_filename, pdf_to_image, extract_text_OCR

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

# Parse arguments from command line
argumentParser = argparse.ArgumentParser()
argumentParser.add_argument('--path', help='path to pdf folder or file', default=".")
args = vars(argumentParser.parse_args())


# Define signal handlers
def signal_handler(sign, frame):
    logger.info("Ctrl+C pressed")
    logger.info("Stopping")
    sys.exit(0)


# Start signal handlers
signal.signal(signal.SIGINT, signal_handler)

# Read PDFs from path
docs = Documents(args["path"])
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

    get_pdf_object(doc)

    if doc.extractable:
        extract_info(doc)
        logger.debug('Document information:' + '\n' + doc.document_info_to_string())
        extract_table_of_contents(doc)
        logger.debug('Table of contents: \n' + doc.table_of_contents_to_string())
        extract_page_layouts(doc)
        extract_paragraphs(doc)
        if len(doc.paragraphs) == 0:
            logger.info("Regular text extraction is not possible. Trying to extract text using OCR")
            get_filename(doc)
            pdf_to_image(doc)
            extract_text_OCR(doc)
            logger.debug(doc.text)
        logger.debug('Paragraphs: \n' + '\n'.join(doc.paragraphs))

    else:
        logger.warning("Skipping parsing. Document is not extractable.")
    logger.info('Parsed ' + str(progress_counter) + ' out of ' + str(docs.num_docs) + ' documents')
    progress_counter += 1

logger.info('Done parsing PDFs')
logger.info('Stopping')
sys.exit(0)

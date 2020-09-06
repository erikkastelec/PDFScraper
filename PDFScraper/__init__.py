__version__ = "1.1.6"

import logging


def version():
    return __version__


# set up logging
logger = logging.getLogger("PDFScraper")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)
fileHandler = logging.FileHandler('PDFScraper.log', 'w')
logger.addHandler(consoleHandler)
logger.addHandler(fileHandler)
logger.info("Started")

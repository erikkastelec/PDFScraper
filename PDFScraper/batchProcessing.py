import os

from PDFScraper.dataStructure import Document
from PDFScraper.dataStructure import Documents


def find_pdfs_in_path(docs: Documents, path: str):

    if os.path.exists(path):
        if os.path.isdir(path):  # find PDFs in directory and add them to the list
            count = 0
            for f in os.listdir(path):
                count += 1
                find_pdfs_in_path(docs, path + '/' + f)
        elif os.path.isfile(path) and (path.endswith(".pdf")):

            docs.num_docs += 1
            docs.docs.append(Document(path, docs, True))
        elif os.path.isfile(path) and (path.endswith(".bmp") or path.endswith(".jpg") or path.endswith(".pbm")
                                       or path.endswith(".pgm") or path.endswith(".ppm") or path.endswith(".jpeg")
                                       or path.endswith(".jpe") or path.endswith(".jp2") or path.endswith(".tiff")
                                       or path.endswith(".tif") or path.endswith(".png")):
            docs.num_docs += 1

            docs.docs.append(Document(path, docs, False))

    else:
        raise Exception("Provided path does not exist")

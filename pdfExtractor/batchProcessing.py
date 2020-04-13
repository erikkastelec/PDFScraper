import os

from pdfExtractor.dataStructure import Document
from pdfExtractor.dataStructure import Documents


def find_pdfs_in_path(docs: Documents):
    if os.path.exists(docs.path):
        if os.path.isdir(docs.path):  # find PDFs in directory and add them to the list
            pdfs = [
                f for f in os.listdir(docs.path, docs)
                if os.path.isfile(f) and f.endswith(".pdf")
            ]
            for pdf in pdfs:
                docs.docs.append(Document(pdf))
                docs.num_docs += 1
        elif os.path.isfile(docs.path):
            docs.num_docs = 1
            docs.docs.append(Document(docs.path, docs))

    else:
        raise Exception("Provided path does not exist")

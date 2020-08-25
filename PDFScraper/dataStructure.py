


class Documents:
    def __init__(self, path: str):
        self.num_docs = 0
        self.docs = []
        self.path = path


class Document:
    def __init__(self, path: str, parent: Documents, isPDF: bool):
        self.parent = parent
        self.isPDF = isPDF
        self.author = "unknown"
        self.producer = "unknown"
        self.subject = "unknown"
        self.title = "unknown"
        self.path = path
        self.ocr_path = path
        self.num_pages = None
        self.text = []
        self.images = []
        self.tables = []
        self.ltfigures = []
        self.paragraphs = []
        self.table_of_contents = []
        self.page_layouts = []
        self.doc = None
        self.extractable = False
        self.filename = None

    def document_info_to_string(self):
        return "Author: " + self.author + "\n" \
               + "Producer: " + self.producer + "\n" \
               + "Subject: " + self.subject + "\n" \
               + "Title: " + self.title + "\n" \
               + "Number of Pages: " + str(self.num_pages)

    def table_of_contents_to_string(self):
        output_string = ""
        for tup in self.table_of_contents:
            output_string += str(tup[0]) + ': ' + tup[1] + '\n'
        return output_string

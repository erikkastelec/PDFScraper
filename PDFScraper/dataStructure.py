class Document:
    # general info about document
    class Info:
        def __init__(self):
            self.author = "unknown"
            self.producer = "unknown"
            self.subject = "unknown"
            self.title = "unknown"
            self.table_of_contents = []

    def __init__(self, path: str, is_pdf: bool):
        self.is_pdf = is_pdf
        self.info = Document.Info()
        self.path = path
        self.ocr_path = path
        self.num_pages = None
        self.images = []
        self.tables = []
        self.paragraphs = []
        self.extractable = False
        self.filename = None

    def document_info_to_string(self):
        return "Author: " + self.info.author + "\n" \
               + "Producer: " + self.info.producer + "\n" \
               + "Subject: " + self.info.subject + "\n" \
               + "Title: " + self.info.title + "\n" \
               + "Number of Pages: " + str(self.num_pages)

    def table_of_contents_to_string(self):
        output_string = ""
        for tup in self.info.table_of_contents:
            output_string += str(tup[0]) + ': ' + tup[1] + '\n'
        return output_string

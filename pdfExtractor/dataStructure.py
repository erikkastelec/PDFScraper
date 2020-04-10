class Documents:
    def __init__(self, path: str):
        self.num_docs = 0
        self.docs = []
        self.path = path


class Document:
    def __init__(self, path: str):
        self.author = None
        self.producer = None
        self.subject = None
        self.title = None
        self.path = path
        self.num_pages = None
        self.text = list()
        self.image = []
        self.table = []
        self.paragraphs = []

    def documentInfoToString(self):
        return "Author: " + self.author + "\n" \
               + "Producer: " + self.producer + "\n" \
               + "Subject: " + self.subject + "\n" \
               + "Title: " + self.title + "\n" \
               + "Number of Pages: " + str(self.num_pages)

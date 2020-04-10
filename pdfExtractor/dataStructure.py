class Documents:
    def __init__(self, path: str):
        self.num_docs = 0
        self.docs = []
        self.path = None


class Document:
    def __init__(self, path: str):
        self.author = "unknown"
        self.producer = "unknown"
        self.subject = "unknown"
        self.title = "unknown"
        self.path = path
        self.num_pages = None
        self.text = []
        self.image = []
        self.table = []
        self.paragraphs = []

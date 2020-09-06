# PDFScraper
[![PyPI version](https://badge.fury.io/py/PDFScraper.svg)](https://badge.fury.io/py/PDFScraper)

CLI program for searching text and tables inside of PDF documents and displaying results in HTML. It combines [Pdfminer.six](https://github.com/pdfminer/pdfminer.six), [Camelot](https://github.com/camelot-dev/camelot) and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) in a single program, which is simple to use.

# How to use
### Install using pip

Use pip to install PDFScraper:

<pre>
$ pip install PDFScraper
</pre>

### Arguments
<pre>
optional arguments:
  -h, --help            show this help message and exit
  --path PATH           path to pdf folder or file
  --out OUT             path to output file location
  --log_level {critical,error,warning,info,debug}
                        logger level to use (default: info)
  --search SEARCH       word to search for
  --tessdata TESSDATA   location of tesseract data files
  --tables TABLES       should tables be extracted and searched
  --search_mode SEARCH_MODE
                        And or Or search, when multiple search words are
                        provided
  --multiprocessing MULTIPROCESSING
                        should multiprocessing be enabled
</pre>



`path`, by default ".", specifies the location of the PDF folder or directory.

`out`, by default ".", specifies output directory in which `summary.html` file is created.

`search` argument is used for specifying the word or sentence that will be searched for in the PDF documents.

`tessdata` argument can be used to specify custom tessdata location for OCR analysis.

`tables`, by default True, specifies whether to search for search word in tables. Disabling tables search improves speed significantly.

`search_mode`, by default in 'and' mode, specifies whether all the search terms need to be contained inside paragraph. In 'or' mode, the paragraph is returned if any of the terms are contained. In 'and' mode, the paragraph is returned if all the terms are contained.

`multiprocessing`, by default True, runs process in multiple threads to speed up processing. **Should not be used with OCR as it significantly decreases performance**
### OCR

**tessdata pretrained language [files](https://github.com/tesseract-ocr/tessdata_best) need to be manually added to the tessdata directory.**


OCR analysis of PDF documents currently supports English and Slovenian language. 
Language of the document is automatically detected using [langdetect library](https://github.com/Mimino666/langdetect).


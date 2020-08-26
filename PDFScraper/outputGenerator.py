import codecs
import os
import re
import tempfile
from pathlib import Path

from fuzzywuzzy import fuzz, process
from yattag import Doc, indent

from PDFScraper.dataStructure import Documents


def generate_html(output_path: str, docs: Documents, search_word: str, search_mode: bool):
    # TODO: implement html generation
    doc, tag, text = Doc().tagtext()

    doc.asis('<!DOCTYPE html>')

    with tag('html'):
        with tag('head'):
            with tag('style'):
                doc.asis('''

// Breakpoints
$bp-maggie: 15em; 
$bp-lisa: 30em;
$bp-bart: 48em;
$bp-marge: 62em;
$bp-homer: 75em;

// Styles
* {
 @include box-sizing(border-box);
 
 &:before,
 &:after {
   @include box-sizing(border-box);
 }
}

body {
  font-family: $helvetica;
  color: rgba(94,93,82,1);
}

a {
  color: rgba(51,122,168,1);
  
  &:hover,
  &:focus {
    color: rgba(75,138,178,1); 
  }
}

.container {
  margin: 5% 3%;
  
  @media (min-width: $bp-bart) {
    margin: 2%; 
  }
  
  @media (min-width: $bp-homer) {
    margin: 2em auto;
    max-width: $bp-homer;
  }
}

.responsive-table {
  width: 100%;
  margin-bottom: 1.5em;
  border-spacing: 0;
  
  @media (min-width: $bp-bart) {
    font-size: .9em; 
  }
  
  @media (min-width: $bp-marge) {
    font-size: 1em; 
  }
  
  thead {
    // Accessibly hide <thead> on narrow viewports
    position: absolute;
    clip: rect(1px 1px 1px 1px); /* IE6, IE7 */
    padding: 0;
    border: 0;
    height: 1px; 
    width: 1px; 
    overflow: hidden;
    
    @media (min-width: $bp-bart) {
      // Unhide <thead> on wide viewports
      position: relative;
      clip: auto;
      height: auto;
      width: auto;
      overflow: auto;
    }
    
    th {
      background-color: rgba(29,150,178,1);
      border: 1px solid rgba(29,150,178,1);
      font-weight: normal;
      text-align: center;
      color: white;
      
      &:first-of-type {
        text-align: left; 
      }
    }
  }
  
  // Set these items to display: block for narrow viewports
  tbody,
  tr,
  th,
  td {
    display: block;
    padding: 0;
    text-align: left;
    white-space: normal;
  }
  
  tr {   
    @media (min-width: $bp-bart) {
      // Undo display: block 
      display: table-row; 
    }
  }
  
  th,
  td {
    padding: .5em;
    vertical-align: middle;
    
    @media (min-width: $bp-lisa) {
      padding: .75em .5em; 
    }
    
    @media (min-width: $bp-bart) {
      // Undo display: block 
      display: table-cell;
      padding: .5em;
    }
    
    @media (min-width: $bp-marge) {
      padding: .75em .5em; 
    }
    
    @media (min-width: $bp-homer) {
      padding: .75em; 
    }
  }
  
  caption {
    margin-bottom: 1em;
    font-size: 1em;
    font-weight: bold;
    text-align: center;
    
    @media (min-width: $bp-bart) {
      font-size: 1.5em;
    }
  }
  
  tfoot {
    font-size: .8em;
    font-style: italic;
    
    @media (min-width: $bp-marge) {
      font-size: .9em;
    }
  }
  
  tbody {
    @media (min-width: $bp-bart) {
      // Undo display: block 
      display: table-row-group; 
    }
    
    tr {
      margin-bottom: 1em;
      
      @media (min-width: $bp-bart) {
        // Undo display: block 
        display: table-row;
        border-width: 1px;
      }
      
      &:last-of-type {
        margin-bottom: 0; 
      }
      
      &:nth-of-type(even) {
        @media (min-width: $bp-bart) {
          background-color: rgba(94,93,82,.1);
        }
      }
    }
    
    th[scope="row"] {
      background-color: rgba(29,150,178,1);
      color: white;
      
      @media (min-width: $bp-lisa) {
        border-left: 1px solid  rgba(29,150,178,1);
        border-bottom: 1px solid  rgba(29,150,178,1);
      }
      
      @media (min-width: $bp-bart) {
        background-color: transparent;
        color: rgba(94,93,82,1);
        text-align: left;
      }
    }
    
    td {
      text-align: right;
      
      @media (min-width: $bp-bart) {
        border-left: 1px solid  rgba(29,150,178,1);
        border-bottom: 1px solid  rgba(29,150,178,1);
        text-align: center; 
      }
      
      &:last-of-type {
        @media (min-width: $bp-bart) {
          border-right: 1px solid  rgba(29,150,178,1);
        } 
      }
    }
    
    td[data-type=currency] {
      text-align: right; 
    }
    
    td[data-title]:before {
      content: attr(data-title);
      float: left;
      font-size: .8em;
      color: rgba(94,93,82,.75);
      
      @media (min-width: $bp-lisa) {
        font-size: .9em; 
      }
      
      @media (min-width: $bp-bart) {
        // Don’t show data-title labels 
        content: none; 
      }
    } 
  }
}
''')

        with tag('body'):
            with tag('h1', id="heading"):
                text('Summary of search results')
            doc_index = 0
            for document in docs.docs:
                with tag('div', id=str(doc_index)):
                    doc_index += 1
                    header_printed = False

                    # output extracted paragraphs

                    for paragraph in document.paragraphs:
                        # split paragraph into sentences.
                        split = paragraph.split(".")
                        for word in search_word.split(","):
                            print_paragraph = False
                            for string in split:
                                if (len(word) <= len(string)) and fuzz.partial_ratio(word, string) > 80:
                                    print_paragraph = True
                                    break
                            # exit after finding first match when or mode is selected
                            if print_paragraph and not search_mode:
                                break
                            # exit if one of words was not Found in and mode
                            if not print_paragraph and search_mode:
                                break

                        if print_paragraph:
                            with tag('p'):
                                if not header_printed:
                                    with tag('h2'):
                                        text("Found in document with location: " + str(document.path))
                                header_printed = True
                                text(paragraph)
                    # output extracted tables
                    table_index = 0
                    for table in document.tables:
                        with tag('div', id="table" + str(table_index), klass="container"):
                            table_index += 1
                            tempfile_path = tempfile.gettempdir() + "/PDFScraper"
                            try:
                                os.makedirs(tempfile_path)
                            except FileExistsError:
                                pass
                            tempfile_path = tempfile_path + "/table"
                            table.df[0].str.strip('.!? \n\t')
                            # perform fuzzy search over all columns
                            found = False
                            for i in range(0, table.shape[1]):
                                if not found:
                                    for x in process.extract(search_word, table.df[i].astype(str).values.tolist(),
                                                             scorer=fuzz.partial_ratio):
                                        if x[1] > 80:
                                            table.to_html(tempfile_path, classes="responsive-table", index=False)
                                            with codecs.open(tempfile_path, 'r') as table_file:
                                                # replace \n in table to fix formatting
                                                tab = re.sub(r'\\n', '<br>', table_file.read())
                                                if not header_printed:
                                                    with tag('h2'):
                                                        text("Found in document with location: " + str(document.path))
                                                doc.asis(tab)
                                                os.remove(tempfile_path)
                                            found = True
                                            break

    # write HTML to file
    # check if output path is a directory
    if not os.path.isdir(output_path):
        output_path = str(Path(output_path).parent)
    with open(output_path + "/summary.html", "w") as file:
        file.write(indent(doc.getvalue()))

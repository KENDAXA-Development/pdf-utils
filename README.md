## Tools for processing pdf files

This is a small and light-weighted library for processing pdf files in python.
One of the use-cases might be the extraction of pdf-annotations for ML / NLP.

Support for

* obtaining textual and vizual content of pdf files
* locating positions of words
* fetching pdf annotations
* adding digital layer to image-pdfs
* re-creating a clean pdf file with annotations removed,

etc

## Dependencies

Main tool for reading pdf files is the PyPDF2 library.

Apart of pip requirement, you should have [Poppler](https://poppler.freedesktop.org/) installed. (We use of its `pdftotext`, and `pdftoppm` commands.)

## Tools for processing pdf files

This is a small and light-weighted library for processing pdf files in python.
One of the use-cases might be the extraction of pdf-annotations for ML / NLP.

Support for

* obtaining textual and vizual content of pdf files
* locating positions of words
* fetching pdf annotations
* adding digital layer to image-pdfs
* re-creating a clean pdf file with annotations removed


## Dependencies

Main tool for reading pdf files is the PyPDF2 library.

Apart of pip requirement, you should have [Poppler](https://poppler.freedesktop.org/) and [Tesseract](https://tesseract-ocr.github.io/tessdoc/Home.html) installed. 
We use Poppler mainly for extracting images and text from pdfs, and Tesseract is needed for pytesseract.

## How to

Some examples of usage are shown in the [notebook]("https://bitbucket.kendaya.net/projects/KXLAB/repos/pdf-tools/browse/notebook/Demo.ipynb").

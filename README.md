## Tools for processing pdf files

This is a light-weighted library for processing pdf files in python.
One of the use-cases might be the extraction of pdf-annotations for ML / NLP.

Support for

* obtaining textual and vizual content of pdf files
* locating positions of words
* fetching pdf annotations
* adding a digital layer to image-pdfs
* re-creating a clean pdf file with annotations removed


## Dependencies

Main tools for reading pdf files are the PyPDF2 library. Non-python dependencies are
 
* [Poppler](https://poppler.freedesktop.org/),
* [Tesseract](https://tesseract-ocr.github.io/tessdoc/Home.html), and 
* [OpenCV](https://opencv.org/).

To install Poppler, see the guide in the [pdf2image readme](https://pypi.org/project/pdf2image/).

## How to

Some examples of usage are shown in the [notebook](./notebook/Demo.ipynb).

## Todo

* Add detection of page-orientation (upside-down, rotated,...) based on images.
* Add some of our experiments with "naive" table detection
* Get rid of PyPDF2 as [it is not maintained](https://stackoverflow.com/questions/63199763/maintained-alternatives-to-pypdf2); replace by PyMUPdf or pdfMiner.six.

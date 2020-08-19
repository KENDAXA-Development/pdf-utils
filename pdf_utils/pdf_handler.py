"""Tools to process one pdf file.

Main methods support extracting textual content, extracting images, localizing positions of words,
extracting annotations, and converting an image-like pdf into "searchable" pdf via doing ocr.
"""
import logging
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
from PIL import Image
from PyPDF2 import PdfFileReader
from lxml import html

from pdf_utils.converter import image_from_pdf_page, merge_pdfs
from pdf_utils.ocr import Scanner
from pdf_utils.rectangle import Rectangle

logger = logging.getLogger(__name__)


class CannotReadPdf(Exception):
    """PyPDF2 cannot read the pdf."""


class Pdf:
    """Process one pdf file."""

    parser = html.HTMLParser(encoding="utf-8")

    def __init__(self, pdf_path: Union[str, Path]) -> None:
        """Define pdf path, pdf reader, initialize images."""
        self.pdf_path = Path(pdf_path)
        self.pdf_file = open(self.pdf_path, 'rb')
        self.pdf_reader = PdfFileReader(self.pdf_file)

        if self.pdf_reader.isEncrypted:
            try:
                self.pdf_reader.decrypt("")
            except NotImplementedError:
                raise CannotReadPdf(f"cannot decrypt pdf file: {pdf_path}")

        self._images = {}
        self._rotated = {}

        self._simple_text = None  # results of simple pdftotext
        self._layout_text = None  # result of pdftotext with -layout param
        # root of the xml tree representing the `pdftotext -bbox-layout output that includes bounding boxes of words
        self._root = None

    @property
    def name(self) -> str:
        """Return pdf's file name."""
        return self.pdf_path.name

    @property
    def number_of_pages(self) -> int:
        """Get number of pages in the pdf."""
        return self.pdf_reader.getNumPages()

    def get_width_height(self, page_idx: int = 0) -> Tuple[int, int]:
        """Return the with and height of the pdf page.

        If pdf page is internally rotated by 90 or 270 degrees, we swap the internal pdf width and height.
        This should reflect the width and height that is visible to the end-user.
        """
        crop_box = self.pdf_reader.getPage(page_idx).cropBox
        if not int(crop_box[0]) == int(crop_box[1]) == 0:
            raise CannotReadPdf(f"cannot read pdf width / height on page {page_idx}, crop_box = {crop_box}")
        pdf_width = int(crop_box.getWidth())
        pdf_height = int(crop_box.getHeight())

        page_rotation = self.page_rotation(page_idx)
        if page_rotation in {90, 270}:
            pdf_width, pdf_height = pdf_height, pdf_width

        if pdf_width < 0 or pdf_height < 0:
            logger.warning(f"negative page size detected, w={pdf_width}, h={pdf_height}, ignoring sign")

        return abs(pdf_width), abs(pdf_height)

    def page_rotation(self, page_idx: int) -> bool:
        """Expose self._rotated."""
        if page_idx in self._rotated:
            return self._rotated[page_idx]
        self._rotated[page_idx] = self.pdf_reader.getPage(page_idx).get("/Rotate", 0)
        return self._rotated[page_idx]

    def page_image(self,
                   page_idx: int = 0,
                   dpi: int = 150,
                   recompute: bool = False,
                   rotation_thres: float = 0.1) -> Union[Image.Image, np.ndarray]:
        """Get the image of a pdf page.

        If the page has internal nonzero "Rotation", we ignore it; we just call pdftoppm and don't rotate anything.
        Note that a second call, even with different dpi, will return the cached image, unless 'recompute' flag is on.

        :param page_idx: page number, starting from zero
        :param dpi: dpi
        :param recompute: if True, image will be rerendered even if computed before
        :param rotation_thres: if image w/h ratio and pdf-page w/h ratio differ too much, raise Exception
        :return: image of the pdf page
        """
        # if image already exists, reuse it
        if page_idx in self._images and not recompute:
            img = self._images[page_idx]
        else:
            img = image_from_pdf_page(str(self.pdf_path), page_num=page_idx, dpi=dpi, return_numpy=False)
            self._images[page_idx] = img

            w, h = self.get_width_height(page_idx)
            img_w, img_h = img.size
            is_inconsistent = abs(img_h / img_w - h / w) > rotation_thres
            if is_inconsistent:
                raise CannotReadPdf(f"inconsistent width/height ratio on page {page_idx}: "
                                    f"page = ({img_w, img_h}), pdf = {(w, h)}")
        return img

    @property
    def images(self) -> Iterable[Image.Image]:
        """Return all images as a list."""
        return (self.page_image(page_idx) for page_idx in range(self.number_of_pages))

    def extract_text_from_pdf(self,
                              pdftotext_layout_argument: Optional[str] = None,
                              page_idx: Optional[int] = None) -> str:
        """Get textual pdf content. Wrapper of Poppler's pdftotext.

        :param pdftotext_layout_argument: None, "-layout" or "-bbox-layout". Argument passed to the pdftotext
        :return: pdftotext result
        """
        pdftotext_args = ["pdftotext"]
        if pdftotext_layout_argument is not None:
            pdftotext_args.append(pdftotext_layout_argument)

        if page_idx is not None:
            pdftotext_args.extend(["-f", str(page_idx + 1), "-l", str(page_idx + 1)])

        return subprocess.check_output(
            pdftotext_args + [str(self.pdf_path), "-"], universal_newlines=True)

    @property
    def simple_text(self) -> str:
        """Use `pdftotext` to extract textual content."""
        if self._simple_text is None:
            self._simple_text = self.extract_text_from_pdf()
        return self._simple_text

    @property
    def layout_text(self) -> str:
        """Use `pdftotext -layout` to extract textual content."""
        if self._layout_text is None:
            self._layout_text = self.extract_text_from_pdf("-layout")
        return self._layout_text

    def get_page_as_html(self, page_idx: int) -> html.HtmlElement:
        """Get textual content including bounding boxes of each word, represented as the root of the xml tree."""
        bbox_text = self.extract_text_from_pdf(pdftotext_layout_argument="-bbox-layout", page_idx=page_idx)
        return html.fromstring(bbox_text, parser=self.parser)

    def get_pages(self) -> Dict[int, List[html.HtmlElement]]:
        """Return a dictionary {page_num: list_of_words (as xml elements)}."""
        res = {}
        for page_idx in range(self.number_of_pages):
            res[page_idx] = self.get_page_as_html(page_idx=page_idx).findall(".//word")
        return res

    def get_pages_as_text(self) -> Dict[int, List[str]]:
        """Return a dictionary {page_num : list_of_words (as strings)}."""
        return {
            page_nr: list(map(lambda w: w.text if w.text is not None else "", words))
            for page_nr, words in self.get_pages().items()}

    def recreate_digital_content(self,
                                 output_pdf: str,
                                 images_dpi: int = 150,
                                 higher_dpi_for_scan: Optional[int] = None,
                                 tesseract_lang: str = "eng",
                                 tesseract_conf: str = "") -> None:
        """Get images, do OCR and create a new pdf with new text layer.

        Can be useful for documents which are only images.
        If there is a textual layer at the beginning, it will be lost.

        :param output_pdf: path to the output pdf file
        :param images_dpi: resolution of images that will be used for ocr, and that will be inserted into the final pdf
        :param higher_dpi_for_scan: if not None, higher resolution image will be created for ocr only
        :param tesseract_lang: language to expect
        :param tesseract_conf: tesseract configuration
        """
        temp_dir, pdf_paths = mkdtemp(), []
        for page_idx in range(self.number_of_pages):
            img = self.page_image(
                page_idx=page_idx,
                dpi=images_dpi,
                recompute=True)  # this make take some time, but less than ocr
            current_pdf_name = str(Path(temp_dir) / f"{page_idx}.pdf")
            pdf_paths.append(current_pdf_name)
            pdf_width, pdf_height = self.get_width_height(page_idx)
            img_for_ocr = img
            if higher_dpi_for_scan is not None:
                if higher_dpi_for_scan < images_dpi:
                    logger.warning("lower resolution is used for OCR than for insertion into the pdf; ocr can be bad")
                img_for_ocr = self.page_image(page_idx, dpi=higher_dpi_for_scan, recompute=True)
            ocr_text = Scanner.ocr_one_image(img_for_ocr, tesseract_lang, tesseract_conf)
            Scanner.image_to_one_page_ocred_pdf(
                img, current_pdf_name, pdf_width=pdf_width, pdf_height=pdf_height, ocr_text=ocr_text)

        merge_pdfs(output_pdf, *pdf_paths)
        # cleanup
        shutil.rmtree(temp_dir)

    @staticmethod
    def get_bounding_box_of_elem(elem: html.HtmlElement) -> Rectangle:
        """Return coordinates of the bounding box of a word, as a 4-tuple."""
        return Rectangle(
            x_min=elem.attrib["xmin"],
            y_min=elem.attrib["ymin"],
            x_max=elem.attrib["xmax"],
            y_max=elem.attrib["ymax"])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.__del__()

    def __del__(self):
        self.pdf_file.close()

    def __repr__(self) -> str:
        return f"<Pdf object associated with {self.pdf_path}>"

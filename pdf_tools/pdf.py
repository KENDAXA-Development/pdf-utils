"""Tools to process one pdf file.

Main methods support extracting textual content, extracting images, localizing positions of words,
extracting annotations, and converting an image-like pdf into "searchable" pdf via doing ocr.
"""
import logging
import subprocess
from pathlib import Path
from typing import Tuple, List, Union, Dict, Optional

import numpy as np
from PIL import Image
from PyPDF2 import PdfFileReader
from lxml import html

from pdf_tools.converter import image_from_pdf_page
from pdf_tools.rectangle import Rectangle


class CannotReadPdf(Exception):
    """PyPDF2 cannot read the pdf."""


class Pdf:
    """Process one pdf file."""

    parser = html.HTMLParser(encoding="utf-8")

    def __init__(self, pdf_path: str) -> None:
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
        return self.pdf_path.name

    @property
    def number_of_pages(self) -> int:
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
            logging.warning(f"negative page size detected, w={pdf_width}, h={pdf_height}, ignoring sign")

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
    def images(self) -> List[Image.Image]:
        """Return all images as a list."""
        return [self.page_image(page_idx) for page_idx in range(self.number_of_pages)]

    def _extract_text_from_pdf(self, pdftotext_layout_argument: Optional[str] = None) -> str:
        """Get textual pdf content. Wrapper of Poppler's pdftotext.

        :param pdftotext_layout_argument: None, "-layout" or "-bbox-layout". Argument passed to the pdftotext
        :return: pdftotext result
        """
        pdftotext_args = ["pdftotext", "-enc", "UTF-8"]
        if pdftotext_layout_argument is not None:
            pdftotext_args.append(pdftotext_layout_argument)
        return subprocess.check_output(
            pdftotext_args + [str(self.pdf_path), "-"], universal_newlines=True)

    def get_simple_text(self) -> str:
        """Use `pdftotext` to extract textual content."""
        if self._simple_text is None:
            self._simple_text = self._extract_text_from_pdf()
        return self._simple_text

    def get_layout_text(self) -> str:
        """Use `pdftotext -layout` to extract textual content."""
        if self._layout_text is None:
            self._layout_text = self._extract_text_from_pdf("-layout")
        return self._layout_text

    def get_text_with_bb(self) -> html.HtmlElement:
        """Get textual content including bounding boxes of each word, represented as the root of the xml tree."""
        if self._root is None:
            bbox_text = self._extract_text_from_pdf("-bbox-layout")
            self._root = html.fromstring(bbox_text, parser=self.parser)
        return self._root

    def get_pages(self) -> Dict[int, List[html.HtmlElement]]:
        """Return a dictionary {page_num: list_of_words (as xml elements)}."""
        res = {}
        root = self.get_text_with_bb()
        for page_num, page in enumerate(root.findall(".//page")):
            res[page_num] = page.findall(".//word")
        return res

    def get_pages_as_text(self) -> Dict[int, List[str]]:
        """Return a dictionary {page_num : list_of_words (as strings)}."""
        return {
            page_nr: list(map(lambda w: w.text if w.text is not None else "", words))
            for page_nr, words in self.get_pages().items()}

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
"""
Various basic tools for conversions between pdf's, text, images and words and word indices.
The most basic conversion function are just wrappers around the Poppler utils `pdftotext` and `pdftoppm`.
"""
from typing import Union, List, Optional, Tuple, Dict
import subprocess

import numpy as np
import pdf2image
from PIL import Image

from .rectangle import Rectangle


class RotatedPdfException(Exception):
    """Ratio of pdf-width / pdf_height does not agree with the ratio image_width / image_height"""


def image_from_pdf_page(pdf_path: str,
                        page_num: int,
                        dpi: int = 150,
                        return_numpy: bool = True,
                        rotate_by: int = 0) -> Union[Image.Image, np.ndarray]:
    """Return the requested page as a png-image PIL object (no file creation) or a numpy array.

    Page numbers are here counted from zero.

    https://iq.opengenus.org/pdf_to_image_in_python/
    """
    images = pdf2image.convert_from_path(
        pdf_path,
        dpi=dpi,
        output_folder=None,
        first_page=page_num + 1,
        last_page=page_num + 1,
        fmt='png',
        thread_count=1,
        userpw=None,
        use_cropbox=False,
        strict=False)
    img = images[0]
    if rotate_by:
        img = img.rotate(rotate_by, expand=True)
    if return_numpy:
        img = np.array(img)
    return img


def pdf_box_to_image_box(pdf_box: Rectangle,
                         pdf_width: int,
                         pdf_height: int,
                         img_width: int,
                         img_height: int) -> Rectangle:
    """Convert a box in pdf coordinates into the box in image coordinates.

    :param pdf_box: a Rectangle representing some area in a pdf page
    :param pdf_width:
    :param pdf_height:
    :param img_width:
    :param img_height:
    :return: a corresponding Rectangle in the image-coordinates
    """
    if abs(img_height / img_width - pdf_height / pdf_width) > 0.1:
        raise RotatedPdfException("Pdf seems to be rotated, skipping")

    w_scale = img_width / pdf_width
    h_scale = img_width / pdf_width
    return Rectangle(
        x_min=pdf_box.x_min * w_scale,
        y_min=pdf_box.y_min * h_scale,
        x_max=pdf_box.x_max * w_scale,
        y_max=pdf_box.y_max * h_scale,
        dtype=int,
    )


def save_images_to_pdf(images: List[Image.Image], output_pdf: str) -> None:
    """Saves a list of images as a vanilla image-pdf (no text content), each image one page."""
    images[0].save(output_pdf, "PDF", save_all=True, append_images=images[1:])


def extract_text_from_pdf(pdf_path: str, pdftotext_layout_argument: Optional[str] = None) -> str:
    """Wrapper of Poppler's pdftotext.

    :param pdf_path: pdf file path
    :param pdftotext_layout_argument: None, "-layout" or "-bbox-layout". Argument passed to the pdftotext
    :return: pdftotext result
    """
    pdftotext_args = ["pdftotext", "-enc", "UTF-8"]
    if pdftotext_layout_argument is not None:
        pdftotext_args.append(pdftotext_layout_argument)
    return subprocess.check_output(
        pdftotext_args + [str(pdf_path), "-"], universal_newlines=True)


def get_indices_of_words(words: List[str], char_span: Tuple[int, int]) -> Dict:
    """
    Given a list of words and a span of 'matched characters', we compute here which words are matched
    :param words: list of words (strings)
    :param char_span: a tuple (lower_index, upper_index) denoting character span of text segment within ' '.join(words)
    lower_index is inclusive, upper_index is exclusive
    :return:
        'full words': list of indices of words that are fully included in the char_span,
        'partial words': list of indices of words that are partially included in the char_span,
    """
    lo, hi = char_span
    ind, full_words, partial_words = 0, [], []
    for i, w in enumerate(words):
        current_lo, current_hi = ind, ind + len(w)
        if lo <= current_lo and hi >= current_hi:
            full_words.append(i)
        elif lo < current_hi and hi > current_lo:
            partial_words.append(i)
        else:  # no intersection
            pass
        ind += len(w) + 1 # update counter
    return {
        "full_words": full_words,
        "partial_words": partial_words
    }

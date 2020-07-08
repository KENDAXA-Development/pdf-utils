"""Various basic tools for conversions between pdf's, text, images and words and word indices."""
import logging
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from typing import Union, List, Tuple, Dict

import numpy as np
import pdf2image
import pytesseract
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from pdf_tools.rectangle import Rectangle


class RotatedPdfException(Exception):
    """Ratio of pdf-width / pdf_height does not agree with the ratio image_width / image_height."""


def image_from_pdf_page(pdf_path: str,
                        page_num: int,
                        dpi: int = 150,
                        return_numpy: bool = True,
                        rotate_by: int = 0) -> Union[Image.Image, np.ndarray]:
    """Return the requested page as a png-image PIL object (no file creation) or a numpy array.

    Page numbers are counted from zero.
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
    """Save a list of images as a vanilla image-pdf (no text content), each image on one page."""
    images[0].save(output_pdf, "PDF", save_all=True, append_images=images[1:])


def ocr_one_image(im: Image.Image,
                  lang: str = "eng",
                  config: str = "--psm 12 --oem 3") -> List[Dict]:
    """Compute a dictionary with detected words and bounding boxes.

    :param im: input image
    :param lang: language code
    :param config: tesseract configuration
    :return: list of dictionaries of type {"word": word, "bb": bounding box of the word}
    """
    d = pytesseract.image_to_data(
        im, output_type=pytesseract.Output.DICT, lang=lang, config=config)
    result = []
    for i in range(len(d["level"])):
        word = d["text"][i]
        if word.strip():
            left, top, width, height = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
            result.append({
                "word": word,
                "bb": Rectangle(left, top, left + width, top + height)
            })
    return result


def image_to_one_page_ocred_pdf(im: Image.Image,
                                pdf_path: str,
                                ocr_text: List[Dict],
                                output_pdf_width: int,
                                font_name: str = "Helvetica") -> None:
    """Convert the image into a pdf with added textual layer and store it to disc.

    Run tesseract OCR and add invisible textual content so that the pdf is searchable / clickable.
    :param im: input image
    :param pdf_path: path to output pdf
    :param ocr_text: information about words and their bounding boxes
    :param output_pdf_width: with of output pdf page
    :param font_name
    """
    print("output pdf width", output_pdf_width)
    print("im.size[0]", im.size[0])
    rescale = output_pdf_width / im.size[0]
    if rescale > 1:
        logging.warning("making the pdf page larger than the image (consider doing ocr on larger im)")
    output_pdf_height = int(im.size[1] * rescale)
    new_pdf = Canvas(pdf_path, pagesize=(output_pdf_width, output_pdf_height))

    im_resized = im.resize((output_pdf_width, output_pdf_height))
    new_pdf.drawImage(
        ImageReader(im_resized),
        0, 0, width=output_pdf_width, height=output_pdf_height)

    for word_and_position in ocr_text:
        word = word_and_position["word"]
        bb = word_and_position["bb"].rescale(multiply_width_by=rescale, multiply_height_by=rescale)

        text = new_pdf.beginText()
        text.setFont(font_name, bb.height)
        text.setTextRenderMode(3)  # invisible
        text.setTextOrigin(bb.x_min, output_pdf_height - bb.y_max)  # bottom-left corner
        text.setHorizScale(100 * bb.width / new_pdf.stringWidth(word, "Helvetica", bb.height))
        text.textLine(word)
        new_pdf.drawText(text)

    new_pdf.save()


def convert_image_list_to_searchable_pdf(images: List[Image.Image],
                                         pdf_path: str,
                                         output_pdf_width: int,
                                         tesseract_lang: str = "eng",
                                         tesseract_config: str = "--psm 12 --oem 3"
                                         ):
    """Create a pdf from images with digital content comming from pytesseract."""
    td, tmp_paths = mkdtemp(), []
    for page_idx, im in enumerate(images):
        current_tmp_path = str(Path(td) / f"{page_idx}.pdf")
        tmp_paths.append(current_tmp_path)
        logging.info(f"Tesseracting page {page_idx}...")
        image_to_one_page_ocred_pdf(
            im,
            pdf_path=current_tmp_path,
            ocr_text=ocr_one_image(im, tesseract_lang, tesseract_config),
            output_pdf_width=output_pdf_width)

    # combine single-page pdfs into one
    subprocess.run([
        "pdfunite", *tmp_paths, pdf_path
    ])
    # cleanup
    shutil.rmtree(td)


def get_indices_of_words(words: List[str], char_span: Tuple[int, int]) -> Dict:
    """Given a list of words and a span of 'matched characters', compute which words are matched.

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
        ind += len(w) + 1  # update counter
    return {
        "full_words": full_words,
        "partial_words": partial_words
    }

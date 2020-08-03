import os
import re
import unittest
from tempfile import mkstemp

import numpy as np
from PIL import Image

from kx_pdf_tools.ocr import Scanner
from kx_pdf_tools.pdf_handler import Pdf
from kx_pdf_tools.rectangle import Rectangle
from tests import FIRST_PDF_PAGE_PATH, PDF_PATH, PDF_ROTATED_PATH
from tests.object_similarity import naive_image_similarity


class TestPdf(unittest.TestCase):

    pdf = Pdf(PDF_PATH)
    pdf_rotated = Pdf(PDF_ROTATED_PATH)

    def test_basic_attributes(self):
        """Check correctness of path, name and number of pages."""
        self.assertEqual(self.pdf.pdf_path, PDF_PATH)
        self.assertEqual(self.pdf.name, "example.pdf")
        self.assertEqual(self.pdf.number_of_pages, 2)

    def test_width_height_rotation(self):
        """Check width, height, and extracted page rotation."""
        w, h = self.pdf.get_width_height(0)
        wr, hr = self.pdf_rotated.get_width_height(0)

        # width and height of the original pdf
        self.assertLessEqual(abs(w - 595), 1)
        self.assertLessEqual(abs(h - 842), 1)

        # rotated pdf should have width and height swapped
        self.assertLessEqual(abs(hr - 595), 1)
        self.assertLessEqual(abs(wr - 842), 1)

        # check page rotation
        self.assertEqual(self.pdf.page_rotation(0), 0)
        self.assertEqual(self.pdf.page_rotation(1), 0)
        self.assertEqual(self.pdf_rotated.page_rotation(0), 90)

    def test_page_image(self):
        """Check consistency of first-page image, reference image, and recovered image from rotated pdf."""
        im_1 = self.pdf.page_image(0)
        im_rot_1 = self.pdf_rotated.page_image(0)

        im_1_reconstructed = im_rot_1.rotate(90, expand=True)

        # sizes should coincide
        self.assertEqual(im_1.size, im_1_reconstructed.size)
        # first pdf page should be similar to the rotated first page of rotated pdf
        self.assertGreater(
            naive_image_similarity(np.array(im_1), np.array(im_1_reconstructed)), 0.98
        )
        # first page should be similar to the precomputed image from disc
        self.assertGreater(
            naive_image_similarity(
                np.array(im_1),
                np.array(Image.open(str(FIRST_PDF_PAGE_PATH)))),
            0.98
        )

        images = list(self.pdf.images)
        images_rotated = list(self.pdf_rotated.images)

        # the 'images' method should return the precomputed images from a buffer, so here we require exact match
        self.assertEqual(im_1, images[0])
        self.assertEqual(im_rot_1, images_rotated[0])

    def test_text_extraction_from_pdf(self):
        """This is essentially testing pdftotext (probably coming from Poppler, of Xpdf)."""
        simple_text = self.pdf.simple_text
        layout_text = self.pdf.layout_text
        # xml with bounding boxes of words
        root = self.pdf.get_page_as_html(0)

        # list of strings (one per page)
        simple_pages = [page for page in simple_text.split("\f") if page]
        layout_pages = [page for page in layout_text.split("\f") if page]

        # We have two pages in the pdf
        self.assertEqual(len(simple_pages), 2)
        self.assertEqual(len(layout_pages), 2)

        # Test that first page contain expected words
        words_in_first_page = set(simple_pages[0].split())
        self.assertTrue({"Lorem", "ipsum", "Aron", "killed", "pf@kendaxa.com"}.issubset(words_in_first_page))
        self.assertFalse({"Autobahn", "Das", "The", "name", "hungry", "kendaxa@kendaxa.com"} & words_in_first_page)

        # this regex should be matched in a reasonably extracted layout-first-page-text
        self.assertTrue(re.search(r"Stolen\s+bike\s+500\s+Euro\s+3%", layout_pages[0]))
        self.assertTrue(re.search(r"impuls@faktor.net\s*\n", layout_pages[1]))

        # Find bounding box of 'extreme' word on first page
        extreme_element = root.xpath(".//word[text()='extreme']")[0]
        extreme_bb = Rectangle(
            x_min=extreme_element.attrib["xmin"],
            y_min=extreme_element.attrib["ymin"],
            x_max=extreme_element.attrib["xmax"],
            y_max=extreme_element.attrib["ymax"])

        # Check that the bounding box is reasonable
        self.assertTrue(
            extreme_bb in Rectangle(
                x_min=220,
                y_min=530,
                x_max=290,
                y_max=590
            ))

    def test_text_extraction_from_rotated_pdf(self):
        """Check that bounding box of a word in pdf is where it should be."""
        pages = self.pdf.get_pages()
        pages_rotated = self.pdf_rotated.get_pages()
        pages_txt = self.pdf.get_pages_as_text()

        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages_txt), 2)

        first_el_pdf = pages[0][0]
        first_el_pdf_rotated = pages_rotated[0][0]

        # both pdf should start with "Insurance" on the first page
        self.assertEqual(first_el_pdf.text, "Insurance")
        self.assertEqual(first_el_pdf_rotated.text, "Insurance")

        # enforce approximate bounding box of this first word
        self.assertTrue(
            self.pdf.get_bounding_box_of_elem(pages[0][0]) in (
                Rectangle(x_min=72, y_min=98, x_max=165, y_max=128)))

        self.assertTrue(
            self.pdf_rotated.get_bounding_box_of_elem(pages_rotated[0][0]) in (
                Rectangle(x_min=712, y_min=70, x_max=750, y_max=162)))

    def test_pdf_recreation(self):
        """Test the method `recreate_digital_content`.

        We convert the example pdf to a new pdf created from images and ocr.
        Then we test that
            * image-content of first page is similar to image of the reconstructed pdf, and
            * textual content of first page is the same as ocr-result from first page-image.
        (Ocr itself is tested in the test_ocr module.)
        """
        tmp_pdf_file = mkstemp()[1]
        self.pdf.recreate_digital_content(
            tmp_pdf_file, tesseract_lang='eng', tesseract_conf="")
        recreated = Pdf(tmp_pdf_file)

        # pdf should have two pages
        self.assertEqual(recreated.number_of_pages, 2)

        # size of first page should be unchanged
        pdf_widh, pdf_height = self.pdf.get_width_height(0)
        self.assertEqual(recreated.get_width_height(0), (pdf_widh, pdf_height))

        im_width, im_height = self.pdf.page_image(0, dpi=150).size
        im_recreated = recreated.page_image(0, dpi=150)

        # first page image original and reconstructed (widht equal dpi) should have approximately the same size
        self.assertLess(abs(im_width - im_recreated.size[0]) / im_width, 0.05)
        self.assertLess(abs(im_height - im_recreated.size[1]) / im_height, 0.05)

        # first page should be similar to the first reconstructed page (after resizing)
        im_recreated = im_recreated.resize((im_width, im_height))
        self.assertGreater(
            naive_image_similarity(
                np.array(self.pdf.page_image(0)),
                np.array(im_recreated)),
            0.98
        )

        # check digital content
        # we will compare dictionaries {word: bounding_box} in reconstructed pdf and in ocr scan of the original one
        # these two dictionaries should have equal keys, and similar values for all keys which represent unique words
        words_and_bounding_boxes = recreated.get_pages()[0]
        words_and_bounding_boxes = {
            item.text: Pdf.get_bounding_box_of_elem(item).relative_to_size(width=pdf_widh, height=pdf_height)
            for item in words_and_bounding_boxes}

        scanned_words_and_bounding_boxes = Scanner.ocr_one_image(
            self.pdf.page_image(0), lang="eng", config="")
        scanned_words_and_bounding_boxes = {
            item["word"]: item["bb"] for item in scanned_words_and_bounding_boxes}

        # both dictionaries should have the same keys
        self.assertEqual(set(scanned_words_and_bounding_boxes), set(words_and_bounding_boxes))

        # bounding boxes of the word "left" should be approximately equal (iou at least 0.4)
        self.assertGreater(
            scanned_words_and_bounding_boxes["left"].get_iou(
                words_and_bounding_boxes["left"]),
            0.4
        )

        # cleanup
        os.remove(tmp_pdf_file)

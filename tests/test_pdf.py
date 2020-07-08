import re
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from lxml import html
from tests.image_comparison import naive_image_similarity

from pdf_tools.pdf import Pdf
from pdf_tools.rectangle import Rectangle


class TestPdf(unittest.TestCase):

    here = Path(__file__).parent
    pdf = Pdf(here / "data_git" / "example.pdf")
    pdf_rotated = Pdf(here / "data_git" / "example_rotated.pdf")

    def test_basic_attributes(self):
        self.assertEqual(self.pdf.pdf_path, self.here / "data_git" / "example.pdf")
        self.assertEqual(self.pdf.name, "example.pdf")
        self.assertEqual(self.pdf.number_of_pages, 2)

    def test_width_height_rotation(self):
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
                np.array(Image.open(str(self.here / "data_git" / "example_150-1.png")))),
            0.98
        )

        images = self.pdf.images
        images_rotated = self.pdf_rotated.images

        # the 'images' method should return the precomputed images from a buffer, so here we require exact match
        self.assertEqual(im_1, images[0])
        self.assertEqual(im_rot_1, images_rotated[0])

    def test_text_extraction_from_pdf(self):
        """This is essentially testing pdftotext (probably coming from Poppler, of Xpdf)."""
        simple_text = self.pdf.get_simple_text()
        layout_text = self.pdf.get_layout_text()
        # xml with bounding boxes of words
        root = self.pdf.get_text_with_bb()

        # list of strings (one per page)
        simple_pages = [page for page in simple_text.split("\f") if page]
        layout_pages = [page for page in layout_text.split("\f") if page]

        # We have two pages in the pdf
        self.assertEqual(len(simple_pages), 2)
        self.assertEqual(len(layout_pages), 2)
        self.assertEqual(len(root.findall(".//page")), 2)

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
        root = self.pdf.get_text_with_bb()

        # here we at least check the type
        self.assertTrue(isinstance(root, html.HtmlElement))

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

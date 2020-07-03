import unittest
from tempfile import mkstemp
import os
import re

from PIL import Image
import numpy as np
from lxml import html

from pdf_tools import converter
from pdf_tools.rectangle import Rectangle
from tests.image_comparison import naive_image_similarity


class TestRectangle(unittest.TestCase):

    sample_pdf_path = "data_git/example.pdf"
    first_page_150_dpi = "data_git/example_150-1.png"
    second_page_150_dpi = "data_git/example_150-2.png"

    def test_image_from_pdf_page(self):
        im_1 = np.array(Image.open(self.first_page_150_dpi))
        im_from_pdf = converter.image_from_pdf_page(self.sample_pdf_path, page_num=0, dpi=150, return_numpy=True)

        self.assertEqual(im_1.shape, im_from_pdf.shape)
        self.assertLess(np.mean(im_1 - im_from_pdf), 0.01)

    def test_pdf_box_to_image_box(self):
        pdf_box = Rectangle(10, 10, 20, 30)
        image_box_1 = Rectangle(100, 100, 200, 300)
        image_box_2 = Rectangle(100, 100, 300, 200)

        pdf_box_converted = converter.pdf_box_to_image_box(
            pdf_box=pdf_box, pdf_width=50, pdf_height=100, img_width=500, img_height=1000)
        self.assertEqual(
            pdf_box_converted, image_box_1
        )

        self.assertRaises(
            converter.RotatedPdfException,
            converter.pdf_box_to_image_box,
            pdf_box=pdf_box, pdf_width=50, pdf_height=100, img_width=1000, img_height=500)


    def test_images_to_pdf(self):
        """We take two images and create a pdf out of it.
        Then we convert this pdf to images and check that first page should be similar to the original first image.
        """
        im1 = Image.open(self.first_page_150_dpi)
        im2 = Image.open(self.second_page_150_dpi)

        _, temporary_pdf_path = mkstemp()
        converter.save_images_to_pdf([im1, im2], temporary_pdf_path)

        # reconstruction of the first page
        image_reconstructed = converter.image_from_pdf_page(temporary_pdf_path, page_num=0, dpi=72, return_numpy=True)

        # 72 dpi should create image of unchanged size
        self.assertEqual(image_reconstructed.shape, np.array(im1).shape)

        # the reconstructed image should have high similarity with the first page
        self.assertGreater(naive_image_similarity(image_reconstructed, np.array(im1)), 0.95)

        # the reconstructed image should have low similarity with the second page
        self.assertLess(naive_image_similarity(image_reconstructed, np.array(im2)), 0.3)

        os.remove(temporary_pdf_path)

    def test_text_extraction_from_pdf(self):
        """This is essentially testing pdftotext (probably coming from Poppler, of Xpdf)."""
        simple_text = converter.extract_text_from_pdf(self.sample_pdf_path)
        layout_text = converter.extract_text_from_pdf(self.sample_pdf_path, "-layout")
        # xml with bounding boxes of words
        bbox_xml = converter.extract_text_from_pdf(self.sample_pdf_path, "-bbox-layout")
        parser = html.HTMLParser(encoding="utf-8")
        root = html.fromstring(bbox_xml, parser=parser)

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

    def test_indices_of_words(self):
        words = [
            "This", "is", "a", "medium-long", "sentence", "about", "the", "friendly-looking",
            "dog", "eating", "small", "children."]
        pattern = re.compile(r"about the fr")
        span = pattern.search(' '.join(words)).span()

        matched_words = converter.get_indices_of_words(words, span)

        # 'about' and 'the' are fully matched, 'friendly-looking' is partially matched
        self.assertTrue(matched_words["full_words"], [5, 6])
        self.assertTrue(matched_words["partial_words"], [7])

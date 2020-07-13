import os
import re
import unittest
from tempfile import mkstemp

import numpy as np
from PIL import Image
from tests import pdf_path, first_page_150_dpi_path, second_page_150_dpi_path
from tests.object_similarity import naive_image_similarity

from pdf_tools import converter
from pdf_tools.rectangle import Rectangle


class TestRectangle(unittest.TestCase):

    def test_image_from_pdf_page(self):
        """Convert a pdf page to image."""
        im_1 = np.array(Image.open(str(first_page_150_dpi_path)))
        im_from_pdf = converter.image_from_pdf_page(pdf_path, page_num=0, dpi=150, return_numpy=True)

        self.assertEqual(im_1.shape, im_from_pdf.shape)
        self.assertLess(np.mean(im_1 - im_from_pdf), 0.01)

    def test_pdf_box_to_image_box(self):
        """Transform bounding box from points to pixels.

        If shape ratios do not match, an exception should be risen.
        """
        pdf_box = Rectangle(10, 10, 20, 30)
        image_box_1 = Rectangle(100, 100, 200, 300)

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
        """Create pdf from images and back to images and check consistency.

        We take two images and create a pdf out of it.
        Then we convert this pdf to images and check that first page should be similar to the original first image.
        """
        im1 = Image.open(str(first_page_150_dpi_path))
        im2 = Image.open(str(second_page_150_dpi_path))

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

    def test_indices_of_words(self):
        """Test conversion of a text-span into indices of words that are fully or partially within the span."""
        words = [
            "This", "is", "a", "medium-long", "sentence", "about", "the", "friendly-looking",
            "dog", "eating", "small", "children."]
        pattern = re.compile(r"about the fr")
        span = pattern.search(' '.join(words)).span()

        matched_words = converter.get_indices_of_words(words, span)

        # 'about' and 'the' are fully matched, 'friendly-looking' is partially matched
        self.assertTrue(matched_words["full_words"], [5, 6])
        self.assertTrue(matched_words["partial_words"], [7])

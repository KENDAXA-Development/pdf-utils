import os
import re
import unittest
from pathlib import Path
from tempfile import mkstemp

from tests import pdf_path

from pdf_tools.ocr import Scanner
from pdf_tools.pdf_handler import Pdf


class TestScanner(unittest.TestCase):

    example_pdf = Pdf(pdf_path)
    first_page_large = example_pdf.page_image(page_idx=0, dpi=300)
    ocr_data = None

    def setUp(self) -> None:
        self.ocr_data = Scanner.ocr_one_image(self.first_page_large)

    def test_image_ocr(self):
        """Test that correct words are ocred and that the word 'iruri' is on approximately proper position."""
        found_words_from_ocr = {item["word"] for item in self.ocr_data}
        digital_first_page = self.example_pdf.get_pages()[0]
        digital_words_first_page = {w.text.strip() for w in digital_first_page if w.text.strip()}

        # interlap of detected and digital words should be large
        inter = len(found_words_from_ocr & digital_words_first_page)
        iou = inter / (len(found_words_from_ocr) + len(digital_words_first_page) - inter)
        self.assertTrue(iou > 0.9)

        # further, let's find the word 'irure' in both digital content and scanned content
        irure_el = self.example_pdf.text_with_bb.xpath('.//word[text()="irure"]')[0]
        irure_digital_bb = Pdf.get_bounding_box_of_elem(irure_el).relative_to_size(
            width=self.example_pdf.get_width_height(0)[0],
            height=self.example_pdf.get_width_height(0)[1]
        )
        irure_ocred_bb = list(filter(lambda i: i["word"] == "irure", self.ocr_data))[0]["bb"]

        # Bounding box of 'irure' should be similar in both cases.
        # However, we need to be tolerant here, as bounding boxes of scanned text are typically smaller
        # than the digital ones. So let's require intersection over union at least 0.4.
        self.assertGreater(irure_ocred_bb.get_iou(irure_digital_bb), 0.4)

    def test_ocred_pdf(self):
        """Convert the example_pdf into an image and the image back into a one-page pdf: test consistency."""
        pdf_path = mkstemp()[1]
        Scanner.image_to_one_page_ocred_pdf(self.first_page_large,
                                            pdf_path,
                                            pdf_width=self.example_pdf.get_width_height()[0],
                                            pdf_height=self.example_pdf.get_width_height()[1],
                                            ocr_text=self.ocr_data
                                            )
        scanned_pdf = Pdf(pdf_path)
        # get digital content of the scanned pdf
        scanned_text = scanned_pdf.layout_text
        self.assertTrue(
            re.search(r"of\s+all\s+factories\s+10\s+bil\.\s+Euro\s+4\%", scanned_text)
        )
        # cleanup
        os.remove(pdf_path)

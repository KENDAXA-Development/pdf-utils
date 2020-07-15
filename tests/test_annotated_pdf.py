import os
import re
import unittest
from tempfile import mkstemp

import numpy as np
from PIL import Image

from kx_pdf_tools.annotated_pdf import AnnotatedPdf
from kx_pdf_tools.annotation import AnnotationExtractor
from kx_pdf_tools.pdf_handler import Pdf
from tests import ANNOTATED_PDF_PATH, FIRST_PDF_PAGE_PATH, PDF_PATH
from tests.object_similarity import annotations_are_similar, naive_image_similarity


class TestAnnotatedPdf(unittest.TestCase):

    annotated_pdf = AnnotatedPdf(ANNOTATED_PDF_PATH)
    extracted_annots = AnnotationExtractor.get_annot_from_pdf(annotated_pdf)

    risk_pattern = re.compile(r"Being\s+killed\s+at\s+train\s+station")
    deductible_pattern = re.compile(r"1\s?%")
    currency_pattern = re.compile(r"Euro")

    def test_raw_annotations(self):
        """Check that the raw_annotations extracted from AnnotatedPdf coincides with what AnnotationExtractor returns.

        Functionality of the AnnotationExtractor itself is tested in the test_ocr module.
        """
        raw_annotations = self.annotated_pdf.raw_annotations

        self.assertEqual(len(raw_annotations), len(self.extracted_annots))

        for i in range(len(raw_annotations)):
            self.assertTrue(annotations_are_similar(raw_annotations[i], self.extracted_annots[i]))

    def test_enriched_annotations(self):
        """Check that enriched annotation for our example pdf coincide with expected results."""
        enriched = self.annotated_pdf.enriched_annotations

        # check that only rectangle-types are here
        rectangle_annots = [annot for annot in self.extracted_annots if annot.type == "rectangle"]
        for i, annot in enumerate(rectangle_annots):
            self.assertTrue(annotations_are_similar(annot, enriched[i]["annotation"]))

        # check that the textual content of first annotation is correct
        self.assertEqual(
            ' '.join(w["word"].text for w in enriched[0]["words"]),
            "Being killed at train station")

        # check that the 'scores' of words in first rectangle annotation are reasonable
        for i, w in enumerate(enriched[0]["words"]):
            word_bb = Pdf.get_bounding_box_of_elem(w["word"])
            self.assertGreater(w["score"], 0.9)

            self.assertLess(
                word_bb.intersection(rectangle_annots[0].box).area / word_bb.area - w["score"],
                0.01)

    def test_pdf_with_no_anno(self):
        """Check that annotation lists are empty for a pdf with no annotations."""
        pdf_no_annot = AnnotatedPdf(PDF_PATH)
        self.assertListEqual(pdf_no_annot.raw_annotations, [])
        self.assertListEqual(pdf_no_annot.enriched_annotations, [])

    def test_annotated_flows(self):
        """Test annotated flows extracted from pre-defined document.

        The annotated words with annotation's text_content equal to "risk" should be words
        that approximately look like "Being killed at train station".
        """
        annotated_flows = self.annotated_pdf.get_flows_with_annotations()
        for flow_id in annotated_flows:
            current_flow = annotated_flows[flow_id]
            for k in current_flow["annotated_indices"]:
                annotated_text = ' '.join(current_flow["words"][i] for i in current_flow["annotated_indices"][k])
                if k == "risk":
                    self.assertTrue(self.risk_pattern.search(annotated_text))
                elif k == "deductible in %":
                    self.assertTrue(self.deductible_pattern.search(annotated_text))
                elif k == "currency":
                    self.assertTrue(self.currency_pattern.search(annotated_text))

    def test_annotated_flows_with_one_char_normalization(self):
        """Test annotated flows with a nontrivial transformation of the annotation's text_content.

        Here we convert each annotation's text_content into it's lower-cased first character.
        So "Risk" becomes "r" only.
        """
        annotated_flows_with_one_char_annotations = self.annotated_pdf.get_flows_with_annotations(
            transform_anno_text_description=lambda text: text.lower()[0])

        for flow_id in annotated_flows_with_one_char_annotations:
            current_flow = annotated_flows_with_one_char_annotations[flow_id]

            for k in current_flow["annotated_indices"]:
                annotated_text = ' '.join(current_flow["words"][i] for i in current_flow["annotated_indices"][k])
                # here we expected one-character keys
                self.assertTrue(len(k) == 1)
                # 'r' stands for 'risk', etc
                if k == "r":
                    self.assertTrue(self.risk_pattern.search(annotated_text))
                elif k == "d":
                    self.assertTrue(self.deductible_pattern.search(annotated_text))
                elif k == "c":
                    self.assertTrue(self.currency_pattern.search(annotated_text))

    def test_annotation_removal(self):
        """Remove all annotation and test consistency."""
        temp_pdf_file = mkstemp()[1]
        self.annotated_pdf.remove_annotations_and_save(temp_pdf_file)
        pdf_no_annots = AnnotatedPdf(temp_pdf_file)

        # no annotations should be in this new pdf_no_annots
        self.assertListEqual(pdf_no_annots.raw_annotations, [])

        # first page should look similar than the reference page
        first_page_no_anno = pdf_no_annots.page_image(0, dpi=150)
        first_im_ref = Image.open(str(FIRST_PDF_PAGE_PATH))
        self.assertGreater(
            naive_image_similarity(
                np.array(first_im_ref),
                np.array(first_page_no_anno.resize(first_im_ref.size))),
            0.99
        )

        os.remove(temp_pdf_file)

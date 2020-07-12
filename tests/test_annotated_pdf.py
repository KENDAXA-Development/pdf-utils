import os
import re
import unittest
from pathlib import Path
from tempfile import mkstemp

import numpy as np
from PIL import Image
from tests.object_similarity import annotations_are_similar, naive_image_similarity

from pdf_tools.annotated_pdf import AnnotatedPdf
from pdf_tools.annotation import AnnotationExtractor
from pdf_tools.pdf_handler import Pdf


class TestAnnotatedPdf(unittest.TestCase):

    here = Path(__file__).parent

    pdf_path = str(here / "data_git" / "example.pdf")

    annotated_pdf_path = str(here / "data_git" / "example_annotated.pdf")
    annotated_pdf = AnnotatedPdf(annotated_pdf_path)

    extracted_annots = AnnotationExtractor.get_annot_from_pdf(annotated_pdf)

    def test_raw_annotations(self):
        raw_annotations = self.annotated_pdf.raw_annotations

        self.assertEqual(len(raw_annotations), len(self.extracted_annots))

        for i in range(len(raw_annotations)):
            self.assertTrue(annotations_are_similar(raw_annotations[i], self.extracted_annots[i]))

    def test_enriched_annotations(self):
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
        pdf_no_annot = AnnotatedPdf(self.pdf_path)
        self.assertListEqual(pdf_no_annot.raw_annotations, [])
        self.assertListEqual(pdf_no_annot.enriched_annotations, [])

    def test_annotated_flows(self):
        """Test annotated flows extracted from pre-defined document.

        The annotated words with annotation's text_content equal to "risk" should be words
        that approximately look like "Being killed at train station".

        If we cann the get_flows_with_annotations method with a non-default parameter transform_anno_text_description,
        then the annotation's text_content is normalized first; here we test a normalization that keeps first char only.
        """
        risk_pattern = re.compile(r"Being\s+killed\s+at\s+train\s+station")
        deductible_pattern = re.compile(r"1\s?%")
        currency_pattern = re.compile(r"Euro")

        annotated_flows = self.annotated_pdf.get_flows_with_annotations()
        # here we convert each annotation's text_content into the first lower-cased character only
        annotated_flows_with_one_char_annotations = self.annotated_pdf.get_flows_with_annotations(
            transform_anno_text_description=lambda text: text.lower()[0]
        )

        for flow_id in annotated_flows:
            current_flow = annotated_flows[flow_id]
            current_flow_one_char_annot = annotated_flows_with_one_char_annotations[flow_id]

            for k in current_flow["annotated_indices"]:
                annotated_text = ' '.join(current_flow["words"][i] for i in current_flow["annotated_indices"][k])
                if k == "risk":
                    self.assertTrue(risk_pattern, annotated_text)
                if k == "deductible in %":
                    self.assertTrue(deductible_pattern, annotated_text)
                if k == "currency":
                    self.assertTrue(currency_pattern, annotated_text)

            for k in current_flow_one_char_annot["annotated_indices"]:
                annotated_text = ' '.join(current_flow["words"][i] for i in current_flow["annotated_indices"][k])
                # here we expected one-character keys
                self.assertTrue(len(k) == 1)
                # 'r' stands for 'risk', etc
                if k == "r":
                    self.assertTrue(risk_pattern, annotated_text)
                if k == "d":
                    self.assertTrue(deductible_pattern, annotated_text)
                if k == "c":
                    self.assertTrue(currency_pattern, annotated_text)

    def test_annotation_removal(self):
        temp_pdf_file = mkstemp()[1]
        self.annotated_pdf.remove_annotations_and_save(temp_pdf_file)
        pdf_no_annots = AnnotatedPdf(temp_pdf_file)

        # no annotations should be in this new pdf_no_annots
        self.assertListEqual(pdf_no_annots.raw_annotations, [])

        # first page should look similar than the reference page
        first_page_no_anno = pdf_no_annots.page_image(0, dpi=150)
        first_im_ref = Image.open(str(self.here / "data_git" / "example_150-1.png"))
        self.assertGreater(
            naive_image_similarity(
                np.array(first_im_ref),
                np.array(first_page_no_anno.resize(first_im_ref.size))),
            0.99
        )

        os.remove(temp_pdf_file)

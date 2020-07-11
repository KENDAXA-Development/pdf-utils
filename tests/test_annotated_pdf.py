import unittest
from pathlib import Path

from tests.object_similarity import annotations_are_similar

from pdf_tools.annotated_pdf import AnnotatedPdf
from pdf_tools.annotation import AnnotationExtractor
from pdf_tools.pdf_handler import Pdf

class TestAnnotatedPdf(unittest.TestCase):

    here = Path(__file__).parent
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

    def test_annotated_flows(self):
        from pprint import pprint
        pprint(self.annotated_pdf.get_flows_with_annotations())

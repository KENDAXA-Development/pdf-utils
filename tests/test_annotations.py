import json
import os
import unittest
from tempfile import mkstemp

from pdf_utils.annotation import Annotation, AnnotationExtractor
from pdf_utils.pdf_handler import Pdf
from pdf_utils.rectangle import Rectangle
from tests import ANNOTATED_PDF_PATH
from tests.object_similarity import annotations_are_similar


class TestAnnotation(unittest.TestCase):

    annotated_pdf = Pdf(ANNOTATED_PDF_PATH)
    extractor = AnnotationExtractor()

    expected_annotations = [
        Annotation(
            page=0,
            type="note",
            box=Rectangle(x_min=87.58, y_min=45.574, x_max=107.58, y_max=65.574),
            text_content="Daniel, include also the remaining 133 pages in the pdf!!!!",
            who_annotated="peter"),
        Annotation(
            page=0,
            type="rectangle",
            box=Rectangle(x_min=83.46, y_min=504.12, x_max=221.12, y_max=518),
            text_content="risk",
            who_annotated="peter"),
        Annotation(
            page=0,
            type="rectangle",
            box=Rectangle(x_min=321.27, y_min=503, x_max=374.16, y_max=517.63),
            text_content="coverage_total",
            who_annotated="peter"),
        Annotation(
            page=0,
            type="rectangle",
            box=Rectangle(x_min=373.4, y_min=504.5, x_max=399.66, y_max=518),
            text_content="currency",
            who_annotated="peter"),
        Annotation(
            page=0,
            type="rectangle",
            box=Rectangle(x_min=465.68, y_min=504.87, x_max=486.31, y_max=517.25),
            text_content="deductible in %",
            who_annotated="peter"),
        Annotation(
            page=1,
            type="oval",
            box=Rectangle(x_min=55.7, y_min=133.72, x_max=338.9, y_max=177.23),
            text_content="add Honza",
            who_annotated="peter"),
    ]

    def test_assertion_in_annotation_type(self):
        """If type is not in ADMISSIBLE_ANNOTATIONS, an error should be raised."""
        self.assertRaises(
            AssertionError,
            lambda: Annotation(page=0, type="invisible", box=Rectangle(0, 0, 0, 0)))

    def test_annotation_creation(self):
        """Test the creation of one Annotation object."""
        ann = Annotation(
            page=12,
            type="rectangle",
            box=Rectangle(10, 10, 13, 13),
            text_content="FPP3",
            who_annotated="terminator II",
            label=3)

        expected_annotation_as_dict = {
            "page": 12,
            "type": "rectangle",
            "box": {
                "x_min": 10,
                "y_min": 10,
                "x_max": 13,
                "y_max": 13},
            "text_content": "FPP3",
            "who_annotated": "terminator II",
            "label": 3}

        self.assertEqual(ann.as_dict, expected_annotation_as_dict)

    def test_annotation_extraction(self):
        """Extract annotation from file and check that they correspond to expected annotations."""
        annotations = self.extractor.get_annot_from_pdf(self.annotated_pdf)

        # each annotation is found in expected
        for annot in annotations:
            with self.subTest(annotation=annot):
                self.assertTrue(
                    any(annotations_are_similar(annot, other)
                        for other in self.expected_annotations))
        # each expected annotation is found in annotations
        for exp_annot in self.expected_annotations:
            with self.subTest(expected_annotation=exp_annot):
                self.assertTrue(
                    any(annotations_are_similar(exp_annot, other)
                        for other in annotations))

    def test_dump_annotations_to_file(self):
        """Dump annotations to file, load them from file, and compare that all is consistent."""
        annotations = self.extractor.get_annot_from_pdf(self.annotated_pdf)
        temp_json_file = mkstemp()[1]
        self.extractor.dump_annotations_to_file(annotations, temp_json_file)
        with open(temp_json_file) as f:
            annots_from_file = json.load(f)

        for i, annot in enumerate(annots_from_file):
            # check that i'th annotation on page page_idx is the same in annotations and in annots_from_file
            with self.subTest(annotation=annot):
                self.assertTrue(
                    annotations_are_similar(
                        Annotation(
                            page=annot["page"],
                            type=annot["type"],
                            box=Rectangle.from_dict(annot["box"]),
                            text_content=annot["text_content"],
                            who_annotated=annot["who_annotated"],
                            label=annot["label"]),
                        annotations[i]))

        os.remove(temp_json_file)

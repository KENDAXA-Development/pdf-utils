import json
import os
import unittest
from pathlib import Path
from tempfile import mkstemp

from pdf_tools.annotation import Annotation, AnnotationExtractor
from pdf_tools.pdf_handler import Pdf
from pdf_tools.rectangle import Rectangle


class TestAnnotation(unittest.TestCase):

    here = Path(__file__).parent
    annotated_pdf_path = str(here / "data_git" / "example_annotated.pdf")
    annotated_pdf = Pdf(annotated_pdf_path)
    extractor = AnnotationExtractor()

    expected_annotations = {
        0: [
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
                who_annotated = "peter"),
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
                who_annotated="peter")],
        1: [
            Annotation(
                page=1,
                type="oval",
                box=Rectangle(x_min=55.7, y_min=133.72, x_max=338.9, y_max=177.23),
                text_content="add Honza",
                who_annotated="peter")]}

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

    @staticmethod
    def annotations_are_similar(first: Annotation, second: Annotation, thres: float = 0.99) -> bool:
        """Check the two annotations are the same, possibly up to minor differences in bounding boxes."""
        return (
            first.page == second.page) and (
            first.type == second.type) and (
            first.text_content == second.text_content) and (
            first.label == second.label) and (
            first.who_annotated == second.who_annotated) and (
            first.box.get_iou(second.box) > thres)

    def test_annotation_extraction(self):
        """Extract annotation from file and check that they correspond to expected annotations."""
        annotations = self.extractor.get_annot_from_pdf(self.annotated_pdf)
        for page_idx in annotations:
            for annot in annotations[page_idx]:
                self.assertTrue(
                    any(self.annotations_are_similar(annot, other)
                        for other in self.expected_annotations[page_idx]))

    def test_dump_annotations_to_file(self):
        """Dump annotations to file, load them from file, and compare that all is consistent."""
        annotations = self.extractor.get_annot_from_pdf(self.annotated_pdf)
        temp_json_file = mkstemp()[1]
        self.extractor.dump_annotations_to_file(annotations, temp_json_file)
        with open(temp_json_file) as f:
            annots_from_file = json.load(f)

        for page_idx in annots_from_file:
            for i, annot in enumerate(annots_from_file[page_idx]):
                # check that i'th annotation on page page_idx is the same in annotations and in annots_from_file
                self.assertTrue(
                    self.annotations_are_similar(
                        Annotation(
                            page=annot["page"],
                            type=annot["type"],
                            box=Rectangle.from_dict(annot["box"]),
                            text_content=annot["text_content"],
                            who_annotated=annot["who_annotated"],
                            label=annot["label"]),
                        annotations[int(page_idx)][i]))

        os.remove(temp_json_file)

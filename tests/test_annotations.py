import unittest
from pathlib import Path

from pdf_tools.annotation import Annotation, AnnotationExtractor
from pdf_tools.pdf import Pdf
from pdf_tools.rectangle import Rectangle


class TestAnnotation(unittest.TestCase):

    here = Path(__file__).parent
    annotated_pdf_path = str(here / "data_git" / "example_annotated.pdf")
    annotated_pdf = Pdf(annotated_pdf_path)
    extractor = AnnotationExtractor()

    expected_annotations = {
        0: [
            Annotation(page=0,
                       type="note",
                       box=Rectangle(x_min=87.58, y_min=45.574, x_max=107.58, y_max=65.574),
                       label=None,
                       text_content="Daniel, include also the remaining 133 pages in the pdf!!!!"),
            Annotation(page=0,
                       type="rectangle",
                       box=Rectangle(x_min=83.46, y_min=504.12, x_max=221.12, y_max=518),
                       label=None,
                       text_content="risk"),
            Annotation(page=0,
                       type="rectangle",
                       box=Rectangle(x_min=321.27, y_min=503, x_max=374.16, y_max=517.63),
                       label=None,
                       text_content="coverage_total"),
            Annotation(page=0,
                       type="rectangle",
                       box=Rectangle(x_min=373.4, y_min=504.5, x_max=399.66, y_max=518),
                       label=None,
                       text_content="currency"),
            Annotation(page=0,
                       type="rectangle",
                       box=Rectangle(x_min=465.68, y_min=504.87, x_max=486.31, y_max=517.25),
                       label=None,
                       text_content="deductible in %")],
        1: [
            Annotation(page=1,
                       type="oval",
                       box=Rectangle(x_min=55.7, y_min=133.72, x_max=338.9, y_max=177.23),
                       label=None,
                       text_content="add Honza")]}

    def test_annotation_creation(self):
        """Create one annotation, convert to dictionary and check that it is still correct."""
        self.assertEqual(
            Annotation(
                page=12,
                type="rectangle",
                box=Rectangle(10, 10, 13, 13),
                label=3,
                text_content="FPP3"
            ).as_dict,
            {
                "page": 12,
                "type": "rectangle",
                "box": Rectangle(10, 10, 13, 13).as_dict,
                "label": 3,
                "text_content": "FPP3"})

    @staticmethod
    def annotations_are_similar(first: Annotation, second: Annotation, thres: float = 0.99) -> bool:
        """Check the two annotations are the same, possibly up to minor differences in bounding boxes."""
        return (
            first.page == second.page) and (
            first.type == second.type) and (
            first.text_content == second.text_content) and (
            first.label == second.label) and (
            first.box.get_iou(second.box) > thres)

    def test_annotation_extraction(self):
        """Extract annotation from file and check that they correspond to expected annotations."""
        annotations = self.extractor.get_annot_from_pdf(self.annotated_pdf)
        for page_idx in annotations:
            for annot in annotations[page_idx]:
                self.assertTrue(
                    any(self.annotations_are_similar(annot, other)
                        for other in self.expected_annotations[page_idx]))

"""Tools to extract (but not create) pdf annotations."""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from PyPDF2.generic import ByteStringObject, IndirectObject
from PyPDF2.pdf import PageObject

from kx_pdf_tools.pdf_handler import CannotReadPdf, Pdf
from kx_pdf_tools.rectangle import Rectangle

logger = logging.getLogger(__name__)


# change this if you want to include other annotations types from pdfs
ADMISSIBLE_ANNOTATION_TYPES = {"rectangle", "oval", "ovál", "note"}


class Annotation:
    """Data class representing one pdf-annotation."""

    def __init__(
            self,
            page: int,
            type: str,  # noqa A102
            box: Rectangle,
            text_content: Optional[str] = None,
            who_annotated: Optional[str] = None,
            label: Optional[int] = None) -> None:
        """Create annotation with given data.

        :param page: indicating on which page the annotation is
        :param type: annotation type, should be one of the ADMISSIBLE_ANNOTATION_TYPES
        :param box: bounding box of the annotation (assuming pdf-coordinates in points)
        :param text_content: text_content
        :param who_annotated: persons name or id
        :param label: optional, not comming from pdf, but can be used for ML
        """
        assert type in ADMISSIBLE_ANNOTATION_TYPES, f"unsupported annotation type: '{type}'"
        self.page = page
        self.type = type if type != "ovál" else "oval"
        self.box = box
        self.text_content = text_content
        self.who_annotated = who_annotated
        self.label = label

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page": self.page,
            "type": self.type,
            "box": self.box.as_dict,
            "label": self.label,
            "who_annotated": self.who_annotated,
            "text_content": self.text_content,
        }

    def __repr__(self) -> str:
        return json.dumps(self.as_dict)


class AnnotationExtractor:
    """Extract raw annotations from pdf.

    The main method is `get_annots_from_pdf`.
    """

    @staticmethod
    def get_annot_from_pdf(pdf: Pdf) -> List[Annotation]:
        """Fetch annotations from annotated pdf and outputs as a list of annotation objects.

        :param pdf: Pdf object, representing a pdf file
        :return: List of Annotation objects, as found in the pdf document
        """
        outputs = []
        for idx in range(pdf.number_of_pages):
            outputs += AnnotationExtractor._parse_annot_pdf_page(pdf.pdf_reader.getPage(idx), idx)
        return outputs

    @staticmethod
    def dump_annotations_to_file(annotations: List[Annotation], output_path: str) -> None:
        """Json serialization of a list of Annotations."""
        assert os.path.isdir(os.path.dirname(output_path)), f"folder {os.path.dirname(output_path)} doesn't exist."
        with open(output_path, "w") as f:
            json.dump([annot.as_dict for annot in annotations], f)

    @staticmethod
    def _create_annotations_bounding_box(box_as_list: List,
                                         page_height: Union[int, float],
                                         from_above: bool = True) -> Rectangle:
        """Get the rectangle representing the bounding box of an annotation.

        When extracting an annotation from PyPDF2 Reader, then the bounding box of an annotation
        has some slightly unintuitive format. Here we convert it to our standard Rectangle object.

        :param box_as_list: list of 4 numbers, assumed to be (x_min, y_min, x_max, y_max).
            Vertical coordinates are increasing from below!
        :param page_height: number
        :param from_above: if True (default), we renormalize the vertical coordinate to increase from above.
        :return: adjusted Rectangle object
        """
        return Rectangle(
            x_min=float(box_as_list[0]),
            y_min=float(page_height) - float(box_as_list[3]) if from_above else float(box_as_list[1]),
            x_max=float(box_as_list[2]),
            y_max=float(page_height) - float(box_as_list[1]) if from_above else float(box_as_list[3]))

    @staticmethod
    def _parse_annot_pdf_page(page: PageObject, page_idx: int) -> List[Annotation]:
        """Fetch annotations on this pdf page and return them as a list."""
        outputs = []
        if not (page.cropBox[0] == page.cropBox[1] == 0):
            raise CannotReadPdf(
                f"cannot find positions of annotations, cropBox of page does not start with zeros (={page.cropBox})")

        page_height = page.cropBox[3]  # assuming the mediabox has form [0,0,width,height]
        annots = page.get('/Annots', [])
        if not isinstance(annots, list):
            # something is strange
            if not isinstance(annots, IndirectObject):
                logger.warning(f"cannot read annotations from {input}")
                return []
            annots = annots.getObject()  # now let's hope to get a list; in some cases this helps
            if not isinstance(annots, list):
                logger.warning(f"cannot read annotations from {input}")
                return []
        for ann in annots:
            current = ann.getObject()
            if "/Subj" in current:
                annot_type = current["/Subj"].lower()
                current_rec = AnnotationExtractor._create_annotations_bounding_box(current.get("/Rect"), page_height)
                text_content = current.get("/Contents")
                who_annotated = current.get("/T")
                if isinstance(text_content, ByteStringObject):
                    text_content = text_content.decode('utf-8')
                if annot_type in ADMISSIBLE_ANNOTATION_TYPES:
                    outputs.append(Annotation(
                        page=page_idx,
                        type=annot_type,
                        box=current_rec,
                        text_content=text_content,
                        who_annotated=who_annotated))
                else:
                    logger.warning(f"foreign annotation found (type {annot_type}, src {input})")
        return outputs

    @staticmethod
    def _group_by_pages(records: List[Annotation]) -> Dict[int, List[Annotation]]:
        """Transform the records to a dictionary {page_nr: [records on that page]}."""
        result = defaultdict(list)
        for record in records:
            page_num = record.page
            result[page_num].append(record)
        return dict(result)

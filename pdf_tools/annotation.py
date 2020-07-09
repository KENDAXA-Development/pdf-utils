"""Tools to extract (but not create) pdf annotations."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, List, Dict, Optional, Union

from PyPDF2.generic import ByteStringObject, IndirectObject
from PyPDF2.pdf import PageObject

from pdf_tools.pdf import Pdf
from pdf_tools.rectangle import Rectangle


# change this if you want to include other annotations types from pdfs
ADMISSIBLE_ANNOTATION_TYPES = {"rectangle", "oval", "ovál", "note"}


class Annotation:
    """Data class representing one pdf-annotation."""

    def __init__(
            self,
            page: int,
            type: str,
            box: Rectangle,
            label: Optional[int] = None,
            text_content: Optional[str] = None) -> None:
        assert type in ADMISSIBLE_ANNOTATION_TYPES
        self.page = page
        self.type = type if type != "ovál" else "oval"
        self.box = box
        self.text_content = text_content
        self.label = label

    @property
    def as_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page,
            "type": self.type,
            "box": self.box.as_dict,
            "label": self.label,
            "text_content": self.text_content,
        }

    def __repr__(self) -> str:
        return json.dumps(self.as_dict)


class AnnotationExtractor:
    """Extract raw annotations from pdf.

    The main method is `get_annots_from_pdf`.
    """

    @staticmethod
    def _create_rectangle(box_as_list: List, page_height: Union[int, float], from_above: bool = True) -> Rectangle:
        """Normalize the box raw pdf output.

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
        page_height = page.mediaBox[3]  # assuming the mediabox has form [0,0,width,height]
        annots = page.get('/Annots', [])
        if not isinstance(annots, list):
            # something is strange
            if not isinstance(annots, IndirectObject):
                logging.error(f"cannot read annotations from {input}")
                return []
            annots = annots.getObject()  # now let's hope to get a list; in some cases this helps
            if not isinstance(annots, list):
                logging.error(f"cannot read annotations from {input}")
                return []
        for ann in annots:
            current = ann.getObject()
            if "/Subj" in current:
                annot_type = current["/Subj"].lower()
                current_rec = AnnotationExtractor._create_rectangle(current.get("/Rect"), page_height)
                text_content = current.get("/Contents")
                if isinstance(text_content, ByteStringObject):
                    text_content = text_content.decode('utf-8')
                if annot_type in ADMISSIBLE_ANNOTATION_TYPES:
                    outputs.append(Annotation(
                        page=page_idx,
                        type=annot_type,
                        box=current_rec,
                        text_content=text_content))
                else:
                    logging.warning(f"foreign annotation found (type {annot_type}, src {input})")
        return outputs

    @staticmethod
    def _group_by_pages(records: List[Annotation]) -> Dict[int, List[Annotation]]:
        """Transform the records to a dictionary {page_nr: [records on that page]}."""
        result = defaultdict(list)
        for record in records:
            page_num = record.page
            result[page_num].append(record)
        return dict(result)

    @staticmethod
    def get_annot_from_pdf(pdf: Pdf) -> Dict[int, List[Annotation]]:
        """Fetch annotations from annotated pdf and outputs as a dictionary.

        :param pdf: Pdf object (object of kx_signatures.pdf.Pdf class)
        return: dictionary {page_num : [list_of_annotations_on_that_page]}
        """
        outputs = []
        for idx in range(pdf.number_of_pages):
            outputs += AnnotationExtractor._parse_annot_pdf_page(pdf.pdf_reader.getPage(idx), idx)
        return AnnotationExtractor._group_by_pages(outputs)

    @staticmethod
    def dump_annotations_to_file(annotations: Dict[int, List[Annotation]], output_path: str):
        """Json serialization of a list of Annotations."""
        js = {}
        for page in annotations:
            js[page] = [annot.as_dict for annot in annotations[page]]
        with open(output_path, "w") as f:
            json.dump(js, f)

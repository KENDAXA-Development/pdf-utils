"""Tools to digitalize annotations from a pdf.

While the pdf_tools.annotation.AnnotationExtractor fetches the raw annotations, here we match their bounding boxes
with actual words.
"""
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Union

from lxml import html

from pdf_tools.annotation import Annotation, AnnotationExtractor
from pdf_tools.pdf_handler import Pdf


class AnnotatedPdf(Pdf):
    """Tools to process one annotated pdf."""

    default_threshold = 0.4
    minimal_threshold = 0.2

    def __init__(self, pdf_path: Union[str, Path]) -> None:
        """Fetch annotations and match their bounding boxes with words in the document."""
        super().__init__(pdf_path)

        # Row annotations contain bounding boxes, but not textual content of what is inside these bounding boxes.
        self.raw_annotations = AnnotationExtractor().get_annot_from_pdf(self)

        # Enriched_annotations also contains information about textual content.
        # The structure is
        # {
        #     "page_nr": [
        #         {
        #             "annotation": annotation,
        #             "words": [{"word": str, "bounding_box": Rectangle, "score": float}, ...]
        #         },
        #         {...}, ...
        #     ]}.
        self.enriched_annotations = self._match_annotations_with_words(self.raw_annotations)

    @staticmethod
    def _get_scored_words(words_in_page: List[html.HtmlElement],
                          one_annotation: Annotation,
                          threshold: float) -> List[Dict]:
        """For one page and a given annotation, find all words that has high overlap with annotation's bounding box.

        Return a list of potential word-candidates with form
        [{
            "word": html element representing the word,
            "score": proportion of the word box intersecting the annotation box
        ...,]
        """
        scored_words = []
        for word in words_in_page:
            word_box = Pdf.get_bounding_box_of_elem(word)
            annotation_and_box_interection = word_box.intersection(one_annotation.box)
            score = 0 if annotation_and_box_interection is None else annotation_and_box_interection.area / word_box.area
            if score > threshold:
                scored_words.append({
                    "word": word,
                    "score": score})
        return scored_words

    def _find_words_related_to_one_annotation(self,
                                              annotation: Annotation,
                                              words_in_page: List[html.HtmlElement]) -> List[Dict]:
        """Find words with high overlap with bounding box of a given annotation.

        :param annotation: one Annotation object
        :param words_in_page: list of html elements representing words on a pdf page
        :return: list of dictionaries of type
            {
                "word": html element representing the word,
                "score": proportion of the word box intersecting the annotation box
            }
        """
        words = self._get_scored_words(words_in_page, annotation, self.default_threshold)
        if words:
            return words

        # we didn't succeed, let's refine our search
        words = self._get_scored_words(words_in_page, annotation, self.minimal_threshold)
        if words:
            best_word = max(words, key=lambda item: item["score"])  # let's take the largest one
            logging.warning(
                f"Only weak annotation-word match. We are returning the word with largest overlap "
                f"('{best_word['word']}', score = {best_word['score']})")
            return [best_word]

        # we still didn't succeed
        logging.error(f"cannot match annotation {annotation} with any word-element (file {self.pdf_path.stem})")
        return []

    def _match_annotations_with_words(self,
                                      raw_annotations: Dict[int, List[Annotation]],
                                      match_anno_types: Tuple[str] = ("rectangle",)) -> Dict[int, Dict]:
        """Match boxes from annotations and bounding boxes of words.

        :param raw_annotations: annotations as extracted by AnnotationExtractor
        :param match_anno_types: annotation types for which we want to obtain textual content
        :return: dictionary of type
         { page_num: [
            {"annotation": Annotation, "words": [{"word": word_as_etree_el, "score": overlap_score}, ...]}, ...
            ]
        }.
        The score is always the intersection over union from annotation box and the bounding box of word.
        """
        pages = self.get_pages()

        matched_annotations = defaultdict(list)
        for page_idx in raw_annotations:
            for annot in raw_annotations[page_idx]:
                if annot.type in match_anno_types:
                    matched_annotations[page_idx].append({
                        "annotation": annot,
                        "words": self._find_words_related_to_one_annotation(annot, pages[page_idx])})
        return dict(matched_annotations)
    #
    # def get_flows_with_annotations(self):
    #     """
    #     returns a data structure of type
    #     {flow_index:
    #         {"words": [list of strings],
    #          "annotated_indices" {annotation_type: [list_of_indices_of_words], ...}}
    #     }
    #     it generalizes the 'get_flows' method of the parent class (Pdf)
    #     recommended use: if the annotations are mainly rectangles
    #     """
    #     flows_to_id = {flow: i for i, flow in enumerate(self.root.findall(".//flow"))}
    #     flows_to_annot = {}
    #     matched_annotations = self.get_matched_annotations()
    #     for page_num in matched_annotations:
    #         for annot in matched_annotations[page_num]:
    #             if annot["annotation"].type == 'rectangle':
    #                 if annot["words"]:
    #                     words = [w["word"] for w in annot["words"]]
    #                     neighborhood_in_flow = self.get_neighborhood_of_words(words)
    #                     if neighborhood_in_flow is None:
    #                         logging.error(f"cannot get annotated flows for {self.pdf_path}")
    #                         continue
    #                     current_flow = neighborhood_in_flow["flow"]
    #                     current_flow_id = flows_to_id[current_flow]
    #                     if current_flow_id not in flows_to_annot:
    #                         flows_to_annot[current_flow_id] = {
    #                             "words": neighborhood_in_flow["words"],
    #                             "annotated_indices": defaultdict(list),
    #                             "page": page_num
    #                         }
    #                     annot_type = annot["annotation"].text_content.lower()[0] # first char of text_content
    #                     flows_to_annot[current_flow_id]["annotated_indices"][annot_type] += (
    #                         neighborhood_in_flow["indices"])
    #
    #     for page_num, page in enumerate(self.root.findall(".//page")):
    #         for flow in page.findall(".//flow"):
    #             flow_id = flows_to_id[flow]
    #             if flow_id not in flows_to_annot:
    #                 flows_to_annot[flow_id] = {
    #                     "words": [w.text for w in flow.findall(".//word")],
    #                     "page": page_num,
    #                     "annotated_indices": defaultdict(list),
    #                 }
    #     return dict(sorted(flows_to_annot.items()))
    #
    # def get_neighborhood_of_words(self, annotated_words):
    #     """
    #     annotated_words: list of words, represented as etree-elements
    #     Output: a dict-object with attributes
    #        'flow': flow as an etree-element
    #        'words': list of words in the flow (as strings)
    #        'indices': list of indices of the words that are within annotated_words
    #
    #     """
    #     if not annotated_words:
    #         logging.error(f"no annotated_words, cannot create neighborhood ({self.pdf_path})")
    #         return None
    #     parents = [w.getparent().getparent().getparent() for w in annotated_words]
    #     if not len(set(parents)) == 1:
    #         logging.error(f"words in the annotation are in different blocks or flows, cannot fetch neighborhood "
    #                       f"(file {self.pdf_path})")
    #         return None
    #
    #     common_parent = parents[0]
    #     annotated_indices, words_in_section = [], []
    #     for i, word in enumerate(common_parent.findall(".//word")):
    #         words_in_section.append(word.text)
    #         if word in annotated_words:
    #             annotated_indices.append(i)
    #
    #     # checks if annotated words follow subsequently
    #     if not annotated_indices == list(range(min(annotated_indices), max(annotated_indices) + 1)):
    #         logging.warning(f"annotated words are not connected (file {self.pdf_path})")
    #
    #     return {
    #         "flow": common_parent,
    #         "words": words_in_section,
    #         "indices": annotated_indices
    #     }
    #

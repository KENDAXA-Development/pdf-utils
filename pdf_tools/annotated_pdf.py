"""Tools to digitalize annotations from a pdf.

While the pdf_tools.annotation.AnnotationExtractor fetches the raw annotations, here we match their bounding boxes
with actual words, and provide tools for seeing these words in context.
"""
import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from lxml import html

from pdf_tools.annotation import Annotation, AnnotationExtractor
from pdf_tools.pdf_handler import Pdf


class AnnotatedPdf(Pdf):
    """Tools to process one annotated pdf."""

    match_words_threshold = 0.4
    match_words_minimal_threshold = 0.2
    match_annotation_types = ("rectangle", )

    minimal_words_in_document = 10

    def __init__(self, pdf_path: Union[str, Path]) -> None:
        super().__init__(pdf_path)
        self._raw_annotations = None
        self._enriched_annotations = None
        self._flow_to_id = None

    @property
    def raw_annotations(self) -> List[Annotation]:
        """Extract annotations from pdf."""
        if self._raw_annotations is None:
            self._raw_annotations = AnnotationExtractor().get_annot_from_pdf(self)
        return self._raw_annotations

    @property
    def enriched_annotations(self) -> List[Dict]:
        """Extract 'rectangle' annotations with matched words.

        Enriched_annotations contain information about pdf textual content within the annotation's bounding-box.
        We assume that the pdf is 'digital', or has been ocred already.
        The return value has structure
        [{
            "annotation": annotation,
            "words": [{"word": word_as_html_element, "bounding_box": Rectangle, "score": float}, ...]},
            {...},
            ...,
        ]
        """
        if self._enriched_annotations is None:
            self._enriched_annotations = self._match_annotations_with_words(self.raw_annotations)
        return self._enriched_annotations

    def get_flows_with_annotations(self,
                                   transform_anno_text_description: Callable[[str], str] = lambda s: s
                                   ) -> Dict[int, Dict]:
        """Extract 'rectangle'-type annotations in the context of neighboring words or sentences.

        For this to work, we expect that the pdf is digital, or has been ocred before.

        The poppler pdftotext output structures a document into
            pages > flows > blocks > lines > words.
        Here we work on the level of `flow`s, which are typically paragraphs or small blocks of text.

        With every annotation of 'rectangle' type, we find the corresponding flow and return the words
        and indices of annotated words within this flow.

        :param transform_anno_text_description:
            a function to convert the annotations "text_content" into another string (identity function by default).
            This can be used if we want to normalize text_content comming from different annotators, for instance.
        :return:
            The return dictionary has type
            {
                flow_index: {
                    "words": [list of words in the flow],
                    "page": page number, starting from 0,
                    "annotated_indices": {
                        annotation_description: [list_of_indices_of_words],
                        annather_annotation_description: [list of indices],
                        ...
                    }
                }
            }.
        """
        # check if digital content exists
        if len(self.text_with_bb.findall(".//word")) < self.minimal_words_in_document:
            logging.error("Cannot extract digital content from pdf (no words there).")
            return {}

        # enumerate flows
        flows_to_id = self._enumerate_flows()
        # create flows with words, but no annotations yet
        annotated_flows = self._initialize_flows()

        # iterate over annotations whose types are within self.match_annotation_types
        for annot in self.enriched_annotations:
            if not annot["words"]:
                logging.warning(f"annotation {annot} found with no words")
                continue

            # create a list of html-elements representing annotated words
            words = [w["word"] for w in annot["words"]]
            # neighborhood of some words is a dict with keys 'flow', 'words', 'indices'
            neighborhood = self._get_neighborhood_of_words(words)
            if neighborhood is None:
                logging.error(f"cannot get annotated flows for {self.pdf_path}")
                continue
            # here we find in which flow the annotation is
            current_flow_id = flows_to_id[neighborhood["flow"]]
            annot_text_content = annot["annotation"].text_content
            if not annot_text_content:
                logging.warning(f"rectangle annotation with empty text_content found, annot={annot['annotation']}")
                continue
            # normalize annotation's text_content
            annot_description = transform_anno_text_description(annot_text_content)
            # we add indices of annotated words into the annot_description
            annotated_flows[current_flow_id]["annotated_indices"][annot_description] += neighborhood["indices"]

        return dict(sorted(annotated_flows.items()))

    def _initialize_flows(self) -> Dict[int, Dict]:
        """Create a dictionary from flow_id to information about words in this flow."""
        flows = {}
        flow_to_id = self._enumerate_flows()
        for page_num, page in enumerate(self.text_with_bb.findall(".//page")):
            for flow in page.findall(".//flow"):
                flow_id = flow_to_id[flow]
                flows[flow_id] = {
                    "words": [w.text for w in flow.findall(".//word")],
                    "page": page_num,
                    "annotated_indices": defaultdict(list),
                }
        return flows

    def _enumerate_flows(self, recompute: bool = False) -> Dict[html.HtmlElement, int]:
        """Get a dictionary from flow (as html element) to flow_id (integer)."""
        if self._flow_to_id is None or recompute:
            self._flow_to_id = {flow: i for i, flow in enumerate(self.text_with_bb.findall(".//flow"))}
        return self._flow_to_id

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
        words = self._get_scored_words(words_in_page, annotation, self.match_words_threshold)
        if words:
            return words

        # we didn't succeed, let's refine our search
        words = self._get_scored_words(words_in_page, annotation, self.match_words_minimal_threshold)
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
                                      raw_annotations: List[Annotation]) -> List[Dict]:
        """Match boxes from annotations and bounding boxes of words.

        :param raw_annotations: annotations as extracted by AnnotationExtractor
        :return: dictionary of type
         { page_num: [
            {"annotation": Annotation, "words": [{"word": word_as_html_element, "score": overlap_score}, ...]}, ...
            ]
        }.
        The score is always the intersection over union from annotation box and the bounding box of word.
        """
        pages = self.get_pages()

        matched_annotations = []
        for annot in raw_annotations:
            if annot.type in self.match_annotation_types:
                matched_annotations.append({
                    "annotation": annot,
                    "words": self._find_words_related_to_one_annotation(annot, pages[annot.page])})
        return matched_annotations

    def _get_neighborhood_of_words(self, words: List[html.HtmlElement]) -> Optional[Dict]:
        """For a list of given words, compute the corresponding section and indices of these words within section.

        The html structure of the pdf consists hierarchically of pages, flows, blocks, lines, and words.
        This method finds the parent flow of a list of words, and returns indices of words.

        :param words: list of words, represented as html-elements
        :return: a dictionary with form
           'flow': flow as a html-element
           'words': list of words in the flow (as strings)
           'indices': list of indices of the words that are within annotated_words.
        """
        if not words:
            logging.error(f"no annotated_words, cannot create neighborhood ({self.pdf_path})")
            return None
        # grand-grand-parents of a word is a flow
        parents = [w.getparent().getparent().getparent() for w in words]
        if not len(set(parents)) == 1:
            logging.error(f"words in the annotation are in different flows, cannot fetch neighborhood "
                          f"(file {self.pdf_path})")
            return None

        ancestor = parents[0]
        annotated_indices, words_in_section = [], []
        for i, word in enumerate(ancestor.findall(".//word")):
            words_in_section.append(word.text)
            if word in words:
                annotated_indices.append(i)

        # checks if annotated words follow subsequently
        if not annotated_indices == list(range(min(annotated_indices), max(annotated_indices) + 1)):
            logging.warning(f"annotated words are not connected (file {self.pdf_path})")

        return {
            "flow": ancestor,
            "words": words_in_section,
            "indices": annotated_indices
        }

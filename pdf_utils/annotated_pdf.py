"""Tools to digitalize annotations from a pdf.

While the pdf_utils.annotation.AnnotationExtractor fetches the raw annotations, here we match their bounding boxes
with actual words, and provide tools for seeing these words in context.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from operator import itemgetter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.generic import IndirectObject, NameObject, NumberObject
from lxml import html

from pdf_utils.annotation import Annotation, AnnotationExtractor
from pdf_utils.pdf_handler import Pdf

logger = logging.getLogger(__name__)


class AnnotatedPdf(Pdf):
    """Tools to process one annotated pdf."""

    _match_words_threshold = 0.4
    _match_words_minimal_threshold = 0.2
    _enrich_annotation_types = ("rectangle",)

    minimal_words_in_document = 10

    def __init__(self, pdf_path: Union[str, Path]) -> None:
        super().__init__(pdf_path)
        self._raw_annotations = AnnotationExtractor().get_annot_from_pdf(self)
        self._enriched_annotations = None

        # list of all pages, as html element
        self._pages_as_html = [self.get_page_as_html(page_idx).find(".//page")
                               for page_idx in range(self.number_of_pages)]
        self._page_to_page_idx = {page: page_idx for page_idx, page in enumerate(self._pages_as_html)}

        # List of all flow, as they are in the html pages.
        # This should be the only place where we search in html, so that all flows are unique as objects
        self._flows_as_html = sum([page.findall(".//flow") for page in self._pages_as_html], [])
        self._flow_to_id = {flow: _id for _id, flow in enumerate(self._flows_as_html)}

    @property
    def raw_annotations(self) -> List[Annotation]:
        """Extract annotations from pdf."""
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
            self._enriched_annotations = self._match_annotations_with_words()
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
        nr_words = sum(len(v) for v in self.get_pages().values())
        if nr_words < self.minimal_words_in_document:
            logger.warning("Cannot extract digital content from pdf (no words there).")
            return {}

        # create flows with words, but no annotations yet
        annotated_flows = self._initialize_flows()

        # iterate over annotations whose types are within self.match_annotation_types
        for annot in self.enriched_annotations:
            if not annot["words"]:
                logger.warning(f"annotation {annot} found with no words")
                continue

            # create a list of html-elements representing annotated words
            words = [w["word"] for w in annot["words"]]
            # neighborhood of some words is a dict with keys 'flow', 'words', 'indices'
            neighborhood = self._get_neighborhood_of_words(words)
            if neighborhood is None:
                logger.warning(f"cannot get ancestor flow for the words {[w.text for w in words]} "
                               f"(file {self.pdf_path}, skipping")
                continue
            # here we find in which flow the annotation is
            current_flow_id = self._flow_to_id[neighborhood["flow"]]
            annot_text_content = annot["annotation"].text_content
            if not annot_text_content:
                logger.warning(f"rectangle annotation with empty text_content found, annot={annot['annotation']}")
                continue
            # normalize annotation's text_content
            annot_description = transform_anno_text_description(annot_text_content)
            # we add indices of annotated words into the annot_description
            annotated_flows[current_flow_id]["annotated_indices"][annot_description] += neighborhood["indices"]

        return annotated_flows

    def _match_annotations_with_words(self) -> List[Dict]:
        """Extract 'rectangle' annotations with matched words.

        This is the backend of the `enriched_annotations` method.
        """
        pages = self._pages_as_html
        matched_annotations = []
        for annot in self.raw_annotations:
            if annot.type in self._enrich_annotation_types:
                matched_annotations.append({
                    "annotation": annot,
                    "words": self._find_words_related_to_one_annotation(
                        annot,
                        pages[annot.page].findall(".//word"))})
        return matched_annotations

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
        words = self._get_scored_words(words_in_page, annotation, self._match_words_threshold)
        if words:
            return words

        # we didn't succeed, let's refine our search
        words = self._get_scored_words(words_in_page, annotation, self._match_words_minimal_threshold)
        if words:
            best_word = max(words, key=itemgetter("score"))  # let's take the largest one
            logger.warning(
                f"Only weak annotation-word match. We are returning the word with largest overlap "
                f"('{best_word['word']}', score = {best_word['score']})")
            return [best_word]

        # we still didn't succeed
        logger.warning(f"cannot match annotation {annotation} with any word-element (file {self.pdf_path.stem})")
        return []

    def _initialize_flows(self) -> Dict[int, Dict]:
        """Create a dictionary from flow_id to information about words in this flow."""
        flows = {}
        for flow in self._flows_as_html:
            flow_id = self._flow_to_id[flow]
            parent_page = flow.getparent()
            flows[flow_id] = {
                "words": [w.text for w in flow.findall(".//word")],
                "page": self._page_to_page_idx[parent_page],
                "annotated_indices": defaultdict(list)}
        return flows

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
        assert words, f"no annotated_words, cannot create neighborhood ({self.pdf_path})"

        # grand-grand-parents of a word is a flow
        parents = [w.getparent().getparent().getparent() for w in words]
        if not len(set(parents)) == 1:
            logger.warning(f"words in the annotation are in different flows, cannot fetch neighborhood "
                           f"(file {self.pdf_path}) -- skipping")
            return None

        ancestor = parents[0]
        annotated_indices, words_in_section = [], []
        for i, word in enumerate(ancestor.findall(".//word")):
            words_in_section.append(word.text)
            if word in words:
                annotated_indices.append(i)

        # checks if annotated words follow subsequently
        if not annotated_indices == list(range(min(annotated_indices), max(annotated_indices) + 1)):
            logger.warning(f"annotated words are not connected (file {self.pdf_path})")

        return {
            "flow": ancestor,
            "words": words_in_section,
            "indices": annotated_indices
        }

    def _clean_writer(self) -> PdfFileWriterX:
        """Return a FileWriter linked with a pdf copy with all annotations removed."""
        pdf = PdfFileWriterX()
        pdf.cloneDocumentFromReader(self.pdf_reader)
        for i in range(self.number_of_pages):
            page = pdf.getPage(i)
            if '/Annots' in page:
                del page['/Annots']
        return pdf

    def remove_annotations_and_save(self, output_pdf_path: str) -> None:
        """Get rid of annotations and store to a new pdf file."""
        clean = self._clean_writer()
        with open(output_pdf_path, "wb") as f:
            logger.info(f"creating a new pdf {output_pdf_path}")
            clean.write(f)


class PdfFileWriterX(PdfFileWriter):
    """This is overwriting of original class because if cloning issue.

    The fix is copy-paste from https://github.com/mstamy2/PyPDF2/issues/219#issuecomment-131252808.
    """

    def cloneDocumentFromReader(self, reader: PdfFileReader, *args) -> None:
        """Create a copy (clone) of a document from a PDF file reader.

        :param reader: PDF file reader instance from which the clone
            should be created.
        :callback after_page_append (function): Callback function that is invoked after
            each page is appended to the writer. Signature includes a reference to the
            appended page (delegates to appendPagesFromReader). Callback signature:

            :param writer_pageref (PDF page reference): Reference to the page just
                appended to the document.
        """
        mustAddTogether = False
        newInfoRef = self._info
        oldPagesRef = self._pages
        oldPages = self.getObject(self._pages)

        # If there have already been any number of pages added

        if oldPages[NameObject("/Count")] > 0:
            # Keep them
            mustAddTogether = True
        else:
            # Through the page object out
            if oldPages in self._objects:
                newInfoRef = self._pages
                self._objects.remove(oldPages)

        # Clone the reader's root document
        self.cloneReaderDocumentRoot(reader)
        if not self._root:
            self._root = self._addObject(self._root_object)

        # Sweep for all indirect references
        externalReferenceMap = {}
        self.stack = []
        newRootRef = self._sweepIndirectReferences(externalReferenceMap, self._root)

        # Delete the stack to reset
        del self.stack

        # Clean-Up Time!!!
        # Get the new root of the PDF
        realRoot = self.getObject(newRootRef)

        # Get the new pages tree root and its ID Number
        tmpPages = realRoot[NameObject("/Pages")]
        newIdNumForPages = 1 + self._objects.index(tmpPages)

        # Make an IndirectObject just for the new Pages
        self._pages = IndirectObject(newIdNumForPages, 0, self)

        # If there are any pages to add back in
        if mustAddTogether:
            # Set the new page's root's parent to the old
            # page's root's reference
            tmpPages[NameObject("/Parent")] = oldPagesRef
            # Add the reference to the new page's root in
            # the old page's kids array

            newPagesRef = self._pages
            oldPages[NameObject("/Kids")].append(newPagesRef)
            # Set all references to the root of the old/new
            # page's root
            self._pages = oldPagesRef
            realRoot[NameObject("/Pages")] = oldPagesRef
            # Update the count attribute of the page's root
            oldPages[NameObject("/Count")] = \
                NumberObject(oldPages[NameObject("/Count")] + tmpPages[NameObject("/Count")])
        else:
            # Bump up the info's reference b/c the old
            # page's tree was bumped off
            self._info = newInfoRef

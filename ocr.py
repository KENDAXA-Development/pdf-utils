from typing import Dict, List

from PIL import Image
import pytesseract

from pdf_tools.rectangle import Rectangle


class Scanner:
    """Ocr image, create searchable pdf from images."""

    def __init__(self):
        pass

    @classmethod
    def ocr_one_image(cls, im: Image.Image,
                      lang: str = "eng",
                      config: str = "--psm 12 --oem 3") -> List[Dict]:
        """Compute a dictionary with detected words and bounding boxes.

        :param im: input image
        :param lang: language code
        :param config: tesseract configuration
        :return: list of dictionaries of type {"word": word, "bb": bounding box of the word, relative to page size}
        """
        d = pytesseract.image_to_data(
            im, output_type=pytesseract.Output.DICT, lang=lang, config=config)
        result = []
        for i in range(len(d["level"])):
            word = d["text"][i]
            if word.strip():
                left, top, width, height = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
                result.append({
                    "word": word,
                    "bb": Rectangle(left, top, left + width, top + height).relative_to_size(
                        width=im.size[0],
                        height=im.size[1]
                    )
                })
        return result


if __name__ == "__main__":
    pass



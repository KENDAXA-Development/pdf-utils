"""Rectangle class implements bounding boxes representation.

Main methods support various bounding-boxes operations such as
* conversion between various formats, or
* computing intersections, unions and subbox-relations.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class Rectangle:
    """
    Data class for storing bounding boxes.

    The need of this arose to remove ambiguity about what is width and what is height, in a 4-tuple.
    """

    def __init__(self, x_min, y_min, x_max, y_max, dtype=float) -> None:
        """Define ranges for x and y and compute width and height of the rectangle.

        The parameters are assumed to be in this order -- x_min, y_min, x_max, y_max
        """
        self.x_min = dtype(x_min)
        self.y_min = dtype(y_min)
        self.x_max = dtype(x_max)
        self.y_max = dtype(y_max)
        if (self.x_min > self.x_max) or (self.y_min > self.y_max):
            logger.warning(f"rectangle lower bound is larger than upper bound (x: {x_min, x_max}, y: {y_min, y_max})")

    @property
    def width(self):
        """Get width of the rectangle."""
        return self.x_max - self.x_min

    @property
    def height(self):
        """Get height of the rectangle."""
        return self.y_max - self.y_min

    @property
    def area(self):
        """Get area of the rectangle."""
        return self.width * self.height

    @property
    def center(self) -> tuple:
        """Get rectangle's center as a pair (x,y)."""
        x = (self.x_max + self.x_min) / 2
        y = (self.y_max + self.y_min) / 2
        return x, y

    @property
    def as_dict(self):
        """Convert to dict."""
        return {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
        }

    @classmethod
    def from_dict(cls, rect_dict: Dict, dtype=float) -> Rectangle:
        """Create a rectangle from a dictionary.

        :param rect_dict: dictionary with keys 'x_min', 'y_min', 'x_max', 'y_max'.
        """
        return Rectangle(**rect_dict, dtype=dtype)

    def to_coco(self, rounding: Optional[int] = 2) -> Dict:
        """Convert to a dictionary with keys x_center, y_center, width, height.

        :param rounding: how many decimal places to use for the resulting floats
        """
        x_center, y_center = self.center
        return {
            "x_center": x_center if rounding is None else round(x_center, rounding),
            "y_center": y_center if rounding is None else round(y_center, rounding),
            "width": self.width if rounding is None else round(self.width, rounding),
            "height": self.height if rounding is None else round(self.height, rounding)
        }

    @classmethod
    def from_coco(cls, x_center, y_center, width, height) -> Rectangle:
        """Create a rectangle from center and width and height."""
        w_half = width / 2
        h_half = height / 2
        return Rectangle(x_center - w_half, y_center - h_half, x_center + w_half, y_center + h_half)

    @staticmethod
    def from_image(img: np.ndarray) -> Rectangle:
        """Take a numpy array-image and returns the full image bounding box as a Rectangle."""
        height, width = img.shape[:2]
        return Rectangle(x_min=0, y_min=0, x_max=width, y_max=height, dtype=int)

    def contains_other(self, other: Rectangle) -> bool:
        """Check if other rectangle is a sub-rectangle of the current one."""
        return other.x_min >= self.x_min and other.x_max <= self.x_max and (
            other.y_min >= self.y_min and other.y_max <= self.y_max)

    def rescale(self, multiply_width_by, multiply_height_by) -> Rectangle:
        """Multiplies horizontal and vertical ranges by constants."""
        return Rectangle(
            x_min=self.x_min * multiply_width_by,
            y_min=self.y_min * multiply_height_by,
            x_max=self.x_max * multiply_width_by,
            y_max=self.y_max * multiply_height_by
        )

    def to_int(self) -> Rectangle:
        """Create a new rectangle with all coordinats rounded to integers."""
        return Rectangle(**self.as_dict, dtype=int)

    def relative_to_size(self, width, height) -> Rectangle:
        """Renormalizes rectangle coordinates relative to reference width and height.

        Returned will be values between 0 and 1.
        """
        return self.rescale(multiply_width_by=1 / width, multiply_height_by=1 / height)

    def intersection(self, other: Rectangle) -> Optional[Rectangle]:
        """Return interscetion Rectangle if nontrivial, else None."""
        x_min = max(self.x_min, other.x_min)
        y_min = max(self.y_min, other.y_min)
        x_max = min(self.x_max, other.x_max)
        y_max = min(self.y_max, other.y_max)
        if x_min > x_max or y_min > y_max:
            return None
        return Rectangle(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)

    def get_iou(self, rect: Rectangle) -> float:
        """Compute intersection over union."""
        inter = self.intersection(rect)
        if not inter:
            return 0
        return inter.area / float(self.area + rect.area - inter.area)

    def smallest_common_superrectangle(self, other: Rectangle) -> Rectangle:
        """Return a rectangle containing both self and other."""
        return Rectangle(
            x_min=min(self.x_min, other.x_min),
            y_min=min(self.y_min, other.y_min),
            x_max=max(self.x_max, other.x_max),
            y_max=max(self.y_max, other.y_max)
        )

    def intersection_width_some_other(self, others: List[Rectangle]) -> bool:
        """Return True if some of the other rectangles intersects this rectangle, False otherwise."""
        return any(self.intersection(other) for other in others)

    @staticmethod
    def normalize_list_of_rectangles(rectangles: List[Rectangle]) -> List[Rectangle]:
        """Recursively replaces intersecting rectangle pair by their lowest common superrectangle."""
        if len(rectangles) < 2:
            return rectangles

        first = rectangles[0]

        first_intersects_some = False
        for i in range(1, len(rectangles)):
            if first.get_iou(rectangles[i]):  # intersection nontrivial
                rectangles[i] = rectangles[i].smallest_common_superrectangle(first)
                first_intersects_some = True
        rest_normalized = Rectangle.normalize_list_of_rectangles(rectangles[1:])
        return rest_normalized if first_intersects_some else [first] + rest_normalized

    def __contains__(self, other: Rectangle) -> bool:
        """Check if the other box is a subbox of the current box.

        It is true if the other box is "fully inside" the current box.
        We are a bit mixing the "is element" and "subset" relations, but meaning should be clear from the context.
        For instance,
            `Rectangle(1, 1, 2, 2) in Rectangle(0, 0, 5, 5)` is True, while
            `Rectangle(1, 1, 2, 2) in Rectangle(1, 1.1, 2, 3)` is False.
        """
        return self.contains_other(other)

    def __eq__(self, other: Rectangle) -> bool:
        return self.as_dict == other.as_dict

    def __repr__(self) -> str:
        return f"<Rectangle(x_min={self.x_min}, y_min={self.y_min}, x_max={self.x_max}, y_max={self.y_max})>"

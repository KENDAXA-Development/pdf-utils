import unittest

import numpy as np

from pdf_utils.rectangle import Rectangle


class TestRectangle(unittest.TestCase):

    def test_width_height(self):
        example_rect = Rectangle(x_min=0, y_min=1, x_max=2, y_max=33)
        self.assertEqual(example_rect.width, 2)
        self.assertEqual(example_rect.height, 32)
        self.assertEqual(example_rect.area, 64)
        self.assertEqual(example_rect.center, (1, 17))

    def test_io(self):
        example_rect = Rectangle(x_min=0, y_min=1, x_max=2, y_max=33)
        self.assertEqual(
            example_rect.as_dict,
            dict(x_min=0, y_min=1, x_max=2, y_max=33)
        )
        self.assertEqual(
            example_rect,
            Rectangle.from_dict(dict(x_min=0, y_min=1, x_max=2, y_max=33))
        )

        self.assertEqual(
            example_rect.to_coco(),
            dict(x_center=1, y_center=17, width=2, height=32)
        )
        self.assertEqual(
            example_rect,
            Rectangle.from_coco(**dict(x_center=1, y_center=17, width=2, height=32))
        )

    def test_image2box(self):
        h, w = 123, 234
        black_image = np.zeros((h, w))
        self.assertEqual(
            Rectangle(0, 0, w, h),
            Rectangle.from_image(black_image)
        )

    def test_subrectangle(self):
        small = Rectangle(0, 1, 2, 3)
        medium1 = Rectangle(0, 1, 4, 10)
        medium2 = Rectangle(-1, 1, 4, 3)
        large = Rectangle(-1, 0, 4, 10)

        self.assertTrue(small in medium1)
        self.assertTrue(small in medium2)
        self.assertTrue(small in large)
        self.assertTrue(medium1 in large)
        self.assertTrue(medium2 in large)

        self.assertFalse(medium1 in small)
        self.assertFalse(medium2 in small)
        self.assertFalse(large in small)
        self.assertFalse(large in medium1)
        self.assertFalse(large in medium2)

    def test_resizing_methods(self):
        example_rect = Rectangle(0.0, 1.5, 2.0, 33.3)
        self.assertEqual(
            example_rect.rescale(0.1, 10),
            Rectangle(0, 15, 0.2, 333)
        )

        self.assertEqual(
            example_rect.to_int(),
            Rectangle(0, 1, 2, 33)
        )

        self.assertEqual(
            example_rect.relative_to_size(width=100, height=200),
            Rectangle(x_min=0, y_min=1.5 / 200, x_max=2.0 / 100, y_max=33.3 / 200)
        )

    def test_intersection(self):
        """Tests the intersection and iou."""
        r1 = Rectangle(0, 1, 2, 3)
        r2 = Rectangle(-10, -10, 0, 0)
        r3 = Rectangle(1, 1, 5, 5)

        self.assertIsNone(r1.intersection(r2))
        self.assertIsNone(r2.intersection(r1))
        self.assertIsNone(r2.intersection(r3))
        self.assertIsNone(r3.intersection(r2))

        self.assertEqual(r1.intersection(r3), Rectangle(1, 1, 2, 3))
        self.assertEqual(r3.intersection(r1), Rectangle(1, 1, 2, 3))

        self.assertEqual(r1.get_iou(r2), 0)
        self.assertEqual(r2.get_iou(r1), 0)
        self.assertEqual(r1.get_iou(r3), 1 / 9)
        self.assertEqual(r3.get_iou(r1), 1 / 9)

        self.assertTrue(r1.intersection_width_some_other([r2, r3]))
        self.assertFalse(r2.intersection_width_some_other([r1, r3]))

    def test_smallest_common_superrectangle(self):
        r1, r2 = Rectangle(0, 0, 1, 1), Rectangle(10, 10, 11, 11)
        self.assertEqual(
            r1.smallest_common_superrectangle(r2),
            Rectangle(0, 0, 11, 11)
        )

        self.assertEqual(
            r2.smallest_common_superrectangle(r1),
            Rectangle(0, 0, 11, 11)
        )

    def test_normalization(self):
        first = Rectangle(0, 0, 2, 2)
        second = Rectangle(3, 3, 5, 5)
        in_between = Rectangle(1, 1, 4, 4)
        far_away = Rectangle(100, 1, 120, 4)

        normalization = Rectangle.normalize_list_of_rectangles([first, second, far_away, in_between])
        expected_normalization_1 = Rectangle(x_min=100.0, y_min=1.0, x_max=120.0, y_max=4.0)
        expected_normalization_2 = Rectangle(x_min=0.0, y_min=0.0, x_max=5.0, y_max=5.0)

        self.assertTrue(any([
            normalization == [expected_normalization_1, expected_normalization_2],
            normalization == [expected_normalization_2, expected_normalization_1]]))

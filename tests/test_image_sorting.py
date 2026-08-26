# -*- coding: utf-8 -*-
from __future__ import absolute_import

import unittest

from libs.fileView import natural_path_key


class NaturalImageSortingTests(unittest.TestCase):
    def test_leading_numeric_identifier_is_sorted_by_integer_value(self):
        names = [
            '000100_camera.jpg',
            '000200_camera.jpg',
            '000400_camera.jpg',
            '000201_camera.jpg',
            '000102_camera.jpg',
            '000301_camera.jpg',
        ]

        self.assertEqual([
            '000100_camera.jpg',
            '000102_camera.jpg',
            '000200_camera.jpg',
            '000201_camera.jpg',
            '000301_camera.jpg',
            '000400_camera.jpg',
        ], sorted(names, key=natural_path_key))

    def test_letters_are_case_insensitive_and_numbers_remain_natural(self):
        names = ['B10.jpg', 'a10.jpg', 'b2.jpg', 'A2.jpg']

        self.assertEqual(
            ['A2.jpg', 'a10.jpg', 'b2.jpg', 'B10.jpg'],
            sorted(names, key=natural_path_key))

    def test_directory_components_participate_in_the_same_order(self):
        names = ['area10/1.jpg', 'area2/10.jpg', 'area2/2.jpg']

        self.assertEqual(
            ['area2/2.jpg', 'area2/10.jpg', 'area10/1.jpg'],
            sorted(names, key=natural_path_key))


if __name__ == '__main__':
    unittest.main()

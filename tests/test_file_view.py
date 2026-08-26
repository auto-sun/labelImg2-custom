# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import tempfile
import unittest

from PyQt5.QtCore import Qt

from libs.fileView import CFileListModel


class FileListConfirmationStateTests(unittest.TestCase):
    def test_refresh_preserves_green_state_by_full_image_path(self):
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, '1.jpg')
            second = os.path.join(directory, '2.jpg')
            model = CFileListModel()
            model.setStringList([first, second])
            model.setData(model.index(0), 3, Qt.BackgroundRole)

            model.setStringList([second, first])

            self.assertFalse(model.dispList[0][2])
            self.assertTrue(model.dispList[1][2])
            self.assertEqual(
                Qt.green,
                model.data(model.index(1), Qt.BackgroundRole).color())

    def test_same_filename_in_another_directory_does_not_inherit_state(self):
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, 'first', 'same.jpg')
            second = os.path.join(directory, 'second', 'same.jpg')
            model = CFileListModel()
            model.setStringList([first])
            model.setData(model.index(0), 1, Qt.BackgroundRole)

            model.setStringList([second])

            self.assertFalse(model.dispList[0][2])


if __name__ == '__main__':
    unittest.main()

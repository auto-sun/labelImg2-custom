# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import tempfile
import unittest
from unittest import mock

from PyQt5.QtCore import Qt

from libs.fileView import CFileListModel


class FileListConfirmationStateTests(unittest.TestCase):
    def test_deferred_refresh_does_not_open_annotation_files(self):
        with tempfile.TemporaryDirectory() as directory:
            image = os.path.join(directory, '1.jpg')
            model = CFileListModel()
            with mock.patch.object(
                    model, 'parseOne', side_effect=AssertionError(
                        'annotation parsing must be deferred')) as parser:
                model.setStringList(
                    [image], directory, directory,
                    scanAnnotations=False)
            parser.assert_not_called()
            self.assertEqual(-1, model.dispList[0][1])

    def test_background_count_update_preserves_confirmation_state(self):
        with tempfile.TemporaryDirectory() as directory:
            image = os.path.join(directory, '1.jpg')
            model = CFileListModel()
            model.setStringList([image], scanAnnotations=False)
            model.dispList[0][2] = True

            self.assertTrue(model.updateAnnotationCount(0, image, 7))

            self.assertEqual(7, model.annotationCount(model.index(0)))
            self.assertEqual(7, model.totalAnnotationCount())
            self.assertTrue(model.dispList[0][2])

            model.resetAnnotationCounts()
            self.assertEqual(0, model.totalAnnotationCount())
            self.assertEqual(-1, model.dispList[0][1])
            self.assertTrue(model.dispList[0][2])

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

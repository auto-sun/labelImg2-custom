# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import tempfile
import unittest
from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from libs.fileView import CFileListModel, CFileView


class FileListConfirmationStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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

    def test_review_mark_is_pale_red_and_survives_reordering(self):
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, '1.jpg')
            second = os.path.join(directory, '2.jpg')
            model = CFileListModel()
            model.setStringList([first, second], scanAnnotations=False)
            model.setData(model.index(0), 3, Qt.BackgroundRole)
            self.assertTrue(model.setFlagged(model.index(0), True))
            self.assertEqual(
                '#ffd2d2',
                model.data(model.index(0), Qt.BackgroundRole).color().name())

            model.setStringList([second, first], scanAnnotations=False)

            self.assertFalse(model.isFlagged(model.index(0)))
            self.assertTrue(model.isFlagged(model.index(1)))
            self.assertTrue(model.dispList[1][2])
            self.assertTrue(model.setFlagged(model.index(1), False))
            self.assertEqual([], model.flaggedPaths())

    def test_selected_review_mark_still_paints_red(self):
        with tempfile.TemporaryDirectory() as directory:
            view = CFileView()
            view.resize(260, 100)
            model = view.model()
            model.setStringList(
                [os.path.join(directory, 'review.jpg')],
                scanAnnotations=False)
            index = model.index(0)
            model.setFlagged(index, True)
            view.setCurrentIndex(index)
            view.show()
            self.app.processEvents()

            rect = view.visualRect(index)
            image = view.viewport().grab().toImage()
            color = image.pixelColor(rect.right() - 10, rect.center().y())
            self.assertGreater(color.red(), color.green() + 20)
            view.close()


if __name__ == '__main__':
    unittest.main()

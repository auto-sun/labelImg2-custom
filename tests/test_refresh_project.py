# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QItemSelectionModel, Qt
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

import labelImg


class MemorySettings(object):
    def __init__(self):
        self.data = {}

    def load(self):
        return True

    def save(self):
        return True

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


class RefreshProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        self.temporary = tempfile.TemporaryDirectory()
        self.imageDir = os.path.join(self.temporary.name, 'images')
        self.annotationDir = os.path.join(
            self.temporary.name, 'annotations')
        os.makedirs(self.imageDir)
        os.makedirs(self.annotationDir)
        self.firstImage = self.createImage('1.jpg')
        self.thirdImage = self.createImage('3.jpg')

        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath,
            defaultSaveDir=self.annotationDir)
        self.window.importDirImages(
            self.imageDir, resumeFilePath=self.firstImage)
        self.window.annotationScanTimer.stop()

    def tearDown(self):
        self.window.annotationScanTimer.stop()
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def createImage(self, filename):
        path = os.path.join(self.imageDir, filename)
        image = QImage(100, 80, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))
        self.assertTrue(image.save(path))
        return path

    def test_refresh_button_is_in_file_list_controls(self):
        action = self.window.actions.refreshProject

        self.assertIs(action, self.window.refreshButton.defaultAction())
        self.assertTrue(action.isEnabled())
        self.assertFalse(action.icon().isNull())
        self.assertEqual('F5', action.shortcut().toString())

    def test_refresh_rescans_images_labels_and_preserves_current(self):
        firstIndex = self.window.fileModel.index(0)
        self.window.fileModel.setData(
            firstIndex, 0, Qt.BackgroundRole)
        secondImage = self.createImage('2.jpg')
        os.remove(self.thirdImage)
        with open(os.path.join(self.annotationDir, '1.txt'),
                  'w', encoding='utf-8') as stream:
            stream.write('0 0.5 0.5 0.2 0.2\n')

        self.assertTrue(self.window.refreshProjectDirectories())

        self.assertEqual(
            [self.firstImage, secondImage],
            list(self.window.fileModel.stringList()))
        self.assertEqual(self.firstImage, self.window.filePath)
        self.assertEqual(1, len(self.window.canvas.shapes))
        self.assertTrue(self.window.fileModel.dispList[0][2])
        self.assertTrue(self.window.annotationScanTimer.isActive())

    def test_refresh_selects_nearest_row_when_current_was_removed(self):
        thirdIndex = self.window.fileModel.index(1)
        self.window.filesm.setCurrentIndex(
            thirdIndex, QItemSelectionModel.SelectCurrent)
        self.assertEqual(self.thirdImage, self.window.filePath)
        os.remove(self.thirdImage)

        self.assertTrue(self.window.refreshProjectDirectories())

        self.assertEqual([self.firstImage],
                         list(self.window.fileModel.stringList()))
        self.assertEqual(self.firstImage, self.window.filePath)

    def test_review_mark_survives_refresh_and_is_saved(self):
        self.assertTrue(self.window.toggleSelectedImageFlag())
        self.assertTrue(self.window.fileModel.isFlagged(
            self.window.filesm.currentIndex()))
        saved = self.window.settings.get(labelImg.SETTING_FLAGGED_IMAGES)
        self.assertEqual(1, len(saved))

        self.assertTrue(self.window.refreshProjectDirectories())
        self.assertTrue(self.window.fileModel.isFlagged(
            self.window.filesm.currentIndex()))
        self.assertTrue(self.window.toggleSelectedImageFlag())
        self.assertEqual([], self.window.settings.get(
            labelImg.SETTING_FLAGGED_IMAGES))

    def test_review_mark_is_restored_in_a_new_window(self):
        self.assertTrue(self.window.toggleSelectedImageFlag())
        savedData = dict(self.window.settings.data)

        class RestoredSettings(MemorySettings):
            def __init__(self):
                self.data = dict(savedData)

        labelImg.Settings = RestoredSettings
        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        reopened = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath,
            defaultSaveDir=self.annotationDir)
        try:
            reopened.importDirImages(
                self.imageDir, resumeFilePath=self.firstImage)
            self.assertTrue(reopened.fileModel.isFlagged(
                reopened.filesm.currentIndex()))
        finally:
            reopened.annotationScanTimer.stop()
            reopened.setClean()
            reopened.close()


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF, QItemSelectionModel
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

import labelImg
from libs.constants import FORMAT_YOLO
from libs.shape import Shape


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


def make_shape(label='person'):
    shape = Shape(label=label)
    for point in ((10, 10), (40, 10), (40, 40), (10, 40)):
        shape.addPoint(QPointF(*point))
    shape.line_color = QColor(0, 255, 0)
    shape.fill_color = QColor(255, 0, 0, 128)
    shape.isRotated = True
    shape.close()
    return shape


class LabelStatisticsTests(unittest.TestCase):
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

        self.imagePaths = []
        for name in ('one.jpg', 'two.jpg'):
            path = os.path.join(self.imageDir, name)
            image = QImage(100, 80, QImage.Format_RGB32)
            image.fill(QColor(255, 255, 255))
            self.assertTrue(image.save(path))
            self.imagePaths.append(path)

        self.writeYolo('one.txt', 2)
        self.writeYolo('two.txt', 1)

        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)
        self.window.dirname = self.imageDir
        self.window.defaultSaveDir = self.annotationDir
        self.window.annotationFormat = FORMAT_YOLO
        self.window.fileModel.setStringList(
            self.imagePaths, self.imageDir, self.annotationDir,
            FORMAT_YOLO)
        self.window.updateLabelStatistics()

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def writeYolo(self, name, count):
        path = os.path.join(self.annotationDir, name)
        with open(path, 'w', encoding='utf-8') as stream:
            for _index in range(count):
                stream.write('0 0.5 0.5 0.2 0.2\n')

    def loadFirstImage(self):
        index = self.window.fileModel.index(0)
        self.window.filesm.blockSignals(True)
        self.window.filesm.setCurrentIndex(
            index, QItemSelectionModel.SelectCurrent)
        self.window.filesm.blockSignals(False)
        self.assertTrue(self.window.loadFile(self.imagePaths[0]))

    def test_statistics_panel_is_below_box_list(self):
        layout = self.window.dock.widget().layout()
        self.assertGreater(
            layout.indexOf(self.window.labelStatisticsGroup),
            layout.indexOf(self.window.labelList))
        self.assertEqual('3', self.window.projectLabelCount.text())
        self.assertEqual('0', self.window.currentImageLabelCount.text())
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())

    def test_loading_existing_labels_does_not_count_as_session_work(self):
        self.loadFirstImage()

        self.assertEqual('3', self.window.projectLabelCount.text())
        self.assertEqual('2', self.window.currentImageLabelCount.text())
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())

    def test_new_box_updates_all_counts_and_undo_rolls_session_back(self):
        self.loadFirstImage()
        self.window.beginUndoOperation()
        shape = make_shape(self.window.labelHist[0])
        self.window.canvas.shapes.append(shape)
        self.window.addLabel(shape, sessionCreated=True)
        self.window.setDirty()

        self.assertEqual('4', self.window.projectLabelCount.text())
        self.assertEqual('3', self.window.currentImageLabelCount.text())
        self.assertEqual('1', self.window.sessionLabelCountDisplay.text())

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual('3', self.window.projectLabelCount.text())
        self.assertEqual('2', self.window.currentImageLabelCount.text())
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())

    def test_deleting_session_box_reduces_count_and_undo_restores_it(self):
        self.loadFirstImage()
        self.window.beginUndoOperation()
        shape = make_shape(self.window.labelHist[0])
        self.window.canvas.shapes.append(shape)
        self.window.addLabel(shape, sessionCreated=True)
        self.window.setDirty()
        self.window.resetUndoHistory()

        self.window.canvas._setSelectedShapes([shape])
        self.window.deleteSelectedShape()

        self.assertEqual('3', self.window.projectLabelCount.text())
        self.assertEqual('2', self.window.currentImageLabelCount.text())
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual('4', self.window.projectLabelCount.text())
        self.assertEqual('3', self.window.currentImageLabelCount.text())
        self.assertEqual('1', self.window.sessionLabelCountDisplay.text())

    def test_deleting_an_existing_box_does_not_reduce_session_count(self):
        self.loadFirstImage()
        existing = self.window.canvas.shapes[0]
        self.window.canvas._setSelectedShapes([existing])

        self.window.deleteSelectedShape()

        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())
        self.assertEqual('1', self.window.currentImageLabelCount.text())

    def test_mixed_multi_delete_only_subtracts_session_boxes(self):
        self.loadFirstImage()
        existing = self.window.canvas.shapes[0]
        created = make_shape(self.window.labelHist[0])
        self.window.canvas.shapes.append(created)
        self.window.addLabel(created, sessionCreated=True)
        self.window.setDirty()
        self.window.canvas._setSelectedShapes([existing, created])

        self.window.deleteSelectedShape()

        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())
        self.assertEqual('1', self.window.currentImageLabelCount.text())

    def test_cut_and_paste_restores_session_box_count(self):
        self.loadFirstImage()
        created = make_shape(self.window.labelHist[0])
        self.window.canvas.shapes.append(created)
        self.window.addLabel(created, sessionCreated=True)
        self.window.setDirty()
        self.window.canvas._setSelectedShapes([created])

        self.window.cutShapeToClipboard()
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())
        self.window.pasteShapeFromClipboard()
        self.assertEqual('1', self.window.sessionLabelCountDisplay.text())

    def test_session_provenance_survives_save_and_image_reload(self):
        self.loadFirstImage()
        shape = make_shape(self.window.labelHist[0])
        self.window.canvas.shapes.append(shape)
        self.window.addLabel(shape, sessionCreated=True)
        self.window.setDirty()
        self.assertTrue(self.window.saveFile())

        self.assertTrue(self.window.loadFile(self.imagePaths[1]))
        self.assertTrue(self.window.loadFile(self.imagePaths[0]))
        sessionShapes = [
            item for item in self.window.canvas.shapes
            if item.sessionCreated]
        self.assertEqual(1, len(sessionShapes))

        self.window.canvas._setSelectedShapes(sessionShapes)
        self.window.deleteSelectedShape()
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())

    def test_session_count_is_not_saved_between_windows(self):
        self.window.recordSessionLabels(7)
        self.assertEqual('7', self.window.sessionLabelCountDisplay.text())
        self.window.setClean()
        self.window.close()

        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)

        self.assertEqual(0, self.window.sessionLabelCount)
        self.assertEqual('0', self.window.sessionLabelCountDisplay.text())


if __name__ == '__main__':
    unittest.main()

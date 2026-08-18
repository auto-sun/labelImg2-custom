#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF, QItemSelectionModel, Qt
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication, QMessageBox

import labelImg
from libs.constants import (FORMAT_PASCALVOC, FORMAT_YOLO,
                            FORMAT_YOLO_OBB)
from libs.pascal_voc_io import PascalVocReader
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
    for point in ((10, 10), (60, 10), (60, 50), (10, 50)):
        shape.addPoint(QPointF(*point))
    shape.line_color = QColor(0, 255, 0)
    shape.fill_color = QColor(255, 0, 0, 128)
    shape.isRotated = True
    shape.close()
    return shape


class EmptyAnnotationTests(unittest.TestCase):
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

        self.imagePath = os.path.join(self.imageDir, 'one.jpg')
        image = QImage(100, 80, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))
        self.assertTrue(image.save(self.imagePath))

        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)
        self.window.dirname = self.imageDir
        self.window.defaultSaveDir = self.annotationDir
        self.window.fileModel.setStringList(
            [self.imagePath], self.imageDir, self.annotationDir,
            self.window.annotationFormat)
        index = self.window.fileModel.index(0)
        self.window.filesm.blockSignals(True)
        self.window.filesm.setCurrentIndex(
            index, QItemSelectionModel.SelectCurrent)
        self.window.filesm.blockSignals(False)
        self.assertTrue(self.window.loadFile(self.imagePath))

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def selectFormat(self, annotationFormat):
        self.window.annotationFormat = annotationFormat
        for currentFormat, action in self.window.annotationFormatActions.items():
            action.setChecked(currentFormat == annotationFormat)

    def addSessionShape(self):
        shape = make_shape()
        self.window.canvas.shapes.append(shape)
        self.window.addLabel(shape, sessionCreated=True)
        self.window.setDirty()
        self.window.resetUndoHistory()
        return shape

    def test_action_is_in_top_toolbar_and_enabled_with_image(self):
        action = self.window.actions.createEmptyAnnotation

        self.assertEqual('生成空标签', action.text())
        self.assertIn(action, self.window.tools.actions())
        self.assertFalse(action.icon().isNull())
        self.assertTrue(action.isEnabled())

    def test_pascal_voc_selection_creates_empty_xml(self):
        self.selectFormat(FORMAT_PASCALVOC)

        self.assertTrue(self.window.createEmptyAnnotation())

        annotationPath = os.path.join(self.annotationDir, 'one.xml')
        self.assertTrue(os.path.isfile(annotationPath))
        self.assertEqual([], PascalVocReader(annotationPath).getShapes())
        display = self.window.fileModel.data(
            self.window.fileModel.index(0), Qt.DisplayRole)
        self.assertIn('[BG]', display)

    def test_yolo_selection_creates_zero_byte_txt(self):
        self.selectFormat(FORMAT_YOLO)

        with mock.patch.object(
                labelImg, 'save_yolo_annotations',
                wraps=labelImg.save_yolo_annotations) as saveWriter:
            self.assertTrue(self.window.createEmptyAnnotation())

        annotationPath = os.path.join(self.annotationDir, 'one.txt')
        self.assertEqual(0, os.path.getsize(annotationPath))
        self.assertEqual(FORMAT_YOLO, saveWriter.call_args.args[-1])

    def test_yolo_obb_selection_uses_obb_writer_mode(self):
        self.selectFormat(FORMAT_YOLO_OBB)

        with mock.patch.object(
                labelImg, 'save_yolo_annotations',
                wraps=labelImg.save_yolo_annotations) as saveWriter:
            self.assertTrue(self.window.createEmptyAnnotation())

        annotationPath = os.path.join(self.annotationDir, 'one.txt')
        self.assertEqual(0, os.path.getsize(annotationPath))
        self.assertEqual(FORMAT_YOLO_OBB, saveWriter.call_args.args[-1])

    def test_existing_boxes_require_confirmation_and_cancel_keeps_them(self):
        self.selectFormat(FORMAT_YOLO_OBB)
        shape = self.addSessionShape()

        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.No):
            self.assertFalse(self.window.createEmptyAnnotation())

        self.assertEqual([shape], self.window.canvas.shapes)
        self.assertFalse(os.path.exists(
            os.path.join(self.annotationDir, 'one.txt')))
        self.assertEqual(1, self.window.sessionLabelCount)

    def test_confirm_clears_saves_and_can_be_undone(self):
        self.selectFormat(FORMAT_YOLO_OBB)
        self.addSessionShape()

        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.Yes):
            self.assertTrue(self.window.createEmptyAnnotation())

        annotationPath = os.path.join(self.annotationDir, 'one.txt')
        self.assertEqual([], self.window.canvas.shapes)
        self.assertEqual(0, os.path.getsize(annotationPath))
        self.assertEqual(0, self.window.sessionLabelCount)
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(1, len(self.window.canvas.shapes))
        self.assertEqual(1, self.window.sessionLabelCount)

    def test_save_failure_restores_original_boxes(self):
        self.selectFormat(FORMAT_YOLO_OBB)
        self.addSessionShape()

        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.Yes), \
                mock.patch.object(self.window, 'saveFile', return_value=False):
            self.assertFalse(self.window.createEmptyAnnotation())

        self.assertEqual(1, len(self.window.canvas.shapes))
        self.assertEqual('person', self.window.canvas.shapes[0].label)
        self.assertEqual(1, self.window.sessionLabelCount)


if __name__ == '__main__':
    unittest.main()

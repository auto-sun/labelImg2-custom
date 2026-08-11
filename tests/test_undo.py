#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QApplication

import labelImg
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


def make_shape(label, left, top, right, bottom):
    shape = Shape(label=label)
    for point in ((left, top), (right, top),
                  (right, bottom), (left, bottom)):
        shape.addPoint(QPointF(*point))
    shape.line_color = QColor(0, 255, 0)
    shape.fill_color = QColor(255, 0, 0, 128)
    shape.isRotated = True
    shape.close()
    return shape


class UndoOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)
        self.window.filePath = os.path.abspath('undo-test.jpg')
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(255, 255, 255))
        self.window.canvas.loadPixmap(pixmap)
        self.window.resetUndoHistory()

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings

    def add_and_select(self, *shapes):
        self.replace_shapes(*shapes)
        self.window.setClean()
        self.window.resetUndoHistory()

    def replace_shapes(self, *shapes):
        self.window.labelModel.clear()
        self.window.labelModel.setHorizontalHeaderLabels(
            ['Label', 'Extra Info'])
        self.window.ShapeItemDict.clear()
        self.window.ItemShapeDict.clear()
        self.window.canvas.visible.clear()
        self.window.canvas.selectedShape = None
        self.window.canvas.selectedShapes = []
        self.window.canvas.loadShapes(shapes)
        for shape in shapes:
            self.window.addLabel(shape)
        self.window.canvas._setSelectedShapes(list(shapes))

    def test_shortcuts_keep_paste_and_add_standard_undo(self):
        self.assertEqual('Ctrl+Z', self.window.actions.undo.shortcut().toString())
        self.assertEqual(
            'Ctrl+X',
            self.window.actions.cutToClipboard.shortcut().toString())
        self.assertEqual(
            'Ctrl+V',
            self.window.actions.pasteFromClipboard.shortcut().toString())

    def test_auto_save_is_enabled_by_default(self):
        self.assertTrue(self.window.autoSaving.isChecked())

    def test_saved_auto_save_off_preference_is_respected(self):
        class AutoSaveOffSettings(MemorySettings):
            def __init__(self):
                super(AutoSaveOffSettings, self).__init__()
                self.data['autosave'] = False

        self.window.setClean()
        self.window.close()
        labelImg.Settings = AutoSaveOffSettings
        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)

        self.assertFalse(self.window.autoSaving.isChecked())

    def test_undo_restores_a_moved_box(self):
        shape = make_shape('person', 10, 20, 50, 70)
        self.add_and_select(shape)
        originalPoints = [(point.x(), point.y()) for point in shape.points]

        self.window.canvas.moveOnePixel('Right')
        self.assertEqual(11.0, self.window.canvas.shapes[0].points[0].x())
        self.assertTrue(self.window.actions.undo.isEnabled())

        self.assertTrue(self.window.undoLastOperation())
        restoredPoints = [
            (point.x(), point.y())
            for point in self.window.canvas.shapes[0].points]
        self.assertEqual(originalPoints, restoredPoints)

    def test_undo_removes_pasted_boxes(self):
        shape = make_shape('person', 20, 20, 60, 80)
        self.add_and_select(shape)
        self.window.copyShapeToClipboard()

        self.window.pasteShapeFromClipboard()
        self.assertEqual(2, len(self.window.canvas.shapes))
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(1, len(self.window.canvas.shapes))
        self.assertEqual('person', self.window.canvas.shapes[0].label)

    def test_undo_restores_all_deleted_boxes(self):
        first = make_shape('person', 10, 10, 40, 50)
        second = make_shape('SafeHat', 80, 20, 120, 60)
        self.add_and_select(first, second)

        self.window.deleteSelectedShape()
        self.assertEqual([], self.window.canvas.shapes)
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(
            ['person', 'SafeHat'],
            [shape.label for shape in self.window.canvas.shapes])
        self.assertEqual(2, len(self.window.canvas.selectedShapes))

    def test_cut_removes_all_selected_boxes_and_undo_restores_them(self):
        first = make_shape('person', 10, 10, 40, 50)
        second = make_shape('SafeHat', 80, 20, 120, 60)
        self.add_and_select(first, second)

        self.window.cutShapeToClipboard()

        self.assertEqual([], self.window.canvas.shapes)
        self.assertEqual(
            ['person', 'SafeHat'],
            [shape.label for shape in self.window._shapeClipboard])
        self.assertTrue(self.window._shapeClipboardIsCut)
        self.assertEqual(1, len(self.window._undoStack))

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(
            ['person', 'SafeHat'],
            [shape.label for shape in self.window.canvas.shapes])

    def test_first_paste_after_cut_keeps_original_coordinates(self):
        shape = make_shape('person', 20, 30, 60, 90)
        self.add_and_select(shape)
        originalPoints = [(point.x(), point.y()) for point in shape.points]

        self.window.cutShapeToClipboard()
        self.window.pasteShapeFromClipboard()

        self.assertEqual(1, len(self.window.canvas.shapes))
        pastedPoints = [
            (point.x(), point.y())
            for point in self.window.canvas.shapes[0].points]
        self.assertEqual(originalPoints, pastedPoints)
        self.assertFalse(self.window._shapeClipboardIsCut)

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual([], self.window.canvas.shapes)
        self.assertTrue(self.window.undoLastOperation())
        restoredPoints = [
            (point.x(), point.y())
            for point in self.window.canvas.shapes[0].points]
        self.assertEqual(originalPoints, restoredPoints)

    def test_undo_restores_a_changed_class(self):
        shape = make_shape('person', 10, 20, 50, 70)
        self.add_and_select(shape)

        self.window.ShapeItemDict[shape].setText('SafeHat')
        self.assertEqual('SafeHat', shape.label)
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual('person', self.window.canvas.shapes[0].label)

    def test_undo_restores_background_state(self):
        self.window.setClean()
        self.window.resetUndoHistory()
        self.window.labelAsBackground()
        self.assertTrue(self.window.back_sample)

        self.assertTrue(self.window.undoLastOperation())
        self.assertFalse(self.window.back_sample)

    def test_single_model_overwrite_becomes_one_undo_step(self):
        original = make_shape('person', 10, 10, 40, 50)
        self.add_and_select(original)
        self.window.prepareSingleAutoAnnotationUndo()
        self.assertFalse(self.window.actions.undo.isEnabled())

        modelResult = make_shape('SafeHat', 80, 20, 120, 60)
        self.window.resetUndoHistory()  # Simulate the completion reload.
        self.replace_shapes(modelResult)
        self.assertTrue(self.window.restoreSingleAutoAnnotationUndo())

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(
            ['person'],
            [shape.label for shape in self.window.canvas.shapes])

    def test_single_model_append_undo_removes_only_model_result(self):
        original = make_shape('person', 10, 10, 40, 50)
        self.add_and_select(original)
        self.window.prepareSingleAutoAnnotationUndo()

        kept = make_shape('person', 10, 10, 40, 50)
        modelResult = make_shape('SafeHat', 80, 20, 120, 60)
        self.window.resetUndoHistory()
        self.replace_shapes(kept, modelResult)
        self.assertTrue(self.window.restoreSingleAutoAnnotationUndo())

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(
            ['person'],
            [shape.label for shape in self.window.canvas.shapes])

    def test_failed_single_model_run_preserves_earlier_undo_history(self):
        shape = make_shape('person', 10, 20, 50, 70)
        self.add_and_select(shape)
        self.window.canvas.moveOnePixel('Right')
        self.assertEqual(1, len(self.window._undoStack))
        self.window.prepareSingleAutoAnnotationUndo()

        self.window.resetUndoHistory()  # Simulate a format-change reload.
        self.assertFalse(self.window.restoreSingleAutoAnnotationUndo())
        self.assertEqual(1, len(self.window._undoStack))
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(10.0, self.window.canvas.shapes[0].points[0].x())

    def test_repeated_undo_walks_back_multiple_operations(self):
        shape = make_shape('person', 30, 30, 70, 90)
        self.add_and_select(shape)
        self.window.copyShapeToClipboard()
        self.window.pasteShapeFromClipboard()
        self.window.pasteShapeFromClipboard()
        self.assertEqual(3, len(self.window.canvas.shapes))

        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(2, len(self.window.canvas.shapes))
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(1, len(self.window.canvas.shapes))
        self.assertFalse(self.window.actions.undo.isEnabled())


if __name__ == '__main__':
    unittest.main()

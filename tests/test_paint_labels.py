#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import labelImg
from libs.shape import Shape


class MemorySettings(object):
    data = {}

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


class RecordingPainter(object):
    def __init__(self):
        self.texts = []
        self.positions = []

    def setPen(self, *_args):
        pass

    def drawPath(self, *_args):
        pass

    def setFont(self, *_args):
        pass

    def drawText(self, x, y, text):
        self.texts.append(text)
        self.positions.append((x, y))


def make_shape():
    shape = Shape(label='person', paintLabel=True)
    for x, y in ((10, 10), (80, 10), (80, 60), (10, 60)):
        shape.addPoint(QPointF(x, y))
    shape.isRotated = False
    shape.close()
    return shape


class PaintLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_painted_text_contains_class_name_and_optional_extra_info(self):
        shape = make_shape()
        painter = RecordingPainter()
        shape.paint(painter)
        self.assertEqual(['person'], painter.texts)

        shape.extra_label = 'review'
        painter = RecordingPainter()
        shape.paint(painter)
        self.assertEqual(['person (review)'], painter.texts)

        shape.paintLabel = False
        painter = RecordingPainter()
        shape.paint(painter)
        self.assertEqual([], painter.texts)

    def test_label_at_top_edge_stays_inside_canvas(self):
        shape = Shape(label='person', paintLabel=True)
        for x, y in ((10, 0), (80, 0), (80, 60), (10, 60)):
            shape.addPoint(QPointF(x, y))
        shape.isRotated = False
        shape.close()
        painter = RecordingPainter()
        shape.paint(painter)
        self.assertEqual(['person'], painter.texts)
        self.assertGreater(painter.positions[0][1], 0)

    def test_ctrl_shift_l_toggles_label_painting(self):
        original_settings = labelImg.Settings
        MemorySettings.data.clear()
        labelImg.Settings = MemorySettings
        window = None
        try:
            window = labelImg.MainWindow()
            shape = make_shape()
            shape.paintLabel = False
            window.canvas.shapes.append(shape)
            window.show()
            window.activateWindow()
            QApplication.setActiveWindow(window)
            window.canvas.setFocus()
            update_calls = []
            original_update = window.canvas.update

            def track_update(*args):
                update_calls.append(True)
                original_update(*args)

            window.canvas.update = track_update

            QTest.keyClick(window.canvas, Qt.Key_L,
                           Qt.ControlModifier | Qt.ShiftModifier)
            QApplication.processEvents()
            self.assertTrue(window.paintLabelsOption.isChecked())
            self.assertTrue(shape.paintLabel)
            self.assertEqual(1, len(update_calls))

            QTest.keyClick(window.canvas, Qt.Key_L,
                           Qt.ControlModifier | Qt.ShiftModifier)
            QApplication.processEvents()
            self.assertFalse(window.paintLabelsOption.isChecked())
            self.assertFalse(shape.paintLabel)
            self.assertEqual(2, len(update_calls))
        finally:
            if window is not None:
                window.setClean()
                window.close()
            labelImg.Settings = original_settings

    def test_ctrl_shift_l_toggles_only_selected_box_label(self):
        original_settings = labelImg.Settings
        MemorySettings.data.clear()
        labelImg.Settings = MemorySettings
        window = None
        try:
            window = labelImg.MainWindow()
            first = make_shape()
            second = make_shape()
            first.paintLabel = False
            second.paintLabel = False
            window.canvas.shapes.extend((first, second))
            window.addLabel(first)
            window.addLabel(second)
            window.canvas.selectShape(first)
            window.show()
            window.activateWindow()
            QApplication.setActiveWindow(window)
            window.canvas.setFocus()
            QTest.qWait(10)

            QTest.keyClick(window.canvas, Qt.Key_L,
                           Qt.ControlModifier | Qt.ShiftModifier)
            QApplication.processEvents()

            self.assertTrue(first.paintLabel)
            self.assertFalse(second.paintLabel)
            self.assertFalse(window.paintLabelsOption.isChecked())
        finally:
            if window is not None:
                window.setClean()
                window.close()
            labelImg.Settings = original_settings

    def test_r_hides_selected_box_and_all_boxes_without_selection(self):
        original_settings = labelImg.Settings
        MemorySettings.data.clear()
        labelImg.Settings = MemorySettings
        window = None
        try:
            window = labelImg.MainWindow()
            first = make_shape()
            second = make_shape()
            window.canvas.shapes.extend((first, second))
            window.addLabel(first)
            window.addLabel(second)
            window.canvas.selectShape(first)
            window.show()
            window.activateWindow()
            QApplication.setActiveWindow(window)
            window.canvas.setFocus()
            QTest.qWait(10)

            QTest.keyClick(window.canvas, Qt.Key_R)
            QApplication.processEvents()
            self.assertFalse(window.canvas.isVisible(first))
            self.assertTrue(window.canvas.isVisible(second))
            self.assertFalse(window.labelList.verticalHeader().isChecked[0])

            window.canvas.deSelectShape()
            QTest.keyClick(window.canvas, Qt.Key_R)
            QApplication.processEvents()
            self.assertFalse(window.canvas.isVisible(first))
            self.assertFalse(window.canvas.isVisible(second))
            QTest.keyClick(window.canvas, Qt.Key_R)
            QApplication.processEvents()
            self.assertTrue(window.canvas.isVisible(first))
            self.assertTrue(window.canvas.isVisible(second))
        finally:
            if window is not None:
                window.setClean()
                window.close()
            labelImg.Settings = original_settings


if __name__ == '__main__':
    unittest.main()

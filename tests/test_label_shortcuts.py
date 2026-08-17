#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import labelImg
from libs.constants import SETTING_LABEL_SHORTCUTS
from libs.labelShortcutDialog import (LabelShortcutValidationError,
                                      validate_label_shortcuts)
from libs.shape import Shape


class MemorySettings(object):
    data_store = {}

    def __init__(self):
        self.data = self.data_store

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


def make_shape():
    shape = Shape()
    for point in ((10, 10), (80, 10), (80, 60), (10, 60)):
        shape.addPoint(QPointF(*point))
    shape.line_color = QColor(0, 255, 0)
    shape.fill_color = QColor(255, 0, 0, 128)
    shape.isRotated = True
    shape.close()
    return shape


class LabelShortcutValidationTests(unittest.TestCase):
    def test_multiple_mappings_are_normalized(self):
        mappings = validate_label_shortcuts(
            [{'shortcut': '1', 'label': 'SafeHat'},
             {'shortcut': 'Shift+2', 'label': 'person'}],
            ['SafeHat', 'person'])

        self.assertEqual(
            [{'shortcut': '1', 'label': 'SafeHat'},
             {'shortcut': 'Shift+2', 'label': 'person'}],
            mappings)

    def test_label_must_come_from_predefined_classes(self):
        with self.assertRaises(LabelShortcutValidationError):
            validate_label_shortcuts(
                [{'shortcut': '1', 'label': 'temporary_label'}],
                ['SafeHat'])

    def test_duplicate_and_reserved_shortcuts_are_rejected(self):
        with self.assertRaises(LabelShortcutValidationError):
            validate_label_shortcuts(
                [{'shortcut': '1', 'label': 'SafeHat'},
                 {'shortcut': '1', 'label': 'person'}],
                ['SafeHat', 'person'])
        with self.assertRaises(LabelShortcutValidationError):
            validate_label_shortcuts(
                [{'shortcut': 'E', 'label': 'SafeHat'}],
                ['SafeHat'], {'E': 'OBB drawing'})

    def test_multi_step_key_sequences_are_rejected(self):
        with self.assertRaises(LabelShortcutValidationError):
            validate_label_shortcuts(
                [{'shortcut': 'Ctrl+K, Ctrl+S', 'label': 'SafeHat'}],
                ['SafeHat'])


class LabelShortcutWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        MemorySettings.data_store.clear()
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        self.classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = self.createWindow()

    def createWindow(self):
        window = labelImg.MainWindow(
            defaultPrefdefClassFile=self.classesPath)
        window.filePath = os.path.abspath('label-shortcut-test.jpg')
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(255, 255, 255))
        window.canvas.loadPixmap(pixmap)
        window.resetUndoHistory()
        return window

    def tearDown(self):
        if self.window is not None:
            self.window.setClean()
            self.window.close()
        labelImg.Settings = self.originalSettings

    def test_settings_button_is_in_box_labels_panel(self):
        layout = self.window.dock.widget().layout()
        self.assertGreaterEqual(
            layout.indexOf(self.window.labelShortcutSettingsButton), 0)
        self.assertLess(
            layout.indexOf(self.window.labelShortcutSettingsButton),
            layout.indexOf(self.window.labelList))

    def test_shortcut_selects_label_and_enters_obb_drawing(self):
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': 'SafeHat'}])

        self.window.show()
        self.window.activateWindow()
        QApplication.setActiveWindow(self.window)
        self.window.canvas.setFocus()
        QTest.qWait(10)
        QTest.keyClick(self.window.canvas, ord('1'))
        QApplication.processEvents()

        self.assertEqual('SafeHat', self.window.default_label)
        self.assertEqual('SafeHat', self.window._pendingLabelShortcut)
        self.assertTrue(self.window.canvas.drawing())
        self.assertTrue(self.window.canvas.canDrawRotatedRect)

    def test_existing_and_direct_shortcuts_cannot_be_overridden(self):
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': 'SafeHat'}])

        with self.assertRaises(LabelShortcutValidationError):
            self.window.setLabelShortcutMappings(
                [{'shortcut': 'E', 'label': 'SafeHat'}])
        with self.assertRaises(LabelShortcutValidationError):
            self.window.setLabelShortcutMappings(
                [{'shortcut': 'Z', 'label': 'SafeHat'}])

        self.assertEqual(
            [{'shortcut': '1', 'label': 'SafeHat'}],
            self.window.labelShortcutMappings)

    def test_dynamic_annotation_label_is_not_an_allowed_target(self):
        self.window.labelHist.append('temporary_label')

        with self.assertRaises(LabelShortcutValidationError):
            self.window.setLabelShortcutMappings(
                [{'shortcut': '1', 'label': 'temporary_label'}])

    def test_mappings_persist_and_reload(self):
        expected = [
            {'shortcut': '1', 'label': 'SafeHat'},
            {'shortcut': '2', 'label': 'person'},
        ]
        self.window.setLabelShortcutMappings(expected)
        self.assertEqual(
            expected, MemorySettings.data_store[SETTING_LABEL_SHORTCUTS])

        self.window.setClean()
        self.window.close()
        self.window = self.createWindow()

        self.assertEqual(expected, self.window.labelShortcutMappings)
        self.assertEqual(2, len(self.window.labelShortcutActions))

    def test_shortcuts_are_disabled_while_label_editor_is_active(self):
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': 'SafeHat'}])
        action = self.window.labelShortcutActions[0]

        self.window.setLabelEditorActive(True)
        self.assertFalse(action.isEnabled())
        self.window.setLabelEditorActive(False)
        self.assertTrue(action.isEnabled())

    def test_shortcut_box_skips_picker_but_normal_box_opens_it(self):
        editCalls = []
        originalEdit = self.window.labelList.edit
        self.window.labelList.edit = lambda index: editCalls.append(index)
        try:
            self.window.setLabelShortcutMappings(
                [{'shortcut': '1', 'label': 'SafeHat'}])
            self.window.labelShortcutActions[0].trigger()
            first = make_shape()
            self.window.canvas.shapes.append(first)
            self.window.newShape(False)

            self.assertEqual('SafeHat', first.label)
            self.assertEqual([], editCalls)
            self.assertIsNone(self.window._pendingLabelShortcut)

            second = make_shape()
            self.window.canvas.shapes.append(second)
            self.window.newShape(False)
            self.assertEqual(1, len(editCalls))
        finally:
            self.window.labelList.edit = originalEdit

    def test_cancel_clears_pending_shortcut_label(self):
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': 'SafeHat'}])
        self.window.labelShortcutActions[0].trigger()

        self.window.createCancel()

        self.assertIsNone(self.window._pendingLabelShortcut)
        self.assertTrue(self.window.canvas.editing())


if __name__ == '__main__':
    unittest.main()

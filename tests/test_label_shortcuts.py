#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QToolButton

import labelImg
from libs.constants import SETTING_LABEL_SHORTCUTS
from libs.labelShortcutDialog import (LabelShortcutValidationError,
                                      validate_label_shortcuts)
from libs.labelView import CCommonOrderComboBox
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
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.txt',
                delete=False) as classFile:
            classFile.write('SafeHat\nperson\nexcavator\n')
            self.classesPath = classFile.name
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
        if os.path.isfile(self.classesPath):
            os.remove(self.classesPath)
        labelImg.Settings = self.originalSettings

    def test_shortcut_settings_moved_to_settings_menu(self):
        self.assertIn(
            self.window.labelShortcutSettingsAction,
            self.window.menus.settings.actions())
        self.assertFalse(any(
            button.objectName() == 'labelShortcutSettingsButton'
            for button in self.window.dock.widget().findChildren(QToolButton)))
        self.assertIn(
            self.window.menus.annotationFormat.menuAction(),
            self.window.menus.settings.actions())
        self.assertNotIn(
            self.window.menus.annotationFormat.menuAction(),
            self.window.menus.file.actions())

    def test_settings_language_choices_are_applied_and_persisted(self):
        originalClasses = list(self.window.predefinedClasses)
        self.assertTrue(self.window.setLanguage('ja'))
        self.assertIn('設定', self.window.menus.settings.menuAction().text())
        self.assertIn('形式', self.window.menus.annotationFormat.menuAction().text())
        self.assertEqual('ja', MemorySettings.data_store['language'])
        self.assertEqual(originalClasses, list(self.window.predefinedClasses))

        self.assertTrue(self.window.setLanguage('ar'))
        self.assertEqual(Qt.RightToLeft, self.window.layoutDirection())
        self.window.setLanguage('zh')

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

    def test_e_uses_toolbar_box_type_and_toggles_drawing(self):
        self.window.toggleActions(True)
        self.window.show()
        self.window.activateWindow()
        QApplication.setActiveWindow(self.window)
        self.window.canvas.setFocus()

        self.assertEqual('obb', self.window.boxTypeComboBox.currentData())
        QTest.keyClick(self.window.canvas, Qt.Key_E)
        self.assertTrue(self.window.canvas.drawing())
        self.assertTrue(self.window.canvas.canDrawRotatedRect)
        QTest.keyClick(self.window.canvas, Qt.Key_E)
        self.assertTrue(self.window.canvas.editing())

        self.window.boxTypeComboBox.setCurrentIndex(0)
        self.window.canvas.setFocus()
        QTest.keyClick(self.window.canvas, Qt.Key_E)
        self.assertTrue(self.window.canvas.drawing())
        self.assertFalse(self.window.canvas.canDrawRotatedRect)
        self.window.canvas.current = Shape()
        self.window.canvas.line.points = [QPointF(10, 10)]
        QTest.keyClick(self.window.canvas, Qt.Key_E)
        self.assertTrue(self.window.canvas.editing())
        self.assertIsNone(self.window.canvas.current)
        self.assertEqual([], self.window.canvas.line.points)

    def test_toolbar_draw_buttons_still_start_their_own_box_type(self):
        self.window.toggleActions(True)
        self.assertIn(
            self.window.actions.boxTypeControl,
            self.window.editTools.actions())
        self.window.actions.create.trigger()
        self.assertTrue(self.window.canvas.drawing())
        self.assertFalse(self.window.canvas.canDrawRotatedRect)
        self.assertEqual('rect', self.window.boxTypeComboBox.currentData())

        self.window.actions.drawSelectedBox.trigger()
        self.window.actions.createRo.trigger()
        self.assertTrue(self.window.canvas.drawing())
        self.assertTrue(self.window.canvas.canDrawRotatedRect)
        self.assertEqual('obb', self.window.boxTypeComboBox.currentData())

    def test_e_starts_selected_type_when_toolbar_selector_has_focus(self):
        self.window.toggleActions(True)
        self.window.show()
        self.window.activateWindow()
        QApplication.setActiveWindow(self.window)
        self.window.boxTypeComboBox.setCurrentIndex(0)
        self.window.boxTypeComboBox.setFocus()

        QTest.keyClick(self.window.boxTypeComboBox, Qt.Key_E)

        self.assertTrue(self.window.canvas.drawing())
        self.assertFalse(self.window.canvas.canDrawRotatedRect)

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

    def test_e_selects_class_in_editor_without_starting_drawing(self):
        action = self.window.actions.drawSelectedBox
        action.setEnabled(True)
        editor = CCommonOrderComboBox(self.window)
        editor.addItems(self.window.labelHist)
        expected = next(
            label for label in self.window.labelHist
            if label.casefold().startswith('e'))

        self.window.show()
        self.window.activateWindow()
        QApplication.setActiveWindow(self.window)
        editor.show()
        editor.setFocus()
        try:
            self.window.setLabelEditorActive(True)
            self.assertFalse(action.isEnabled())
            self.assertTrue(self.window.canvas.editing())

            QTest.keyClick(editor, Qt.Key_E)
            QApplication.processEvents()

            self.assertEqual(expected, editor.currentText())
            self.assertTrue(self.window.canvas.editing())
        finally:
            self.window.setLabelEditorActive(False)
            editor.deleteLater()

        self.assertTrue(action.isEnabled())

    def test_chinese_class_can_be_selected_by_full_pinyin(self):
        editor = CCommonOrderComboBox(self.window)
        editor.addItems([u'苹果', u'火龙果', u'黄瓜'])
        editor.show()
        editor.setFocus()
        try:
            QTest.keyClicks(editor, 'huolongguo')
            self.assertEqual(u'火龙果', editor.currentText())
        finally:
            editor.deleteLater()

    def test_chinese_class_can_be_selected_by_pinyin_initials(self):
        editor = CCommonOrderComboBox(self.window)
        editor.addItems([u'苹果', u'火龙果', u'黄瓜'])
        editor.show()
        editor.setFocus()
        try:
            QTest.keyClicks(editor, 'hlg')
            self.assertEqual(u'火龙果', editor.currentText())
        finally:
            editor.deleteLater()

    def test_same_pinyin_initial_keeps_common_usage_order(self):
        self.window.labelHist = [u'火龙果', u'黄瓜', u'葡萄']
        self.window.labelUsage = {
            u'火龙果': {'count': 1, 'last': 1},
            u'黄瓜': {'count': 4, 'last': 4},
            u'葡萄': {'count': 2, 'last': 2},
        }

        self.assertEqual(
            [u'黄瓜', u'火龙果', u'葡萄'],
            self.window.labelSelectionOrder())

    def test_editor_shortcut_changes_class_without_starting_drawing(self):
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': 'SafeHat'}])
        shape = make_shape()
        shape.label = 'person'
        self.window.canvas.shapes.append(shape)
        self.window.addLabel(shape)
        index = self.window.labelModel.index(0, 0)

        self.window.show()
        self.window.labelList.setCurrentIndex(index)
        self.window.labelList.edit(index)
        QApplication.processEvents()
        editor = self.window.labelList.findChild(CCommonOrderComboBox)
        self.assertIsNotNone(editor)
        self.assertTrue(self.window._labelEditorActive)

        QTest.keyClick(editor, Qt.Key_1)
        QApplication.processEvents()

        self.assertEqual('SafeHat', shape.label)
        self.assertTrue(self.window.canvas.editing())
        self.assertIsNone(self.window._pendingLabelShortcut)
        self.assertFalse(self.window.labelShortcutActions[0].isEnabled())

    def test_shortcut_widgets_do_not_accept_ime_composition(self):
        editor = CCommonOrderComboBox(self.window)
        try:
            self.assertFalse(editor.testAttribute(Qt.WA_InputMethodEnabled))
            self.assertFalse(self.window.canvas.testAttribute(
                Qt.WA_InputMethodEnabled))
            self.assertFalse(self.window.fileListView.testAttribute(
                Qt.WA_InputMethodEnabled))
        finally:
            editor.deleteLater()

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

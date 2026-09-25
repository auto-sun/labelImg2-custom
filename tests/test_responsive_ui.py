#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication, QFileDialog

import labelImg
from libs.labelShortcutDialog import LabelShortcutDialog
from libs.ui_geometry import (available_screen_geometry,
                              responsive_dialog_size)


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


class ResponsiveUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.class_file = os.path.join(self.temp.name, 'classes.txt')
        with open(self.class_file, 'w', encoding='utf-8') as stream:
            stream.write('person\nSafeHat\n')
        self.settings_patch = mock.patch.object(labelImg, 'Settings',
                                                MemorySettings)
        self.settings_patch.start()
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=self.class_file)

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        self.settings_patch.stop()
        self.temp.cleanup()

    def test_dialog_size_adapts_to_common_screen_sizes(self):
        self.assertEqual(QSize(980, 700), responsive_dialog_size(
            QSize(1920, 1080)))
        self.assertEqual(QSize(980, 599), responsive_dialog_size(
            QSize(1366, 768)))
        self.assertEqual(QSize(720, 540), responsive_dialog_size(
            QSize(800, 600)))
        self.assertEqual(QSize(592, 432), responsive_dialog_size(
            QSize(640, 480)))
        self.assertEqual(QSize(720, 464), responsive_dialog_size(
            QSize(911, 512)))
        self.assertEqual(QSize(252, 252), responsive_dialog_size(
            QSize(300, 300)))

    def test_shortcut_dialog_is_roomy_and_rows_fit_editors(self):
        dialog = LabelShortcutDialog(
            [{'shortcut': '1', 'label': 'SafeHat'}],
            ['person', 'SafeHat'], parent=self.window)
        available = available_screen_geometry(dialog)
        self.assertGreaterEqual(dialog.width(), min(700, available.width() - 48))
        self.assertLessEqual(dialog.width(), available.width())
        self.assertLessEqual(dialog.height(), available.height())
        editor = dialog.table.cellWidget(0, 0)
        self.assertGreaterEqual(
            dialog.table.rowHeight(0), editor.sizeHint().height() + 8)
        dialog.close()

    def test_toolbar_controls_fit_text_and_wrap_on_narrow_windows(self):
        self.window.show()
        self.window.resize(700, 520)
        QApplication.processEvents()
        self.window.updateToolbarLayout()
        self.assertTrue(self.window.toolBarBreak(self.window.editTools))
        self.assertGreaterEqual(self.window.boxTypeComboBox.width(),
                                self.window.boxTypeComboBox.sizeHint().width())
        self.assertGreaterEqual(
            self.window.autoAnnotationConfidenceSpinBox.width(),
            self.window.autoAnnotationConfidenceSpinBox.sizeHint().width())

        self.window.resize(1900, 900)
        QApplication.processEvents()
        self.window.updateToolbarLayout()
        self.assertFalse(self.window.toolBarBreak(self.window.editTools))

    def test_all_directory_pickers_allow_native_windows_dialog(self):
        with mock.patch.object(QFileDialog, 'getExistingDirectory',
                               return_value='') as picker:
            self.window.openAnnotationDirDialog()
            options = picker.call_args.args[3]
            self.assertFalse(options & QFileDialog.DontUseNativeDialog)

        with mock.patch.object(QFileDialog, 'getExistingDirectory',
                               return_value='') as picker:
            self.window.openDirDialog()
            options = picker.call_args.args[3]
            self.assertFalse(options & QFileDialog.DontUseNativeDialog)

        self.window.defaultSaveDir = None
        with mock.patch.object(QFileDialog, 'getExistingDirectory',
                               return_value='') as picker:
            self.window.ensureSingleAutoAnnotationSaveDir()
            options = picker.call_args.args[3]
            self.assertFalse(options & QFileDialog.DontUseNativeDialog)


if __name__ == '__main__':
    unittest.main()

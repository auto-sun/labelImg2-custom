#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QFileDialog

import labelImg
from libs.classFileDialog import (ClassFileDialog, ClassFileError,
                                  read_class_file)
from libs.constants import (SETTING_CLASS_FILE,
                            SETTING_CLASS_FILE_HISTORY,
                            SETTING_LABEL_SHORTCUTS)
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


class ClassFileParserTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary.cleanup()

    def writeClasses(self, name, content, encoding='utf-8'):
        path = os.path.join(self.temporary.name, name)
        with open(path, 'w', encoding=encoding) as stream:
            stream.write(content)
        return path

    def test_reads_utf8_bom_and_preserves_internal_spaces(self):
        path = self.writeClasses(
            'class.txt', '\ufeff person \nNo SafeHat\n\npipe row\n')
        self.assertEqual(
            ['person', 'No SafeHat', 'pipe row'], read_class_file(path))

    def test_rejects_duplicate_and_empty_class_files(self):
        duplicate = self.writeClasses('duplicate.txt', 'person\nperson\n')
        empty = self.writeClasses('empty.txt', '\n  \n')
        with self.assertRaises(ClassFileError):
            read_class_file(duplicate)
        with self.assertRaises(ClassFileError):
            read_class_file(empty)


class ClassFileWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        MemorySettings.data_store.clear()
        self.bundledPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.customPath = self.writeClasses(
            'project_classes.txt', 'apple\nname melon\noranges_\n')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=self.bundledPath)

    def tearDown(self):
        if self.window is not None:
            self.window.setClean()
            self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def writeClasses(self, name, content):
        path = os.path.join(self.temporary.name, name)
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(content)
        return path

    def test_file_menu_and_box_labels_have_entry_points(self):
        self.assertEqual(
            u'选择类别文件...',
            self.window.actions.selectClassFile.text().replace('&', ''))
        layout = self.window.dock.widget().layout()
        self.assertGreaterEqual(
            layout.indexOf(self.window.classFileButton), 0)
        self.assertLess(
            layout.indexOf(self.window.classFileButton),
            layout.indexOf(self.window.labelList))

    def test_dialog_previews_ids_names_and_history(self):
        dialog = ClassFileDialog(
            self.customPath, [self.bundledPath], self.window)
        self.assertEqual(2, dialog.historyCombo.count())
        self.assertEqual(3, dialog.previewTable.rowCount())
        self.assertEqual('0', dialog.previewTable.item(0, 0).text())
        self.assertEqual('name melon', dialog.previewTable.item(1, 1).text())
        self.assertTrue(dialog.applyButton.isEnabled())
        dialog.close()

    def test_browse_picker_uses_native_file_manager_with_txt_filter(self):
        dialog = ClassFileDialog(
            self.customPath, [self.bundledPath], self.window)
        picker = dialog.createBrowseDialog(self.temporary.name)
        self.assertFalse(picker.testOption(QFileDialog.DontUseNativeDialog))
        if hasattr(QFileDialog, 'DontUseCustomDirectoryIcons'):
            self.assertTrue(picker.testOption(
                QFileDialog.DontUseCustomDirectoryIcons))
        self.assertEqual(QFileDialog.List, picker.viewMode())
        self.assertEqual(QFileDialog.ExistingFile, picker.fileMode())
        self.assertEqual([u'类别文件 (*.txt)'], picker.nameFilters())
        picker.close()
        dialog.close()

    def test_apply_updates_classes_history_default_and_shortcuts(self):
        oldLabel = self.window.predefinedClasses[0]
        self.window.setLabelShortcutMappings(
            [{'shortcut': '1', 'label': oldLabel}])
        self.window.default_label = oldLabel

        removed = self.window.applyClassFile(self.customPath)

        self.assertEqual(1, removed)
        self.assertEqual(
            ('apple', 'name melon', 'oranges_'),
            self.window.predefinedClasses)
        self.assertEqual('apple', self.window.default_label)
        self.assertEqual([], self.window.labelShortcutMappings)
        self.assertEqual(
            os.path.abspath(self.customPath),
            MemorySettings.data_store[SETTING_CLASS_FILE])
        self.assertEqual(
            os.path.abspath(self.customPath),
            MemorySettings.data_store[SETTING_CLASS_FILE_HISTORY][0])
        self.assertEqual(
            [], MemorySettings.data_store[SETTING_LABEL_SHORTCUTS])
        self.assertIn('project_classes.txt', self.window.classFileButton.text())

    def test_switching_preserves_existing_unknown_box_and_clean_state(self):
        legacy = Shape(label='legacy_only')
        self.window.canvas.shapes = [legacy]
        self.window.dirty = False

        self.window.applyClassFile(self.customPath)

        self.assertIn('legacy_only', self.window.labelHist)
        self.assertNotIn('legacy_only', self.window.predefinedClasses)
        self.assertIs(legacy, self.window.canvas.shapes[0])
        self.assertFalse(self.window.dirty)

    def test_switching_class_file_does_not_rescan_image_list(self):
        with mock.patch.object(
                self.window.fileModel, 'setStringList') as rebuild, \
                mock.patch.object(
                    self.window.fileModel, 'parseOne') as parse_annotation:
            self.window.applyClassFile(self.customPath)
        rebuild.assert_not_called()
        parse_annotation.assert_not_called()

    def test_saved_selection_is_restored_on_next_window(self):
        self.window.setClean()
        self.window.close()
        MemorySettings.data_store[SETTING_CLASS_FILE] = self.customPath
        MemorySettings.data_store[SETTING_CLASS_FILE_HISTORY] = [
            self.customPath, self.bundledPath]

        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=self.bundledPath)

        self.assertEqual(
            os.path.abspath(self.customPath), self.window.classFilePath)
        self.assertEqual(
            ('apple', 'name melon', 'oranges_'),
            self.window.predefinedClasses)

    def test_missing_saved_file_falls_back_to_bundled_classes(self):
        self.window.setClean()
        self.window.close()
        MemorySettings.data_store[SETTING_CLASS_FILE] = os.path.join(
            self.temporary.name, 'missing.txt')

        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=self.bundledPath)

        self.assertEqual(
            os.path.abspath(self.bundledPath), self.window.classFilePath)
        self.assertGreater(len(self.window.predefinedClasses), 0)


if __name__ == '__main__':
    unittest.main()

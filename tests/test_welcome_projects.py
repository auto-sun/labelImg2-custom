import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

import labelImg
from libs.constants import SETTING_FILENAME, SETTING_LAST_OPEN_DIR, SETTING_SAVE_DIR
from test_delete_image import MemorySettings


class WelcomeProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.images = os.path.join(self.temp.name, 'images')
        os.mkdir(self.images)
        self.image = os.path.join(self.images, 'one.png')
        image = QImage(100, 80, QImage.Format_RGB32)
        image.fill(Qt.white)
        self.assertTrue(image.save(self.image))
        self.settings = MemorySettings()
        self.settings['autoCheckUpdates'] = False

    def newWindow(self):
        with patch.object(labelImg, 'Settings', return_value=self.settings):
            window = labelImg.MainWindow()
        self.addCleanup(window.close)
        return window

    def test_welcome_folder_entry_opens_both_native_pickers_then_loads(self):
        window = self.newWindow()
        labels = os.path.join(self.temp.name, 'annotations')
        os.mkdir(labels)
        self.assertIs(window.workspace.currentWidget(), window.welcomePage)
        self.assertEqual(0, window.welcomePage.recent.count())
        with patch.object(QFileDialog, 'getExistingDirectory',
                          side_effect=[self.images, labels]) as picker:
            window.welcomePage.openFolder.click()
        self.assertEqual(2, picker.call_count)
        self.assertEqual(self.temp.name, picker.call_args.args[2])
        self.assertEqual(labels, window.annotationBindings[self.images])
        self.assertEqual(self.image, window.filePath)
        self.assertIs(window.workspace.currentWidget(), window.scrollArea)
        window.closeFile()
        self.assertIs(window.workspace.currentWidget(), window.welcomePage)
        self.assertEqual(self.images, window.welcomePage.recent.item(0).data(Qt.UserRole))

    def test_two_detected_label_folders_are_direct_choices(self):
        window = self.newWindow()
        for name in ('labels', 'label'):
            os.mkdir(os.path.join(self.temp.name, name))

        def choose_singular(prompt):
            choices = {button.text(): button for button in prompt.buttons()}
            self.assertIn('labels', choices)
            choices['label'].click()
            return 0

        with patch.object(QMessageBox, 'exec_', choose_singular), patch.object(
                QFileDialog, 'getExistingDirectory') as picker:
            window.openImageProject(self.images)
        picker.assert_not_called()
        self.assertEqual(os.path.join(self.temp.name, 'label'), window.defaultSaveDir)
        self.assertEqual(self.image, window.filePath)

    def test_cancel_label_choice_keeps_the_open_image_and_binding(self):
        window = self.newWindow()
        window.importDirImages(self.images)
        other = os.path.join(self.temp.name, 'other-images')
        os.mkdir(other)
        with patch.object(QFileDialog, 'getExistingDirectory',
                          side_effect=[other, '']):
            window.openDirDialog()
        self.assertEqual(self.images, window.dirname)
        self.assertEqual(self.image, window.filePath)
        self.assertNotIn(other, window.annotationBindings)

    def test_startup_resumes_previous_project_without_picker(self):
        labels = os.path.join(self.temp.name, 'labels')
        os.mkdir(labels)
        self.settings[SETTING_LAST_OPEN_DIR] = self.images
        self.settings[SETTING_SAVE_DIR] = labels
        self.settings[SETTING_FILENAME] = self.image
        with patch.object(QFileDialog, 'getExistingDirectory') as picker, patch.object(
                QMessageBox, 'exec_') as prompt:
            window = self.newWindow()
            self.app.processEvents()
        picker.assert_not_called()
        prompt.assert_not_called()
        self.assertEqual(self.image, window.filePath)
        self.assertEqual(labels, window.defaultSaveDir)
        self.assertIs(window.workspace.currentWidget(), window.scrollArea)

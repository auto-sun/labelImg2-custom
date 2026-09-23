#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

from libs import settings as settings_module
from libs.lib import newIcon


class PackagingPathsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_frozen_settings_are_writable_under_user_appdata(self):
        with tempfile.TemporaryDirectory() as roaming_dir:
            with mock.patch.object(sys, 'frozen', True, create=True), \
                    mock.patch.dict(os.environ, {'APPDATA': roaming_dir}):
                settings = settings_module.Settings()
                self.assertEqual(
                    os.path.join(roaming_dir, 'LabelImg2Custom',
                                 'labelImg2Settings3.pkl'), settings.path)
                settings['selected_class'] = 'SafeHat'
                self.assertTrue(settings.save())
                restored = settings_module.Settings()
                self.assertTrue(restored.load())
                self.assertEqual('SafeHat', restored['selected_class'])

    def test_icon_loading_does_not_depend_on_current_directory(self):
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory() as unrelated_dir:
            try:
                os.chdir(unrelated_dir)
                icon = newIcon('tag-black-shape.svg')
                self.assertFalse(icon.pixmap(32, 32).isNull())
            finally:
                os.chdir(original_dir)


if __name__ == '__main__':
    unittest.main()

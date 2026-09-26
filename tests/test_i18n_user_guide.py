# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget

from libs.i18n import LANGUAGES, LanguageManager, translate
from libs.userGuide import UserGuideDialog


class I18nAndGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_seven_supported_languages_have_localized_settings(self):
        self.assertEqual(
            {'en', 'zh', 'ja', 'es', 'ar', 'fr', 'ko'}, set(LANGUAGES))
        for language in LANGUAGES:
            expected = 'Settings' if language == 'en' else None
            translated = translate('Settings', language)
            if expected:
                self.assertEqual(expected, translated)
            else:
                self.assertNotEqual('Settings', translated)

    def test_arabic_uses_right_to_left_direction(self):
        widget = QWidget()
        manager = LanguageManager(widget, 'ar')
        manager.apply()
        self.assertEqual(Qt.RightToLeft, widget.layoutDirection())
        manager.apply('fr')
        self.assertEqual(Qt.LeftToRight, widget.layoutDirection())
        widget.close()

    def test_guide_orders_shortcuts_before_basic_and_advanced_sections(self):
        dialog = UserGuideDialog('zh')
        browser = dialog.findChild(__import__(
            'PyQt5.QtWidgets', fromlist=['QTextBrowser']).QTextBrowser)
        html = browser.toHtml()
        self.assertLess(html.index('快捷键'), html.index('基础使用'))
        self.assertLess(html.index('基础使用'), html.index('进阶使用'))
        dialog.close()


if __name__ == '__main__':
    unittest.main()

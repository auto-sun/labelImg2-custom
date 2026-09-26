# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDoubleSpinBox, QWidget

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

    def test_confidence_prefix_and_model_tooltip_follow_selected_language(self):
        root = QWidget()
        confidence = QDoubleSpinBox(root)
        confidence.setObjectName('autoAnnotationConfidenceSpinBox')
        confidence.setPrefix('置信度 ')
        confidence.setToolTip(
            '模型置信度阈值（0.01–1.00）；数值越高，保留的预测框通常越少。')
        manager = LanguageManager(root, 'fr')

        manager.apply()

        self.assertEqual('Confiance ', confidence.prefix())
        self.assertIn('Seuil de confiance', confidence.toolTip())
        self.assertEqual(
            'Annoter l’image actuelle avec un modèle YOLO / YOLO OBB local',
            translate('使用本地 YOLO / YOLO OBB 模型标注当前图片', 'fr'))
        self.assertEqual(
            'Confidence: 0.25',
            translate('置信度：%.2f', 'en') % 0.25)
        for language in LANGUAGES:
            if language != 'zh':
                self.assertNotEqual(
                    '置信度 ', translate('置信度 ', language))
                self.assertNotEqual(
                    '模型置信度阈值（0.01–1.00）；数值越高，保留的预测框通常越少。',
                    translate(
                        '模型置信度阈值（0.01–1.00）；数值越高，保留的预测框通常越少。',
                        language))
                self.assertNotEqual(
                    '使用本地 YOLO / YOLO OBB 模型标注当前图片',
                    translate(
                        '使用本地 YOLO / YOLO OBB 模型标注当前图片',
                        language))
        self.assertIn(
            'confidence',
            translate('自动标注置信度已设为 %.2f。', 'en') % 0.25)

        manager.apply('zh')
        self.assertEqual('置信度 ', confidence.prefix())
        self.assertIn('模型置信度阈值', confidence.toolTip())
        root.close()

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

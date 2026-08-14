#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

import labelImg
from libs.constants import (FORMAT_PASCALVOC, FORMAT_YOLO,
                            FORMAT_YOLO_OBB)
from libs.labelFile import LabelFile
from libs.pascal_voc_io import PascalVocReader
from libs.yolo_obb_io import inspect_yolo_file, save_yolo_annotations


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


class FakeProgressDialog(object):
    instances = []

    def __init__(self, label, cancel, minimum, maximum, parent):
        self.label = label
        self.minimum = minimum
        self.maximum = maximum
        self.values = []
        self.closed = False
        self.__class__.instances.append(self)

    def setWindowTitle(self, _title):
        pass

    def setWindowModality(self, _modality):
        pass

    def setMinimumDuration(self, _duration):
        pass

    def setAutoClose(self, _enabled):
        pass

    def setAutoReset(self, _enabled):
        pass

    def setValue(self, value):
        self.values.append(value)

    def setLabelText(self, label):
        self.label = label

    def show(self):
        pass

    def wasCanceled(self):
        return False

    def close(self):
        self.closed = True


class AnnotationFormatConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        self.temporary = tempfile.TemporaryDirectory()
        self.imageDir = os.path.join(self.temporary.name, 'images')
        self.annotationDir = os.path.join(
            self.temporary.name, 'annotations')
        os.makedirs(os.path.join(self.imageDir, 'nested'))
        os.makedirs(os.path.join(self.annotationDir, 'nested'))
        self.imagePath = os.path.join(
            self.imageDir, 'nested', 'sample.jpg')
        image = QImage(120, 80, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))
        self.assertTrue(image.save(self.imagePath))

        classesPath = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)
        self.window.dirname = self.imageDir
        self.window.defaultSaveDir = self.annotationDir
        self.label = self.window.labelHist[0]
        self.basePath = os.path.join(
            self.annotationDir, 'nested', 'sample')
        FakeProgressDialog.instances = []

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def shape_dict(self, rotated=True):
        return {
            'label': self.label,
            'points': [(20.0, 15.0), (70.0, 20.0),
                       (65.0, 55.0), (15.0, 50.0)],
            'line_color': (0, 255, 0, 255),
            'fill_color': (255, 0, 0, 128),
            'difficult': False,
            'direction': 0.1 if rotated else 0.0,
            'center': QPointF(42.5, 35.0),
            'isRotated': rotated,
            'extra_text': '',
        }

    def create_xml(self):
        path = self.basePath + '.xml'
        LabelFile().savePascalVocFormat(
            path, [self.shape_dict()], self.imagePath, None)
        return path

    def create_txt(self, annotation_format):
        path = self.basePath + '.txt'
        save_yolo_annotations(
            path, [self.shape_dict(annotation_format == FORMAT_YOLO_OBB)],
            120, 80, self.window.labelHist, annotation_format)
        return path

    def change_format(self, target_format, convert_existing=True):
        with mock.patch.object(
                labelImg, 'QProgressDialog', FakeProgressDialog), \
                mock.patch.object(
                    labelImg.QMessageBox, 'information', return_value=0
                ) as information, \
                mock.patch.object(
                    labelImg.QMessageBox, 'warning', return_value=0
                ) as warning:
            result = self.window.setAnnotationFormat(
                target_format, convertExisting=convert_existing)
        return result, information, warning

    def test_xml_to_yolo_obb_converts_all_and_shows_progress(self):
        xmlPath = self.create_xml()

        result, information, warning = self.change_format(FORMAT_YOLO_OBB)

        txtPath = self.basePath + '.txt'
        self.assertTrue(result)
        self.assertFalse(os.path.exists(xmlPath))
        self.assertTrue(os.path.isfile(txtPath))
        self.assertEqual((FORMAT_YOLO_OBB, 1), inspect_yolo_file(txtPath))
        self.assertEqual(1, len(FakeProgressDialog.instances))
        progress = FakeProgressDialog.instances[0]
        self.assertEqual(1, progress.maximum)
        self.assertEqual(1, progress.values[-1])
        self.assertTrue(progress.closed)
        information.assert_called_once()
        warning.assert_not_called()

    def test_yolo_obb_to_xml_removes_old_txt(self):
        txtPath = self.create_txt(FORMAT_YOLO_OBB)
        self.window.annotationFormat = FORMAT_YOLO_OBB

        result, information, warning = self.change_format(FORMAT_PASCALVOC)

        xmlPath = self.basePath + '.xml'
        self.assertTrue(result)
        self.assertFalse(os.path.exists(txtPath))
        self.assertEqual(1, len(PascalVocReader(xmlPath).getShapes()))
        information.assert_called_once()
        warning.assert_not_called()

    def test_yolo_obb_to_yolo_rewrites_shared_txt_extension(self):
        txtPath = self.create_txt(FORMAT_YOLO_OBB)
        self.window.annotationFormat = FORMAT_YOLO_OBB

        result, information, warning = self.change_format(FORMAT_YOLO)

        self.assertTrue(result)
        self.assertEqual((FORMAT_YOLO, 1), inspect_yolo_file(txtPath))
        information.assert_called_once()
        warning.assert_not_called()

    def test_no_labels_changes_format_without_opening_progress(self):
        result, information, warning = self.change_format(FORMAT_YOLO)

        self.assertTrue(result)
        self.assertEqual(FORMAT_YOLO, self.window.annotationFormat)
        self.assertEqual([], FakeProgressDialog.instances)
        information.assert_called_once()
        self.assertIn(
            u'当前数据集还没有标签',
            information.call_args[0][2])
        warning.assert_not_called()

    def test_legacy_export_menu_and_methods_are_removed(self):
        self.assertFalse(hasattr(self.window.menus, 'exportAnnotations'))
        self.assertFalse(hasattr(self.window, 'exportAsYOLO'))
        self.assertFalse(hasattr(self.window, 'exportAsYOLOOBB'))
        self.assertNotIn(
            'Export to',
            [action.text() for action in self.window.menus.file.actions()])

    def test_model_format_selection_does_not_convert_existing_labels(self):
        xmlPath = self.create_xml()

        result, information, warning = self.change_format(
            FORMAT_YOLO_OBB, convert_existing=False)

        self.assertTrue(result)
        self.assertTrue(os.path.isfile(xmlPath))
        self.assertFalse(os.path.exists(self.basePath + '.txt'))
        self.assertEqual([], FakeProgressDialog.instances)
        information.assert_not_called()
        warning.assert_not_called()

    def test_failed_conversion_keeps_the_original_annotation(self):
        txtPath = self.basePath + '.txt'
        with open(txtPath, 'w', encoding='utf-8') as stream:
            stream.write('this is not a YOLO annotation\n')
        self.window.annotationFormat = FORMAT_YOLO

        result, information, warning = self.change_format(FORMAT_PASCALVOC)

        self.assertTrue(result)
        self.assertTrue(os.path.isfile(txtPath))
        self.assertFalse(os.path.exists(self.basePath + '.xml'))
        information.assert_not_called()
        warning.assert_called_once()
        self.assertIn(
            u'原文件已保留',
            warning.call_args[0][2])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import types
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

import labelImg
from libs.auto_annotation import AutoAnnotationThread, shapes_for_job


class FakeBoxes(object):
    xyxy = [[10.0, 20.0, 30.0, 40.0]]
    cls = [0]


class FakeResult(object):
    orig_shape = (100, 100)
    boxes = FakeBoxes()


class FakeYOLO(object):
    task = 'detect'
    names = {0: 'apple'}

    def __init__(self, _model_path):
        pass

    def predict(self, **_kwargs):
        return [FakeResult()]


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


class AutoAnnotationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.existing = [{
            'label': 'apples',
            'points': [(1, 1), (5, 1), (5, 5), (1, 5)],
            'isRotated': False,
        }]
        self.generated = [{
            'label': 'apples',
            'points': [(10, 20), (30, 20), (30, 40), (10, 40)],
            'isRotated': False,
        }]

    def test_append_keeps_existing_shapes(self):
        shapes = shapes_for_job({
            'existing_policy': 'append',
            'existing_shapes': self.existing,
        }, self.generated)
        self.assertEqual(self.existing + self.generated, shapes)

    def test_overwrite_uses_only_generated_shapes(self):
        shapes = shapes_for_job({
            'existing_policy': 'overwrite',
            'existing_shapes': self.existing,
        }, self.generated)
        self.assertEqual(self.generated, shapes)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            shapes_for_job({'existing_policy': 'unknown'}, self.generated)

    def test_thread_appends_and_returns_single_image_result(self):
        fake_module = types.ModuleType('ultralytics')
        fake_module.YOLO = FakeYOLO
        previous_module = sys.modules.get('ultralytics')
        sys.modules['ultralytics'] = fake_module
        try:
            with tempfile.TemporaryDirectory() as directory:
                annotation_base = os.path.join(directory, 'image')
                summaries = []
                failures = []
                thread = AutoAnnotationThread(
                    'fake.pt',
                    [{
                        'image_path': os.path.join(directory, 'image.jpg'),
                        'annotation_base': annotation_base,
                        'existing_policy': 'append',
                        'existing_shapes': self.existing,
                        'return_shapes': True,
                    }],
                    ['apples'])
                thread.completed.connect(summaries.append)
                thread.failed.connect(failures.append)
                thread.run()

                self.assertEqual([], failures)
                self.assertEqual(1, len(summaries))
                summary = summaries[0]
                self.assertEqual(1, summary['saved'])
                self.assertEqual(1, summary['objects'])
                self.assertEqual(2, len(
                    summary['job_results'][0]['saved_shapes']))
                with open(annotation_base + '.txt', 'r', encoding='utf-8') as stream:
                    self.assertEqual(2, len(stream.read().splitlines()))
        finally:
            if previous_module is None:
                del sys.modules['ultralytics']
            else:
                sys.modules['ultralytics'] = previous_module

    def test_thread_overwrites_an_existing_txt_when_requested(self):
        fake_module = types.ModuleType('ultralytics')
        fake_module.YOLO = FakeYOLO
        previous_module = sys.modules.get('ultralytics')
        sys.modules['ultralytics'] = fake_module
        try:
            with tempfile.TemporaryDirectory() as directory:
                annotation_base = os.path.join(directory, 'image')
                with open(annotation_base + '.txt', 'w', encoding='utf-8') as stream:
                    stream.write('0 0.05 0.05 0.02 0.02\n')
                summaries = []
                thread = AutoAnnotationThread(
                    'fake.pt',
                    [{
                        'image_path': os.path.join(directory, 'image.jpg'),
                        'annotation_base': annotation_base,
                        'existing_policy': 'overwrite',
                        'return_shapes': True,
                    }],
                    ['apples'])
                thread.completed.connect(summaries.append)
                thread.run()

                self.assertEqual(1, summaries[0]['saved'])
                self.assertEqual(0, summaries[0]['skipped'])
                with open(annotation_base + '.txt', 'r', encoding='utf-8') as stream:
                    lines = stream.read().splitlines()
                self.assertEqual(1, len(lines))
                self.assertNotIn('0.05 0.05', lines[0])
        finally:
            if previous_module is None:
                del sys.modules['ultralytics']
            else:
                sys.modules['ultralytics'] = previous_module

    def test_batch_default_still_skips_existing_annotations(self):
        fake_module = types.ModuleType('ultralytics')
        fake_module.YOLO = FakeYOLO
        previous_module = sys.modules.get('ultralytics')
        sys.modules['ultralytics'] = fake_module
        try:
            with tempfile.TemporaryDirectory() as directory:
                annotation_base = os.path.join(directory, 'image')
                original = '0 0.05 0.05 0.02 0.02\n'
                with open(annotation_base + '.txt', 'w', encoding='utf-8') as stream:
                    stream.write(original)
                summaries = []
                thread = AutoAnnotationThread(
                    'fake.pt',
                    [{
                        'image_path': os.path.join(directory, 'image.jpg'),
                        'annotation_base': annotation_base,
                    }],
                    ['apples'])
                thread.completed.connect(summaries.append)
                thread.run()

                self.assertEqual(0, summaries[0]['saved'])
                self.assertEqual(1, summaries[0]['skipped'])
                with open(annotation_base + '.txt', 'r', encoding='utf-8') as stream:
                    self.assertEqual(original, stream.read())
        finally:
            if previous_module is None:
                del sys.modules['ultralytics']
            else:
                sys.modules['ultralytics'] = previous_module


class SingleAutoAnnotationToolbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_single_image_action_is_in_top_toolbar(self):
        original_settings = labelImg.Settings
        labelImg.Settings = MemorySettings
        try:
            classes_path = os.path.join(
                os.path.dirname(labelImg.__file__),
                'data', 'predefined_classes.txt')
            window = labelImg.MainWindow(
                defaultPrefdefClassFile=classes_path)
            action = window.actions.singleAutoAnnotate
            self.assertEqual('标注当前图', action.text())
            self.assertIn(action, window.tools.actions())
            self.assertFalse(action.icon().isNull())
            self.assertFalse(action.isEnabled())
            window.close()
        finally:
            labelImg.Settings = original_settings


if __name__ == '__main__':
    unittest.main()

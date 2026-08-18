#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

import labelImg
from libs.auto_annotation import (AutoAnnotationThread, class_similarity,
                                  match_model_classes, shapes_for_job)
from libs.constants import SETTING_AUTO_ANNOTATION_CONFIDENCE


class FakeBoxes(object):
    xyxy = [[10.0, 20.0, 30.0, 40.0]]
    cls = [0]


class FakeResult(object):
    orig_shape = (100, 100)
    boxes = FakeBoxes()


class FakeYOLO(object):
    task = 'detect'
    names = {0: 'apple'}
    last_predict_kwargs = None

    def __init__(self, _model_path):
        pass

    def predict(self, **kwargs):
        type(self).last_predict_kwargs = kwargs
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

    def test_exact_model_class_beats_an_earlier_shared_token(self):
        mapping, details = match_model_classes(
            {0: 'pipe_row'}, ['Drill_pipe', 'pipe_row'])
        self.assertEqual('pipe_row', mapping[0])
        self.assertEqual('pipe_row', details[0]['project_name'])
        self.assertEqual(1.0, details[0]['score'])

    def test_shared_token_is_not_scored_as_a_full_name_match(self):
        self.assertLess(
            class_similarity('pipe_row', 'Drill_pipe'),
            class_similarity('pipe_row', 'pipe_row'))

    def test_normalized_full_name_match_beats_fuzzy_candidates(self):
        mapping, _details = match_model_classes(
            {0: 'PIPE-ROW'}, ['Drill_pipe', 'pipe_row'])
        self.assertEqual('pipe_row', mapping[0])

    def test_every_exact_preset_name_maps_back_to_itself(self):
        classes_path = os.path.join(
            os.path.dirname(labelImg.__file__),
            'data', 'predefined_classes.txt')
        with open(classes_path, 'r', encoding='utf-8') as stream:
            project_classes = [line.strip() for line in stream if line.strip()]
        model_names = dict(enumerate(project_classes))
        mapping, _details = match_model_classes(
            model_names, project_classes)
        self.assertEqual(model_names, mapping)

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

    def test_thread_passes_selected_confidence_to_ultralytics(self):
        fake_module = types.ModuleType('ultralytics')
        fake_module.YOLO = FakeYOLO
        previous_module = sys.modules.get('ultralytics')
        sys.modules['ultralytics'] = fake_module
        FakeYOLO.last_predict_kwargs = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                summaries = []
                thread = AutoAnnotationThread(
                    'fake.pt',
                    [{
                        'image_path': os.path.join(directory, 'image.jpg'),
                        'annotation_base': os.path.join(directory, 'image'),
                    }],
                    ['apples'],
                    confidence=0.63)
                thread.completed.connect(summaries.append)
                thread.run()

                self.assertAlmostEqual(
                    0.63, FakeYOLO.last_predict_kwargs['conf'])
                self.assertAlmostEqual(0.63, summaries[0]['confidence'])
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

    def test_confidence_control_is_persistent_and_used_by_both_modes(self):
        class SavedConfidenceSettings(MemorySettings):
            def __init__(self):
                super(SavedConfidenceSettings, self).__init__()
                self.data[SETTING_AUTO_ANNOTATION_CONFIDENCE] = 0.55

        original_settings = labelImg.Settings
        labelImg.Settings = SavedConfidenceSettings
        try:
            classes_path = os.path.join(
                os.path.dirname(labelImg.__file__),
                'data', 'predefined_classes.txt')
            window = labelImg.MainWindow(
                defaultPrefdefClassFile=classes_path)
            control = window.actions.autoAnnotationConfidenceControl
            spin_box = window.autoAnnotationConfidenceSpinBox
            self.assertIn(control, window.tools.actions())
            self.assertAlmostEqual(0.55, spin_box.value())

            spin_box.setValue(0.70)
            self.assertAlmostEqual(
                0.70,
                window.settings.data[SETTING_AUTO_ANNOTATION_CONFIDENCE])

            for mode in ('batch', 'single'):
                with self.subTest(mode=mode), mock.patch.object(
                        labelImg, 'AutoAnnotationThread') as thread_class:
                    thread = thread_class.return_value
                    thread.isRunning.return_value = False
                    window.startAutoAnnotationJobs(
                        [{'image_path': 'image.jpg',
                          'annotation_base': 'image'}],
                        mode=mode)

                    self.assertAlmostEqual(
                        0.70, thread_class.call_args.kwargs['confidence'])
                    self.assertFalse(spin_box.isEnabled())
                    window.finishAutoAnnotationUi()
                    self.assertTrue(spin_box.isEnabled())
                    window.autoAnnotationThread = None

            window.close()
        finally:
            labelImg.Settings = original_settings

    def test_invalid_saved_confidence_falls_back_to_default(self):
        class InvalidConfidenceSettings(MemorySettings):
            def __init__(self):
                super(InvalidConfidenceSettings, self).__init__()
                self.data[SETTING_AUTO_ANNOTATION_CONFIDENCE] = 'invalid'

        original_settings = labelImg.Settings
        labelImg.Settings = InvalidConfidenceSettings
        try:
            classes_path = os.path.join(
                os.path.dirname(labelImg.__file__),
                'data', 'predefined_classes.txt')
            window = labelImg.MainWindow(
                defaultPrefdefClassFile=classes_path)
            self.assertAlmostEqual(
                0.25, window.autoAnnotationConfidenceSpinBox.value())
            window.close()
        finally:
            labelImg.Settings = original_settings


if __name__ == '__main__':
    unittest.main()

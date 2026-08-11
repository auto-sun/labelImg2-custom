#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
"""Background inference and class matching for automatic annotation."""
from __future__ import absolute_import

import difflib
import os
import unicodedata

from PyQt5.QtCore import QThread, pyqtSignal

from .constants import FORMAT_YOLO, FORMAT_YOLO_OBB
from .pascal_voc_io import XML_EXT
from .yolo_obb_io import YOLO_EXT, save_yolo_annotations


def _singularize(token):
    """Return a conservative English singular form for fuzzy comparison."""
    if len(token) > 4 and token.endswith('ies'):
        return token[:-3] + 'y'
    if len(token) > 3 and token.endswith('s') and not token.endswith('ss'):
        return token[:-1]
    return token


def _name_parts(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    text = ''.join(character if character.isalnum() else ' '
                   for character in text)
    tokens = [token for token in text.split() if token]
    singular_tokens = [_singularize(token) for token in tokens]
    return ''.join(tokens), ''.join(singular_tokens), singular_tokens


def _is_subsequence(short_text, long_text):
    if not short_text:
        return False
    position = 0
    for character in long_text:
        if character == short_text[position]:
            position += 1
            if position == len(short_text):
                return True
    return False


def class_similarity(model_name, project_name):
    """Return a deterministic fuzzy similarity score in the range 0..1."""
    model_compact, model_singular, model_tokens = _name_parts(model_name)
    project_compact, project_singular, project_tokens = _name_parts(
        project_name)
    if not model_compact or not project_compact:
        return 0.0
    if model_compact == project_compact:
        return 1.0
    if model_singular == project_singular:
        return 0.995

    shorter = min(len(model_singular), len(project_singular))
    longer = max(len(model_singular), len(project_singular))
    length_ratio = float(shorter) / float(longer)
    scores = [
        difflib.SequenceMatcher(
            None, model_compact, project_compact).ratio(),
        difflib.SequenceMatcher(
            None, model_singular, project_singular).ratio(),
    ]

    if shorter >= 3:
        if (model_singular in project_singular or
                project_singular in model_singular):
            scores.append(0.93 + 0.05 * length_ratio)
        if (model_singular.startswith(project_singular) or
                project_singular.startswith(model_singular)):
            scores.append(0.90 + 0.07 * length_ratio)
        short_name, long_name = sorted(
            (model_singular, project_singular), key=len)
        if _is_subsequence(short_name, long_name):
            scores.append(0.80 + 0.12 * length_ratio)

    for model_token in model_tokens:
        for project_token in project_tokens:
            scores.append(difflib.SequenceMatcher(
                None, model_token, project_token).ratio())
            if (len(model_token) >= 3 and
                    (model_token in project_token or
                     project_token in model_token)):
                token_ratio = (float(min(len(model_token), len(project_token))) /
                               float(max(len(model_token), len(project_token))))
                scores.append(0.92 + 0.06 * token_ratio)
    return min(1.0, max(scores))


def model_name_items(model_names):
    """Normalize Ultralytics' dict/list class-name representation."""
    if isinstance(model_names, dict):
        items = []
        for class_id, name in model_names.items():
            try:
                numeric_id = int(class_id)
            except (TypeError, ValueError):
                continue
            items.append((numeric_id, str(name)))
        return sorted(items, key=lambda item: item[0])
    return [(index, str(name)) for index, name in enumerate(model_names or [])]


def match_model_classes(model_names, project_classes):
    """Map every model class id to its most similar project class."""
    project_classes = [str(name) for name in project_classes or [] if str(name)]
    if not project_classes:
        raise ValueError('The project class preset is empty.')

    mapping = {}
    details = []
    for class_id, model_name in model_name_items(model_names):
        best_index = max(
            range(len(project_classes)),
            key=lambda index: (
                class_similarity(model_name, project_classes[index]),
                -index))
        project_name = project_classes[best_index]
        score = class_similarity(model_name, project_name)
        mapping[class_id] = project_name
        details.append({
            'class_id': class_id,
            'model_name': model_name,
            'project_name': project_name,
            'score': score,
        })
    if not mapping:
        raise ValueError('The model does not contain any class names.')
    return mapping, details


def _as_list(value):
    if value is None:
        return []
    if hasattr(value, 'detach'):
        value = value.detach()
    if hasattr(value, 'cpu'):
        value = value.cpu()
    if hasattr(value, 'tolist'):
        return value.tolist()
    return list(value)


def _image_size(result):
    shape = getattr(result, 'orig_shape', None)
    if shape and len(shape) >= 2:
        return int(shape[1]), int(shape[0])
    image = getattr(result, 'orig_img', None)
    if image is not None and hasattr(image, 'shape') and len(image.shape) >= 2:
        return int(image.shape[1]), int(image.shape[0])
    raise ValueError('The model result does not contain the source image size.')


def _clip(value, upper_bound):
    return max(0.0, min(float(value), float(upper_bound)))


def shapes_from_result(result, annotation_format, class_mapping):
    """Convert one Ultralytics result into LabelImg2 shape dictionaries."""
    image_width, image_height = _image_size(result)
    shapes = []
    if annotation_format == FORMAT_YOLO_OBB:
        predictions = getattr(result, 'obb', None)
        if predictions is None:
            raise ValueError('The OBB model returned no OBB result container.')
        coordinates = _as_list(getattr(predictions, 'xyxyxyxy', None))
        class_ids = _as_list(getattr(predictions, 'cls', None))
        for raw_points, raw_class_id in zip(coordinates, class_ids):
            class_id = int(raw_class_id)
            if class_id not in class_mapping:
                continue
            points = [
                (_clip(point[0], image_width),
                 _clip(point[1], image_height))
                for point in raw_points
            ]
            if len(points) != 4:
                continue
            shapes.append({
                'label': class_mapping[class_id],
                'points': points,
                'isRotated': True,
            })
    else:
        predictions = getattr(result, 'boxes', None)
        if predictions is None:
            raise ValueError('The detection model returned no box result container.')
        coordinates = _as_list(getattr(predictions, 'xyxy', None))
        class_ids = _as_list(getattr(predictions, 'cls', None))
        for raw_box, raw_class_id in zip(coordinates, class_ids):
            class_id = int(raw_class_id)
            if class_id not in class_mapping or len(raw_box) != 4:
                continue
            x_min = _clip(raw_box[0], image_width)
            y_min = _clip(raw_box[1], image_height)
            x_max = _clip(raw_box[2], image_width)
            y_max = _clip(raw_box[3], image_height)
            if x_max <= x_min or y_max <= y_min:
                continue
            shapes.append({
                'label': class_mapping[class_id],
                'points': [
                    (x_min, y_min), (x_max, y_min),
                    (x_max, y_max), (x_min, y_max),
                ],
                'isRotated': False,
            })
    return shapes, image_width, image_height


class AutoAnnotationThread(QThread):
    """Load a local Ultralytics model and annotate image jobs off the UI thread."""

    modelLoaded = pyqtSignal(str, object)
    progressChanged = pyqtSignal(int, int, str, int, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, model_path, jobs, project_classes, confidence=0.25,
                 parent=None):
        super(AutoAnnotationThread, self).__init__(parent)
        self.model_path = model_path
        self.jobs = list(jobs)
        self.project_classes = list(project_classes)
        self.confidence = float(confidence)

    def cancel(self):
        self.requestInterruption()

    def run(self):
        try:
            try:
                from ultralytics import YOLO
            except ImportError as error:
                raise RuntimeError(
                    'Automatic annotation requires ultralytics. '
                    'Run: pip install -r requirements.txt') from error

            model = YOLO(self.model_path)
            task = str(getattr(model, 'task', '') or '').casefold()
            if task == 'obb':
                annotation_format = FORMAT_YOLO_OBB
            elif task == 'detect':
                annotation_format = FORMAT_YOLO
            else:
                raise ValueError(
                    'Only YOLO detection and YOLO OBB .pt models are supported; '
                    'this model reports task %r.' % (task or 'unknown'))

            class_mapping, mapping_details = match_model_classes(
                getattr(model, 'names', None), self.project_classes)
            self.modelLoaded.emit(annotation_format, mapping_details)

            total = len(self.jobs)
            saved = 0
            skipped = 0
            object_count = 0
            errors = []
            for index, job in enumerate(self.jobs):
                if self.isInterruptionRequested():
                    break

                image_path = job['image_path']
                annotation_base = job['annotation_base']
                if (os.path.isfile(annotation_base + XML_EXT) or
                        os.path.isfile(annotation_base + YOLO_EXT)):
                    skipped += 1
                    self.progressChanged.emit(
                        index + 1, total, image_path, 0, 'skipped')
                    continue

                try:
                    results = model.predict(
                        source=image_path,
                        conf=self.confidence,
                        verbose=False,
                        save=False)
                    if self.isInterruptionRequested():
                        break
                    if not results:
                        raise ValueError('The model returned no result.')
                    shapes, image_width, image_height = shapes_from_result(
                        results[0], annotation_format, class_mapping)
                    save_yolo_annotations(
                        annotation_base + YOLO_EXT,
                        shapes,
                        image_width,
                        image_height,
                        self.project_classes,
                        annotation_format)
                    saved += 1
                    object_count += len(shapes)
                    self.progressChanged.emit(
                        index + 1, total, image_path, len(shapes), 'saved')
                except Exception as error:
                    errors.append('%s: %s' % (image_path, error))
                    self.progressChanged.emit(
                        index + 1, total, image_path, 0, 'error')

            self.completed.emit({
                'cancelled': self.isInterruptionRequested(),
                'total': total,
                'saved': saved,
                'skipped': skipped,
                'objects': object_count,
                'errors': errors,
                'format': annotation_format,
                'mapping': mapping_details,
            })
        except Exception as error:
            self.failed.emit(str(error))

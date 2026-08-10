#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read and write Ultralytics-style YOLO and YOLO OBB annotations."""
from __future__ import absolute_import

import math
import os

from .constants import FORMAT_YOLO, FORMAT_YOLO_OBB


YOLO_EXT = '.txt'
YOLO_OBB_EXT = YOLO_EXT


class YoloError(ValueError):
    """Raised when a YOLO annotation cannot be parsed or written safely."""


# Backwards-compatible name retained for callers added before generic YOLO
# support was introduced.
YoloObbError = YoloError


def _parse_record(text, filepath, line_number):
    fields = text.split()
    if len(fields) == 5:
        annotation_format = FORMAT_YOLO
    elif len(fields) == 9:
        annotation_format = FORMAT_YOLO_OBB
    else:
        raise YoloError(
            '%s:%d: expected either 5 values '
            '(class_id cx cy width height) or 9 values '
            '(class_id x1 y1 x2 y2 x3 y3 x4 y4), got %d' %
            (filepath, line_number, len(fields)))

    try:
        values = [float(field) for field in fields]
    except ValueError:
        raise YoloError(
            '%s:%d: every value must be numeric' %
            (filepath, line_number))

    if not all(math.isfinite(value) for value in values):
        raise YoloError(
            '%s:%d: values must be finite numbers' %
            (filepath, line_number))

    class_value = values[0]
    class_id = int(class_value)
    if class_value != class_id or class_id < 0:
        raise YoloError(
            '%s:%d: class_id must be a non-negative integer' %
            (filepath, line_number))

    return annotation_format, class_id, values[1:]


def _iter_records(filepath, expected_format=None):
    detected_format = None
    with open(filepath, 'r', encoding='utf-8-sig') as stream:
        for line_number, raw_line in enumerate(stream, 1):
            text = raw_line.strip()
            if not text or text.startswith('#'):
                continue
            annotation_format, class_id, coordinates = _parse_record(
                text, filepath, line_number)
            if expected_format and annotation_format != expected_format:
                raise YoloError(
                    '%s:%d: expected %s records, found %s' %
                    (filepath, line_number, expected_format,
                     annotation_format))
            if detected_format and annotation_format != detected_format:
                raise YoloError(
                    '%s:%d: YOLO and YOLO OBB records cannot be mixed '
                    'in one TXT file' % (filepath, line_number))
            detected_format = annotation_format
            yield annotation_format, class_id, coordinates


def inspect_yolo_file(filepath):
    """Return ``(detected_format, object_count)`` for a YOLO TXT file."""
    detected_format = None
    count = 0
    for annotation_format, _class_id, _coordinates in _iter_records(filepath):
        detected_format = annotation_format
        count += 1
    return detected_format, count


def count_yolo_objects(filepath):
    """Return the number of valid, non-empty YOLO records in *filepath*."""
    return inspect_yolo_file(filepath)[1]


def count_yolo_obb_objects(filepath):
    """Return the number of valid, non-empty OBB records in *filepath*."""
    return sum(1 for _ in _iter_records(
        filepath, expected_format=FORMAT_YOLO_OBB))


class YoloReader(object):
    """Convert normalized YOLO box or OBB records to LabelImg2 shapes."""

    def __init__(self, filepath, image_width, image_height, class_names,
                 expected_format=None):
        self.filepath = filepath
        self.image_width = float(image_width)
        self.image_height = float(image_height)
        self.class_names = list(class_names or [])
        self.expected_format = expected_format
        self.annotation_format = None
        self.shapes = []
        self.verified = False
        self._parse()

    def _parse(self):
        if self.image_width <= 0 or self.image_height <= 0:
            raise YoloError(
                '%s: image width and height must be positive' % self.filepath)

        for annotation_format, class_id, coordinates in _iter_records(
                self.filepath, expected_format=self.expected_format):
            self.annotation_format = annotation_format
            if class_id >= len(self.class_names):
                raise YoloError(
                    '%s: class_id %d is outside the current class list '
                    'containing %d classes' %
                    (self.filepath, class_id, len(self.class_names)))

            if annotation_format == FORMAT_YOLO:
                center_x, center_y, width, height = coordinates
                if width <= 0 or height <= 0:
                    raise YoloError(
                        '%s: YOLO width and height must be positive' %
                        self.filepath)
                center_x *= self.image_width
                center_y *= self.image_height
                width *= self.image_width
                height *= self.image_height
                points = [
                    (center_x - width / 2.0, center_y - height / 2.0),
                    (center_x + width / 2.0, center_y - height / 2.0),
                    (center_x + width / 2.0, center_y + height / 2.0),
                    (center_x - width / 2.0, center_y + height / 2.0),
                ]
                is_rotated = False
                direction = 0.0
            else:
                points = []
                for index in range(0, 8, 2):
                    points.append((
                        coordinates[index] * self.image_width,
                        coordinates[index + 1] * self.image_height))

                edge_x = points[1][0] - points[0][0]
                edge_y = points[1][1] - points[0][1]
                if edge_x == 0 and edge_y == 0:
                    raise YoloError(
                        '%s: an OBB has identical first and second corners' %
                        self.filepath)
                is_rotated = True
                direction = math.atan2(edge_y, edge_x) % (2 * math.pi)

            self.shapes.append((
                self.class_names[class_id], points, None, None,
                False, is_rotated, direction, ''))

    def getShapes(self):
        return self.shapes


class YoloObbReader(YoloReader):
    """Compatibility reader that accepts only YOLO OBB records."""

    def __init__(self, filepath, image_width, image_height, class_names):
        super(YoloObbReader, self).__init__(
            filepath, image_width, image_height, class_names,
            expected_format=FORMAT_YOLO_OBB)


def _format_number(value):
    return '{:.8f}'.format(value).rstrip('0').rstrip('.') or '0'


def save_yolo_annotations(filepath, shapes, image_width, image_height,
                          class_names, annotation_format):
    """Save LabelImg2 shape dictionaries as YOLO or YOLO OBB TXT."""
    if annotation_format not in (FORMAT_YOLO, FORMAT_YOLO_OBB):
        raise YoloError(
            'Unsupported YOLO annotation format: %s' % annotation_format)

    image_width = float(image_width)
    image_height = float(image_height)
    if image_width <= 0 or image_height <= 0:
        raise YoloError('Image width and height must be positive')

    class_map = {}
    for class_id, class_name in enumerate(class_names or []):
        class_map.setdefault(class_name, class_id)

    lines = []
    for shape in shapes:
        label = shape['label']
        if label not in class_map:
            raise YoloError(
                'Unknown class %r; add it to the current class preset first' %
                label)
        points = [(float(x), float(y)) for x, y in shape['points']]
        if len(points) != 4:
            raise YoloError(
                'Class %r does not contain exactly four box corners' % label)

        if annotation_format == FORMAT_YOLO:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            if xmax <= xmin or ymax <= ymin:
                raise YoloError('Class %r has an empty box' % label)
            values = [
                (xmin + xmax) / 2.0 / image_width,
                (ymin + ymax) / 2.0 / image_height,
                (xmax - xmin) / image_width,
                (ymax - ymin) / image_height,
            ]
        else:
            values = []
            for x, y in points:
                values.extend((x / image_width, y / image_height))

        lines.append('%d %s' % (
            class_map[label],
            ' '.join(_format_number(value) for value in values)))

    output_parent = os.path.dirname(os.path.abspath(filepath))
    if output_parent:
        os.makedirs(output_parent, exist_ok=True)
    temporary_path = filepath + '.tmp'
    try:
        with open(temporary_path, 'w', encoding='utf-8', newline='\n') as stream:
            if lines:
                stream.write('\n'.join(lines) + '\n')
        os.replace(temporary_path, filepath)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

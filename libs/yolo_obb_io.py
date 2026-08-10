#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read Ultralytics-style YOLO OBB annotation files."""
from __future__ import absolute_import

import math


YOLO_OBB_EXT = '.txt'


class YoloObbError(ValueError):
    """Raised when a YOLO OBB annotation cannot be parsed safely."""


def _parse_record(text, filepath, line_number):
    fields = text.split()
    if len(fields) != 9:
        raise YoloObbError(
            '%s:%d: expected 9 values '
            '(class_id x1 y1 x2 y2 x3 y3 x4 y4), got %d' %
            (filepath, line_number, len(fields)))

    try:
        values = [float(field) for field in fields]
    except ValueError:
        raise YoloObbError(
            '%s:%d: every value must be numeric' %
            (filepath, line_number))

    if not all(math.isfinite(value) for value in values):
        raise YoloObbError(
            '%s:%d: values must be finite numbers' %
            (filepath, line_number))

    class_value = values[0]
    class_id = int(class_value)
    if class_value != class_id or class_id < 0:
        raise YoloObbError(
            '%s:%d: class_id must be a non-negative integer' %
            (filepath, line_number))

    return class_id, values[1:]


def _iter_records(filepath):
    with open(filepath, 'r', encoding='utf-8-sig') as stream:
        for line_number, raw_line in enumerate(stream, 1):
            text = raw_line.strip()
            if not text or text.startswith('#'):
                continue
            yield _parse_record(text, filepath, line_number)


def count_yolo_obb_objects(filepath):
    """Return the number of valid, non-empty OBB records in *filepath*."""
    return sum(1 for _ in _iter_records(filepath))


class YoloObbReader(object):
    """Convert normalized YOLO OBB corners into LabelImg2 shape tuples."""

    def __init__(self, filepath, image_width, image_height, class_names):
        self.filepath = filepath
        self.image_width = float(image_width)
        self.image_height = float(image_height)
        self.class_names = list(class_names or [])
        self.shapes = []
        self.verified = False
        self._parse()

    def _parse(self):
        if self.image_width <= 0 or self.image_height <= 0:
            raise YoloObbError(
                '%s: image width and height must be positive' % self.filepath)

        for class_id, coordinates in _iter_records(self.filepath):
            if class_id >= len(self.class_names):
                raise YoloObbError(
                    '%s: class_id %d is outside the current class list '
                    '(0-%d)' %
                    (self.filepath, class_id, len(self.class_names) - 1))

            points = []
            for index in range(0, 8, 2):
                points.append((
                    coordinates[index] * self.image_width,
                    coordinates[index + 1] * self.image_height))

            edge_x = points[1][0] - points[0][0]
            edge_y = points[1][1] - points[0][1]
            if edge_x == 0 and edge_y == 0:
                raise YoloObbError(
                    '%s: an OBB has identical first and second corners' %
                    self.filepath)

            direction = math.atan2(edge_y, edge_x) % (2 * math.pi)
            self.shapes.append((
                self.class_names[class_id], points, None, None,
                False, True, direction, ''))

    def getShapes(self):
        return self.shapes

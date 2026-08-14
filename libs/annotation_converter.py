#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
"""Safe conversion between LabelImg2 annotation formats."""
from __future__ import absolute_import

import os

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImageReader

from .constants import (FORMAT_PASCALVOC, FORMAT_YOLO, FORMAT_YOLO_OBB)
from .labelFile import LabelFile, LabelFileError
from .pascal_voc_io import PascalVocReader, XML_EXT
from .yolo_obb_io import (YoloError, YoloReader, YOLO_EXT,
                          save_yolo_annotations)


class AnnotationConversionError(Exception):
    """Raised when an annotation cannot be converted without data loss."""


def _shape_tuple_to_dict(shape_info):
    """Convert a reader tuple into the dictionary expected by the writers."""
    if len(shape_info) == 5:
        label, points, line_color, fill_color, difficult = shape_info
        extra_text = ''
        is_rotated = False
        direction = 0.0
    elif len(shape_info) == 6:
        (label, points, line_color, fill_color, difficult,
         extra_text) = shape_info
        is_rotated = False
        direction = 0.0
    elif len(shape_info) == 7:
        (label, points, line_color, fill_color, difficult,
         is_rotated, direction) = shape_info
        extra_text = ''
    elif len(shape_info) == 8:
        (label, points, line_color, fill_color, difficult,
         is_rotated, direction, extra_text) = shape_info
    else:
        raise AnnotationConversionError(
            'Unsupported annotation shape containing %d fields' %
            len(shape_info))

    points = [(float(x), float(y)) for x, y in points]
    if len(points) != 4:
        raise AnnotationConversionError(
            'Class %r does not contain exactly four box corners' % label)
    center = QPointF(
        sum(point[0] for point in points) / 4.0,
        sum(point[1] for point in points) / 4.0)
    return {
        'label': label,
        'points': points,
        'line_color': line_color,
        'fill_color': fill_color,
        'difficult': bool(difficult),
        'direction': float(direction),
        'center': center,
        'isRotated': bool(is_rotated),
        'extra_text': extra_text or '',
    }


def _read_image_size(image_path):
    reader = QImageReader(image_path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise AnnotationConversionError(
            'Cannot read image %s: %s' %
            (image_path, reader.errorString()))
    return image.width(), image.height()


def _read_shapes(source_path, image_width, image_height, class_names):
    extension = os.path.splitext(source_path)[1].lower()
    if extension == XML_EXT:
        reader = PascalVocReader(source_path)
        source_width, source_height, _depth = reader.getSize()
        if source_width <= 0 or source_height <= 0:
            raise AnnotationConversionError(
                'Cannot read a valid Pascal VOC annotation from %s' %
                source_path)
        return reader.getShapes(), bool(reader.verified)
    if extension == YOLO_EXT:
        reader = YoloReader(
            source_path, image_width, image_height, class_names)
        return reader.getShapes(), False
    raise AnnotationConversionError(
        'Unsupported annotation extension: %s' % extension)


def _write_pascal_voc(target_path, shapes, image_path, verified):
    temporary_path = target_path + '.conversion.tmp'
    label_file = LabelFile()
    label_file.verified = bool(verified)
    try:
        label_file.savePascalVocFormat(
            temporary_path, shapes, image_path, None)
        os.replace(temporary_path, target_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def convert_annotation_file(image_path, source_path, target_format,
                            class_names):
    """Convert one annotation and remove its old format after a safe write.

    Returns ``(target_path, object_count)``. YOLO and YOLO OBB share the TXT
    extension, so conversions between them atomically rewrite the same file.
    """
    if target_format not in (
            FORMAT_PASCALVOC, FORMAT_YOLO, FORMAT_YOLO_OBB):
        raise AnnotationConversionError(
            'Unsupported target annotation format: %s' % target_format)
    if not os.path.isfile(source_path):
        raise AnnotationConversionError(
            'Annotation file does not exist: %s' % source_path)

    try:
        image_width, image_height = _read_image_size(image_path)
        raw_shapes, verified = _read_shapes(
            source_path, image_width, image_height, class_names)
        shapes = [_shape_tuple_to_dict(shape) for shape in raw_shapes]
    except AnnotationConversionError:
        raise
    except (LabelFileError, YoloError, OSError, UnicodeError,
            ValueError, TypeError) as error:
        raise AnnotationConversionError(str(error))

    base_path = os.path.splitext(source_path)[0]
    target_path = base_path + (
        XML_EXT if target_format == FORMAT_PASCALVOC else YOLO_EXT)
    target_parent = os.path.dirname(os.path.abspath(target_path))
    if target_parent:
        os.makedirs(target_parent, exist_ok=True)

    try:
        if target_format == FORMAT_PASCALVOC:
            _write_pascal_voc(
                target_path, shapes, image_path, verified)
        else:
            save_yolo_annotations(
                target_path, shapes, image_width, image_height,
                class_names, target_format)
    except (LabelFileError, YoloError, OSError, UnicodeError, ValueError) as error:
        raise AnnotationConversionError(str(error))

    if (os.path.normcase(os.path.abspath(source_path)) !=
            os.path.normcase(os.path.abspath(target_path))):
        try:
            os.remove(source_path)
        except OSError as error:
            raise AnnotationConversionError(
                'Converted to %s but could not remove %s: %s' %
                (target_path, source_path, error))
    return target_path, len(shapes)

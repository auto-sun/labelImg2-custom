#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
"""Incremental annotation inspection helpers used by the GUI timer."""
from __future__ import absolute_import

import os
from collections import Counter

from .constants import (FORMAT_PASCALVOC, FORMAT_YOLO, FORMAT_YOLO_OBB)
from .pascal_voc_io import PascalVocReader, XML_EXT
from .yolo_obb_io import YOLO_EXT, YoloError, inspect_yolo_file


class AnnotationScanner(object):
    """Inspect individual labels; scheduling is handled by MainWindow."""

    def __init__(self, openedDir, annotationDir, preferredFormat):
        self.openedDir = (os.path.abspath(openedDir)
                          if openedDir else None)
        self.annotationDir = (os.path.abspath(annotationDir)
                              if annotationDir else None)
        self.preferredFormat = preferredFormat
        self.inspection = {
            'counts': Counter(),
            'newest_format': None,
            'newest_mtime': None,
            'empty_txt': 0,
            'errors': [],
            'cancelled': False,
        }

    def annotationBasePath(self, imagePath):
        if self.annotationDir:
            if self.openedDir:
                try:
                    relative = os.path.relpath(imagePath, self.openedDir)
                except ValueError:
                    relative = None
                if (relative is not None and relative != os.pardir and
                        not relative.startswith(os.pardir + os.sep) and
                        not os.path.isabs(relative)):
                    return os.path.join(
                        self.annotationDir, os.path.splitext(relative)[0])
            return os.path.join(
                self.annotationDir,
                os.path.splitext(os.path.basename(imagePath))[0])
        return os.path.splitext(imagePath)[0]

    def recordFormat(self, annotationFormat, modified):
        if annotationFormat not in (
                FORMAT_PASCALVOC, FORMAT_YOLO, FORMAT_YOLO_OBB):
            return
        inspection = self.inspection
        inspection['counts'][annotationFormat] += 1
        if (inspection['newest_mtime'] is None or
                modified > inspection['newest_mtime']):
            inspection['newest_mtime'] = modified
            inspection['newest_format'] = annotationFormat

    def inspectImage(self, imagePath):
        inspection = self.inspection
        basePath = self.annotationBasePath(imagePath)
        candidates = []

        xmlPath = basePath + XML_EXT
        if os.path.isfile(xmlPath):
            modified = os.path.getmtime(xmlPath)
            try:
                count = len(PascalVocReader(xmlPath).getShapes())
            except Exception as error:
                count = None
                inspection['errors'].append((xmlPath, str(error)))
            self.recordFormat(FORMAT_PASCALVOC, modified)
            candidates.append((FORMAT_PASCALVOC, modified, count))

        txtPath = basePath + YOLO_EXT
        if os.path.isfile(txtPath):
            modified = os.path.getmtime(txtPath)
            try:
                annotationFormat, count = inspect_yolo_file(txtPath)
                if annotationFormat is None and count == 0:
                    inspection['empty_txt'] += 1
                self.recordFormat(annotationFormat, modified)
                candidates.append((annotationFormat, modified, count))
            except (OSError, UnicodeError, YoloError, ValueError) as error:
                inspection['errors'].append((txtPath, str(error)))
                candidates.append((None, modified, None))

        if not candidates:
            return None
        selected = max(
            candidates,
            key=lambda item: (
                item[1], item[0] == self.preferredFormat))
        return selected[2]

    def inspectStandaloneFile(self, path):
        inspection = self.inspection
        extension = os.path.splitext(path)[1].lower()
        modified = os.path.getmtime(path)
        if extension == XML_EXT:
            self.recordFormat(FORMAT_PASCALVOC, modified)
            return
        if extension != YOLO_EXT:
            return
        try:
            annotationFormat, count = inspect_yolo_file(path)
            if annotationFormat is None and count == 0:
                inspection['empty_txt'] += 1
            self.recordFormat(annotationFormat, modified)
        except (OSError, UnicodeError, YoloError, ValueError) as error:
            inspection['errors'].append((path, str(error)))


def iter_annotation_files(directory):
    """Yield XML/TXT paths lazily without listing a huge tree at once."""
    if not directory or not os.path.isdir(directory):
        return
    pending = [os.path.abspath(directory)]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(entry.path)
                        elif (entry.is_file(follow_symlinks=False) and
                              os.path.splitext(entry.name)[1].lower() in
                              (XML_EXT, YOLO_EXT)):
                            yield entry.path
                    except OSError:
                        continue
        except OSError:
            continue

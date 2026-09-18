# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import re
import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from .constants import FORMAT_PASCALVOC
from .pascal_voc_io import PascalVocReader, XML_EXT
from .yolo_obb_io import YOLO_EXT, count_yolo_objects

_NATURAL_TOKEN_RE = re.compile(r'(\d+)')
PENDING_ANNOTATION_COUNT = -1

def natural_path_key(path):
    """Sort text alphabetically and every digit run by integer value."""
    normalized = str(path).replace('\\', '/').casefold()
    tokens = []
    for token in _NATURAL_TOKEN_RE.split(normalized):
        if not token:
            continue
        if token.isdigit():
            tokens.append((0, int(token), len(token)))
        else:
            tokens.append((1, token))
    return tuple(tokens)


class CFileListModel(QStringListModel):
    def __init__(self, parent = None):
        super(CFileListModel, self).__init__(parent)
        
        self.dispList = []
        self._totalAnnotationCount = 0

    @staticmethod
    def _pathKey(path):
        """Return a stable key for keeping per-image UI state on refresh."""
        return os.path.normcase(os.path.abspath(str(path)))
    
    def parseOne(self, s, openedDir=None, defaultSaveDir=None,
                 annotationFormat=FORMAT_PASCALVOC):
        if openedDir is not None and defaultSaveDir is not None:
            relname = os.path.relpath(s, openedDir)
            relname = os.path.splitext(relname)[0]
            annotationBasePath = os.path.join(defaultSaveDir, relname)
        else:
            annotationBasePath = os.path.splitext(s)[0]
        xmlPath = annotationBasePath + XML_EXT
        yoloPath = annotationBasePath + YOLO_EXT
        candidates = ((xmlPath, 'xml'), (yoloPath, 'txt'))
        if annotationFormat != FORMAT_PASCALVOC:
            candidates = tuple(reversed(candidates))

        for annotationPath, kind in candidates:
            if not os.path.isfile(annotationPath):
                continue
            try:
                if kind == 'xml':
                    count = len(PascalVocReader(annotationPath).getShapes())
                else:
                    count = count_yolo_objects(annotationPath)
            # A malformed annotation must not crash the recursive file-list
            # scan. Loading the image later shows the detailed parser error.
            except Exception:
                count = None
            return [os.path.split(s)[1], count, False]

        return [os.path.split(s)[1], None, False]

    def setStringList(self, strings, openedDir=None, defaultSaveDir=None,
                      annotationFormat=FORMAT_PASCALVOC,
                      scanAnnotations=True):
        # Rebuilding the list is necessary after model annotation and format
        # conversion so counts stay current. Keep the green confirmation
        # state for images that are still present; it is session UI state and
        # cannot be reconstructed from YOLO/YOLO OBB TXT files.
        visitedByPath = {}
        for path, info in zip(self.stringList(), self.dispList):
            if len(info) > 2 and info[2]:
                visitedByPath[self._pathKey(path)] = True

        self.dispList = []

        for s in strings:
            if scanAnnotations:
                info = self.parseOne(
                    s, openedDir, defaultSaveDir, annotationFormat)
            else:
                # Display the image immediately. Annotation counts are filled
                # by the background scanner so large projects never block the
                # GUI while every XML/TXT is opened.
                info = [os.path.split(s)[1],
                        PENDING_ANNOTATION_COUNT, False]
            info[2] = visitedByPath.get(self._pathKey(s), False)
            self.dispList.append(info)

        self._totalAnnotationCount = sum(
            info[1] for info in self.dispList
            if isinstance(info[1], int) and info[1] > 0)
        return super(CFileListModel, self).setStringList(strings)

    def updateAnnotationCount(self, row, imagePath, count):
        """Apply one background scan result without marking it verified."""
        if row < 0 or row >= len(self.dispList):
            return False
        index = self.index(row)
        modelPath = self.data(index, Qt.EditRole)
        if self._pathKey(modelPath) != self._pathKey(imagePath):
            return False
        info = self.dispList[row]
        oldCount = info[1] if isinstance(info[1], int) else 0
        newCount = count if isinstance(count, int) else None
        self._totalAnnotationCount -= max(0, oldCount)
        self._totalAnnotationCount += max(0, newCount or 0)
        info[1] = newCount
        self.dispList[row] = info
        self.dataChanged.emit(
            index, index, [Qt.DisplayRole, Qt.BackgroundRole])
        return True

    def resetAnnotationCounts(self):
        """Clear cached counts without rebuilding a large QStringListModel."""
        for info in self.dispList:
            info[1] = PENDING_ANNOTATION_COUNT
        self._totalAnnotationCount = 0
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0), self.index(self.rowCount() - 1),
                [Qt.DisplayRole, Qt.BackgroundRole])

    def annotationCount(self, index):
        """Return the cached object count for one image, or zero."""
        row = index.row() if index is not None else -1
        if row < 0 or row >= len(self.dispList):
            return 0
        count = self.dispList[row][1]
        return count if isinstance(count, int) and count > 0 else 0

    def totalAnnotationCount(self):
        """Return the total number of valid boxes cached by the file list."""
        return self._totalAnnotationCount

    def data(self, index, role):
        item = self.dispList[index.row()]
        pathname, count = item[0], item[1]
        if role == Qt.DisplayRole:
            if count == PENDING_ANNOTATION_COUNT:
                res_str = '%s […]' % (pathname,)
            elif count is None:
                res_str = '%s [0]' % (pathname,)
            else:
                if count == 0:
                    res_str = '%s [BG]' % (pathname,)
                else:
                    res_str = '%s [%d]' % (pathname, count)
            return res_str
        elif role == Qt.ToolTipRole:
            return super(CFileListModel, self).data(index, Qt.EditRole)
        elif role == Qt.BackgroundRole:
            if item[1] is None: # or item[1] == 0:
                brush = QBrush(Qt.transparent)
            else:
                brush = QBrush(Qt.lightGray)
            if item[2]:
                brush = QBrush(Qt.green)
            return brush
        else:
            return super(CFileListModel, self).data(index, role)

    def setData(self, index, value, role = None):

        if index.row() < 0:
            return super(CFileListModel, self).setData(index, value, role)

        if role == Qt.BackgroundRole:
            if index.row() < len(self.dispList):
                info = self.dispList[index.row()]
                oldCount = info[1] if isinstance(info[1], int) else 0
                newCount = value if isinstance(value, int) else 0
                self._totalAnnotationCount -= max(0, oldCount)
                self._totalAnnotationCount += max(0, newCount)
                info[1] = value
                info[2] = True
                self.dispList[index.row()] = info

        return super(CFileListModel, self).setData(index, value, role)


class CFileItemEditDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super(CFileItemEditDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        return editor


class CFileView(QListView):
    def __init__(self, parent = None):
        super(CFileView, self).__init__(parent)
        
        model = CFileListModel(self)
        self.setModel(model)

        delegate = CFileItemEditDelegate(self)
        self.setItemDelegateForColumn(0, delegate)
        
        


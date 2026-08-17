# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from .constants import FORMAT_PASCALVOC
from .pascal_voc_io import PascalVocReader, XML_EXT
from .yolo_obb_io import YOLO_EXT, count_yolo_objects

class CFileListModel(QStringListModel):
    def __init__(self, parent = None):
        super(CFileListModel, self).__init__(parent)
        
        self.dispList = []
    
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
                      annotationFormat=FORMAT_PASCALVOC):
        self.dispList = []

        for s in strings:
            info = self.parseOne(
                s, openedDir, defaultSaveDir, annotationFormat)
            self.dispList.append(info)

        return super(CFileListModel, self).setStringList(strings)

    def annotationCount(self, index):
        """Return the cached object count for one image, or zero."""
        row = index.row() if index is not None else -1
        if row < 0 or row >= len(self.dispList):
            return 0
        count = self.dispList[row][1]
        return count if isinstance(count, int) and count > 0 else 0

    def totalAnnotationCount(self):
        """Return the total number of valid boxes cached by the file list."""
        return sum(
            count for _name, count, _visited in self.dispList
            if isinstance(count, int) and count > 0)

    def data(self, index, role):
        item = self.dispList[index.row()]
        pathname, count = item[0], item[1]
        if role == Qt.DisplayRole:
            if count is None:
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
        
        


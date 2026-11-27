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
from .shortcut_input import disable_ime_for_shortcuts

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
        self._flaggedPaths = set()
        self._agentLocked = set()
        self._agentLockText = ''

    def setAgentLockedPaths(self, paths, tooltip):
        locked = {self._pathKey(p) for p in paths}
        if locked == self._agentLocked and tooltip == self._agentLockText:
            return
        self._agentLocked = locked
        self._agentLockText = tooltip
        if self.rowCount():
            self.dataChanged.emit(self.index(0),self.index(self.rowCount()-1),
                                  [Qt.DisplayRole,Qt.ForegroundRole,Qt.BackgroundRole,Qt.ToolTipRole])

    def isAgentLockedPath(self,path):
        return bool(path) and bool(self._agentLocked) and self._pathKey(path) in self._agentLocked

    def isAgentLocked(self,index):
        return index.isValid() and self.isAgentLockedPath(super().data(index,Qt.EditRole))

    def flags(self,index):
        flags=super().flags(index)
        if self.isAgentLocked(index):
            return flags & ~(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return flags

    @staticmethod
    def _pathKey(path):
        """Return a stable key for keeping per-image UI state on refresh."""
        return os.path.normcase(os.path.abspath(str(path)))
    
    def parseOne(self, s, openedDir=None, defaultSaveDir=None,
                 annotationFormat=FORMAT_PASCALVOC):
        if callable(getattr(self, 'annotationPathResolver', None)):
            annotationBasePath = self.annotationPathResolver(s)
        elif openedDir is not None and defaultSaveDir is not None:
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

    def setFlaggedPaths(self, paths):
        """Restore review marks by full path so sorting and refresh keep them."""
        self._flaggedPaths = {
            self._pathKey(path) for path in paths if isinstance(path, str)}
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0), self.index(self.rowCount() - 1),
                [Qt.BackgroundRole, Qt.ToolTipRole])

    def flaggedPaths(self):
        return sorted(self._flaggedPaths)

    def isFlagged(self, index):
        if index is None or not index.isValid():
            return False
        return self._pathKey(self.data(index, Qt.EditRole)) in self._flaggedPaths

    def setFlagged(self, index, flagged):
        if index is None or not index.isValid():
            return False
        key = self._pathKey(self.data(index, Qt.EditRole))
        if flagged:
            self._flaggedPaths.add(key)
        else:
            self._flaggedPaths.discard(key)
        self.dataChanged.emit(
            index, index, [Qt.BackgroundRole, Qt.ToolTipRole])
        return True

    def data(self, index, role):
        if not index.isValid() or not 0 <= index.row() < len(self.dispList):
            return None
        item = self.dispList[index.row()]
        pathname, count = item[0], item[1]
        locked = role in (Qt.DisplayRole,Qt.ToolTipRole,Qt.BackgroundRole) and self.isAgentLocked(index)
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
            return ('[MCP] ' if locked else '') + res_str
        elif role == Qt.ToolTipRole:
            path = super(CFileListModel, self).data(index, Qt.EditRole)
            if locked:
                return self._agentLockText + '\n' + path
            return (u'待确认标签\n%s' % path
                    if self.isFlagged(index) else path)
        elif role == Qt.BackgroundRole:
            if locked:
                return QBrush(QColor(218,218,218))
            if self.isFlagged(index):
                return QBrush(QColor(255, 210, 210))
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
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.BackgroundRole])
                return True

        return super(CFileListModel, self).setData(index, value, role)


class CFileItemEditDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super(CFileItemEditDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        return editor

    def paint(self, painter, option, index):
        if index.model().isFlagged(index) and not index.model().isAgentLocked(index):
            # Keep the review color visible even while this row is selected.
            option = QStyleOptionViewItem(option)
            option.palette.setColor(
                QPalette.Highlight, QColor(255, 210, 210))
            option.palette.setColor(
                QPalette.HighlightedText,
                option.palette.color(QPalette.Text))
        super(CFileItemEditDelegate, self).paint(painter, option, index)
        if option.state & QStyle.State_Selected:
            # The active image remains identifiable even when the canvas
            # takes focus or a review flag uses the same red as other rows.
            painter.save()
            painter.setPen(QPen(option.palette.color(QPalette.Active, QPalette.Highlight), 2)
                           if not index.model().isFlagged(index)
                           else QPen(QColor('#96363d'), 2))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()


class CFileView(QListView):
    deleteImageRequested = pyqtSignal()

    def __init__(self, parent = None):
        super(CFileView, self).__init__(parent)
        self.rightClickSelectionInProgress = False
        self._leftPressActive = False
        self._pendingCenter = False
        self._dragOrigin = None
        self._dragAnchor = None
        self._dragSelection = None
        self._dragAdd = False
        self._band = QRubberBand(QRubberBand.Rectangle,self.viewport())
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        model = CFileListModel(self)
        self.setModel(model)
        disable_ime_for_shortcuts(self)

        delegate = CFileItemEditDelegate(self)
        self.setItemDelegateForColumn(0, delegate)

    def focusInEvent(self, event):
        super(CFileView, self).focusInEvent(event)
        disable_ime_for_shortcuts(self)

    def scrollContentsBy(self, dx, dy):
        super(CFileView, self).scrollContentsBy(dx, dy)
        if dx or dy:
            # Qt normally copies the cached pixels and only repaints the
            # newly exposed strip. Redraw visible rows from the model as
            # well, so a stale Windows backing store cannot show old rows
            # at positions that already hit-test to new images.
            self.viewport().update()

    def currentChanged(self, current, previous):
        super(CFileView, self).currentChanged(current, previous)
        self.viewport().update()

    def centerCurrentRow(self, index):
        # QListView finishes its click selection on release. Moving the row
        # out from under the pointer before then can select a different row.
        if self._leftPressActive:
            self._pendingCenter = True
        else:
            self.scrollTo(index, QAbstractItemView.PositionAtCenter)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._dragOrigin is None:
            super().mouseReleaseEvent(event)
            return
        index = self.indexAt(self._dragOrigin)
        dragged = self._band.isVisible() or (
            (event.pos()-self._dragOrigin).manhattanLength() >= QApplication.startDragDistance())
        modifiers=event.modifiers()
        if dragged:
            self.updateRubberSelection(event.pos())
        elif index.isValid() and index.flags() & Qt.ItemIsSelectable:
            sm=self.selectionModel()
            if modifiers & Qt.ShiftModifier and self.currentIndex().isValid():
                self.selectRowsBetween(self.currentIndex().row(),index.row(),self._dragAdd)
            elif modifiers & Qt.ControlModifier:
                sm.select(index,QItemSelectionModel.Toggle)
            else:
                sm.setCurrentIndex(index,QItemSelectionModel.ClearAndSelect)
        self._band.hide()
        self._dragOrigin=self._dragAnchor=self._dragSelection=None
        self._leftPressActive=False
        if self._pendingCenter:
            self._pendingCenter=False
            self.centerCurrentRow(self.currentIndex())
        self.setFocus(Qt.MouseFocusReason)
        event.accept()

    def selectRowsBetween(self,first,last,add=False):
        model=self.model()
        selection=QItemSelection()
        begin=None
        for row in range(min(first,last),max(first,last)+2):
            idx=model.index(row)
            selectable=row<=max(first,last) and bool(idx.flags() & Qt.ItemIsSelectable)
            if selectable and begin is None:
                begin=idx
            elif not selectable and begin is not None:
                selection.select(begin,model.index(row-1))
                begin=None
        sm=self.selectionModel()
        if add and self._dragSelection is not None:
            sm.select(self._dragSelection,QItemSelectionModel.ClearAndSelect)
            sm.select(selection,QItemSelectionModel.Select)
        else:
            sm.select(selection,QItemSelectionModel.ClearAndSelect)

    def rowAtVertical(self,pos):
        if not self.model().rowCount():
            return None
        point=QPoint(self.viewport().rect().center().x(),
                     max(0,min(self.viewport().height()-1,pos.y())))
        index=self.indexAt(point)
        return index.row() if index.isValid() else self.model().rowCount()-1

    def updateRubberSelection(self,pos):
        row=self.rowAtVertical(pos)
        if self._dragAnchor is not None and row is not None:
            self.selectRowsBetween(self._dragAnchor,row,self._dragAdd)
        self._band.setGeometry(QRect(self._dragOrigin,pos).normalized())
        self._band.show()

    def mouseMoveEvent(self,event):
        if self._dragOrigin is not None:
            if (self._band.isVisible() or
                    (event.pos()-self._dragOrigin).manhattanLength()>=QApplication.startDragDistance()):
                self.updateRubberSelection(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def event(self, event):
        # The main window also uses Delete for removing selected boxes.  Claim
        # the shortcut only while File List itself has focus so the two
        # operations never conflict.
        if (event.type() == QEvent.ShortcutOverride and
                event.key() == Qt.Key_Delete):
            event.accept()
            return True
        return super(CFileView, self).event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.currentIndex().isValid():
            event.accept()
            self.deleteImageRequested.emit()
            return
        navigationKey = event.key() in (Qt.Key_Up, Qt.Key_Down)
        super(CFileView, self).keyPressEvent(event)
        if navigationKey and self.currentIndex().isValid():
            # Loading the new image focuses the canvas; keep keyboard list
            # navigation active so repeated Up/Down presses remain usable.
            self.setFocus(Qt.ShortcutFocusReason)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._leftPressActive=True
            self._pendingCenter=False
            self._dragOrigin=event.pos()
            self._dragAnchor=self.rowAtVertical(event.pos())
            self._dragAdd=bool(event.modifiers() & Qt.ControlModifier)
            self._dragSelection=self.selectionModel().selection() if self._dragAdd else None
            self.setFocus(Qt.MouseFocusReason)
            event.accept()
            return
        # Loading a newly clicked image gives focus to the canvas. Restore it
        # after the synchronous selection change so a following Delete key is
        # handled by File List, as the user expects.
        self.rightClickSelectionInProgress = event.button() == Qt.RightButton
        if self.rightClickSelectionInProgress:
            index=self.indexAt(event.pos())
            if self.selectionModel().isSelected(index) or self.model().isAgentLocked(index):
                self.rightClickSelectionInProgress=False
                self.setFocus(Qt.MouseFocusReason)
                event.accept()
                return
        self._leftPressActive = event.button() == Qt.LeftButton
        self._pendingCenter = False
        try:
            super(CFileView, self).mousePressEvent(event)
        finally:
            self.rightClickSelectionInProgress = False
        self.setFocus(Qt.MouseFocusReason)


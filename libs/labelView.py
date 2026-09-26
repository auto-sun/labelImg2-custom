# -*- coding: utf-8 -*-
from __future__ import absolute_import

import sys
from functools import lru_cache
from pypinyin import lazy_pinyin
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from .shortcut_input import disable_ime_for_shortcuts


@lru_cache(maxsize=4096)
def label_search_keys(label):
    """Match Chinese names by full pinyin and pinyin initials."""
    syllables = lazy_pinyin(label)
    return (label.casefold(),
            ''.join(syllables).casefold(),
            ''.join(syllable[:1] for syllable in syllables).casefold())

class HashableQStandardItem(QStandardItem):
    def __init__(self, text):
        super(HashableQStandardItem, self).__init__(text)

    def __hash__(self):
        return hash(id(self))


class CCommonOrderComboBox(QComboBox):
    searchTimeoutMs = 1200

    def __init__(self, parent=None):
        super(CCommonOrderComboBox, self).__init__(parent)
        disable_ime_for_shortcuts(self)
        self._lastSearchKey = None
        self._lastSearchTime = 0
        self._matchPosition = -1
        self._searchPrefix = ''
        self._shortcutLabels = {}

    def focusInEvent(self, event):
        super(CCommonOrderComboBox, self).focusInEvent(event)
        disable_ime_for_shortcuts(self)

    def setShortcutMappings(self, mappings):
        self._shortcutLabels = {
            str(mapping['shortcut']).casefold(): mapping['label']
            for mapping in mappings}

    def matchesPrefix(self, prefix):
        return [index for index in range(self.count())
                if any(key.startswith(prefix)
                       for key in label_search_keys(self.itemText(index)))]

    def keyPressEvent(self, event):
        shortcut = QKeySequence(
            int(event.modifiers()) | int(event.key())).toString(
                QKeySequence.PortableText).casefold()
        mappedLabel = self._shortcutLabels.get(shortcut)
        if mappedLabel is not None:
            index = self.findText(mappedLabel)
            if index >= 0:
                self.setCurrentIndex(index)
                event.accept()
                return

        text = event.text().casefold()
        if (len(text) == 1 and text.isalpha() and
                not event.modifiers() & (
                    Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            now = QDateTime.currentMSecsSinceEpoch()
            withinTimeout = now - self._lastSearchTime <= self.searchTimeoutMs
            repeated = (withinTimeout and text == self._lastSearchKey and
                        self._searchPrefix == text)
            prefix = (self._searchPrefix + text
                      if withinTimeout and self._searchPrefix and not repeated
                      else text)
            matches = self.matchesPrefix(prefix)
            if not matches and prefix != text:
                prefix = text
                matches = self.matchesPrefix(prefix)
            if matches:
                self._matchPosition = ((self._matchPosition + 1) % len(matches)
                                       if repeated else 0)
                self._searchPrefix = prefix
                self._lastSearchKey = text
                self._lastSearchTime = now
                self.setCurrentIndex(matches[self._matchPosition])
                event.accept()
                return
        super(CCommonOrderComboBox, self).keyPressEvent(event)


class CComboBoxDelegate(QStyledItemDelegate):
    editingActiveChanged = pyqtSignal(bool)
    labelChosen = pyqtSignal(str)

    def __init__(self, parent, listItem):
        super(CComboBoxDelegate, self).__init__(parent)
        self.listItem = listItem
        self.shortcutMappings = []

    def updateListItem(self, listItem):
        self.listItem = listItem

    def createEditor(self, parent, option, index):
        editor = CCommonOrderComboBox(parent)
        editor.setShortcutMappings(self.shortcutMappings)
        for i in self.listItem:
            editor.addItem(i)
        editor.currentIndexChanged.connect(self.editorIndexChanged)
        editor.setCurrentIndex(0)
        self.editingActiveChanged.emit(True)
        return editor

    def destroyEditor(self, editor, index):
        chosen = editor.currentText()
        if chosen:
            self.labelChosen.emit(chosen)
        self.editingActiveChanged.emit(False)
        return super(CComboBoxDelegate, self).destroyEditor(editor, index)

    # commit data early, prevent to loss data when clicking OpenNextImg
    def editorIndexChanged(self, index):
        combox = self.sender()
        self.commitData.emit(combox)

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole)
        if sys.version_info < (3, 0, 0):
            text = text.toPyObject()
        combox = editor
        combox.setProperty("initialLabel", text)
        tindex = combox.findText(text)
        combox.setCurrentIndex(tindex)

    def setModelData(self, editor, model, index):
        comboBox = editor
        strData = comboBox.currentText()
        oldstrData = index.model().data(index, Qt.EditRole)
        if strData != oldstrData:
            model.setData(index, strData, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class CEditDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super(CEditDelegate, self).__init__(parent)
        self.editor = None
        self.parent = parent
        
    def createEditor(self, parent, option, index):
        self.editor = QLineEdit(parent)
        self.editor.textEdited.connect(self.textEdited)
        return self.editor

    def textEdited(self, str):
        self.parent.extraChanged(str)

    def setEditorData(self, editor, index):
        return super(CEditDelegate, self).setEditorData(editor, index)

    def destroyEditor(self, editor, index):
        self.parent.extraChanged(index.data())
        ret = super(CEditDelegate, self).destroyEditor(editor, index)
        self.editor = None
        return ret

    def earlyCommit(self, index):
        if self.editor is not None:
            self.commitData.emit(self.editor)
            self.destroyEditor(self.editor, index)


class CHeaderView(QHeaderView):
    clicked = pyqtSignal(int, bool)
    _x_offset = 3
    _y_offset = 0 # This value is calculated later, based on the height of the paint rect
    _width = 20
    _height = 20

    def __init__(self, orientation, parent=None):
        super(CHeaderView, self).__init__(orientation, parent)
        self.setFixedWidth(40)
        self.isChecked = []

    def rowsInserted(self, parent, start, end):
        self.isChecked.insert(start, 1)
        return super(CHeaderView, self).rowsInserted(parent, start, end)

    def rowsAboutToBeRemoved(self, parent, start, end):
        del self.isChecked[start]
        return super(CHeaderView, self).rowsAboutToBeRemoved(parent, start, end)

    def setSectionChecked(self, logicalIndex, checked):
        if 0 <= logicalIndex < len(self.isChecked):
            self.isChecked[logicalIndex] = 1 if checked else 0
            self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        self._y_offset = int((rect.height()-self._width)/2.)
        
        option = QStyleOptionButton()
        option.state = QStyle.State_Enabled | QStyle.State_Active
        option.rect = QRect(rect.x() + self._x_offset, rect.y() + self._y_offset, self._width, self._height)
        
        if self.isChecked[logicalIndex]:
            option.state |= QStyle.State_On
        else:
            option.state |= QStyle.State_Off

        self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, option, painter)
        #self.style().drawControl(QStyle.CE_CheckBox, option, painter)
    
    def mouseReleaseEvent(self, e):
        index = self.logicalIndexAt(e.pos())
        
        if 0 <= index < self.count():
            # vertical orientation
            y = self.sectionViewportPosition(index)
            if self._x_offset < e.pos().x() < self._x_offset + self._width \
                and y + self._y_offset < e.pos().y() < y + self._y_offset + self._height:
                if self.isChecked[index] == 1:
                    self.isChecked[index] = 0
                else:
                    self.isChecked[index] = 1
                self.clicked.emit(index, self.isChecked[index])
                
                self.viewport().update()
            else:
                super(CHeaderView, self).mousePressEvent(e)
        else:
            super(CHeaderView, self).mousePressEvent(e)


class CLabelView(QTableView):
    extraEditing = pyqtSignal(QModelIndex, str)
    toggleEdit = pyqtSignal(bool)
    def __init__(self, labelHist, parent = None):
        super(CLabelView, self).__init__(parent)
        disable_ime_for_shortcuts(self)
        
        header = CHeaderView(Qt.Vertical, self)
        self.setVerticalHeader(header)

        self.label_delegate = CComboBoxDelegate(self, labelHist)
        self.setItemDelegateForColumn(0, self.label_delegate)
        self.extra_delegate = CEditDelegate(self)
        self.setItemDelegateForColumn(1, self.extra_delegate)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setStyleSheet("selection-background-color: rgb(0,90,140)")

        model = QStandardItemModel(self)
        model.setColumnCount(2)
        model.setHorizontalHeaderLabels(["Label", "Extra Info"])

        self.setModel(model)
        
        self.sm = self.selectionModel()

    def focusInEvent(self, event):
        super(CLabelView, self).focusInEvent(event)
        disable_ime_for_shortcuts(self)

    def extraChanged(self, str):
        self.extraEditing.emit(self.sm.currentIndex(), str)

    def earlyCommit(self):
        # TODO: verify currentIndex
        extra_index = self.model().index(self.sm.currentIndex().row(), 1)
        self.extra_delegate.earlyCommit(extra_index)

    def updateLabelList(self, labelHist):
        self.label_delegate.updateListItem(labelHist)

    def updateShortcutMappings(self, mappings):
        self.label_delegate.shortcutMappings = list(mappings)

    def keyPressEvent(self, e):
        key = e.key()
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            if self.extra_delegate.editor is None:
                self.toggleEdit.emit(True)
        return super(QTableView, self).keyPressEvent(e)

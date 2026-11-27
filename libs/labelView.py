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
    search_label = label.strip()
    syllables = lazy_pinyin(search_label)
    return (search_label.casefold(),
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
        text = event.text().casefold()
        now = QDateTime.currentMSecsSinceEpoch()
        withinTimeout = now - self._lastSearchTime <= self.searchTimeoutMs
        repeated = (withinTimeout and text == self._lastSearchKey and
                    self._searchPrefix == text)
        # An explicit shortcut wins on the first press. Repeating a letter
        # inside the category editor cycles all matching initials, including
        # Chinese pinyin, instead of trapping the user on the mapped label.
        if mappedLabel is not None and not (repeated and text.isalpha()):
            index = self.findText(mappedLabel)
            if index >= 0:
                self._lastSearchTime = now
                self._lastSearchKey = text
                self._searchPrefix = text
                matches = self.matchesPrefix(text) if text else []
                self._matchPosition = matches.index(index) if index in matches else -1
                self.setCurrentIndex(index)
                event.accept()
                return

        if (len(text) == 1 and text.isalpha() and
                not event.modifiers() & (
                    Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
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


class CLabelRowDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super(CLabelRowDelegate, self).sizeHint(option, index)
        size.setHeight(max(size.height(), option.fontMetrics.height() + 8))
        return size


class CComboBoxDelegate(CLabelRowDelegate):
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


class CEditDelegate(CLabelRowDelegate):
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





class CLabelView(QTreeView):
    extraEditing = pyqtSignal(QModelIndex, str)
    toggleEdit = pyqtSignal(bool)
    def __init__(self, labelHist, parent = None):
        super(CLabelView, self).__init__(parent)
        disable_ime_for_shortcuts(self)
        
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)
        self.setIndentation(16)
        self.setIconSize(QSize(11, 11))
        self.setAllColumnsShowFocus(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._preferredExtraWidth = None
        self._fittingColumns = False

        self.label_delegate = CComboBoxDelegate(self, labelHist)
        self.setItemDelegateForColumn(0, self.label_delegate)
        self.extra_delegate = CEditDelegate(self)
        self.setItemDelegateForColumn(1, self.extra_delegate)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

        model = QStandardItemModel(self)
        model.setColumnCount(2)
        model.setHorizontalHeaderLabels(["Label", "Extra Info"])

        self.setModel(model)
        self._configureColumns()
        self.header().sectionResized.connect(self._rememberExtraWidth)
        model.columnsInserted.connect(self._configureColumns)
        model.headerDataChanged.connect(self._fitExtraColumn)
        self.groups = {}
        model.modelReset.connect(self.groups.clear)
        
        self.sm = self.selectionModel()

    def _configureColumns(self, *_):
        header = self.header()
        if header.count() < 2:
            return
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self._fitExtraColumn()

    def _fitExtraColumn(self, *_):
        header = self.header()
        if header.count() < 2 or self._fittingColumns:
            return
        custom_width = self._preferredExtraWidth
        heading = self.model().headerData(1, Qt.Horizontal, Qt.DisplayRole) or ''
        default_width = max(84, header.fontMetrics().horizontalAdvance(str(heading)) + 18)
        limit = int(self.viewport().width() * (0.40 if custom_width else 0.30))
        width = max(header.minimumSectionSize(), min(custom_width or default_width, limit))
        if header.sectionSize(1) != width:
            self._fittingColumns = True
            try:
                header.resizeSection(1, width)
            finally:
                self._fittingColumns = False

    def _rememberExtraWidth(self, column, old_width, new_width):
        if column == 1 and old_width > 0 and not self._fittingColumns and self.header().count() == 2:
            self._preferredExtraWidth = new_width

    def resizeEvent(self, event):
        super(CLabelView, self).resizeEvent(event)
        self._fitExtraColumn()

    def clearLabels(self):
        # Clearing the model itself also removes its columns. Qt then
        # recreates them with default widths on the next image.
        self.groups.clear()
        model = self.model()
        if model.rowCount():
            model.removeRows(0, model.rowCount())

    @staticmethod
    def styleBoxItem(item, color):
        item.setData(color, Qt.DecorationRole)
        item.setToolTip(item.text())

    def focusInEvent(self, event):
        super(CLabelView, self).focusInEvent(event)
        disable_ime_for_shortcuts(self)

    def extraChanged(self, str):
        self.extraEditing.emit(self.sm.currentIndex(), str)

    def earlyCommit(self):
        # TODO: verify currentIndex
        current = self.sm.currentIndex()
        extra_index = current.sibling(current.row(), 1)
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
        return super(CLabelView, self).keyPressEvent(e)

    def groupFor(self, label):
        group = self.groups.get(label)
        if group is None:
            group = QStandardItem(label)
            group.setData(label, Qt.UserRole)
            group.setEditable(False)
            group.setCheckable(True)
            group.setCheckState(Qt.Checked)
            group.setToolTip(label)
            font = group.font()
            font.setBold(True)
            group.setFont(font)
            menu = QStandardItem('⋯  ▾')
            menu.setEditable(False)
            menu.setTextAlignment(Qt.AlignCenter)
            header_brush = self.palette().alternateBase()
            group.setBackground(header_brush)
            menu.setBackground(header_brush)
            self.groups[label] = group
            self.model().appendRow([group, menu])
        return group

    def updateGroup(self, group):
        count = group.rowCount()
        if not count:
            self.groups.pop(group.data(Qt.UserRole), None)
            self.model().removeRow(group.row())
            return
        group.setText('%s (%d)' % (group.data(Qt.UserRole), count))
        states = {group.child(i).checkState() for i in range(count)}
        group.setCheckState(states.pop() if len(states) == 1 else Qt.PartiallyChecked)

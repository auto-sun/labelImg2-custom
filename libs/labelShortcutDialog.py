#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog and validation helpers for custom label shortcuts."""
from __future__ import absolute_import

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                             QDialogButtonBox, QHBoxLayout, QHeaderView,
                             QLabel, QMessageBox, QPushButton,
                             QKeySequenceEdit, QTableWidget, QVBoxLayout)


class LabelShortcutValidationError(ValueError):
    pass


def canonical_shortcut(value):
    sequence = (value if isinstance(value, QKeySequence)
                else QKeySequence(str(value or '')))
    return sequence.toString(QKeySequence.PortableText)


def validate_label_shortcuts(mappings, class_names, reserved=None):
    """Validate and normalize a list of shortcut/label dictionaries."""
    class_names = tuple(class_names or ())
    allowed = set(class_names)
    reserved = {
        canonical_shortcut(shortcut): description
        for shortcut, description in (reserved or {}).items()
        if canonical_shortcut(shortcut)
    }
    normalized = []
    used = set()

    for row, mapping in enumerate(mappings or (), 1):
        shortcut = canonical_shortcut(mapping.get('shortcut', ''))
        label = str(mapping.get('label', ''))
        if not shortcut:
            raise LabelShortcutValidationError(
                u'第 %d 行尚未设置快捷键。' % row)
        if QKeySequence(shortcut).count() != 1:
            raise LabelShortcutValidationError(
                u'第 %d 行只能设置一个按键或组合键。' % row)
        if label not in allowed:
            raise LabelShortcutValidationError(
                u'第 %d 行的类别“%s”不在预设 class.txt 中。' %
                (row, label))
        key = shortcut.casefold()
        if key in used:
            raise LabelShortcutValidationError(
                u'快捷键“%s”被重复设置。' % shortcut)
        if shortcut in reserved:
            raise LabelShortcutValidationError(
                u'快捷键“%s”与现有功能“%s”冲突，不能设置。' %
                (shortcut, reserved[shortcut]))
        used.add(key)
        normalized.append({'shortcut': shortcut, 'label': label})
    return normalized


class LabelShortcutDialog(QDialog):
    def __init__(self, mappings, class_names, reserved=None, parent=None):
        super(LabelShortcutDialog, self).__init__(parent)
        self.classNames = list(class_names or [])
        self.reserved = dict(reserved or {})
        self.validatedMappings = []
        self.setWindowTitle(u'标签快捷键设置')
        self.setMinimumWidth(580)

        layout = QVBoxLayout(self)
        note = QLabel(
            u'设置“按键 → 预设类别”。按下快捷键后会直接进入该类别的 OBB '
            u'画框状态。快捷键不能与现有功能或其他映射冲突。')
        note.setWordWrap(True)
        layout.addWidget(note)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(
            [u'快捷键', u'预设类别', u'操作'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        rowButtons = QHBoxLayout()
        addButton = QPushButton(u'添加快捷键')
        addButton.clicked.connect(self.addRow)
        rowButtons.addWidget(addButton)
        rowButtons.addStretch(1)
        layout.addLayout(rowButtons)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        buttonBox.button(QDialogButtonBox.Save).setText(u'保存')
        buttonBox.button(QDialogButtonBox.Cancel).setText(u'取消')
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        for mapping in mappings or ():
            self.addRow(mapping.get('shortcut', ''), mapping.get('label'))

    def addRow(self, shortcut='', label=None):
        row = self.table.rowCount()
        self.table.insertRow(row)

        shortcutEditor = QKeySequenceEdit(self.table)
        shortcutEditor.setKeySequence(QKeySequence(str(shortcut or '')))
        self.table.setCellWidget(row, 0, shortcutEditor)

        labelEditor = QComboBox(self.table)
        labelEditor.addItems(self.classNames)
        if label in self.classNames:
            labelEditor.setCurrentIndex(self.classNames.index(label))
        self.table.setCellWidget(row, 1, labelEditor)

        removeButton = QPushButton(u'删除', self.table)
        removeButton.clicked.connect(
            lambda _checked=False, button=removeButton:
            self.removeButtonRow(button))
        self.table.setCellWidget(row, 2, removeButton)
        self.table.setCurrentCell(row, 0)
        shortcutEditor.setFocus(Qt.OtherFocusReason)

    def removeButtonRow(self, button):
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 2) is button:
                self.table.removeRow(row)
                return

    def mappings(self):
        result = []
        for row in range(self.table.rowCount()):
            shortcutEditor = self.table.cellWidget(row, 0)
            labelEditor = self.table.cellWidget(row, 1)
            result.append({
                'shortcut': canonical_shortcut(
                    shortcutEditor.keySequence()),
                'label': labelEditor.currentText(),
            })
        return result

    def accept(self):
        try:
            self.validatedMappings = validate_label_shortcuts(
                self.mappings(), self.classNames, self.reserved)
        except LabelShortcutValidationError as error:
            QMessageBox.warning(self, u'快捷键设置无效', str(error))
            return
        super(LabelShortcutDialog, self).accept()

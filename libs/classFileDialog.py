#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
"""Preview and select reusable class.txt files."""
from __future__ import absolute_import

import os

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
                             QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QComboBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)

from .ui_geometry import available_screen_geometry, responsive_dialog_size


class ClassFileError(ValueError):
    pass


def read_class_file(path):
    """Return class names while preserving their order and internal spaces."""
    path = os.path.abspath(os.path.expanduser(str(path or '')))
    if not path or not os.path.isfile(path):
        raise ClassFileError(u'类别文件不存在：%s' % (path or u'未选择'))

    raw = None
    decode_error = None
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            with open(path, 'r', encoding=encoding) as stream:
                raw = stream.read()
            break
        except UnicodeDecodeError as error:
            decode_error = error
    if raw is None:
        raise ClassFileError(
            u'无法读取类别文件，请将文件保存为 UTF-8 编码。%s' %
            (u'（%s）' % decode_error if decode_error else u''))

    class_names = []
    first_line = {}
    duplicates = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        name = line.strip()
        if not name:
            continue
        if '\x00' in name:
            raise ClassFileError(u'第 %d 行包含无效字符。' % line_number)
        if name in first_line:
            duplicates.append((name, first_line[name], line_number))
            continue
        first_line[name] = line_number
        class_names.append(name)

    if duplicates:
        name, first, repeated = duplicates[0]
        raise ClassFileError(
            u'类别“%s”重复（第 %d 行和第 %d 行）。请先去重。' %
            (name, first, repeated))
    if not class_names:
        raise ClassFileError(u'类别文件中没有可用类别。')
    return class_names


class ClassFileDialog(QDialog):
    """Choose a class file from disk or a persisted recent list."""
    MAX_HISTORY = 12

    def __init__(self, current_path=None, history_paths=None, parent=None):
        super(ClassFileDialog, self).__init__(parent)
        self.selectedPath = None
        self.classNames = []
        self.historyPaths = self.normalizeHistory(
            [current_path] + list(history_paths or []))

        self.setWindowTitle(u'选择类别文件')
        layout = QVBoxLayout(self)

        note = QLabel(
            u'选择一个 class.txt 作为当前项目的标注类别。类别 ID 按文件中的行序从 0 开始；'
            u'空行会忽略，类别名称中的内部空格会保留。')
        note.setWordWrap(True)
        layout.addWidget(note)

        selector = QHBoxLayout()
        selector.addWidget(QLabel(u'历史类别文件：'))
        self.historyCombo = QComboBox(self)
        self.historyCombo.setObjectName('classFileHistoryCombo')
        self.historyCombo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLength)
        self.historyCombo.setMinimumContentsLength(36)
        selector.addWidget(self.historyCombo, 1)
        self.browseButton = QPushButton(u'浏览...', self)
        self.removeButton = QPushButton(u'移出历史', self)
        selector.addWidget(self.browseButton)
        selector.addWidget(self.removeButton)
        layout.addLayout(selector)

        self.pathLabel = QLabel(self)
        self.pathLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pathLabel.setWordWrap(True)
        layout.addWidget(self.pathLabel)

        self.previewTable = QTableWidget(0, 2, self)
        self.previewTable.setObjectName('classFilePreviewTable')
        self.previewTable.setHorizontalHeaderLabels([u'ID', u'类别名称'])
        self.previewTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.previewTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.previewTable.verticalHeader().setVisible(False)
        header = self.previewTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.previewTable, 1)

        self.statusLabel = QLabel(self)
        layout.addWidget(self.statusLabel)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        self.applyButton = self.buttonBox.button(QDialogButtonBox.Open)
        self.applyButton.setText(u'使用此类别文件')
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(u'取消')
        layout.addWidget(self.buttonBox)

        self.browseButton.clicked.connect(self.browse)
        self.removeButton.clicked.connect(self.removeCurrentHistory)
        self.historyCombo.currentIndexChanged.connect(self.refreshPreview)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.rebuildHistoryCombo(current_path)
        available = available_screen_geometry(self).size()
        initial = responsive_dialog_size(
            available, minimum_desired=QSize(680, 500))
        self.setMinimumSize(min(560, initial.width()),
                            min(390, initial.height()))
        self.resize(initial)

    @classmethod
    def normalizeHistory(cls, paths):
        normalized = []
        seen = set()
        for path in paths or ():
            if not path:
                continue
            absolute = os.path.abspath(os.path.expanduser(str(path)))
            key = os.path.normcase(absolute)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(absolute)
            if len(normalized) >= cls.MAX_HISTORY:
                break
        return normalized

    def rebuildHistoryCombo(self, selected_path=None):
        selected_key = (os.path.normcase(os.path.abspath(str(selected_path)))
                        if selected_path else None)
        self.historyCombo.blockSignals(True)
        self.historyCombo.clear()
        selected_index = 0
        for index, path in enumerate(self.historyPaths):
            display = u'%s  —  %s' % (os.path.basename(path), path)
            self.historyCombo.addItem(display, path)
            self.historyCombo.setItemData(index, path, Qt.ToolTipRole)
            if selected_key == os.path.normcase(path):
                selected_index = index
        self.historyCombo.setCurrentIndex(
            selected_index if self.historyPaths else -1)
        self.historyCombo.blockSignals(False)
        self.refreshPreview()

    def currentPath(self):
        if self.historyCombo.currentIndex() < 0:
            return ''
        return str(self.historyCombo.currentData() or '')

    def browse(self, _checked=False):
        start = self.currentPath()
        if os.path.isfile(start):
            start_directory = os.path.dirname(start)
            initially_selected = start
        else:
            start_directory = (start if os.path.isdir(start)
                               else os.path.dirname(start))
            initially_selected = ''

        picker = self.createBrowseDialog(start_directory)
        if initially_selected:
            picker.selectFile(initially_selected)
        if not picker.exec_():
            return
        selected = picker.selectedFiles()
        if not selected:
            return
        path = os.path.abspath(selected[0])
        self.historyPaths = self.normalizeHistory(
            [path] + self.historyPaths)
        self.rebuildHistoryCombo(path)

    def createBrowseDialog(self, start_directory=''):
        """Use Windows Explorer's native picker, filtered to class TXT files."""
        picker = QFileDialog(self, u'选择 class.txt')
        # Set options before configuring the picker, as required by Qt.
        picker.setOption(QFileDialog.DontUseNativeDialog, False)
        if hasattr(QFileDialog, 'DontUseCustomDirectoryIcons'):
            picker.setOption(QFileDialog.DontUseCustomDirectoryIcons, True)
        picker.setAcceptMode(QFileDialog.AcceptOpen)
        picker.setFileMode(QFileDialog.ExistingFile)
        picker.setViewMode(QFileDialog.List)
        picker.setNameFilter(u'类别文件 (*.txt)')
        if start_directory and os.path.isdir(start_directory):
            picker.setDirectory(start_directory)
        return picker

    def removeCurrentHistory(self, _checked=False):
        path = self.currentPath()
        if not path:
            return
        key = os.path.normcase(path)
        self.historyPaths = [item for item in self.historyPaths
                             if os.path.normcase(item) != key]
        self.rebuildHistoryCombo()

    def refreshPreview(self, _index=-1):
        path = self.currentPath()
        self.pathLabel.setText(u'文件：%s' % (path or u'未选择'))
        self.previewTable.setRowCount(0)
        self.classNames = []
        try:
            self.classNames = read_class_file(path)
        except ClassFileError as error:
            self.statusLabel.setText(u'无法使用：%s' % error)
            self.statusLabel.setStyleSheet('color: #b00020;')
            self.applyButton.setEnabled(False)
            self.removeButton.setEnabled(bool(path))
            return

        self.previewTable.setRowCount(len(self.classNames))
        for row, name in enumerate(self.classNames):
            id_item = QTableWidgetItem(str(row))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.previewTable.setItem(row, 0, id_item)
            self.previewTable.setItem(row, 1, QTableWidgetItem(name))
        self.statusLabel.setStyleSheet('')
        self.statusLabel.setText(u'预览完成：共 %d 个类别。' % len(self.classNames))
        self.applyButton.setEnabled(True)
        self.removeButton.setEnabled(True)

    def accept(self):
        path = self.currentPath()
        try:
            class_names = read_class_file(path)
        except ClassFileError as error:
            QMessageBox.warning(self, u'类别文件无效', str(error))
            self.refreshPreview()
            return
        self.selectedPath = os.path.abspath(path)
        self.classNames = class_names
        self.historyPaths = self.normalizeHistory(
            [self.selectedPath] + self.historyPaths)
        super(ClassFileDialog, self).accept()

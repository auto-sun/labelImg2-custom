# -*- coding: utf-8 -*-
from __future__ import absolute_import

import sys
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from .lib import newIcon, labelValidator

BB = QDialogButtonBox


class CMyListModel(QStringListModel):
    def __init__(self, parent = None):
        super(CMyListModel, self).__init__(parent)
        self.rowColors = {}
        

    def data(self, index, role):
        if role == Qt.BackgroundRole:
            if index.row() in self.rowColors:
                return self.rowColors[index.row()]

        return super(CMyListModel, self).data(index, role)

    def setData(self, index, value, role = None):
        if role == Qt.BackgroundRole:
            self.rowColors[index.row()] = value
            return True

        return super(CMyListModel, self).setData(index, value, role)

    def flags(self, index):
        flags = super(CMyListModel, self).flags(index)
        flags ^= Qt.ItemIsEditable
        return flags


class LabelDialog(QDialog):
    defaultLabelChanged = pyqtSignal(str)

    def __init__(self, text="Enter object label", parent=None, listItem=None,
                 defaultLabel=None):
        super(LabelDialog, self).__init__(parent)

        self.edit = QLineEdit()
        self.edit.setText(text)
        self.edit.setValidator(labelValidator())
        self.edit.editingFinished.connect(self.postProcess)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.edit)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)

        self.horlayout = QHBoxLayout()
        self.setDefaultBtn = QPushButton("set as default")
        self.setDefaultBtn.clicked.connect(self.defaultLabel)
        self.addBtn = QPushButton("add")
        self.addBtn.clicked.connect(self.addLabel)
        self.horlayout.addWidget(self.addBtn)
        self.horlayout.addWidget(self.setDefaultBtn)

        self.listView = QListView(self)

        self.model = CMyListModel(self.listView)
        self.listView.setModel(self.model)

        self.sm = self.listView.selectionModel()
        self.default_label = defaultLabel
        self.updateListItems(listItem)
        
        
        self.layout.addWidget(self.listView)
        self.layout.addLayout(self.horlayout)
        self.layout.addWidget(bb)
        self.setLayout(self.layout)

    def updateListItems(self, listItem):
        self.model.setStringList(listItem or [])
        self.setDefaultLabel(self.default_label)

    def setDefaultLabel(self, label):
        labels = self.model.stringList()
        self.model.rowColors = {}
        if not labels:
            self.default_label = None
            return
        if label not in labels:
            label = labels[0]
        self.default_label = label
        index = self.model.index(labels.index(label))
        self.model.setData(index, QBrush(Qt.red), Qt.BackgroundRole)
        self.listView.setCurrentIndex(index)

    def addLabel(self):
        if not self.edit.text() in self.model.stringList():
            lastrow = self.model.rowCount()
            self.model.insertRows(lastrow, 1)
            self.model.setData(self.model.index(lastrow), self.edit.text(), Qt.EditRole)
            self.listView.setCurrentIndex(self.model.index(lastrow))


    def defaultLabel(self):
        curr = self.sm.currentIndex()
        if not curr.isValid():
            return
        label = self.model.data(curr, Qt.EditRole)
        if sys.version_info < (3, 0, 0):
            label = label.toPyObject()
        self.setDefaultLabel(label)
        self.defaultLabelChanged.emit(label)


    def validate(self):
        try:
            if self.edit.text().trimmed():
                self.accept()
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            if self.edit.text().strip():
                self.accept()

    def postProcess(self):
        try:
            self.edit.setText(self.edit.text().trimmed())
        except AttributeError:
            # PyQt5: AttributeError: 'str' object has no attribute 'trimmed'
            self.edit.setText(self.edit.text())

    def popUp(self, move=True):
        self.edit.setFocus(Qt.PopupFocusReason)
        if move:
            self.move(QCursor.pos())
        if self.exec_():
            return self.model.stringList(), self.default_label
        else:
            None


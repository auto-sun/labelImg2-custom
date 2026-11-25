"""Start screen for the empty annotation workspace."""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QScrollArea, QToolButton,
                             QVBoxLayout, QWidget)

from .lib import newIcon


class WelcomePage(QScrollArea):
    recentOpened = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        surface = QWidget()
        surface.setObjectName('welcomeSurface')
        self.setWidget(surface)
        outer = QHBoxLayout(surface)
        outer.setContentsMargins(28, 32, 28, 32)
        outer.addStretch(1)

        panel = QWidget()
        panel.setMaximumWidth(640)
        outer.addWidget(panel, 8, Qt.AlignTop)
        outer.addStretch(1)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title = QLabel('LabelImg2 Custom')
        title.setObjectName('welcomeTitle')
        title.setWordWrap(True)
        layout.addWidget(title)
        subtitle = QLabel('Open a dataset to start annotating.')
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        start = QLabel('Start')
        start.setProperty('welcomeHeading', True)
        layout.addWidget(start)
        self.openFolder = self.addEntry(layout, 'Open Dir', 'dir.svg')
        self.openImage = self.addEntry(layout, 'Open Image', 'open.svg')
        self.help = self.addEntry(layout, 'User Guide', 'info.svg')

        layout.addSpacing(14)
        recent = QLabel('Recent Work')
        recent.setProperty('welcomeHeading', True)
        layout.addWidget(recent)
        self.emptyRecent = QLabel('Recently opened folders and images will appear here.')
        self.emptyRecent.setWordWrap(True)
        layout.addWidget(self.emptyRecent)
        self.recent = QListWidget()
        self.recent.setAlternatingRowColors(True)
        self.recent.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.recent.itemActivated.connect(self.openRecent)
        layout.addWidget(self.recent)
        layout.addStretch()

        self.setStyleSheet("""
            QWidget#welcomeSurface { background: palette(window); }
            QLabel#welcomeTitle { font-size: 30px; font-weight: 700; }
            QLabel[welcomeHeading="true"] { font-size: 17px; font-weight: 700; }
            QToolButton {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 9px 14px;
            }
            QToolButton:hover { background: palette(alternate-base); }
            QToolButton:focus { border: 2px solid palette(highlight); padding: 8px 13px; }
            QListWidget { border: 1px solid palette(mid); border-radius: 6px; }
            QListWidget::item { padding: 7px 10px; }
        """)

    @staticmethod
    def addEntry(layout, text, icon):
        button = QToolButton()
        button.setText(text)
        button.setIcon(newIcon(icon))
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        button.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(button, alignment=Qt.AlignLeading)
        return button

    def setRecentPaths(self, paths):
        self.recent.clear()
        for path in paths:
            name = os.path.basename(os.path.normpath(path)) or path
            icon = 'dir.svg' if os.path.isdir(path) else 'open.svg'
            item = QListWidgetItem(newIcon(icon), '%s     %s' % (name, path))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.recent.addItem(item)
        self.emptyRecent.setVisible(not paths)
        self.recent.setVisible(bool(paths))
        if paths:
            self.recent.setFixedHeight(
                self.recent.sizeHintForRow(0) * len(paths) + 4)

    def openRecent(self, item):
        self.recentOpened.emit(item.data(Qt.UserRole))

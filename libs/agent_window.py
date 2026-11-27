"""Non-modal, read-only task monitor; never edits the manual annotation canvas."""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QSplitter, QVBoxLayout, QWidget)
from .window_motion import MotionDialog


class AgentPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 150)
        self.image = None
        self.original = (1, 1)
        self.boxes = {}

    def setImage(self, image=None, size=(1, 1)):
        self.image, self.original = image, size
        self.clearBoxes()

    def clearBoxes(self):
        self.boxes.clear()
        self.update()

    def showBox(self, slot, label, points):
        self.boxes[slot] = (label, points)
        self.update()
        return len(self.boxes)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#22262c'))
        if self.image is None:
            return
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        width, height = self.original
        scale = min(self.width() / width, self.height() / height)
        origin = QPointF((self.width() - width * scale) / 2,
                         (self.height() - height * scale) / 2)
        painter.drawImage(QRectF(origin.x(), origin.y(), width * scale, height * scale), self.image)
        pen = QPen(QColor('#4cf1f4'), 2, Qt.DashLine)
        for slot, (label, points) in self.boxes.items():
            polygon = QPolygonF([origin + QPointF(x * scale, y * scale) for x, y in points])
            painter.setPen(pen)
            painter.drawPolygon(polygon)
            point = polygon.boundingRect().topLeft()
            painter.setPen(QColor('#4cf1f4'))
            painter.drawText(point + QPointF(3, 14), '#%d %s' % (slot, label))


class AgentTaskWindow(MotionDialog):
    def __init__(self, window, stop):
        super().__init__(window, Qt.Window)
        self.setModal(False)
        self.resize(860, 530)
        self.title = QLabel()
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.files = QListWidget()
        self.files.setUniformItemSizes(True)
        self.files.setSelectionMode(QListWidget.NoSelection)
        self.preview = AgentPreview()
        splitter = QSplitter()
        splitter.addWidget(self.files)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 620])
        self.collapse = QPushButton()
        self.collapse.clicked.connect(self.collapseAnimated)
        self.stop = QPushButton()
        self.stop.clicked.connect(stop)
        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(self.collapse)
        controls.addWidget(self.stop)
        main = QVBoxLayout(self)
        main.addWidget(self.title)
        main.addWidget(splitter, 1)
        main.addLayout(controls)
        self._paths = []

    def setFiles(self, relative_paths):
        self._paths = list(relative_paths)
        self.files.clear()
        self.files.addItems(self._paths)
        self.preview.setImage()

    def updateRows(self, frames, active_seq, translate):
        for frame in frames:
            row = frame['seq']
            item = self.files.item(row)
            if item is None:
                continue
            state = frame['state']
            status = {
                'annotated': 'Saved', 'empty': 'Empty annotation',
                'review': 'Needs review', 'skipped': 'Skipped',
            }.get(state)
            item.setText(('%s · ' % translate(status) if status else '') + self._paths[row])
            item.setToolTip(self._paths[row])
        if active_seq is not None:
            current = self.files.item(active_seq)
            if current is not None:
                current.setText('▶ ' + self._paths[active_seq])
                self.files.scrollToItem(current, QListWidget.PositionAtCenter)

"""Non-modal, read-only task monitor; never edits the manual annotation canvas."""
from PyQt5.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QAbstractScrollArea, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget)
from .ui_geometry import available_screen_geometry, recover_window_frame, screen_work_areas
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
        self._placement_timer = QTimer(self, singleShot=True)
        self._placement_timer.timeout.connect(self.ensureOnScreen)
        self.title = QLabel()
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.files = QListWidget()
        self.files.setUniformItemSizes(True)
        self.files.setSelectionMode(QListWidget.NoSelection)
        self.files.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.files.setTextElideMode(Qt.ElideMiddle)
        self.files.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.files.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.files.setMinimumWidth(120)
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

    def ensureOnScreen(self):
        if not self.isVisible() or self.isMinimized():
            return False
        frame = self.frameGeometry()
        areas = screen_work_areas()
        # Windows can extend the invisible resize border of a genuine
        # maximized window a few logical pixels beyond the work area.
        if self.isMaximized() and any(area.adjusted(-16, -16, 16, 16).contains(frame)
                                     for area in areas):
            return False
        destination = recover_window_frame(frame, areas, available_screen_geometry(self))
        if destination == frame:
            return False

        animator = self.animator()
        if animator is not None:
            animator.finish(self)
        self.setWindowOpacity(1)
        if self.isMaximized():
            self.showNormal()
        decorations = self.frameSize() - self.size()
        content = destination.size() - decorations
        self.resize(content.expandedTo(QSize(1, 1)))
        self.move(destination.topLeft())
        return True

    def present(self, interactive=False):
        was_visible = self.isVisible() and not self.isMinimized()
        animator = self.animator()
        if animator is not None:
            animator.finish(self)
        self.setAttribute(Qt.WA_ShowWithoutActivating, not interactive)
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        moved = self.ensureOnScreen()
        # Recheck once after native maximize/restore and DPI events settle.
        self._placement_timer.start(0)
        if interactive:
            self.raise_()
            self.activateWindow()
            if animator is not None and not was_visible and not moved:
                animator.play(self, self.motionAnchor, opening=True)

    def showAnimated(self):
        self.present(interactive=True)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, '_placement_timer'):
            self._placement_timer.start(0)

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

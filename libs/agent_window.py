"""Non-modal, read-only task monitor; never edits the manual annotation canvas."""
from PyQt5.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QGuiApplication, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QAbstractScrollArea, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget)
from .ui_geometry import (available_screen_geometry, reachable_window_title, recover_window_frame,
                          screen_work_areas, squashed_task_window)
from .window_motion import MotionDialog
from .windows_window_placement import windows_window_placement


def format_duration(seconds, tenths=False):
    total, tenth = divmod(round(seconds * 10) if tenths else int(seconds) * 10, 10)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    text = '%02d:%02d:%02d' % (hours, minutes, seconds)
    return '%s.%d' % (text, tenth) if tenths else text


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
    _PREFERRED_SIZE = QSize(860, 530)

    def __init__(self, window, stop):
        super().__init__(window, Qt.Window)
        self.setModal(False)
        self.resize(self._PREFERRED_SIZE)
        self._last_normal_size = QSize(self._PREFERRED_SIZE)
        self._placement_window = None
        self._placement_timer = QTimer(self, singleShot=True, interval=120)
        self._placement_timer.timeout.connect(self.ensureOnScreen)
        # A native DPI restore can move the frame again after Qt's last geometry
        # event. Watch only while visible so even that move gets picked up.
        self._placement_watch = QTimer(self, interval=750, timerType=Qt.CoarseTimer)
        self._placement_watch.timeout.connect(self.ensureOnScreen)
        self.title = QLabel()
        self.title.setTextFormat(Qt.PlainText)
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.timing = QLabel()
        self.timing.setTextFormat(Qt.PlainText)
        self.timing.setWordWrap(True)
        self.timing.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
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
        main.addWidget(self.timing)
        main.addWidget(splitter, 1)
        main.addLayout(controls)
        self._paths = []

    def setTiming(self, elapsed, average, translate):
        total_text = translate('Total elapsed: {time}').format(time=format_duration(elapsed))
        avg_text = translate('Average per image: {time}').format(
            time=format_duration(average, tenths=True) if average is not None else '—')
        text = total_text + '   ·   ' + avg_text
        if self.timing.text() != text:
            self.timing.setText(text)

    def _prepareForRecovery(self):
        animator = self.animator()
        if animator is not None:
            animator.finish(self)
        self.setWindowOpacity(1)
        if self.isMaximized():
            self.showNormal()

    def _rememberNormalSize(self, frame, area, scale, maximized):
        if maximized or self._placement_timer.isActive() or not area.contains(frame):
            return
        # Keep a logical size, not the previous monitor's physical pixels.
        # Ignore undersized transition frames before they can replace it.
        if (frame.width() >= min(round(450 * scale), area.width() // 2)
                and frame.height() >= min(round(300 * scale), area.height() // 2)):
            self._last_normal_size = QSize(round(frame.width() / scale),
                                           round(frame.height() / scale))

    def ensureOnScreen(self):
        owner = self.parentWidget()
        if not self.isVisible() or self.isMinimized() or (owner is not None and owner.isMinimized()):
            return False
        maximized = self.isMaximized() or self.isFullScreen()
        native = windows_window_placement() if QGuiApplication.platformName() == 'windows' else None
        if native is not None and owner is not None:
            hwnd = int(self.winId())
            geometry = native.geometry(hwnd)
            if geometry is not None:
                if native.dragging():
                    return False
                maximized = maximized or geometry.maximized
                if geometry.title_reachable:
                    if not maximized and squashed_task_window(
                            geometry.frame, geometry.work_area, geometry.scale):
                        self._prepareForRecovery()
                        if native.center_on_window_screen(hwnd, hwnd, self._last_normal_size):
                            return True
                    else:
                        self._rememberNormalSize(geometry.frame, geometry.work_area,
                                                 geometry.scale, maximized)
                        return False
                else:
                    self._prepareForRecovery()
                    if native.center_on_window_screen(hwnd, int(owner.winId()), self._PREFERRED_SIZE):
                        return True

        frame = self.frameGeometry()
        areas = screen_work_areas()
        if QGuiApplication.mouseButtons() & Qt.LeftButton:
            return False
        if reachable_window_title(frame, areas):
            handle = self.windowHandle()
            screen = handle.screen() if handle is not None else None
            area = screen.availableGeometry() if screen else available_screen_geometry(self)
            if maximized or not squashed_task_window(frame, area):
                self._rememberNormalSize(frame, area, 1, maximized)
                return False
            destination = recover_window_frame(QRect(), (), area, self._last_normal_size)
        else:
            destination = recover_window_frame(frame, areas, available_screen_geometry(self))
        if destination == frame:
            return False

        self._prepareForRecovery()
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
        self._schedulePlacementCheck()
        if interactive:
            self.raise_()
            self.activateWindow()
            if animator is not None and not was_visible and not moved:
                animator.play(self, self.motionAnchor, opening=True)

    def showAnimated(self):
        self.present(interactive=True)

    def _schedulePlacementCheck(self, *_):
        if self.isVisible() and not self.isMinimized():
            self._placement_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None and handle is not self._placement_window:
            handle.screenChanged.connect(self._schedulePlacementCheck)
            self._placement_window = handle
        self._placement_watch.start()
        self._schedulePlacementCheck()

    def hideEvent(self, event):
        self._placement_watch.stop()
        self._placement_timer.stop()
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._schedulePlacementCheck()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedulePlacementCheck()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, '_placement_timer'):
            self._schedulePlacementCheck()

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

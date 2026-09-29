import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication, QScrollArea
from libs.canvas import Canvas


class CanvasPanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.area = QScrollArea()
        self.area.resize(500, 400)
        self.canvas = Canvas()
        image = QPixmap(2400, 1800)
        image.fill(Qt.white)
        self.canvas.loadPixmap(image)
        self.canvas.resize(image.size())
        self.area.setWidget(self.canvas)
        self.h = self.area.horizontalScrollBar()
        self.v = self.area.verticalScrollBar()
        self.canvas.panRequest.connect(self.scroll)
        self.area.show()
        self.app.processEvents()
        self.h.setValue(700)
        self.v.setValue(500)
        self.start = self.area.viewport().mapToGlobal(QPoint(200, 160))

    def tearDown(self):
        self.area.close()
        self.canvas.restoreCursor()

    def scroll(self, dx, dy):
        self.h.setValue(self.h.value() + dx)
        self.v.setValue(self.v.value() + dy)

    def event(self, kind, screen):
        local = QPointF(self.canvas.mapFromGlobal(screen))
        buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
        button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
        event = QMouseEvent(kind, local, QPointF(screen), button, buttons, Qt.AltModifier)
        QApplication.sendEvent(self.canvas, event)

    def test_each_screen_move_scrolls_by_full_delta(self):
        for scale in (1.0, 1.75):
            with self.subTest(scale=scale):
                self.canvas.scale = scale
                self.h.setValue(700)
                self.v.setValue(500)
                self.event(QEvent.MouseButtonPress, self.start)
                moved = QSignalSpy(self.canvas.shapeMoved)
                for step in range(1, 16):
                    self.event(QEvent.MouseMove, self.start + QPoint(step * 5, step * 3))
                    self.assertEqual(700 - step * 5, self.h.value())
                    self.assertEqual(500 - step * 3, self.v.value())
                self.event(QEvent.MouseButtonRelease, self.start + QPoint(75, 45))
                self.assertEqual(0, len(moved))

    def test_stationary_pointer_does_not_bounce_after_canvas_moves(self):
        self.event(QEvent.MouseButtonPress, self.start)
        screen = self.start + QPoint(15, 10)
        self.event(QEvent.MouseMove, screen)
        for _ in range(5):
            self.event(QEvent.MouseMove, screen)
            self.assertEqual((685, 490), (self.h.value(), self.v.value()))

    def test_reverse_immediately_after_reaching_scroll_boundary(self):
        self.h.setValue(4)
        self.event(QEvent.MouseButtonPress, self.start)
        self.event(QEvent.MouseMove, self.start + QPoint(10, 0))
        self.assertEqual(0, self.h.value())
        self.event(QEvent.MouseMove, self.start + QPoint(20, 0))
        self.assertEqual(0, self.h.value())
        self.event(QEvent.MouseMove, self.start + QPoint(17, 0))
        self.assertEqual(3, self.h.value())

    def test_release_applies_last_motion_without_an_extra_move_event(self):
        self.event(QEvent.MouseButtonPress, self.start)
        self.event(QEvent.MouseButtonRelease, self.start + QPoint(7, 4))
        self.assertEqual((693, 496), (self.h.value(), self.v.value()))
        self.assertFalse(self.canvas._panning)


if __name__ == '__main__':
    unittest.main()

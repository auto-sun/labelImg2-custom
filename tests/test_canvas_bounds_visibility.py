# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from libs.canvas import Canvas
from libs.shape import Shape


def make_shape(points, rotated=True):
    shape = Shape(label='person')
    for x, y in points:
        shape.addPoint(QPointF(x, y))
    shape.isRotated = rotated
    shape.close()
    return shape


class CanvasBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = Canvas()
        self.canvas.resize(200, 200)
        self.canvas.loadPixmap(QPixmap(100, 100))

    def test_rotated_shape_movement_is_clamped_by_all_vertices(self):
        shape = make_shape(((5, 5), (35, 15), (30, 40), (0, 30)))
        self.canvas.shapes = [shape]
        self.canvas.prevPoint = QPointF(10, 10)

        self.assertTrue(self.canvas.boundedMoveShape(shape, QPointF(80, 90)))
        self.assertGreaterEqual(min(p.x() for p in shape.points), 0)
        self.assertGreaterEqual(min(p.y() for p in shape.points), 0)
        self.assertLessEqual(max(p.x() for p in shape.points), 100)
        self.assertLessEqual(max(p.y() for p in shape.points), 100)

    def test_group_translation_clamps_the_whole_selection(self):
        first = make_shape(((5, 5), (25, 5), (25, 20), (5, 20)))
        second = make_shape(((35, 20), (55, 15), (60, 35), (40, 40)))

        delta = self.canvas._boundedTranslation(
            [first, second], QPointF(-30, 200))

        self.assertEqual(QPointF(-5, 60), delta)
        for point in first.points + second.points:
            self.assertGreaterEqual(point.x() + delta.x(), 0)
            self.assertLessEqual(point.x() + delta.x(), 100)
            self.assertGreaterEqual(point.y() + delta.y(), 0)
            self.assertLessEqual(point.y() + delta.y(), 100)

    def test_rectangle_started_outside_is_snapped_inside(self):
        self.canvas.canDrawRotatedRect = True
        self.canvas.handleDrawing(QPointF(-25, 12))
        self.assertIsNotNone(self.canvas.current)
        self.canvas.line[1] = QPointF(35, 65)
        self.canvas.handleDrawing(QPointF(35, 65))

        self.assertEqual(1, len(self.canvas.shapes))
        for point in self.canvas.shapes[0].points:
            self.assertGreaterEqual(point.x(), 0)
            self.assertLessEqual(point.x(), 100)
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y(), 100)

    def test_marquee_can_start_in_canvas_outside_image(self):
        self.canvas.show()
        QApplication.processEvents()
        # The image is centered in this widget. x=10 maps to image x=-40.
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=QPoint(10, 60))

        self.assertIsNotNone(self.canvas._marqueeStart)
        self.assertLess(self.canvas._marqueeStart.x(), 0)
        self.canvas._clearMarqueeSelection()
        self.canvas.close()


if __name__ == '__main__':
    unittest.main()

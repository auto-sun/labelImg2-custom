#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import math
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QPainterPath, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from libs.canvas import Canvas
from libs.shape import Shape


class CornerHandleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_and_hovered_handles_are_larger(self):
        shape = Shape()
        shape.addPoint(QPointF(50, 50))
        shape.scale = 1.0

        normal = QPainterPath()
        shape.drawVertex(normal, 0)
        self.assertAlmostEqual(12.0, normal.boundingRect().width())

        shape.highlightVertex(0, shape.MOVE_VERTEX)
        hovered = QPainterPath()
        shape.drawVertex(hovered, 0)
        self.assertAlmostEqual(21.0, hovered.boundingRect().width())

    def test_hit_radius_stays_constant_in_screen_pixels(self):
        canvas = Canvas()
        for scale in (0.25, 0.5, 1.0, 2.0, 4.0):
            canvas.scale = scale
            self.assertAlmostEqual(
                canvas.VERTEX_HIT_RADIUS,
                canvas.vertexHitRadius() * scale)

    def test_hit_radius_is_larger_than_old_seven_pixel_target(self):
        canvas = Canvas()
        canvas.scale = 1.0
        self.assertEqual(12.0, canvas.vertexHitRadius())
        self.assertGreater(canvas.vertexHitRadius(), canvas.epsilon)

    def test_border_corner_can_resize_when_drag_pointer_goes_outside(self):
        canvas = Canvas()
        canvas.loadPixmap(QPixmap(100, 100))
        cases = (
            (((0, 20), (80, 20), (80, 90), (0, 90)), 0,
             (-10, 30), (0, 30)),
            (((20, 20), (100, 20), (100, 90), (20, 90)), 1,
             (110, 30), (100, 30)),
            (((20, 10), (100, 10), (100, 100), (20, 100)), 2,
             (110, 80), (100, 80)),
            (((0, 10), (80, 10), (80, 100), (0, 100)), 3,
             (-10, 80), (0, 80)),
        )

        for points, index, drag_to, expected in cases:
            with self.subTest(index=index):
                shape = Shape(label='edge')
                for x, y in points:
                    shape.addPoint(QPointF(x, y))
                shape.direction = 0.0
                shape.close()
                canvas.shapes = [shape]
                canvas.hShape = shape
                canvas.hVertex = index

                canvas.boundedMoveVertex(QPointF(*drag_to))

                self.assertEqual(QPointF(*expected), shape.points[index])
                for point in shape.points:
                    self.assertGreaterEqual(point.x(), 0)
                    self.assertLessEqual(point.x(), 100)
                    self.assertGreaterEqual(point.y(), 0)
                    self.assertLessEqual(point.y(), 100)

    def test_mouse_drag_on_image_edge_corner_remains_responsive(self):
        parent = QWidget()
        parent.filePath = None
        canvas = Canvas(parent)
        canvas.resize(200, 200)
        canvas.loadPixmap(QPixmap(100, 100))
        shape = Shape(label='edge')
        for x, y in ((0, 20), (80, 20), (80, 90), (0, 90)):
            shape.addPoint(QPointF(x, y))
        shape.direction = 0.0
        shape.close()
        canvas.shapes = [shape]

        # The 100x100 image is centered in the 200x200 canvas. Start on its
        # left-edge corner, then drag outside while changing the box height.
        canvas.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, QPointF(50, 70), Qt.NoButton, Qt.NoButton,
            Qt.NoModifier))
        self.assertEqual(0, canvas.hVertex)
        self.assertIs(shape, canvas.hShape)
        canvas.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, QPointF(50, 70), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        canvas.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, QPointF(40, 80), Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
        canvas.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(40, 80), Qt.LeftButton,
            Qt.NoButton, Qt.NoModifier))

        self.assertEqual(QPointF(0, 30), shape.points[0])

    def test_first_corner_drag_after_image_switch_needs_no_hover_move(self):
        parent = QWidget()
        parent.filePath = None
        canvas = Canvas(parent)
        canvas.resize(200, 200)
        canvas.loadPixmap(QPixmap(100, 100))
        old_shape = Shape(label='old')
        for x, y in ((10, 10), (40, 10), (40, 40), (10, 40)):
            old_shape.addPoint(QPointF(x, y))
        old_shape.close()
        canvas.shapes = [old_shape]
        canvas.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, QPointF(60, 60), Qt.NoButton, Qt.NoButton,
            Qt.NoModifier))
        self.assertIs(old_shape, canvas.hShape)

        # The mouse remains still while a new image and its boxes are loaded;
        # no hover event is sent before clicking the new box's edge corner.
        canvas.loadPixmap(QPixmap(100, 100))
        new_shape = Shape(label='new')
        for x, y in ((0, 20), (80, 20), (80, 90), (0, 90)):
            new_shape.addPoint(QPointF(x, y))
        new_shape.close()
        canvas.shapes = [new_shape]
        canvas.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, QPointF(50, 70), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        canvas.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, QPointF(40, 80), Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
        canvas.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(40, 80), Qt.LeftButton,
            Qt.NoButton, Qt.NoModifier))

        self.assertEqual(QPointF(0, 30), new_shape.points[0])
        self.assertIsNot(old_shape, canvas.hShape)

    def test_rotated_edge_corner_resize_stays_inside_image(self):
        canvas = Canvas()
        canvas.loadPixmap(QPixmap(100, 100))
        shape = Shape(label='rotated-edge')
        for x, y in ((0, 50), (50, 25), (100, 50), (50, 75)):
            shape.addPoint(QPointF(x, y))
        shape.direction = math.atan2(-25, 50)
        shape.close()
        canvas.shapes = [shape]
        canvas.hShape = shape
        canvas.hVertex = 0

        canvas.boundedMoveVertex(QPointF(-20, 30))

        self.assertNotEqual(QPointF(0, 50), shape.points[0])
        for point in shape.points:
            self.assertGreaterEqual(point.x(), 0)
            self.assertLessEqual(point.x(), 100)
            self.assertGreaterEqual(point.y(), 0)
            self.assertLessEqual(point.y(), 100)

    def test_all_corners_resize_for_edge_box_with_cardinal_directions(self):
        cases = (
            (math.pi, ((80, 80), (0, 80), (0, 0), (80, 0))),
            (math.pi / 2, ((80, 0), (80, 80), (0, 80), (0, 0))),
        )

        for direction, points in cases:
            for index, (x, y) in enumerate(points):
                with self.subTest(direction=direction, index=index):
                    canvas = Canvas()
                    canvas.loadPixmap(QPixmap(100, 100))
                    shape = Shape(label='edge-cardinal')
                    for px, py in points:
                        shape.addPoint(QPointF(px, py))
                    shape.direction = direction
                    shape.close()
                    canvas.shapes = [shape]
                    canvas.hShape = shape
                    canvas.hVertex = index

                    target = QPointF(x + 10, y + 10)
                    canvas.boundedMoveVertex(target)

                    self.assertEqual(target, shape.points[index])
                    for point in shape.points:
                        self.assertGreaterEqual(point.x(), 0)
                        self.assertLessEqual(point.x(), 100)
                        self.assertGreaterEqual(point.y(), 0)
                        self.assertLessEqual(point.y(), 100)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainterPath
from PyQt5.QtWidgets import QApplication

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


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""Regression tests for the first resize of annotations loaded from XML."""
import math
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from libs.canvas import Canvas
from libs.labelFile import LabelFile
from libs.pascal_voc_io import PascalVocReader, PascalVocWriter
from libs.shape import Shape


class LoadedCornerResizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.parent.filePath = None
        self.canvas = Canvas(self.parent)
        self.canvas.resize(200, 200)
        self.canvas.loadPixmap(QPixmap(100, 100))
        self.addCleanup(self.parent.close)

    def roundtrip_xml(self, points, direction, legacy=True):
        """Exercise production serialization and parsing, not hand-built loads."""
        source = Shape(label='edge')
        for x, y in points:
            source.addPoint(QPointF(x, y))
        source.direction = direction
        source.close()
        shape_info = dict(
            points=[(point.x(), point.y()) for point in source.points],
            center=source.center,
            direction=source.direction,
        )
        box = LabelFile.convertPoints2RotatedBndBox(shape_info)
        # Match legacy XML files even after production serialization stops
        # rounding: their dimensions had 4 decimal places, angles only 6.
        if legacy:
            box = tuple(round(value, 4 if index < 4 else 6)
                        for index, value in enumerate(box))
        with tempfile.TemporaryDirectory(prefix='labelimg-corner-xml-') as folder:
            path = os.path.join(folder, 'edge.xml')
            writer = PascalVocWriter(folder, 'edge.png', (100, 100, 3))
            writer.addRotatedBndBox(*box, 'edge', False, 'legacy')
            writer.save(targetFile=path)
            shapes = PascalVocReader(path).getShapes()
        self.assertEqual(1, len(shapes))
        label, loaded_points, _, _, difficult, rotated, angle, extra = shapes[0]
        shape = Shape(label=label)
        for x, y in loaded_points:
            shape.addPoint(QPointF(x, y))
        shape.direction = angle
        shape.isRotated = rotated
        shape.difficult = difficult
        shape.extra_label = extra
        shape.close()
        return shape

    def drag_without_hover(self, shape, index, target):
        self.canvas.loadPixmap(QPixmap(100, 100))
        self.canvas.loadShapes([shape])
        self.assertIsNone(self.canvas.hShape)
        self.assertIsNone(self.canvas.hVertex)
        offset = self.canvas.offsetToCenter()
        self.canvas.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, shape.points[index] + offset,
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        self.assertIs(shape, self.canvas.hShape)
        self.assertEqual(index, self.canvas.hVertex)
        self.canvas.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, target + offset,
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.canvas.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, target + offset,
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier))

    def assert_inside_image(self, shape):
        for index, point in enumerate(shape.points):
            self.assertFalse(
                self.canvas.outOfPixmap(point),
                'corner %d is outside: (%r, %r)' %
                (index, point.x(), point.y()))

    def assert_rectangle(self, shape):
        edges = [shape.points[(index + 1) % 4] - shape.points[index]
                 for index in range(4)]
        for index, first in enumerate(edges):
            second = edges[(index + 1) % 4]
            lengths = math.hypot(first.x(), first.y()) * math.hypot(
                second.x(), second.y())
            self.assertGreater(lengths, 0.0)
            self.assertAlmostEqual(
                0.0, (first.x() * second.x() + first.y() * second.y()) /
                lengths, places=9)
        for index in (0, 1):
            self.assertAlmostEqual(edges[index].x(), -edges[index + 2].x())
            self.assertAlmostEqual(edges[index].y(), -edges[index + 2].y())

    def test_all_loaded_cardinal_corners_resize_without_hover_or_translation(self):
        cases = (
            (0.0, ((0, 0), (80, 0), (80, 80), (0, 80))),
            (math.pi / 2, ((80, 0), (80, 80), (0, 80), (0, 0))),
            (math.pi, ((80, 80), (0, 80), (0, 0), (80, 0))),
            (3 * math.pi / 2, ((0, 80), (0, 0), (80, 0), (80, 80))),
        )
        for direction, base_points in cases:
            # Cover top/left, top/right, bottom/left, and bottom/right edges.
            for dx, dy in ((0, 0), (20, 0), (0, 20), (20, 20)):
                points = [(x + dx, y + dy) for x, y in base_points]
                for index in range(4):
                    with self.subTest(direction=direction, index=index,
                                      offset=(dx, dy)):
                        shape = self.roundtrip_xml(points, direction)
                        before = [QPointF(point) for point in shape.points]
                        # Shrink inward: a valid resize with no outward demand.
                        target = (before[index] +
                                  (shape.center - before[index]) / 4)
                        self.drag_without_hover(shape, index, target)
                        self.assertNotEqual(before[index], shape.points[index])
                        self.assert_inside_image(shape)
                        self.assert_rectangle(shape)

    def test_loaded_outside_top_can_resize_far_corner_immediately(self):
        shape = self.roundtrip_xml(
            ((20, -3), (80, -3), (80, 80), (20, 80)), 0.0)
        before = [QPointF(point) for point in shape.points]
        self.drag_without_hover(shape, 2, QPointF(90, 90))
        self.assertNotEqual(before[2], shape.points[2])
        self.assert_inside_image(shape)
        self.assert_rectangle(shape)

    def test_bottom_roundoff_snaps_to_bottom_not_top(self):
        point = self.canvas._snapPixmapBoundaryRoundoff(
            QPointF(50, 100 + 5e-8))
        self.assertEqual(QPointF(50, 100), point)

    def test_valid_loaded_box_preserves_fixed_opposite_corner(self):
        for index in range(4):
            with self.subTest(index=index):
                shape = self.roundtrip_xml(
                    ((20, 20), (80, 20), (80, 80), (20, 80)), 0.0)
                before = [QPointF(point) for point in shape.points]
                opposite = (index + 2) % 4
                target = before[index] + (shape.center - before[index]) / 3
                self.drag_without_hover(shape, index, target)
                self.assertNotEqual(before[index], shape.points[index])
                self.assertEqual(before[opposite], shape.points[opposite])
                self.assert_inside_image(shape)
                self.assert_rectangle(shape)

    def test_valid_rotated_loaded_box_preserves_fixed_opposite_corner(self):
        angle = 0.35
        points = [(50 + x * math.cos(angle) - y * math.sin(angle),
                   50 + x * math.sin(angle) + y * math.cos(angle))
                  for x, y in ((-25, -15), (25, -15), (25, 15), (-25, 15))]
        for index in range(4):
            with self.subTest(index=index):
                shape = self.roundtrip_xml(points, angle)
                before = [QPointF(point) for point in shape.points]
                opposite = (index + 2) % 4
                target = before[index] + (shape.center - before[index]) / 3
                self.drag_without_hover(shape, index, target)
                self.assertNotEqual(before[index], shape.points[index])
                self.assertEqual(before[opposite], shape.points[opposite])
                self.assert_inside_image(shape)
                self.assert_rectangle(shape)

    def test_legacy_slanted_edge_box_can_shrink_each_corner(self):
        angle = 0.350000321
        relative = [(x * math.cos(angle) - y * math.sin(angle),
                     x * math.sin(angle) + y * math.cos(angle))
                    for x, y in ((-27.5, -12.5), (27.5, -12.5),
                                 (27.5, 12.5), (-27.5, 12.5))]
        left = min(point[0] for point in relative)
        points = [(x - left, y + 40) for x, y in relative]
        for index in range(4):
            with self.subTest(index=index):
                shape = self.roundtrip_xml(points, angle)
                before = [QPointF(point) for point in shape.points]
                loaded_direction = shape.direction
                target = before[index] + (shape.center - before[index]) / 3
                self.drag_without_hover(shape, index, target)
                self.assertNotEqual(before[index], shape.points[index])
                self.assertEqual(loaded_direction, shape.direction)
                self.assert_inside_image(shape)
                self.assert_rectangle(shape)

    def test_oversized_rotated_loaded_box_can_resize_each_corner(self):
        angle = 0.35
        points = [(50 + x * math.cos(angle) - y * math.sin(angle),
                   50 + x * math.sin(angle) + y * math.cos(angle))
                  for x, y in ((-70, -40), (70, -40), (70, 40), (-70, 40))]
        for index in range(4):
            with self.subTest(index=index):
                shape = self.roundtrip_xml(points, angle)
                baseline = self.canvas._fitResizeBaseline(shape.points)
                target = baseline[index] + (shape.center - baseline[index]) / 3
                self.drag_without_hover(shape, index, target)
                self.assertNotEqual(baseline[index], shape.points[index])
                self.assertEqual(angle, shape.direction)
                self.assert_inside_image(shape)
                self.assert_rectangle(shape)

    def test_oversized_baseline_fit_uses_uniform_scale(self):
        angle = 0.35
        points = [QPointF(50 + x * math.cos(angle) - y * math.sin(angle),
                          50 + x * math.sin(angle) + y * math.cos(angle))
                  for x, y in ((-70, -40), (70, -40), (70, 40), (-70, 40))]
        fitted = self.canvas._fitResizeBaseline(points)
        ratios = []
        for index in range(4):
            edge = points[(index + 1) % 4] - points[index]
            new_edge = fitted[(index + 1) % 4] - fitted[index]
            ratios.append(math.hypot(new_edge.x(), new_edge.y()) /
                          math.hypot(edge.x(), edge.y()))
        self.assertLess(ratios[0], 1.0)
        for ratio in ratios[1:]:
            self.assertAlmostEqual(ratios[0], ratio, places=12)
        shape = Shape(label='fitted')
        shape.points = fitted
        self.assert_inside_image(shape)
        self.assert_rectangle(shape)

    def test_outside_permission_does_not_repair_existing_outside_corner(self):
        shape = self.roundtrip_xml(
            ((20, -3), (80, -3), (80, 80), (20, 80)), 0.0)
        self.canvas.canOutOfBounding = True
        opposite = QPointF(shape.points[0])
        self.drag_without_hover(shape, 2, QPointF(90, 90))
        self.assertEqual(QPointF(90, 90), shape.points[2])
        self.assertEqual(opposite, shape.points[0])
        self.assert_rectangle(shape)

    def test_new_xml_preserves_full_angle_precision(self):
        shape = self.roundtrip_xml(
            ((80, 80), (0, 80), (0, 0), (80, 0)), math.pi, legacy=False)
        self.assertEqual(math.pi, shape.direction)

    def test_new_xml_preserves_center_and_dimensions_precision(self):
        points = ((10.123456789, 15.234567891),
                  (80.987654321, 15.234567891),
                  (80.987654321, 75.876543219),
                  (10.123456789, 75.876543219))
        shape = self.roundtrip_xml(points, 0.0, legacy=False)
        for expected, actual in zip(points, shape.points):
            self.assertAlmostEqual(expected[0], actual.x(), places=10)
            self.assertAlmostEqual(expected[1], actual.y(), places=10)


if __name__ == '__main__':
    unittest.main()

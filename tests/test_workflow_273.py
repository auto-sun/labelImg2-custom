# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMessageBox

import labelImg
from libs.labelView import CCommonOrderComboBox
from libs.shape import Shape


class MemorySettings:
    def __init__(self):
        self.data = {'autoCheckUpdates': False, 'autoSaving': False}

    def load(self):
        return True

    def save(self):
        return True

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


def make_box(label, x, y, width=50, height=60):
    shape = Shape(label=label)
    for point in ((x, y), (x + width, y),
                  (x + width, y + height), (x, y + height)):
        shape.addPoint(QPointF(*point))
    shape.isRotated = True
    shape.close()
    return shape


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings_patch = patch.object(labelImg, 'Settings', MemorySettings)
        self.settings_patch.start()
        self.window = labelImg.MainWindow(defaultPrefdefClassFile=os.path.join(
            os.path.dirname(labelImg.__file__), 'data', 'predefined_classes.txt'))
        self.window.resize(1000, 700)
        self.window.show()
        pixmap = QPixmap(1200, 1000)
        pixmap.fill(Qt.white)
        self.window.image = pixmap.toImage()
        self.window.canvas.loadPixmap(pixmap)
        self.window.canvas.setEnabled(True)
        self.window.zoomWidget.setValue(100)
        self.window.paintCanvas()
        self.app.processEvents()
        self.window.filePath = os.path.abspath('synthetic-workflow-test.jpg')
        self.window.autoSaving.setChecked(False)

    def tearDown(self):
        self.window.setClean()
        self.window.close()
        self.window.canvas.restoreCursor()
        self.settings_patch.stop()

    def mouse(self, kind, image_point, modifiers=Qt.ControlModifier):
        canvas = self.window.canvas
        local = (image_point + canvas.offsetToCenter()) * canvas.scale
        button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
        buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
        handlers = {QEvent.MouseButtonPress: canvas.mousePressEvent,
                    QEvent.MouseButtonRelease: canvas.mouseReleaseEvent,
                    QEvent.MouseMove: canvas.mouseMoveEvent}
        handlers[kind](QMouseEvent(kind, local, button, buttons, modifiers))

    def select_boxes(self, *boxes):
        canvas = self.window.canvas
        canvas.shapes = list(boxes)
        for box in boxes:
            self.window.addLabel(box)
        canvas._setSelectedShapes(list(boxes))
        self.window.resetUndoHistory()

    def test_ctrl_drag_copies_entire_selection_and_one_undo_restores_it(self):
        boxes = [make_box('person', 30, 30), make_box('SafeHat', 130, 60)]
        self.select_boxes(*boxes)
        originals = [[QPointF(p) for p in box.points] for box in boxes]
        start = QPointF(55, 55)
        self.mouse(QEvent.MouseButtonPress, start)
        self.mouse(QEvent.MouseMove, start + QPointF(20, 30))
        self.mouse(QEvent.MouseButtonRelease, start + QPointF(20, 30))
        canvas = self.window.canvas
        self.assertEqual(4, len(canvas.shapes))
        self.assertEqual(2, len(canvas.selectedShapes))
        self.assertEqual(4, self.window.labelModel.rowCount())
        for source, copied, original in zip(boxes, canvas.selectedShapes, originals):
            self.assertEqual(original, source.points)
            self.assertEqual(source.label, copied.label)
            self.assertEqual([p + QPointF(20, 30) for p in original], copied.points)
        self.assertEqual(1, len(self.window._undoStack))
        self.assertTrue(self.window.undoLastOperation())
        self.assertEqual(2, len(canvas.shapes))

    def test_ctrl_click_without_drag_does_not_copy_and_boundary_keeps_group_spacing(self):
        first = make_box('person', 30, 30)
        last = make_box('SafeHat', 1140, 60)
        self.select_boxes(first, last)
        start = QPointF(55, 55)
        self.mouse(QEvent.MouseButtonPress, start)
        self.mouse(QEvent.MouseButtonRelease, start)
        self.assertEqual(2, len(self.window.canvas.shapes))
        self.window.canvas._setSelectedShapes([first, last])
        self.mouse(QEvent.MouseButtonPress, start)
        self.mouse(QEvent.MouseMove, start + QPointF(80, 0))
        self.mouse(QEvent.MouseButtonRelease, start + QPointF(80, 0))
        copies = self.window.canvas.selectedShapes
        self.assertEqual(40, copies[0].points[0].x())
        self.assertEqual(1200, max(p.x() for p in copies[1].points))

    def test_nudge_is_five_image_pixels_and_clamps_at_boundary(self):
        box = make_box('person', 1147, 30)
        self.select_boxes(box)
        self.window.canvas.moveOnePixel('Left')
        self.assertEqual(1142, box.points[0].x())
        self.window.canvas.moveOnePixel('Right')
        self.window.canvas.moveOnePixel('Right')
        self.assertEqual(1150, box.points[0].x())

    def test_all_four_margins_survive_layout_resize_zoom_and_image_switch(self):
        canvas = self.window.canvas
        area = self.window.scrollArea
        bar = area.verticalScrollBar()
        for zoom, width, height, image_size in (
                (100, 1000, 700, (1200, 1000)),
                (35, 1366, 768, (1200, 1000)),
                (150, 1920, 1080, (1200, 1000)),
                (60, 2560, 1440, (3000, 200)),
                (60, 1366, 768, (200, 3000))):
            self.window.resize(width, height)
            pixmap = QPixmap(*image_size)
            pixmap.fill(Qt.white)
            self.window.image = pixmap.toImage()
            canvas.loadPixmap(pixmap)
            self.window.zoomWidget.setValue(zoom)
            self.window.paintCanvas()
            for _ in range(4):
                self.app.processEvents()
            self.assertEqual(area.viewport().height() // 3, canvas.panMargin)
            self.assertEqual(area.viewport().width() // 3, canvas.panHorizontalMargin)
            margin = canvas.panMargin
            top = canvas.offsetToCenter().y() * canvas.scale
            self.assertGreaterEqual(top, margin - 1)
            bar.setValue(bar.minimum())
            self.assertGreaterEqual(top - bar.value(), margin - 1)
            bar.setValue(bar.maximum())
            bottom = top + canvas.pixmap.height() * canvas.scale - bar.value()
            self.assertGreaterEqual(area.viewport().height() - bottom, margin - 1)
            maximum = bar.maximum()
            canvas.updateGeometry()
            canvas.adjustSize()
            self.app.processEvents()
            self.assertEqual(maximum, bar.maximum())
            horizontal_bar = area.horizontalScrollBar()
            left = canvas.offsetToCenter().x() * canvas.scale
            horizontal_margin = canvas.panHorizontalMargin
            self.assertGreaterEqual(left, horizontal_margin - 1)
            horizontal_bar.setValue(horizontal_bar.minimum())
            self.assertGreaterEqual(left - horizontal_bar.value(), horizontal_margin - 1)
            horizontal_bar.setValue(horizontal_bar.maximum())
            right = left + canvas.pixmap.width() * canvas.scale - horizontal_bar.value()
            self.assertGreaterEqual(area.viewport().width() - right, horizontal_margin - 1)
            maximum = horizontal_bar.maximum()
            canvas.updateGeometry()
            canvas.adjustSize()
            self.app.processEvents()
            self.assertEqual(maximum, horizontal_bar.maximum())

    def test_alt_drag_reaches_left_and_right_blank_margins_without_changing_boxes(self):
        canvas = self.window.canvas
        area = self.window.scrollArea
        bar = area.horizontalScrollBar()
        self.select_boxes(make_box('person', 30, 30))
        original = [QPointF(p) for p in canvas.shapes[0].points]
        bar.setValue(canvas.panHorizontalMargin)
        start = area.viewport().mapToGlobal(QPoint(100, 100))

        def drag_event(kind, screen):
            local = QPointF(canvas.mapFromGlobal(screen))
            button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
            buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton
            QApplication.sendEvent(canvas, QMouseEvent(
                kind, local, QPointF(screen), button, buttons, Qt.AltModifier))

        drag_event(QEvent.MouseButtonPress, start)
        drag_event(QEvent.MouseMove, start + QPoint(5000, 0))
        self.assertEqual(bar.minimum(), bar.value())
        left = canvas.offsetToCenter().x() * canvas.scale - bar.value()
        self.assertGreaterEqual(left, canvas.panHorizontalMargin - 1)
        drag_event(QEvent.MouseMove, start + QPoint(-5000, 0))
        self.assertEqual(bar.maximum(), bar.value())
        right = (canvas.offsetToCenter().x() * canvas.scale +
                 canvas.pixmap.width() * canvas.scale - bar.value())
        self.assertGreaterEqual(area.viewport().width() - right, canvas.panHorizontalMargin - 1)
        drag_event(QEvent.MouseButtonRelease, start + QPoint(-5000, 0))
        self.assertEqual(original, canvas.shapes[0].points)

    def test_hover_handles_stay_identical_on_repeated_repaints(self):
        box = make_box('person', 30, 30)
        self.select_boxes(box)
        canvas = self.window.canvas
        point = (box.points[0] + canvas.offsetToCenter()) * canvas.scale
        event = QMouseEvent(QEvent.MouseMove, point, Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        canvas.mouseMoveEvent(event)
        first = canvas.grab().toImage()
        for _ in range(3):
            canvas.repaint()
            self.assertTrue(box.highlightCorner)
            self.assertEqual(first, canvas.grab().toImage())
        QTest.keyClick(canvas, Qt.Key_T)
        self.assertFalse(canvas.hideRotated)
        self.assertNotIn('T', self.window.labelShortcutReservedKeys())

    def test_restart_uses_source_or_installed_executable_after_saving_settings(self):
        for frozen in (False, True):
            with patch.object(sys, 'frozen', frozen, create=True), patch.object(
                    labelImg.QProcess, 'startDetached', return_value=(True, 123)) as launch:
                self.window.restartSoftware()
                program, args, directory = launch.call_args.args
                self.assertEqual(sys.executable, program)
                self.assertEqual([] if frozen else [os.path.abspath(labelImg.__file__)], args)
                self.assertIn('filename', self.window.settings.data)
                self.window.show()

    def test_cancel_restart_keeps_software_open(self):
        self.window.dirty = True
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Cancel), patch.object(
                labelImg.QProcess, 'startDetached') as launch:
            self.window.restartSoftware()
            launch.assert_not_called()
            self.assertTrue(self.window.isVisible())


class PinyinShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mapped_g_then_repeated_g_cycles_pinyin_without_changing_class_spaces(self):
        combo = CCommonOrderComboBox()
        combo.addItems(['果腐病', ' 干枯症 ', '煤烟病'])
        combo.setShortcutMappings([{'shortcut': 'G', 'label': '果腐病'}])
        QTest.keyClick(combo, Qt.Key_G)
        self.assertEqual('果腐病', combo.currentText())
        QTest.keyClick(combo, Qt.Key_G)
        self.assertEqual(' 干枯症 ', combo.currentText())
        QTest.keyClick(combo, Qt.Key_G)
        self.assertEqual('果腐病', combo.currentText())
        combo.close()


if __name__ == '__main__':
    unittest.main()

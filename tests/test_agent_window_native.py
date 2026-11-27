"""Run with QT_QPA_PLATFORM=windows on a real mixed-DPI desktop."""

import ctypes
import os
import unittest
from ctypes import wintypes

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QWidget

from libs.agent_window import AgentTaskWindow
from libs.ui_geometry import squashed_task_window
from libs.windows_window_placement import _rect, windows_window_placement


@unittest.skipUnless(os.environ['QT_QPA_PLATFORM'] == 'windows', 'requires a native Windows desktop')
class NativeTaskWindowPlacementTests(unittest.TestCase):
    def test_late_native_move_recovers_from_both_dpi_scales(self):
        app = QApplication.instance()
        if app is None:
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
            app = QApplication([])
        self.app = app  # Keep the application alive through widget cleanup.
        screens = app.screens()
        if len({screen.devicePixelRatio() for screen in screens}) < 2:
            self.skipTest('requires two monitors with different DPI scales')
        placement = windows_window_placement()
        self.assertIsNotNone(placement)

        owner = QWidget()
        owner.setAttribute(Qt.WA_ShowWithoutActivating)
        owner.resize(640, 440)
        owner.move(app.primaryScreen().availableGeometry().center() - owner.rect().center())
        owner.show()
        self.addCleanup(owner.close)
        window = AgentTaskWindow(owner, lambda: None)
        self.addCleanup(window.close)
        window.present()
        QTest.qWait(220)
        hwnd, owner_hwnd = int(window.winId()), int(owner.winId())

        def read_frame():
            frame = wintypes.RECT()
            self.assertTrue(placement._get_rect(hwnd, ctypes.byref(frame)))
            return _rect(frame)

        def move_physical(x, y, width, height):
            self.assertTrue(placement._position(hwnd, None, x, y, width, height, 0x10 | 4))

        context = placement._dpi_context(-4)
        try:
            areas = []
            for screen in screens:
                # Windows/Qt keep the same screen origins, but not dimensions.
                x, y = screen.geometry().getRect()[:2]
                sample = wintypes.RECT(x + 5, y + 5, x + 6, y + 6)
                monitor = placement._monitor_from_rect(ctypes.byref(sample), 0)
                area = placement._work_area(monitor)
                self.assertTrue(area.isValid(), screen.name())
                areas.append((screen, area))
            home = placement._work_area(placement._monitor_from_window(owner_hwnd, 2))
            scale = placement._dpi(owner_hwnd) / 96
            margin = round(12 * scale)
            expected = QSize(round(860 * scale), round(530 * scale)).boundedTo(
                home.adjusted(margin, margin, -margin, -margin).size())
            for screen, area in areas:
                with self.subTest(screen=screen.name(), scale=screen.devicePixelRatio()):
                    move_physical(area.center().x() - 320, area.center().y() - 220, 640, 440)
                    QTest.qWait(240)
                    self.assertTrue(area.contains(read_frame().center()), read_frame())
                    window.showMaximized()
                    QTest.qWait(180)
                    self.assertTrue(window.isMaximized())
                    window.showMinimized()
                    QTest.qWait(180)
                    self.assertTrue(window.isMinimized())
                    window.present()
                    QTest.qWait(180)
                    self.assertTrue(placement.title_reachable(hwnd))
                    window.showNormal()
                    QTest.qWait(220)

                    # Set a user-sized normal rectangle, then simulate the
                    # on-screen wide/short native frame seen after switching.
                    dpi_scale = placement._dpi(hwnd) / 96
                    good_width = min(round(700 * dpi_scale), area.width() - 48)
                    good_height = min(round(430 * dpi_scale), area.height() - 48)
                    move_physical(area.center().x() - good_width // 2,
                                  area.center().y() - good_height // 2,
                                  good_width, good_height)
                    QTest.qWait(220)
                    last_good = read_frame().size()
                    short_height = min(round(283 * dpi_scale), area.width() // 5,
                                       area.height() // 3)
                    move_physical(area.x() - 6, area.bottom() - short_height - 30,
                                  area.width() + 6, short_height)
                    damaged = placement.geometry(hwnd)
                    self.assertTrue(damaged.title_reachable)
                    self.assertTrue(squashed_task_window(damaged.frame, area, dpi_scale),
                                    damaged.frame)
                    self.assertFalse(window.isMaximized())
                    for _ in range(20):
                        QTest.qWait(80)
                        if read_frame().size() == last_good:
                            break
                    self.assertTrue(area.contains(read_frame()), read_frame())
                    self.assertEqual(last_good, read_frame().size())

                    x = max(3606, max(work.right() for _, work in areas) + 100)
                    move_physical(x, 907, 866, 519)
                    self.assertFalse(placement.title_reachable(hwnd), read_frame())
                    for _ in range(20):
                        QTest.qWait(80)
                        if home.contains(read_frame()) and read_frame().size() == expected:
                            break
                    self.assertTrue(home.contains(read_frame()), read_frame())
                    self.assertEqual(expected, read_frame().size())
                    self.assertEqual(home.center(), read_frame().center())
        finally:
            if context:
                placement._dpi_context(context)

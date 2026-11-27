import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

import labelImg
from libs.release_tour import should_offer_tour
from libs.ui_geometry import reachable_window_title, recover_window_frame, squashed_task_window
from libs.window_motion import MotionDialog, WindowMotion, widget_rect
from test_delete_image import MemorySettings


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_dialog_collapse_uses_entry_and_no_deferred_closure(self):
        owner=QWidget()
        owner.resize(500,400)
        entry=QPushButton('Open',owner)
        entry.setGeometry(40,310,100,28)
        owner.show()
        owner.windowMotion=animator=WindowMotion(owner,MemorySettings())
        dialog=MotionDialog(owner)
        dialog.motionAnchor=entry
        dialog.resize(280,130)
        dialog.show()
        self.addCleanup(owner.close)
        self.app.processEvents()
        original=widget_rect(dialog)
        with patch.object(animator,'available',return_value=True):
            dialog.collapseAnimated()
        self.assertFalse(dialog.isVisible())
        timeline,ghost,_=animator.running[dialog]
        timeline.setCurrentTime(timeline.duration()//2)
        target=widget_rect(entry)
        between=QRect(ghost.geometry())
        self.assertLess(between.width(),original.width())
        self.assertGreater(between.width(),target.width())
        self.assertNotEqual(between.topLeft(),original.topLeft())
        timeline.setCurrentTime(timeline.duration())
        self.assertFalse(animator.running)
        self.assertFalse(ghost.isVisible())

    def test_disable_stops_snapshots_and_does_not_delay_accept(self):
        owner=QWidget()
        owner.show()
        self.addCleanup(owner.close)
        owner.windowMotion=animator=WindowMotion(owner,MemorySettings())
        dialog=MotionDialog(owner)
        dialog.show()
        with patch.object(animator,'available',return_value=True):
            dialog.accept()
        self.assertEqual(dialog.Accepted,dialog.result())
        self.assertTrue(animator.running)
        animator.setEnabled(False)
        self.assertFalse(animator.enabled())
        self.assertFalse(animator.running)
        dialog.show()
        dialog.close()
        self.assertFalse(animator.running)

    def test_different_monitor_entry_never_hides_the_live_dialog(self):
        owner=QWidget()
        owner.show()
        self.addCleanup(owner.close)
        owner.windowMotion=animator=WindowMotion(owner,MemorySettings())
        dialog=MotionDialog(owner)
        dialog.resize(250,130)
        dialog.move(80,80)
        dialog.show()
        self.app.processEvents()
        left=QRect(-1400,-200,1000,900)
        right=QRect(0,0,800,600)
        anchor=lambda:QRect(-900,640,120,22)
        with patch.object(animator,'available',return_value=True), \
                patch('libs.window_motion.screen_work_areas',return_value=[left,right]):
            self.assertFalse(animator.play(dialog,anchor,opening=True))
            self.assertEqual(1,dialog.windowOpacity())
            self.assertTrue(animator.play(dialog,anchor))
        timeline,ghost,_=animator.running[dialog]
        timeline.setCurrentTime(timeline.duration()//2)
        self.assertEqual(widget_rect(dialog),ghost.geometry())
        animator.finishAll()


class MonitorPlacementTests(unittest.TestCase):
    main=QRect(0,0,1920,1040)
    # A smaller logical screen with negative origins and a gap at its right.
    secondary=QRect(-2560,-374,1707,1026)

    def fit(self,frame):
        return recover_window_frame(frame,[self.secondary,self.main],self.main)

    def test_reported_frame_returns_to_owner_screen_at_normal_size(self):
        recovered=self.fit(QRect(3360,1413,4484,519))
        self.assertTrue(self.main.contains(recovered))
        self.assertEqual((860,530),(recovered.width(),recovered.height()))
        self.assertEqual(self.main.center(),recovered.center())

    def test_gap_is_not_a_screen_and_oversize_never_spans_them(self):
        for frame in (QRect(-750,50,420,390),QRect(-2470,-100,4340,530)):
            with self.subTest(frame=frame):
                self.assertTrue(self.main.contains(self.fit(frame)))

    def test_visible_secondary_window_stays_where_the_user_put_it(self):
        placed=QRect(-2300,-200,690,470)
        self.assertEqual(placed,self.fit(placed))
        clipped=QRect(-1800,190,730,530)
        result=self.fit(clipped)
        self.assertTrue(self.secondary.contains(result))
        self.assertEqual(clipped.size(),result.size())

    def test_title_bar_reachability_does_not_confuse_visible_body_with_reachable_title(self):
        areas = [self.secondary, self.main]
        self.assertFalse(reachable_window_title(QRect(3606, 907, 866, 519), areas))
        self.assertFalse(reachable_window_title(QRect(50, -50, 600, 500), areas))
        self.assertTrue(reachable_window_title(QRect(-100, 50, 800, 520), areas))
        self.assertTrue(reachable_window_title(QRect(-8, -8, 1936, 1056), areas))

    def test_squashed_window_uses_current_screen_dimensions_and_scale(self):
        primary = QRect(0, 0, 1920, 1032)
        secondary = QRect(-2560, -374, 2560, 1504)
        self.assertTrue(squashed_task_window(QRect(-18, 695, 1934, 283), primary))
        self.assertTrue(squashed_task_window(QRect(-2550, 300, 2520, 530), secondary, 2))
        self.assertFalse(squashed_task_window(QRect(0, 516, 1920, 516), primary))
        self.assertFalse(squashed_task_window(QRect(10, 400, 900, 283), primary))


class ReleaseTourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        preset=Path(folder.name)/'classes.txt'
        preset.write_text('person\n',encoding='utf8')
        with patch.object(labelImg,'Settings',MemorySettings):
            self.window=labelImg.MainWindow(defaultPrefdefClassFile=str(preset))
        # Exercise the existing feature tour, even on a bugfix release
        # that does not introduce a new tour page.
        self.window.releaseTour.version='2.8.4'
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def test_guide_once_per_version_and_manual_replay(self):
        w=self.window
        tour=w.releaseTour
        self.assertTrue(should_offer_tour(w.settings,'2.8.4'))
        with patch.object(w,'isActiveWindow',return_value=True), \
                patch.object(QApplication,'mouseButtons',return_value=Qt.NoButton):
            self.assertTrue(tour.maybeShow())
        dialog=tour.dialog
        self.assertTrue(dialog.isVisible())
        self.assertEqual(0,dialog.page)
        w.interfaceAnimationsAction.setChecked(False)
        dialog.advance()
        self.assertEqual(1,dialog.page)
        self.assertFalse(dialog.demo.grab().isNull())
        dialog.skip.click()
        self.app.processEvents()
        self.assertIsNone(tour.dialog)
        self.assertFalse(should_offer_tour(w.settings,'2.8.4'))
        self.assertFalse(tour.maybeShow())
        w.newFeaturesAction.trigger()
        self.assertIsNotNone(tour.dialog)
        tour.dialog.reject()
        self.assertEqual(['2.8.4'],w.settings['seenReleaseTours'])

    def test_dirty_manual_annotations_and_opt_out_defer_the_guide(self):
        w=self.window
        w.dirty=True
        try:
            with patch.object(w,'isActiveWindow',return_value=True):
                self.assertFalse(w.releaseTour.maybeShow())
        finally:
            w.dirty=False
        self.assertIsNone(w.releaseTour.dialog)
        self.assertEqual([],w.settings.get('seenReleaseTours',[]))
        w.autoTourAction.setChecked(False)
        self.assertFalse(should_offer_tour(w.settings,'2.8.4'))
        w.newFeaturesAction.trigger()
        self.assertTrue(w.releaseTour.dialog.isVisible())
        w.releaseTour.dialog.reject()

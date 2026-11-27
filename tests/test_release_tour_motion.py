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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QItemSelectionModel, QPoint, Qt
from PyQt5.QtGui import QColor, QImage, QKeyEvent
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QMessageBox

import labelImg


class MemorySettings(object):
    def __init__(self):
        self.data = {}

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


class DeleteImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.originalSettings = labelImg.Settings
        labelImg.Settings = MemorySettings
        self.temporary = tempfile.TemporaryDirectory()
        self.imageDir = os.path.join(self.temporary.name, 'images')
        self.annotationDir = os.path.join(
            self.temporary.name, 'annotations')
        os.makedirs(self.imageDir)
        os.makedirs(self.annotationDir)
        self.firstImage = self.createImage('one.jpg')
        self.secondImage = self.createImage('two.jpg')

        classesPath = os.path.join(self.temporary.name, 'classes.txt')
        with open(classesPath, 'w', encoding='utf-8') as stream:
            stream.write('person\n')
        self.window = labelImg.MainWindow(
            defaultPrefdefClassFile=classesPath)
        self.window.dirname = self.imageDir
        self.window.defaultSaveDir = self.annotationDir
        self.window.fileModel.setStringList(
            [self.firstImage, self.secondImage],
            self.imageDir, self.annotationDir,
            self.window.annotationFormat, scanAnnotations=False)
        index = self.window.fileModel.index(0)
        self.window.filesm.blockSignals(True)
        self.window.filesm.setCurrentIndex(
            index, QItemSelectionModel.SelectCurrent)
        self.window.filesm.blockSignals(False)
        self.assertTrue(self.window.loadFile(self.firstImage))

    def tearDown(self):
        self.window.annotationScanTimer.stop()
        self.window.setClean()
        self.window.close()
        labelImg.Settings = self.originalSettings
        self.temporary.cleanup()

    def createImage(self, filename):
        path = os.path.join(self.imageDir, filename)
        image = QImage(100, 80, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))
        self.assertTrue(image.save(path))
        return path

    def createBothLabels(self):
        xmlPath = os.path.join(self.annotationDir, 'one.xml')
        txtPath = os.path.join(self.annotationDir, 'one.txt')
        with open(xmlPath, 'w', encoding='utf-8') as stream:
            stream.write('<annotation/>')
        with open(txtPath, 'w', encoding='utf-8') as stream:
            stream.write('0 0.5 0.5 0.2 0.2\n')
        return xmlPath, txtPath

    @staticmethod
    def fakeTrash(paths):
        for path in paths:
            os.remove(path)

    def test_context_menu_contains_delete_action(self):
        actions = self.window.fileListContextMenu.actions()
        self.assertIn(self.window.actions.deleteImage, actions)
        self.assertEqual(
            u'删除图片及对应标签...',
            self.window.actions.deleteImage.text())

    def test_multi_selection_menu_has_delete_flag_and_unflag(self):
        w=self.window
        w.show()
        self.app.processEvents()
        second=w.fileModel.index(1)
        w.filesm.select(second,QItemSelectionModel.Select)
        pos=w.fileListView.visualRect(second).center()
        tr=w.agentSession.tr_ui
        def choose(*_):
            actions={a.text():a for a in w.fileListContextMenu.actions()}
            for text in ('Mark %d selected image(s) for review','Unmark %d selected image(s)',
                         'Recycle %d selected image(s) and labels…','Add %d image(s) to Agent Task'):
                self.assertIn(tr(text) % 2,actions)
            actions[tr('Mark %d selected image(s) for review') % 2].trigger()
        with mock.patch.object(w.fileListContextMenu,'exec_',side_effect=choose):
            w.showFileListContextMenu(pos)
        self.assertTrue(w.fileModel.isFlagged(w.fileModel.index(0)))
        self.assertTrue(w.fileModel.isFlagged(w.fileModel.index(1)))
        w.fileModel.setAgentLockedPaths([self.secondImage],'MCP')
        self.assertTrue(w.setImageBatchFlagged([self.firstImage,self.secondImage],False))
        self.assertFalse(w.fileModel.isFlagged(w.fileModel.index(0)))
        self.assertTrue(w.fileModel.isFlagged(w.fileModel.index(1)))
        self.assertEqual(w.fileModel.flaggedPaths(),w.settings[labelImg.SETTING_FLAGGED_IMAGES])

    def test_batch_recycles_only_selected_paths_and_keeps_current_manual_edit(self):
        w=self.window
        third=self.createImage('three.jpg')
        w.fileModel.setStringList([self.firstImage,self.secondImage,third],scanAnnotations=False)
        current=w.fileModel.index(1)
        with w.restoringFileRow():
            w.filesm.setCurrentIndex(current,QItemSelectionModel.ClearAndSelect)
        w.loadFile(self.secondImage)
        w.dirty=True
        xml,txt=self.createBothLabels()
        w.fileModel.setData(current,6,Qt.BackgroundRole)
        with mock.patch.object(QMessageBox,'question',return_value=QMessageBox.Yes) as question, \
                mock.patch.object(labelImg,'move_to_trash',side_effect=self.fakeTrash):
            self.assertTrue(w.recycleImageBatch([self.firstImage,third]))
        question.assert_called_once()
        self.assertEqual([self.secondImage],w.fileModel.stringList())
        self.assertEqual(self.secondImage,w.filePath)
        self.assertTrue(w.dirty)
        self.assertEqual(6,w.fileModel.annotationCount(w.fileModel.index(0)))
        self.assertTrue(w.fileModel.dispList[0][2])
        self.assertTrue(os.path.isfile(self.secondImage))
        self.assertFalse(any(os.path.exists(p) for p in (self.firstImage,third,xml,txt)))

    def test_batch_preserves_shared_sidecars_and_failed_images(self):
        w=self.window
        alias=self.createImage('one.png')  # one.jpg and one.png map to the same label basename.
        w.fileModel.setStringList([self.firstImage,self.secondImage,alias],scanAnnotations=False)
        xml,txt=self.createBothLabels()
        def trash(paths):
            if paths==[alias]:
                raise labelImg.TrashError('locked image')
            self.fakeTrash(paths)
        with mock.patch.object(QMessageBox,'question',return_value=QMessageBox.Yes), \
                mock.patch.object(QMessageBox,'warning') as warning, \
                mock.patch.object(labelImg,'move_to_trash',side_effect=trash):
            self.assertTrue(w.recycleImageBatch([self.firstImage,alias]))
        warning.assert_called_once()
        self.assertTrue(os.path.isfile(alias))
        self.assertTrue(os.path.isfile(xml))
        self.assertTrue(os.path.isfile(txt))
        self.assertFalse(os.path.exists(self.firstImage))

    def test_batch_rechecks_mcp_lock_after_confirmation(self):
        w=self.window
        xml,txt=self.createBothLabels()
        def confirm(*_):
            w.fileModel.setAgentLockedPaths([self.firstImage],'MCP')
            return QMessageBox.Yes
        with mock.patch.object(QMessageBox,'question',side_effect=confirm), \
                mock.patch.object(labelImg,'move_to_trash',side_effect=self.fakeTrash) as trash:
            self.assertTrue(w.recycleImageBatch([self.firstImage,self.secondImage]))
        trash.assert_called_once_with([self.secondImage])
        self.assertTrue(all(os.path.isfile(p) for p in (self.firstImage,xml,txt)))

    def test_right_click_keeps_row_in_place_and_anchors_menu_to_cursor(self):
        self.window.show()
        self.app.processEvents()
        secondIndex = self.window.fileModel.index(1)
        position = self.window.fileListView.visualRect(
            secondIndex).center()
        expectedPosition = QPoint(123, 234)
        menu = mock.Mock()
        self.window.fileListContextMenu = menu

        with mock.patch.object(labelImg, 'QCursor') as cursor, \
                mock.patch.object(
                    self.window, 'centerFileListIndex') as centerIndex:
            cursor.pos.return_value = expectedPosition
            self.window.showFileListContextMenu(position)

        self.assertEqual(secondIndex, self.window.filesm.currentIndex())
        centerIndex.assert_not_called()
        menu.exec_.assert_called_once_with(expectedPosition)
        self.assertFalse(self.window._suppressFileListCenter)

    def test_right_mouse_press_does_not_center_row_before_menu_opens(self):
        self.window.show()
        self.app.processEvents()
        secondIndex = self.window.fileModel.index(1)
        position = self.window.fileListView.visualRect(
            secondIndex).center()

        with mock.patch.object(
                self.window, 'centerFileListIndex') as centerIndex:
            QTest.mousePress(
                self.window.fileListView.viewport(),
                Qt.RightButton, Qt.NoModifier, position)

        self.assertEqual(secondIndex, self.window.filesm.currentIndex())
        centerIndex.assert_not_called()

    def test_right_click_on_long_list_does_not_move_clicked_row(self):
        images = [self.createImage('frame%02d.jpg' % row)
                  for row in range(30)]
        self.window.fileModel.setStringList(
            images, self.imageDir, self.annotationDir,
            self.window.annotationFormat, scanAnnotations=False)
        self.window.show()
        self.app.processEvents()
        targetIndex = self.window.fileModel.index(20)
        self.window.fileListView.scrollTo(
            targetIndex, QAbstractItemView.PositionAtBottom)
        self.app.processEvents()
        before = self.window.fileListView.visualRect(targetIndex).center()

        QTest.mousePress(
            self.window.fileListView.viewport(),
            Qt.RightButton, Qt.NoModifier, before)
        self.app.processEvents()

        after = self.window.fileListView.visualRect(targetIndex).center()
        self.assertEqual(before, after)
        self.assertEqual(targetIndex, self.window.filesm.currentIndex())

    def test_file_list_delete_key_deletes_without_confirmation(self):
        xmlPath, txtPath = self.createBothLabels()
        shortcutEvent = QKeyEvent(
            QEvent.ShortcutOverride, Qt.Key_Delete, Qt.NoModifier)
        self.assertTrue(self.window.fileListView.event(shortcutEvent))
        self.assertTrue(shortcutEvent.isAccepted())

        spy = QSignalSpy(self.window.fileListView.deleteImageRequested)
        keyEvent = QKeyEvent(
            QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        with mock.patch.object(QMessageBox, 'question') as question, \
                mock.patch.object(
                    labelImg, 'move_to_trash', side_effect=self.fakeTrash):
            self.window.fileListView.keyPressEvent(keyEvent)

        self.assertEqual(1, len(spy))
        question.assert_not_called()
        self.assertFalse(os.path.exists(self.firstImage))
        self.assertFalse(os.path.exists(xmlPath))
        self.assertFalse(os.path.exists(txtPath))
        self.assertEqual(self.secondImage, self.window.filePath)

    def test_mouse_selection_keeps_file_list_keyboard_focus(self):
        self.window.show()
        self.app.processEvents()
        secondIndex = self.window.fileModel.index(1)
        position = self.window.fileListView.visualRect(
            secondIndex).center()

        QTest.mouseClick(
            self.window.fileListView.viewport(),
            Qt.LeftButton, Qt.NoModifier, position)
        self.app.processEvents()

        self.assertEqual(self.secondImage, self.window.filePath)
        self.assertTrue(self.window.fileListView.hasFocus())

    def test_keyboard_navigation_focuses_list_then_delete_trashes_image(self):
        self.window.show()
        self.window.canvas.setFocus()
        self.app.processEvents()

        QTest.keyClick(self.window.canvas, Qt.Key_Down)
        self.app.processEvents()
        self.assertEqual(self.secondImage, self.window.filePath)
        self.assertTrue(self.window.fileListView.hasFocus())

        keyEvent = QKeyEvent(
            QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        with mock.patch.object(QMessageBox, 'question') as question, \
                mock.patch.object(
                    labelImg, 'move_to_trash', side_effect=self.fakeTrash):
            self.window.fileListView.keyPressEvent(keyEvent)

        question.assert_not_called()
        self.assertFalse(os.path.exists(self.secondImage))
        self.assertEqual(self.firstImage, self.window.filePath)

    def test_keyboard_navigation_centers_current_file_list_row(self):
        self.window.show()
        self.window.canvas.setFocus()
        self.app.processEvents()
        with mock.patch.object(
                self.window, 'centerFileListIndex') as centerIndex:
            QTest.keyClick(self.window.canvas, Qt.Key_Down)
            self.app.processEvents()

        self.assertEqual(self.secondImage, self.window.filePath)
        centeredRows = [call.args[0].row()
                        for call in centerIndex.call_args_list]
        self.assertIn(1, centeredRows)

    def test_clicked_then_keyboard_navigated_row_is_only_selection_and_centered(self):
        images = [self.createImage('frame%03d.jpg' % i) for i in range(80)]
        view = self.window.fileListView
        self.window.fileModel.setStringList(images, scanAnnotations=False)
        self.window.show()
        self.app.processEvents()
        clicked = self.window.fileModel.index(35)
        view.scrollTo(clicked, QAbstractItemView.PositionAtBottom)
        self.app.processEvents()
        QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                         view.visualRect(clicked).center())
        for row in range(35, 63):
            if row > 35:
                QTest.keyClick(view, Qt.Key_Down)
            self.app.processEvents()
            index = self.window.fileModel.index(row)
            self.assertEqual(images[row], self.window.filePath)
            self.assertEqual([index], view.selectedIndexes())
            self.assertLessEqual(abs(view.visualRect(index).center().y() -
                                     view.viewport().rect().center().y()),
                                 view.visualRect(index).height())

    def test_refresh_notifies_view_of_restored_selection_without_reloading_twice(self):
        self.window.show()
        self.app.processEvents()
        selection = QSignalSpy(self.window.filesm.selectionChanged)
        with mock.patch.object(self.window, 'loadFile', wraps=self.window.loadFile) as load:
            self.window.refreshProjectDirectories()
        self.assertEqual(1, load.call_count)
        self.assertGreater(len(selection), 0)
        self.assertEqual([self.window.filesm.currentIndex()],
                         self.window.fileListView.selectedIndexes())

    def test_left_right_no_longer_switch_images(self):
        self.window.show()
        self.window.canvas.setFocus()
        self.app.processEvents()

        QTest.keyClick(self.window.canvas, Qt.Key_Right)
        QTest.keyClick(self.window.canvas, Qt.Key_Left)
        self.app.processEvents()

        self.assertEqual(self.firstImage, self.window.filePath)

    def test_up_down_keep_moving_a_selected_box(self):
        self.window.show()
        self.window.canvas.setFocus()
        self.window.canvas.selectedShape = object()
        self.app.processEvents()

        with mock.patch.object(
                self.window.canvas, 'moveOnePixel') as moveOnePixel:
            QTest.keyClick(self.window.canvas, Qt.Key_Down)

        moveOnePixel.assert_called_once_with('Down')
        self.assertEqual(self.firstImage, self.window.filePath)

    def test_left_right_move_a_selected_box(self):
        self.window.show()
        self.window.canvas.setFocus()
        self.window.canvas.selectedShape = object()
        self.app.processEvents()

        with mock.patch.object(
                self.window.canvas, 'moveOnePixel') as moveOnePixel:
            QTest.keyClick(self.window.canvas, Qt.Key_Left)
            QTest.keyClick(self.window.canvas, Qt.Key_Right)

        self.assertEqual(
            [mock.call('Left'), mock.call('Right')],
            moveOnePixel.call_args_list)
        self.assertEqual(self.firstImage, self.window.filePath)

    def test_confirm_deletes_image_xml_txt_and_opens_next_image(self):
        xmlPath, txtPath = self.createBothLabels()

        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.Yes), \
                mock.patch.object(
                    labelImg, 'move_to_trash', side_effect=self.fakeTrash):
            self.assertTrue(
                self.window.deleteSelectedImageAndAnnotations())

        self.assertFalse(os.path.exists(self.firstImage))
        self.assertFalse(os.path.exists(xmlPath))
        self.assertFalse(os.path.exists(txtPath))
        self.assertTrue(os.path.isfile(self.secondImage))
        self.assertEqual(self.secondImage, self.window.filePath)
        self.assertEqual([self.secondImage],
                         list(self.window.fileModel.stringList()))

    def test_cancel_keeps_image_and_all_labels(self):
        xmlPath, txtPath = self.createBothLabels()

        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.No):
            self.assertFalse(
                self.window.deleteSelectedImageAndAnnotations())

        self.assertTrue(os.path.isfile(self.firstImage))
        self.assertTrue(os.path.isfile(xmlPath))
        self.assertTrue(os.path.isfile(txtPath))

    def test_repeated_delete_keeps_focus_and_removes_next_image(self):
        self.window.show()
        self.window.fileListView.setFocus()
        self.app.processEvents()
        with mock.patch.object(labelImg, 'move_to_trash', side_effect=self.fakeTrash), \
                mock.patch.object(QMessageBox, 'question') as question:
            QTest.keyClick(QApplication.focusWidget(), Qt.Key_Delete)
            self.app.processEvents()
            self.assertEqual(self.secondImage, self.window.filePath)
            self.assertTrue(self.window.fileListView.hasFocus())
            QTest.keyClick(QApplication.focusWidget(), Qt.Key_Delete)
            self.app.processEvents()
            self.assertEqual(0, self.window.fileModel.rowCount())
            QTest.keyClick(self.window.fileListView, Qt.Key_Delete)
            question.assert_not_called()
        self.assertFalse(os.path.exists(self.firstImage))
        self.assertFalse(os.path.exists(self.secondImage))

    def test_image_delete_failure_leaves_labels_untouched(self):
        xmlPath, txtPath = self.createBothLabels()
        with mock.patch.object(
                QMessageBox, 'question', return_value=QMessageBox.Yes), \
                mock.patch.object(QMessageBox, 'critical'), \
                mock.patch.object(
                    labelImg, 'move_to_trash',
                    side_effect=labelImg.TrashError('locked')):
            self.assertFalse(
                self.window.deleteSelectedImageAndAnnotations())

        self.assertTrue(os.path.isfile(self.firstImage))
        self.assertTrue(os.path.isfile(xmlPath))
        self.assertTrue(os.path.isfile(txtPath))


if __name__ == '__main__':
    unittest.main()

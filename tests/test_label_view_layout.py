import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QStandardItem
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QHeaderView

from libs.labelView import CLabelView


class LabelViewLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = CLabelView(['person_fallen', 'No_SafeHat', 'no_workwear'])
        self.addCleanup(self.view.close)
        self.view.resize(435, 300)
        self.view.show()
        QTest.qWait(25)

    def addBox(self, label):
        group = self.view.groupFor(label)
        box = QStandardItem(label)
        box.setCheckable(True)
        box.setCheckState(Qt.Checked)
        self.view.styleBoxItem(box, QColor('#595d9d'))
        group.appendRow([box, QStandardItem('')])
        self.view.updateGroup(group)
        self.view.expand(group.index())
        return box

    def assertColumnsFillViewport(self):
        view = self.view
        self.assertEqual(QHeaderView.Stretch, view.header().sectionResizeMode(0))
        self.assertAlmostEqual(view.viewport().width(), view.columnWidth(0) + view.columnWidth(1), delta=2)
        self.assertGreaterEqual(view.columnWidth(0), view.viewport().width() * 0.6)

    def test_loading_next_image_keeps_full_width_and_readable_labels(self):
        self.addBox('No_SafeHat')
        self.view.clearLabels()
        self.assertFalse(self.view.groups)
        self.assertEqual('Extra Info', self.view.model().headerData(1, Qt.Horizontal))
        box = self.addBox('person_fallen')
        QTest.qWait(25)
        self.assertColumnsFillViewport()
        self.assertGreater(self.view.visualRect(box.index()).width(),
                           self.view.fontMetrics().horizontalAdvance(box.text()) + 44)
        self.assertEqual('person_fallen', box.toolTip())
        self.assertEqual(QColor('#595d9d'), box.data(Qt.DecorationRole))
        self.assertIsNone(box.data(Qt.BackgroundRole))

    def test_note_column_stays_editable_and_does_not_crowd_out_labels(self):
        self.view.header().resizeSection(1, 112)
        self.view.clearLabels()
        box = self.addBox('person_fallen')
        self.assertEqual(112, self.view.columnWidth(1))
        self.view.resize(255, 300)
        QTest.qWait(25)
        extra = box.index().sibling(box.row(), 1)
        self.assertTrue(extra.flags() & Qt.ItemIsEditable)
        self.assertTrue(self.view.visualRect(extra).isValid())
        self.assertColumnsFillViewport()

    def test_model_recreation_and_localized_heading_restore_stretch(self):
        self.view.model().clear()
        self.view.model().setHorizontalHeaderLabels(['Clase', 'Información adicional'])
        self.addBox('no_workwear')
        QTest.qWait(25)
        self.assertColumnsFillViewport()


if __name__ == '__main__':
    unittest.main()

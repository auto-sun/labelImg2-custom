#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
# LabelImg2 Custom is distributed under GNU AGPL v3.0. Upstream portions
# retain the MIT terms in LICENSE-MIT-UPSTREAM.
from __future__ import absolute_import

import codecs
import math
import os
import platform
import re
import sys
import subprocess
from functools import partial

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QCollator, QLocale

# Add internal libs
from libs.constants import *
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.pascal_voc_io import PascalVocReader, XML_EXT
from libs.yolo_obb_io import (YoloReader, YoloError, YOLO_EXT,
                              save_yolo_annotations)
from libs.auto_annotation import AutoAnnotationThread

from libs.labelView import CLabelView, HashableQStandardItem
from libs.fileView import CFileView
from libs.cvtlabels2yolo import cvt_xml_annotations_to_yolo

__appname__ = 'labelImg2'
__version__ = '2.2.0'

# Utility functions and classes.

def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))

def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = QToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        if actions:
            if isinstance(action, QWidgetAction):
                return super(ToolBar, self).addAction(action)
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            toolbar.addWidget(btn)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))
    UNDO_LIMIT = 50

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Save as Pascal voc xml
        self.defaultSaveDir = defaultSaveDir
        saved_annotation_format = settings.get(
            SETTING_ANNOTATION_FORMAT, FORMAT_PASCALVOC)
        if saved_annotation_format not in SUPPORTED_ANNOTATION_FORMATS:
            saved_annotation_format = FORMAT_PASCALVOC
        self.annotationFormat = saved_annotation_format

        # For loading all image under a directory
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        self.back_sample = False

        self._noSelectionSlot = False

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)
        self.loadLabelUsage(settings.get(SETTING_LABEL_USAGE, {}))

        # Main widgets and related state.
        saved_default_label = settings.get(SETTING_DEFAULT_LABEL, None)
        self.default_label = (saved_default_label
                              if saved_default_label in self.labelHist
                              else (self.labelHist[0] if self.labelHist else None))
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist,
                                       defaultLabel=self.default_label)
        self.labelDialog.defaultLabelChanged.connect(self.rememberDefaultLabel)

        self.ShapeItemDict = {}
        self.ItemShapeDict = {}
        self._shapeClipboard = []
        self._clipboardPasteCount = 0
        self._shapeClipboardSourceFile = None
        self._undoStack = []
        self._undoPendingSnapshot = None
        self._undoRestoring = False
        self.autoAnnotationThread = None
        self.autoAnnotationModelPath = settings.get(
            SETTING_AUTO_ANNOTATION_MODEL, '')
        self.autoAnnotationExistingCount = 0
        self.autoAnnotationMode = None

        labellistLayout = QVBoxLayout()
        labellistLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for edit and diffc button
        self.diffcButton = QCheckBox(u'difficult')
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        labellistLayout.addWidget(self.editButton)
        labellistLayout.addWidget(self.diffcButton)

        # Create and add a widget for showing current label items
        labelListContainer = QWidget()
        labelListContainer.setLayout(labellistLayout)

        self.labelList = CLabelView(self.labelSelectionOrder())
        self.labelModel = self.labelList.model()
        self.labelModel.dataChanged.connect(self.labelDataChanged)
        
        self.labelList.extraEditing.connect(self.updateLabelShowing)

        self.labelsm = self.labelList.selectionModel()
        self.labelsm.currentChanged.connect(self.labelCurrentChanged)

        myHeader = self.labelList.verticalHeader()
        myHeader.clicked.connect(self.labelHeaderClicked)


        labellistLayout.addWidget(self.labelList)

        self.dock = QDockWidget(u'Box Labels', self)
        self.dock.setObjectName(u'Labels')
        self.dock.setWidget(labelListContainer)

        self.labelList.toggleEdit.connect(self.toggleExtraEditing)

        self.fileListView = CFileView()
        

        self.fileModel = self.fileListView.model()
        self.filesm = self.fileListView.selectionModel()
        self.filesm.currentChanged.connect(self.fileCurrentChanged)


        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)

        self.prevButton = QToolButton()
        self.nextButton = QToolButton()
        self.playButton = QToolButton()
        self.prevButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.nextButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.playButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.controlButtonsLayout = QHBoxLayout()
        self.controlButtonsLayout.setAlignment(Qt.AlignLeft)
        self.controlButtonsLayout.addWidget(self.prevButton)
        self.controlButtonsLayout.addWidget(self.nextButton)
        self.controlButtonsLayout.addWidget(self.playButton)

        filelistLayout.addLayout(self.controlButtonsLayout)

        filelistLayout.addWidget(self.fileListView)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)

        self.filedock = QDockWidget(u'File List', self)
        self.filedock.setObjectName(u'Files')
        self.filedock.setWidget(fileListContainer)

        self.zoomWidget = ZoomWidget()

        scroll = QScrollArea()
        self.canvas = Canvas(parent=scroll)
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)
        self.canvas.panRequest.connect(self.panRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setCanvasDirty)
        self.canvas.shapeCopied.connect(self.copyShapeByDragging)
        self.canvas.shapeChangeStarted.connect(self.beginUndoOperation)
        self.canvas.shapeChangeFinished.connect(self.finishUndoOperation)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)
        self.canvas.cancelDraw.connect(self.createCancel)
        self.canvas.toggleEdit.connect(self.toggleExtraEditing)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        self.dock.setFeatures(QDockWidget.DockWidgetFloatable)
        self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.displayTimer = QTimer(self)
        self.displayTimer.setInterval(1000)
        self.displayTimer.timeout.connect(self.autoNext)

        self.playing = False

        # Actions
        action = partial(newAction, self)
        quit = action('&Quit', self.close,
                      'Ctrl+Q', 'power.svg', u'Quit application')

        open = action('&Open', self.openFile,
                      'Ctrl+O', 'open.svg', u'Open image or label file')

        opendir = action('&Open Dir', self.openDirDialog,
                         'Ctrl+u', 'dir.svg', u'Open Dir')

        openAnnotationDir = action(
            '&Open Annotation Dir', self.openAnnotationDirDialog,
            'Ctrl+r', 'dir.svg',
            u'Open the directory used to load and save annotations')

        selectAutoAnnotationModel = action(
            u'选择自动标注模型...', self.selectAutoAnnotationModel,
            None, 'settings.svg', u'选择本地 YOLO / YOLO OBB .pt 模型')
        autoAnnotate = action(
            u'自动标注', self.startAutoAnnotation,
            None, 'batch-processing.svg',
            u'使用本地 YOLO / YOLO OBB 模型批量标注未标注图片')
        singleAutoAnnotate = action(
            u'标注当前图', self.startSingleAutoAnnotation,
            None, 'single-auto-annotation.svg',
            u'使用本地 YOLO / YOLO OBB 模型标注当前图片',
            enabled=False)

        formatXml = action(
            'Pascal VOC XML',
            partial(self.setAnnotationFormat, FORMAT_PASCALVOC),
            checkable=True)
        formatYolo = action(
            'Ultralytics YOLO',
            partial(self.setAnnotationFormat, FORMAT_YOLO),
            checkable=True)
        formatYoloObb = action(
            'Ultralytics YOLO OBB',
            partial(self.setAnnotationFormat, FORMAT_YOLO_OBB),
            checkable=True)
        self.annotationFormatGroup = QActionGroup(self)
        self.annotationFormatGroup.setExclusive(True)
        self.annotationFormatActions = {
            FORMAT_PASCALVOC: formatXml,
            FORMAT_YOLO: formatYolo,
            FORMAT_YOLO_OBB: formatYoloObb,
        }
        for formatAction in self.annotationFormatActions.values():
            self.annotationFormatGroup.addAction(formatAction)
        self.annotationFormatActions[self.annotationFormat].setChecked(True)



        verify = action('&Verify Image', self.verifyImg,
                        'space', 'downloaded.svg', u'Verify Image')

        save = action('&Save', self.saveFileAndRenderList,
                      'Ctrl+S', 'save.svg', u'Save labels to file', enabled=False)

        saveAs = action('&Save As', self.saveFileAs,
                        'Ctrl+Shift+S', 'save.svg', u'Save labels to a different file', enabled=False)

        close = action('&Close', self.closeFile, 'Ctrl+W', 'close.svg', u'Close current file')

        resetAll = action('&ResetAll', self.resetAll, None, 'reset.svg', u'Reset all')

        create = action('Create\nRectBox', self.createShape,
                        None, 'rect.png', u'Draw a new Box', enabled=False)

        createSo = action('Create\nSolidRectBox', self.createSoShape,
                          None, 'rect.png', None, enabled=False)
        createSo.setVisible(False)

        createRo = action('Create\nRotatedRBox', self.createRoShape,
                        'e', 'rectRo.png', u'Draw a new RotatedRBox', enabled=False)        
        
        delete = action('Delete\nRectBox', self.deleteSelectedShape,
                        'Delete', 'cancel2.svg', u'Delete', enabled=False)
        
        labelAsBack = action('Label as background', self.labelAsBackground,
                         None, None, u'Label as background sample for detection training')
        
        deleteLabel = action('No Label', self.deleteLabel,
                              None, None, u'Delete all annotations for current image.S')

        copy = action('&Duplicate\nRectBox', self.copySelectedShape,
                      'Ctrl+D', 'copy.svg', u'Create a duplicate of the selected Box',
                      enabled=False)

        copyToClipboard = action('Copy Box', self.copyShapeToClipboard,
                                 'Ctrl+C', 'copy.svg',
                                 u'Copy selected Box', enabled=False)
        pasteFromClipboard = action('Paste Box', self.pasteShapeFromClipboard,
                                    'Ctrl+V', 'copy.svg',
                                    u'Paste copied Box', enabled=False)
        undo = action('Undo Last Operation', self.undoLastOperation,
                      'Ctrl+Z', None,
                      u'Undo the last box operation', enabled=False)

        showInfo = action('&About', self.showInfoDialog, None, 'info.svg', u'About')

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action('Zoom &In', partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in.svg', u'Increase zoom level', enabled=False)
        zoomOut = action('&Zoom Out', partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out.svg', u'Decrease zoom level', enabled=False)
        zoomOrg = action('&Original size', partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom100.svg', u'Zoom to original size', enabled=False)
        fitWindow = action('&Fit Window', self.setFitWindow,
                           'Ctrl+F', 'zoomReset.svg', u'Zoom follows window size',
                           checkable=True, enabled=False)
        fitWidth = action('Fit &Width', self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width.svg', u'Zoom follows window width',
                          checkable=True, enabled=False)

        openPrevImg = action('&Prev Image', self.openPrevImg,
                             (QKeySequence('a'), QKeySequence(Qt.Key_Left)),
                             'previous.svg', u'Open Prev (A / Left Arrow)')

        openNextImg = action('&Next Image', self.openNextImg,
                             (QKeySequence('d'), QKeySequence(Qt.Key_Right)),
                             'next.svg', u'Open Next (D / Right Arrow)')
        
        play = action('Play', self.playStart,
                    'Ctrl+Shift+P', 'play.svg', u'auto next',
                    checkable=True, enabled=True)
        
        self.prevButton.setDefaultAction(openPrevImg)
        self.nextButton.setDefaultAction(openNextImg)
        self.playButton.setDefaultAction(play)

        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action('&Manage Labels', self.editLabel,
                      'Ctrl+M', 'tags.svg', u'Modify the label of the selected Box',
                      enabled=True)
        self.editButton.setDefaultAction(edit)

        # Lavel list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))

        # Store actions for further handling.
        self.actions = struct(save=save, saveAs=saveAs, open=open, close=close, resetAll = resetAll,
                              create=create, createSo=createSo, createRo=createRo, delete=delete, 
                              labelAsBack=labelAsBack, deleteLabel=deleteLabel, edit=edit, copy=copy,
                              copyToClipboard=copyToClipboard,
                              pasteFromClipboard=pasteFromClipboard,
                              undo=undo,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                               fitWindow=fitWindow, fitWidth=fitWidth, play=play,
                               openPrevImg=openPrevImg, openNextImg=openNextImg,
                               openAnnotationDir=openAnnotationDir,
                               selectAutoAnnotationModel=selectAutoAnnotationModel,
                               autoAnnotate=autoAnnotate,
                               singleAutoAnnotate=singleAutoAnnotate,
                               formatXml=formatXml, formatYolo=formatYolo,
                               formatYoloObb=formatYoloObb,
                               zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save, saveAs, close, resetAll, quit),
                              beginner=(),
                              editMenu=(undo, None, edit,
                                        copyToClipboard, pasteFromClipboard,
                                        copy, delete,
                                        None),
                              beginnerContext=(undo, None,
                                               copyToClipboard, pasteFromClipboard, None,
                                               create, createSo, createRo, copy,
                                               delete, labelAsBack, deleteLabel),
                              onLoadActive=(
                                  close, create, singleAutoAnnotate),
                               onShapesPresent=(saveAs,))
        self._labelNavigationStates = None
        self._focusCanvasAfterLabelEdit = False
        self.labelList.label_delegate.editingActiveChanged.connect(
            self.setLabelEditorActive)
        self.labelList.label_delegate.labelChosen.connect(self.recordLabelUsage)

        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            exportAnnotations=QMenu('Export to'),
            annotationFormat=QMenu('Annotation Format'),
            labelList=labelMenu)

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction("Auto Saving", self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        
        # Add option to enable/disable labels being painted at the top of bounding boxes
        self.paintLabelsOption = QAction("Paint Labels", self)
        # Ctrl+Shift+P is already used by Play. Keep both actions usable by
        # assigning Paint Labels its own shortcut.
        self.paintLabelsOption.setShortcut("Ctrl+Shift+L")
        self.paintLabelsOption.setCheckable(True)
        self.paintLabelsOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.paintLabelsOption.triggered.connect(self.togglePaintLabelsOption)

        self.drawCorner = QAction('Always Draw Corner', self)
        self.drawCorner.setCheckable(True)
        self.drawCorner.setChecked(settings.get(SETTING_DRAW_CORNER, False))
        self.drawCorner.triggered.connect(self.canvas.setDrawCornerState)
        
        addActions(self.menus.annotationFormat,
                   (formatXml, formatYolo, formatYoloObb))

        addActions(self.menus.file,
                   (open, opendir, openAnnotationDir,
                    selectAutoAnnotationModel, singleAutoAnnotate,
                    autoAnnotate, None,
                    self.menus.annotationFormat,
                    self.menus.recentFiles, self.menus.exportAnnotations,
                    save, saveAs, close, resetAll, quit))
        
        export_as_yolo = action('Ultralytics YOLO', self.exportAsYOLO)
        export_as_yolo_obb = action('Ultralytics YOLO OBB', self.exportAsYOLOOBB)

        addActions(self.menus.exportAnnotations, (export_as_yolo, export_as_yolo_obb,))

        addActions(self.menus.help, (showInfo,))
        addActions(self.menus.view, (
            self.autoSaving,
            self.paintLabelsOption,
            self.drawCorner,
            None,
            None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (open, opendir, openAnnotationDir,
            singleAutoAnnotate, autoAnnotate, verify, save, None,
            create, createSo, createRo, copy, delete, None,
            zoomIn, zoom, zoomOut, zoomOrg, fitWindow, fitWidth)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = defaultFilename
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [i for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = settings.get(SETTING_WIN_POSE, QPoint(0, 0))
        self.resize(size)
        self.move(position)
        saveDir = settings.get(SETTING_SAVE_DIR, None)
        self.lastOpenDir = settings.get(SETTING_LAST_OPEN_DIR, None)
        self.lastOpenFile = settings.get(SETTING_FILENAME, None)
        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if (not self.filePath and self.lastOpenDir and
                os.path.isdir(self.lastOpenDir)):
            self.queueEvent(partial(self.importDirImages,
                                    self.lastOpenDir,
                                    self.lastOpenFile))
        elif self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        self.imageDim = QLabel('')
        self.statusBar().addPermanentWidget(self.imageDim)

        self.statFile = QLabel('')
        self.statusBar().addPermanentWidget(self.statFile)

        self.autoAnnotationStatus = QLabel('')
        self.autoAnnotationProgress = QProgressBar()
        self.autoAnnotationProgress.setMinimumWidth(220)
        self.autoAnnotationProgress.setTextVisible(True)
        self.autoAnnotationCancelButton = QPushButton(u'中止')
        self.autoAnnotationCancelButton.clicked.connect(
            self.cancelAutoAnnotation)
        self.statusBar().addPermanentWidget(self.autoAnnotationStatus)
        self.statusBar().addPermanentWidget(self.autoAnnotationProgress)
        self.statusBar().addPermanentWidget(
            self.autoAnnotationCancelButton)
        self.setAutoAnnotationWidgetsVisible(False)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

    def noShapes(self):
        return not self.ItemShapeDict

    def populateModeActions(self):
        tool, menu = self.actions.beginner, self.actions.beginnerContext
        self.tools.clear()
        
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create, self.actions.createSo, self.actions.createRo) 
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def copyShapeForUndo(self, shape):
        """Create an independent shape copy for an undo snapshot."""
        copied = shape.copy()
        copied.points = [QPointF(point) for point in shape.points]
        copied.center = (QPointF(shape.center)
                         if shape.center is not None else None)
        copied.line_color = QColor(shape.line_color)
        copied.fill_color = QColor(shape.fill_color)
        copied.paintLabel = shape.paintLabel
        copied.alwaysShowCorner = shape.alwaysShowCorner
        copied.highlightCorner = False
        copied.highlightClear()
        return copied

    def captureUndoSnapshot(self):
        selected = []
        selectedShapes = list(self.canvas.selectedShapes)
        if (self.canvas.selectedShape is not None and
                self.canvas.selectedShape not in selectedShapes):
            selectedShapes.append(self.canvas.selectedShape)
        for shape in selectedShapes:
            if shape in self.canvas.shapes:
                selected.append(self.canvas.shapes.index(shape))
        return {
            'shapes': [self.copyShapeForUndo(shape)
                       for shape in self.canvas.shapes],
            'selected': selected,
            'back_sample': bool(self.back_sample),
        }

    def undoSnapshotSignature(self, snapshot):
        def colorValue(color):
            return int(QColor(color).rgba())

        shapes = []
        for shape in snapshot['shapes']:
            shapes.append((
                shape.label,
                tuple((point.x(), point.y()) for point in shape.points),
                bool(shape.isRotated),
                float(shape.direction),
                bool(shape.difficult),
                shape.extra_label,
                colorValue(shape.line_color),
                colorValue(shape.fill_color),
            ))
        return tuple(shapes), bool(snapshot['back_sample'])

    def updateUndoAction(self):
        if hasattr(self, 'actions') and hasattr(self.actions, 'undo'):
            self.actions.undo.setEnabled(
                bool(self.filePath and self._undoStack))

    def resetUndoHistory(self):
        self._undoStack = []
        self._undoPendingSnapshot = None
        self.updateUndoAction()

    def beginUndoOperation(self):
        if self._undoRestoring or not self.filePath:
            return
        if self._undoPendingSnapshot is None:
            self._undoPendingSnapshot = self.captureUndoSnapshot()

    def cancelUndoOperation(self):
        self._undoPendingSnapshot = None

    def finishUndoOperation(self):
        if self._undoRestoring or self._undoPendingSnapshot is None:
            return
        previous = self._undoPendingSnapshot
        self._undoPendingSnapshot = None
        current = self.captureUndoSnapshot()
        if (self.undoSnapshotSignature(previous) ==
                self.undoSnapshotSignature(current)):
            return
        self._undoStack.append(previous)
        if len(self._undoStack) > self.UNDO_LIMIT:
            del self._undoStack[:-self.UNDO_LIMIT]
        self.updateUndoAction()

    def undoLastOperation(self, _value=False):
        self.finishUndoOperation()
        if not self.filePath or not self._undoStack:
            return False

        snapshot = self._undoStack.pop()
        self._undoRestoring = True
        try:
            if self.canvas.drawing() or self.canvas.continueDrawing():
                self.canvas.current = None
                self.canvas.line.points = []
                self.createCancel()

            self.labelModel.clear()
            self.labelModel.setHorizontalHeaderLabels(
                ["Label", "Extra Info"])
            self.ShapeItemDict.clear()
            self.ItemShapeDict.clear()
            self.canvas.visible.clear()
            self.canvas.selectedShape = None
            self.canvas.selectedShapes = []

            shapes = [self.copyShapeForUndo(shape)
                      for shape in snapshot['shapes']]
            for shape in shapes:
                shape.selected = False
                self.addLabel(shape)
            self.canvas.loadShapes(shapes)

            selected = [shapes[index] for index in snapshot['selected']
                        if 0 <= index < len(shapes)]
            self.canvas._setSelectedShapes(selected)
            self.back_sample = bool(snapshot['back_sample'])

            for actionItem in self.actions.onShapesPresent:
                actionItem.setEnabled(bool(shapes))
            self.dirty = True
            self.actions.save.setEnabled(True)
            self.canvas.update()
        finally:
            self._undoRestoring = False
            self._undoPendingSnapshot = None
            self.updateUndoAction()

        self.status(u'已撤销上一步操作。', 5000)
        return True

    def setDirty(self):
        self.finishUndoOperation()
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setCanvasDirty(self):
        """Mark an in-progress canvas gesture dirty; commit on release."""
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setBackSample(self):
        self.back_sample = True

    def resetBackSample(self):
        self.back_sample = False

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.actions.createSo.setEnabled(True)
        self.actions.createRo.setEnabled(True)

    def autoNext(self):
        if self.playing:
            suc = self.openNextImg()
            if not suc:
                self.actions.play.triggered.emit(False)
                self.actions.play.setChecked(False)

    def playStart(self, value=True):
        if value:
            self.playing = True
            self.displayTimer.start()
        else:
            self.playing = False
            self.displayTimer.stop()

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.resetUndoHistory()
        self.labelModel.clear()
        self.labelModel.setHorizontalHeaderLabels(["Label", "Extra Info"])
        self.ShapeItemDict.clear()
        self.ItemShapeDict.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.actions.pasteFromClipboard.setEnabled(False)
        self.labelCoordinates.clear()
        self.imageDim.clear()

    def labelDataChanged(self, topLeft, bottomRight):
        item0 = self.labelModel.item(topLeft.row(), 0)
        shape = self.ItemShapeDict[item0]
        self.beginUndoOperation()
        if topLeft.column() == 0:
            shape.label = self.labelModel.data(topLeft)
            if sys.version_info < (3, 0, 0):
                shape.label = shape.label.toPyObject()
            color = generateColorByText(shape.label)
            item1 = self.labelModel.item(topLeft.row(), 1)
            item0.setBackground(color)
            item1.setBackground(color)
            shape.line_color = color
            shape.fill_color = color
        else:
            shape.extra_label = self.labelModel.data(topLeft)
            if sys.version_info < (3, 0, 0):
                shape.extra_label = shape.extra_label.toPyObject()
        self.setDirty()
        
        return

    def updateLabelShowing(self, index, str):
        item0 = self.labelModel.item(index.row(), 0)
        shape = self.ItemShapeDict[item0]
        shape.extra_label = str
        self.canvas.update()

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def showInfoDialog(self):
        msg = (u'{0} v{1}\nGNU AGPL v3.0\n'
               u'Upstream © Chinakook 2018. chinakook@msn.com').format(
            __appname__, __version__)
        QMessageBox.information(self, u'About', msg)

    def createShape(self):
        self.canvas.setEditing(0)
        self.canvas.canDrawRotatedRect = False
        self.actions.create.setEnabled(False)
        self.actions.createSo.setEnabled(False)
        self.actions.createRo.setEnabled(False)

    def createSoShape(self):
        self.canvas.setEditing(2)
        self.canvas.canDrawRotatedRect = False
        self.actions.create.setEnabled(False)
        self.actions.createSo.setEnabled(False)
        self.actions.createRo.setEnabled(False)

    def createRoShape(self):
        # E acts as a toggle for rotated-box drawing mode.
        if self.canvas.drawing() and self.canvas.canDrawRotatedRect:
            self.canvas.current = None
            self.canvas.line.points = []
            self.canvas.setHiding(False)
            self.canvas.update()
            self.createCancel()
            return

        self.canvas.setEditing(0)
        self.canvas.canDrawRotatedRect = True
        self.actions.create.setEnabled(False)
        self.actions.createSo.setEnabled(False)
        # Keep this action enabled so pressing E again can leave drawing mode.
        self.actions.createRo.setEnabled(True)
        
    def createCancel(self):
        self.canvas.setEditing(1)
        self.canvas.restoreCursor()
        self.actions.create.setEnabled(True)
        self.actions.createSo.setEnabled(True)
        self.actions.createRo.setEnabled(True)

    def toggleDrawingSensitive(self, drawing=True):
        if not drawing:
            self.canvas.setEditing(1)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)
            self.actions.createSo.setEnabled(True)
            self.actions.createRo.setEnabled(True)

    def toggleDrawMode(self, edit=1):
        self.canvas.setEditing(edit)

    def toggleExtraEditing(self, state):
        index = self.labelsm.currentIndex()
        #print("ExtraEditing", self.sender())
        editindex = self.labelModel.index(index.row(), 1)
        self.labelList.edit(editindex)

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('print-setup.svg')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def editLabel(self):
        if not self.canvas.editing():
            return
        self.labelDialog.updateListItems(self.labelHist)
        self.setLabelEditorActive(True)
        try:
            res = self.labelDialog.popUp()
        finally:
            self.setLabelEditorActive(False)

        if res is not None:
            self.labelHist, self.default_label = res
            self.refreshLabelSelectionOrder()
            self.rememberDefaultLabel(self.default_label)

    def setLabelEditorActive(self, active):
        navigation_actions = (self.actions.openPrevImg, self.actions.openNextImg)
        if active:
            if self._labelNavigationStates is None:
                self._labelNavigationStates = [
                    item.isEnabled() for item in navigation_actions
                ]
            for item in navigation_actions:
                item.setEnabled(False)
        elif self._labelNavigationStates is not None:
            for item, was_enabled in zip(
                    navigation_actions, self._labelNavigationStates):
                item.setEnabled(was_enabled)
            self._labelNavigationStates = None
            if self._focusCanvasAfterLabelEdit:
                self._focusCanvasAfterLabelEdit = False
                QTimer.singleShot(
                    0, partial(self.canvas.setFocus, Qt.OtherFocusReason))

    def rememberDefaultLabel(self, label):
        if label not in self.labelHist:
            return
        self.default_label = label
        self.settings[SETTING_DEFAULT_LABEL] = label
        self.settings.save()

    def loadLabelUsage(self, raw_usage):
        raw_usage = raw_usage if isinstance(raw_usage, dict) else {}
        self.labelUsage = {}
        self._labelUsageSequence = 0
        for label in self.labelHist:
            entry = raw_usage.get(label, {})
            if isinstance(entry, dict):
                try:
                    count = max(0, int(entry.get('count', 0)))
                    last = max(0, int(entry.get('last', 0)))
                except (TypeError, ValueError):
                    count, last = 0, 0
            else:
                try:
                    count, last = max(0, int(entry)), 0
                except (TypeError, ValueError):
                    count, last = 0, 0
            self.labelUsage[label] = {'count': count, 'last': last}
            self._labelUsageSequence = max(self._labelUsageSequence, last)

    def labelSelectionOrder(self):
        original_index = {label: index for index, label in enumerate(self.labelHist)}
        groups = {}
        for label in self.labelHist:
            initial = label[:1].casefold()
            groups.setdefault(initial, []).append(label)

        ordered = []
        for labels in groups.values():
            labels.sort(key=lambda label: (
                -self.labelUsage.get(label, {}).get('count', 0),
                -self.labelUsage.get(label, {}).get('last', 0),
                original_index[label],
            ))
            ordered.extend(labels)
        return ordered

    def refreshLabelSelectionOrder(self):
        self.labelList.updateLabelList(self.labelSelectionOrder())

    def recordLabelUsage(self, label):
        if label not in self.labelHist:
            return
        self._labelUsageSequence += 1
        entry = self.labelUsage.setdefault(label, {'count': 0, 'last': 0})
        entry['count'] = int(entry.get('count', 0)) + 1
        entry['last'] = self._labelUsageSequence
        self.settings[SETTING_LABEL_USAGE] = self.labelUsage
        self.settings.save()
        if hasattr(self, 'labelList'):
            self.refreshLabelSelectionOrder()


    def fileCurrentChanged(self, current, previous):
        # File-list clicks and navigation shortcuts change the selection
        # before this slot runs. When auto-save is disabled, give the user a
        # chance to keep editing instead of silently discarding new boxes.
        if self.dirty and not self.autoSaving.isChecked():
            self.labelList.earlyCommit()
            if not self.discardChangesDialog():
                self.filesm.blockSignals(True)
                try:
                    self.filesm.setCurrentIndex(
                        previous, QItemSelectionModel.SelectCurrent)
                finally:
                    self.filesm.blockSignals(False)
                if previous.isValid():
                    self.statFile.setText('{0}/{1}'.format(
                        previous.row() + 1, previous.model().rowCount()))
                    self.fileListView.scrollTo(previous)
                return

        self.statFile.setText('{0}/{1}'.format(current.row()+1, current.model().rowCount()))
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                
                self.labelList.earlyCommit()
                if self.dirty is True:
                    if len(self.canvas.shapes) > 0 or self.back_sample:
                        self.fileModel.setData(previous, len(self.canvas.shapes), Qt.BackgroundRole)
                        self.saveFile()
                    else:
                        self.fileModel.setData(previous, None, Qt.BackgroundRole)
                        self.removeFile()
            else:
                self.openAnnotationDirDialog()
                return
        filename = self.fileModel.data(current, Qt.EditRole)
        if filename:
            self.loadFile(filename)

        if self.canvas.selectedShape:
            self.canvas.selectedShape.selected = False
            self.canvas.selectedShape = None
            self.canvas.setHiding(False)
        self.resetBackSample()

    # Add chris
    def btnstate(self, item= None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return
        
        item0 = self.labelModel.itemFromIndex(self.labelModel.index(self.labelsm.currentIndex().row(), 0))
        if item0 is None:
            item0 = self.labelModel.item(self.labelModel.rowCount() - 1,0)

        difficult = self.diffcButton.isChecked()

        try:
            shape = self.ItemShapeDict[item0]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                self.beginUndoOperation()
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                #self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
                pass
        except:
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape and shape in self.ShapeItemDict:
                # When multi-selecting, prevent labelCurrentChanged from
                # calling selectShape (which would clear multi-selection)
                if len(self.canvas.selectedShapes) > 1:
                    self._noSelectionSlot = True
                item0 = self.ShapeItemDict[shape]
                index = self.labelModel.indexFromItem(item0)
                self.labelList.selectRow(index.row())
                #self.labelsm.setCurrentIndex(index, QItemSelectionModel.SelectCurrent)

            else:
                
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.copyToClipboard.setEnabled(selected)

    def addLabel(self, shape):
        shape.paintLabel = self.paintLabelsOption.isChecked()

        item0 = HashableQStandardItem(shape.label)
        item1 = QStandardItem(shape.extra_label)
        color = generateColorByText(shape.label)
        item0.setBackground(color)
        item1.setBackground(color)
        self.labelModel.appendRow([item0, item1])

        self.ShapeItemDict[shape] = item0
        self.ItemShapeDict[item0] = shape
        
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            return

        item0 = self.ShapeItemDict[shape]
        index = self.labelModel.indexFromItem(item0)
        
        self.labelModel.removeRows(index.row(), 1)
        del self.ShapeItemDict[shape]
        del self.ItemShapeDict[item0]

    def remAllLabels(self):
        self.canvas.deleteAll()
        self.labelModel.clear()
        self.ShapeItemDict.clear()
        self.ItemShapeDict.clear()


    def loadLabels(self, shapes):
        s = []
        for shape_info in shapes:
            if len(shape_info) == 5:
                label, points, line_color, fill_color, difficult = shape_info
                extra_label = ''
                isRotated = False
                direction = 0
            elif len(shape_info) == 6:
                label, points, line_color, fill_color, difficult, extra_label = shape_info
                isRotated = False
                direction = 0
            elif len(shape_info) == 7:
                label, points, line_color, fill_color, difficult, isRotated, direction = shape_info
                extra_label = ''
            elif len(shape_info) == 8:
                label, points, line_color, fill_color, difficult, isRotated, direction, extra_label = shape_info
            else:
                pass
            shape = Shape(label=label)
            for x, y in points:
                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.direction = direction
            shape.isRotated = isRotated
            shape.extra_label = extra_label
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)
            
            shape.alwaysShowCorner = self.drawCorner.isChecked()

            if not label in self.labelHist:
                self.labelHist.append(label)
                self.labelUsage.setdefault(label, {'count': 0, 'last': 0})
                self.refreshLabelSelectionOrder()
                

            self.addLabel(shape)

        self.canvas.loadShapes(s)

    def saveLabels(self, annotationFilePath):
        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                       # add chris
                        difficult = s.difficult,
                        direction = s.direction,
                        center = s.center,
                        isRotated = s.isRotated,
                        extra_text = s.extra_label)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        try:
            if self.annotationFormat == FORMAT_PASCALVOC:
                if self.labelFile is None:
                    self.labelFile = LabelFile()
                    self.labelFile.verified = self.canvas.verified
                self.labelFile.savePascalVocFormat(
                    annotationFilePath, shapes, self.filePath, self.imageData,
                    self.lineColor.getRgb(), self.fillColor.getRgb())
            else:
                save_yolo_annotations(
                    annotationFilePath,
                    shapes,
                    self.image.width(),
                    self.image.height(),
                    self.labelHist,
                    self.annotationFormat)
            print('Img: %s -> Its annotation: %s' %
                  (self.filePath, annotationFilePath))
            return True
        except (LabelFileError, YoloError, OSError, UnicodeError) as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        self.beginUndoOperation()
        newShapes = self.canvas.copySelectedShape()
        for shape in newShapes:
            self.addLabel(shape)
        if newShapes:
            self.shapeSelectionChanged(True)
            self.setDirty()
        else:
            self.cancelUndoOperation()

    def copyShapeToClipboard(self):
        shapes = (list(self.canvas.selectedShapes)
                  if self.canvas.selectedShapes
                  else ([self.canvas.selectedShape]
                        if self.canvas.selectedShape else []))
        if not shapes:
            return
        self._shapeClipboard = [shape.copy() for shape in shapes]
        self._clipboardPasteCount = 0
        self._shapeClipboardSourceFile = self.clipboardImageKey()
        self.actions.pasteFromClipboard.setEnabled(
            self.canvas.pixmap is not None and not self.canvas.pixmap.isNull())
        self.status('Copied %d Box(es)' % len(self._shapeClipboard))

    def pasteShapeFromClipboard(self):
        if (not self._shapeClipboard or self.canvas.pixmap is None or
                self.canvas.pixmap.isNull()):
            return

        sameSourceImage = (
            self.clipboardImageKey() == self._shapeClipboardSourceFile)
        if not sameSourceImage:
            # Across images, preserve every copied point at its original coordinate.
            target = None
            offset = QPointF(0, 0)
        elif (self.canvas.contextMenuActive and
              self.canvas.contextMenuPos is not None):
            target = self.canvas.contextMenuPos
            offset = None
        else:
            self._clipboardPasteCount += 1
            target = None
            distance = 10 * self._clipboardPasteCount
            offset = QPointF(distance, distance)

        self.beginUndoOperation()
        newShapes = self.canvas.pasteShapes(
            self._shapeClipboard, target=target, offset=offset,
            constrainToCanvas=sameSourceImage,
            avoidExactOverlap=sameSourceImage)
        if not newShapes:
            self.cancelUndoOperation()
            return
        for shape in newShapes:
            shape.alwaysShowCorner = self.drawCorner.isChecked()
            self.addLabel(shape)
        self.shapeSelectionChanged(True)
        self.setDirty()
        self.status('Pasted %d Box(es)' % len(newShapes))

    def clipboardImageKey(self):
        if not self.filePath:
            return None
        return os.path.normcase(os.path.abspath(self.filePath))

    def copyShapeByDragging(self, shape):
        self.addLabel(shape)
        self.shapeSelectionChanged(True)
        self.setCanvasDirty()


    def labelCurrentChanged(self, current, previous):
        if current.row() < 0:
            return
        # Don't override multi-selection from canvas when label row changes
        if len(self.canvas.selectedShapes) > 1:
            return
        item0 = self.labelModel.itemFromIndex(self.labelModel.index(current.row(), 0))
        if self.canvas.editing():
            self._noSelectionSlot =True
            shape = self.ItemShapeDict[item0]
            self.canvas.selectShape(shape)
            self.diffcButton.setChecked(shape.difficult)

    def labelHeaderClicked(self, index, checked):
        item0 = self.labelModel.item(index, 0)
        shape = self.ItemShapeDict[item0]
        self.canvas.setShapeVisible(shape, checked)

    # Callback functions:
    def newShape(self, continous):
        text = self.default_label
        extra_text = ""
        if text is not None:
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color, extra_text)
            shape.alwaysShowCorner=self.drawCorner.isChecked()

            self.addLabel(shape)
            if continous:
                self.recordLabelUsage(text)
            else:
                # Finish drawing, select the new OBB and immediately open its
                # label combo box so typing an initial can change the class.
                self.canvas.setEditing(1)
                self.canvas.selectShape(shape)
                self.actions.create.setEnabled(True)
                self.actions.createSo.setEnabled(True)
                self.actions.createRo.setEnabled(True)
                item = self.ShapeItemDict.get(shape)
                if item is not None:
                    index = self.labelModel.indexFromItem(item)
                    self.labelList.setCurrentIndex(index)
                    self._focusCanvasAfterLabelEdit = True
                    self.labelList.edit(index)

            self.setDirty()

        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        #units = - delta / (8 * 15)
        units = - delta / (2 * 15)
        bar = self.scrollBars[orientation]
        # bar.setValue(bar.value() + bar.singleStep() * units)
        bar.setValue(int(bar.value() + bar.singleStep() * delta))

    def panRequest(self, delta_x, delta_y):
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]
        h_bar.setValue(h_bar.value() + delta_x)
        v_bar.setValue(v_bar.value() + delta_y)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        # QSpinBox accepts integers only. Wheel zoom calculates a float on
        # Python 3, and passing it through can terminate the Qt application.
        self.zoomWidget.setValue(int(round(value)))

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(int(round(new_h_bar_value)))
        v_bar.setValue(int(round(new_v_bar_value)))

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def loadFile(self, filePath=None):
        """Load the specified file, or the last opened file if None."""
        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString

        unicodeFilePath = filePath
        
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                      (u"<p><b>%s</b></p>"
                                       u"<p>Make sure <i>%s</i> is a valid label file.")
                                      % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
                self.canvas.verified = self.labelFile.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                # self.imageData = read(unicodeFilePath, None)
                self.labelFile = None
                self.canvas.verified = False

            # image = QImage.fromData(self.imageData)
            # if image.isNull():
            #     self.errorMessage(u'Error opening file',
            #                       u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
            #     self.status("Error reading %s" % unicodeFilePath)
            #     return False
            #self.status("Loaded %s" % os.path.basename(unicodeFilePath))

            reader0 = QImageReader(unicodeFilePath)
            reader0.setAutoTransform(True)
            # transformation = reader0.transformation()
            # print(transformation)
            image = reader0.read()
            if image.isNull():
                error = reader0.errorString()
                self.canvas.setEnabled(False)
                self.toggleActions(False)
                self.status(u'无法读取图片：%s（%s）' %
                            (unicodeFilePath, error), 10000)
                self.errorMessage(
                    u'图片读取失败',
                    u'无法打开图片：<br>%s<br><br>%s<br>'
                    u'可以继续切换到其他图片。' %
                    (unicodeFilePath, error))
                return False

            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))
            self.imageDim.setText('%d x %d' % (self.image.width(), self.image.height()))
            if self.labelFile is not None:
                self.loadLabels(self.labelFile.shapes)
            self.setClean()
            self.canvas.setEnabled(True)
            self.actions.pasteFromClipboard.setEnabled(
                bool(self._shapeClipboard))
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            # Load a matching annotation while preserving the image folder's
            # relative subdirectory structure. The selected output format is
            # preferred when XML and TXT both exist; TXT contents are detected
            # automatically as YOLO boxes (5 columns) or YOLO OBB (9 columns).
            vocReader = None
            annotationBasePath = self.annotationBasePathForImage(
                self.filePath)

            xmlPath = annotationBasePath + XML_EXT
            yoloPath = annotationBasePath + YOLO_EXT
            annotationCandidates = ((xmlPath, 'xml'), (yoloPath, 'txt'))
            if self.annotationFormat != FORMAT_PASCALVOC:
                annotationCandidates = tuple(reversed(annotationCandidates))

            for annotationPath, annotationKind in annotationCandidates:
                if not os.path.isfile(annotationPath):
                    continue
                if annotationKind == 'xml':
                    vocReader = self.loadPascalXMLByFilename(annotationPath)
                else:
                    self.loadYOLOByFilename(annotationPath)
                break

            if vocReader is not None:
                vocWidth, vocHeight, _ = vocReader.getSize()
                if self.image.width() != vocWidth or self.image.height() != vocHeight:
                    #self.errorMessage("Image info not matched", "The width or height of annotation file is not matched with that of the image")
                    self.saveFile()

            self.canvas.setFocus(True)
            return True
        return False

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        if self.image.isNull():
            return
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        if (self.image.isNull() or self.canvas.pixmap is None or
                self.canvas.pixmap.isNull()):
            return
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        if not math.isfinite(value) or value <= 0:
            value = 1.0
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        if self.canvas.pixmap is None:
            return 1.0
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        if w1 <= 0 or h1 <= 0 or w2 <= 0 or h2 <= 0:
            return 1.0
        a1 = w1 / h1
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        if self.canvas.pixmap is None:
            return 1.0
        pixmapWidth = self.canvas.pixmap.width()
        if w <= 0 or pixmapWidth <= 0:
            return 1.0
        return w / pixmapWidth

    def setAutoAnnotationWidgetsVisible(self, visible):
        self.autoAnnotationStatus.setVisible(visible)
        self.autoAnnotationProgress.setVisible(visible)
        self.autoAnnotationCancelButton.setVisible(visible)

    def selectAutoAnnotationModel(self, _value=False):
        current_model = self.autoAnnotationModelPath
        if current_model and os.path.isfile(current_model):
            start_path = current_model
        elif current_model:
            start_path = os.path.dirname(current_model)
        else:
            start_path = self.currentPath()
        selected = QFileDialog.getOpenFileName(
            self,
            u'%s - 选择自动标注模型' % __appname__,
            start_path,
            u'Ultralytics PyTorch 模型 (*.pt)')
        if isinstance(selected, (tuple, list)):
            selected = selected[0]
        if not selected:
            return ''
        self.autoAnnotationModelPath = os.path.abspath(selected)
        self.settings[SETTING_AUTO_ANNOTATION_MODEL] = (
            self.autoAnnotationModelPath)
        self.settings.save()
        self.status(
            u'自动标注模型：%s' % self.autoAnnotationModelPath,
            10000)
        return self.autoAnnotationModelPath

    def currentShapesForAutoAnnotation(self):
        """Return current canvas boxes in the format used by YOLO writers."""
        return [{
            'label': shape.label,
            'points': [(point.x(), point.y()) for point in shape.points],
            'isRotated': bool(shape.isRotated),
        } for shape in self.canvas.shapes]

    def ensureSingleAutoAnnotationSaveDir(self):
        """Choose a label directory without reloading unsaved current boxes."""
        if self.defaultSaveDir and os.path.isdir(self.defaultSaveDir):
            return True
        start_path = self.dirname if self.dirname else self.currentPath()
        selected = QFileDialog.getExistingDirectory(
            self,
            u'%s - Open Annotation Dir' % __appname__,
            start_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if not selected:
            return False
        self.defaultSaveDir = os.path.abspath(selected)
        self.settings[SETTING_SAVE_DIR] = self.defaultSaveDir
        self.settings.save()
        self.status(
            u'标签目录：%s' % self.defaultSaveDir,
            10000)
        return True

    def startSingleAutoAnnotation(self, _value=False):
        if (self.autoAnnotationThread is not None and
                self.autoAnnotationThread.isRunning()):
            self.status(u'自动标注正在运行。', 5000)
            return
        if not self.filePath or not os.path.isfile(self.filePath):
            self.errorMessage(
                u'没有当前图片', u'请先打开需要标注的图片。')
            return
        if not self.ensureSingleAutoAnnotationSaveDir():
            return
        if (not self.autoAnnotationModelPath or
                not os.path.isfile(self.autoAnnotationModelPath)):
            if not self.selectAutoAnnotationModel():
                return
        if not self.autoAnnotationModelPath.lower().endswith('.pt'):
            self.errorMessage(
                u'自动标注模型无效',
                u'请选择 Ultralytics YOLO / YOLO OBB 的 .pt 模型文件。')
            return
        if not self.labelHist:
            self.errorMessage(
                u'项目类别为空',
                u'请先在 data/predefined_classes.txt 中配置项目类别。')
            return

        annotation_base = self.annotationBasePathForImage(self.filePath)
        xml_path = annotation_base + XML_EXT
        txt_path = annotation_base + YOLO_EXT
        existing_shapes = self.currentShapesForAutoAnnotation()
        existing_files = [path for path in (xml_path, txt_path)
                          if os.path.isfile(path)]
        has_existing = bool(
            existing_shapes or existing_files or self.back_sample)
        existing_policy = 'overwrite'

        if has_existing:
            prompt = QMessageBox(self)
            prompt.setIcon(QMessageBox.Question)
            prompt.setWindowTitle(u'当前图片已有标签')
            prompt.setText(
                u'当前图片已有 %d 个框%s，请选择处理方式。' %
                (len(existing_shapes),
                 (u'，并检测到 %d 个标签文件' % len(existing_files))
                 if existing_files else u''))
            prompt.setInformativeText(
                u'覆盖原标签：只保留本次模型生成的框。\n'
                u'直接添加：保留当前框，再加入模型生成的框。\n\n'
                u'模型结果保存为 YOLO 或 YOLO OBB TXT；同名 XML 不会删除。')
            overwrite_button = prompt.addButton(
                u'覆盖原标签', QMessageBox.DestructiveRole)
            append_button = prompt.addButton(
                u'直接添加', QMessageBox.AcceptRole)
            prompt.addButton(QMessageBox.Cancel)
            prompt.exec_()
            if prompt.clickedButton() is overwrite_button:
                existing_policy = 'overwrite'
            elif prompt.clickedButton() is append_button:
                existing_policy = 'append'
            else:
                return

        job = {
            'image_path': self.filePath,
            'annotation_base': annotation_base,
            'existing_policy': existing_policy,
            'existing_shapes': (existing_shapes
                                if existing_policy == 'append' else []),
            'return_shapes': True,
        }
        self.startAutoAnnotationJobs([job], mode='single')

    def startAutoAnnotation(self, _value=False):
        if (self.autoAnnotationThread is not None and
                self.autoAnnotationThread.isRunning()):
            self.status(u'自动标注正在运行。', 5000)
            return

        if self.dirty:
            if not self.discardChangesDialog():
                return
            current_file = self.filePath
            if current_file:
                self.loadFile(current_file)

        if not self.defaultSaveDir or not os.path.isdir(self.defaultSaveDir):
            self.openAnnotationDirDialog()
            if (not self.defaultSaveDir or
                    not os.path.isdir(self.defaultSaveDir)):
                return

        if (not self.autoAnnotationModelPath or
                not os.path.isfile(self.autoAnnotationModelPath)):
            if not self.selectAutoAnnotationModel():
                return
        if not self.autoAnnotationModelPath.lower().endswith('.pt'):
            self.errorMessage(
                u'自动标注模型无效',
                u'请选择 Ultralytics YOLO / YOLO OBB 的 .pt 模型文件。')
            return
        if not self.labelHist:
            self.errorMessage(
                u'项目类别为空',
                u'请先在 data/predefined_classes.txt 中配置项目类别。')
            return

        if self.dirname and os.path.isdir(self.dirname):
            image_files = self.scanAllImages(self.dirname)
        elif self.filePath and os.path.isfile(self.filePath):
            image_files = [self.filePath]
        else:
            self.errorMessage(
                u'没有图片', u'请先使用 Open Dir 打开图片目录。')
            return

        jobs = []
        existing_count = 0
        for image_path in image_files:
            annotation_base = self.annotationBasePathForImage(image_path)
            if (os.path.isfile(annotation_base + XML_EXT) or
                    os.path.isfile(annotation_base + YOLO_EXT)):
                existing_count += 1
                continue
            jobs.append({
                'image_path': image_path,
                'annotation_base': annotation_base,
            })
        if not jobs:
            QMessageBox.information(
                self,
                u'自动标注',
                u'当前图片目录中的 %d 张图片都已有 XML 或 TXT 标签，'
                u'没有覆盖任何文件。' % existing_count)
            return

        self.autoAnnotationExistingCount = existing_count
        self.startAutoAnnotationJobs(jobs, mode='batch')

    def startAutoAnnotationJobs(self, jobs, mode):
        self.autoAnnotationMode = mode
        self.autoAnnotationProgress.setRange(0, len(jobs))
        self.autoAnnotationProgress.setValue(0)
        if mode == 'single':
            self.autoAnnotationStatus.setText(u'加载模型…（当前图片）')
        else:
            self.autoAnnotationStatus.setText(
                u'加载模型…（待标注 %d 张）' % len(jobs))
        self.autoAnnotationStatus.setToolTip(self.autoAnnotationModelPath)
        self.autoAnnotationCancelButton.setEnabled(True)
        self.autoAnnotationCancelButton.setText(u'中止')
        self.setAutoAnnotationWidgetsVisible(True)
        self.actions.autoAnnotate.setEnabled(False)
        self.actions.singleAutoAnnotate.setEnabled(False)
        self.actions.selectAutoAnnotationModel.setEnabled(False)
        self.fileListView.setEnabled(False)
        self.canvas.setEnabled(False)

        thread = AutoAnnotationThread(
            self.autoAnnotationModelPath,
            jobs,
            self.labelHist,
            confidence=0.25,
            parent=self)
        thread.modelLoaded.connect(self.autoAnnotationModelLoaded)
        thread.progressChanged.connect(self.autoAnnotationProgressChanged)
        thread.completed.connect(self.autoAnnotationCompleted)
        thread.failed.connect(self.autoAnnotationFailed)
        thread.finished.connect(self.autoAnnotationThreadFinished)
        self.autoAnnotationThread = thread
        thread.start()

    def autoAnnotationModelLoaded(self, annotation_format, mapping_details):
        self.setAnnotationFormat(annotation_format)
        # Switching format can reload the current image; keep editing disabled
        # until the background batch has finished.
        self.canvas.setEnabled(False)
        mapping_text = '\n'.join(
            '%s -> %s (%.1f%%)' %
            (item['model_name'], item['project_name'], item['score'] * 100.0)
            for item in mapping_details)
        self.autoAnnotationStatus.setText(
            u'模型已加载：%s' % self.annotationFormatName(annotation_format))
        self.autoAnnotationStatus.setToolTip(mapping_text)

    def autoAnnotationProgressChanged(self, done, total, image_path,
                                      object_count, state):
        self.autoAnnotationProgress.setRange(0, total)
        self.autoAnnotationProgress.setValue(done)
        filename = os.path.basename(image_path)
        if state == 'saved':
            text = u'%s：%d 个框' % (filename, object_count)
        elif state == 'skipped':
            text = u'%s：已有标签，已跳过' % filename
        else:
            text = u'%s：处理失败，继续下一张' % filename
        self.autoAnnotationStatus.setText(text)
        self.autoAnnotationStatus.setToolTip(image_path)

    def cancelAutoAnnotation(self):
        thread = self.autoAnnotationThread
        if thread is None or not thread.isRunning():
            return
        thread.cancel()
        self.autoAnnotationCancelButton.setEnabled(False)
        self.autoAnnotationCancelButton.setText(u'中止中…')
        self.autoAnnotationStatus.setText(u'将在当前图片推理结束后中止…')

    def autoAnnotationCompleted(self, summary):
        if self.autoAnnotationMode == 'single':
            self.singleAutoAnnotationCompleted(summary)
            return
        self.finishAutoAnnotationUi()
        self.refreshAnnotationFileList(reloadCurrent=bool(self.filePath))

        mapping_lines = [
            '%s -> %s (%.1f%%)' %
            (item['model_name'], item['project_name'], item['score'] * 100.0)
            for item in summary.get('mapping', [])
        ]
        if len(mapping_lines) > 20:
            mapping_lines = mapping_lines[:20] + [
                u'……其余 %d 项请查看状态栏提示。' %
                (len(summary.get('mapping', [])) - 20)]

        title = u'自动标注已中止' if summary.get('cancelled') else u'自动标注完成'
        message_lines = [
            u'保存格式：%s' % self.annotationFormatName(
                summary.get('format')),
            u'新生成标签：%d 张，共 %d 个框' %
            (summary.get('saved', 0), summary.get('objects', 0)),
            u'保护并跳过已有标签：%d 张' %
            (self.autoAnnotationExistingCount + summary.get('skipped', 0)),
        ]
        errors = summary.get('errors', [])
        if errors:
            message_lines.append(u'失败：%d 张' % len(errors))
            message_lines.append(u'前几项错误：')
            message_lines.extend(errors[:5])
        message_lines.append(u'')
        message_lines.append(u'模型类别 -> 项目类别：')
        message_lines.extend(mapping_lines)
        message = '\n'.join(message_lines)

        if errors:
            QMessageBox.warning(self, title, message)
        else:
            QMessageBox.information(self, title, message)
        self.status(message_lines[1] + u'；' + message_lines[2], 15000)

    def singleAutoAnnotationCompleted(self, summary):
        self.finishAutoAnnotationUi()
        self.refreshAnnotationFileList(reloadCurrent=bool(self.filePath))

        results = summary.get('job_results', [])
        result = results[0] if results else None
        errors = summary.get('errors', [])
        if summary.get('cancelled'):
            QMessageBox.information(
                self,
                u'单张自动标注已中止',
                u'当前图片没有写入新的模型标签。')
            self.status(u'单张自动标注已中止。', 10000)
            return
        if errors or result is None:
            message = (u'当前图片自动标注失败。\n\n%s' %
                       '\n'.join(errors[:5]))
            QMessageBox.warning(self, u'单张自动标注失败', message)
            self.status(u'当前图片自动标注失败。', 10000)
            return

        policy_name = (u'直接添加' if result.get('policy') == 'append'
                       else u'覆盖原标签')
        generated_count = len(result.get('generated_shapes', []))
        final_count = len(result.get('saved_shapes', []))
        mapping_lines = [
            '%s -> %s (%.1f%%)' %
            (item['model_name'], item['project_name'], item['score'] * 100.0)
            for item in summary.get('mapping', [])
        ]
        if len(mapping_lines) > 10:
            mapping_lines = mapping_lines[:10] + [
                u'……其余 %d 项略。' %
                (len(summary.get('mapping', [])) - 10)]
        message_lines = [
            u'处理方式：%s' % policy_name,
            u'保存格式：%s' % self.annotationFormatName(
                summary.get('format')),
            u'模型新增：%d 个框' % generated_count,
            u'当前图片最终：%d 个框' % final_count,
            u'保存位置：%s' % result.get('annotation_path', ''),
        ]
        if mapping_lines:
            message_lines.extend((u'', u'模型类别 -> 项目类别：'))
            message_lines.extend(mapping_lines)
        message = '\n'.join(message_lines)
        QMessageBox.information(self, u'单张自动标注完成', message)
        self.status(
            u'当前图片自动标注完成：新增 %d 个框，最终 %d 个框。' %
            (generated_count, final_count),
            15000)

    def autoAnnotationFailed(self, error):
        self.finishAutoAnnotationUi()
        title = (u'单张自动标注失败'
                 if self.autoAnnotationMode == 'single'
                 else u'自动标注失败')
        self.errorMessage(
            title,
            u'%s<br><br>如果提示缺少 ultralytics，请在当前 LabelImg2 '
            u'环境中运行：<br><code>pip install -r requirements.txt</code>' %
            error)

    def finishAutoAnnotationUi(self):
        self.actions.autoAnnotate.setEnabled(True)
        self.actions.singleAutoAnnotate.setEnabled(bool(self.filePath))
        self.actions.selectAutoAnnotationModel.setEnabled(True)
        self.fileListView.setEnabled(True)
        self.canvas.setEnabled(bool(self.filePath))
        self.setAutoAnnotationWidgetsVisible(False)

    def autoAnnotationThreadFinished(self):
        thread = self.sender()
        if thread is self.autoAnnotationThread:
            self.autoAnnotationThread = None
            self.autoAnnotationMode = None
        thread.deleteLater()

    def closeEvent(self, event):
        if (self.autoAnnotationThread is not None and
                self.autoAnnotationThread.isRunning()):
            self.cancelAutoAnnotation()
            QMessageBox.information(
                self,
                u'自动标注正在中止',
                u'请等待当前图片推理结束后再关闭 LabelImg2。')
            event.ignore()
            return
        if not self.mayContinue():
            event.ignore()
            return
        settings = self.settings
        # Remember the current image so directory-based sessions can resume.
        settings[SETTING_FILENAME] = self.filePath if self.filePath else ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = self.defaultSaveDir
        else:
            settings[SETTING_SAVE_DIR] = ""

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ""

        settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_DRAW_CORNER] = self.drawCorner.isChecked()
        settings[SETTING_PAINT_LABEL] = self.paintLabelsOption.isChecked()
        settings[SETTING_DEFAULT_LABEL] = self.default_label
        settings[SETTING_LABEL_USAGE] = self.labelUsage
        settings[SETTING_ANNOTATION_FORMAT] = self.annotationFormat
        settings.save()
    ## User Dialogs ##

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = os.path.abspath(relativePath)
                    images.append(path)
        collator = QCollator()
        locale = QLocale(QLocale.Chinese)
        collator.setLocale(locale)
        collator.setNumericMode(True)
        def sort_key(s):
            return collator.sortKey(s)
        sorted_images = sorted(images, key=sort_key)
        return sorted_images

    def annotationFormatName(self, annotationFormat=None):
        annotationFormat = annotationFormat or self.annotationFormat
        return {
            FORMAT_PASCALVOC: 'Pascal VOC XML',
            FORMAT_YOLO: 'YOLO',
            FORMAT_YOLO_OBB: 'YOLO OBB',
        }.get(annotationFormat, annotationFormat)

    def refreshAnnotationFileList(self, reloadCurrent=False):
        if not self.dirname or not os.path.isdir(self.dirname):
            if reloadCurrent and self.filePath:
                currentFile = self.filePath
                self.loadFile(currentFile)
            return

        currentFile = self.filePath
        imglist = self.scanAllImages(self.dirname)
        self.filesm.blockSignals(True)
        try:
            self.fileModel.setStringList(
                imglist, self.dirname, self.defaultSaveDir,
                self.annotationFormat)
            if currentFile in imglist:
                currentIndex = self.fileModel.index(imglist.index(currentFile))
                self.filesm.setCurrentIndex(
                    currentIndex, QItemSelectionModel.SelectCurrent)
                self.fileListView.scrollTo(currentIndex)
        finally:
            self.filesm.blockSignals(False)

        if reloadCurrent and currentFile and currentFile in imglist:
            self.loadFile(currentFile)

    def setAnnotationFormat(self, annotationFormat, checked=True):
        if not checked or annotationFormat not in SUPPORTED_ANNOTATION_FORMATS:
            return
        changed = annotationFormat != self.annotationFormat
        self.annotationFormat = annotationFormat
        self.annotationFormatActions[annotationFormat].setChecked(True)
        self.settings[SETTING_ANNOTATION_FORMAT] = annotationFormat
        self.settings.save()

        # Keep unsaved boxes on screen when switching output format. If the
        # image is clean, reload it so the newly preferred XML/TXT file is
        # reflected immediately.
        self.refreshAnnotationFileList(
            reloadCurrent=changed and not self.dirty)
        self.status(
            'Annotation format: %s' %
            self.annotationFormatName(annotationFormat),
            8000)

    def openAnnotationDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        path = (self.defaultSaveDir
                if self.defaultSaveDir and os.path.isdir(self.defaultSaveDir)
                else (self.dirname if self.dirname else '.'))
        if dirpath is None:
            dirpath = QFileDialog.getExistingDirectory(
                self,
                '%s - Open Annotation Dir' % __appname__,
                path,
                QFileDialog.ShowDirsOnly |
                QFileDialog.DontResolveSymlinks)
        if not dirpath:
            return

        self.defaultSaveDir = os.path.abspath(dirpath)
        self.settings[SETTING_SAVE_DIR] = self.defaultSaveDir
        self.settings.save()
        self.refreshAnnotationFileList(reloadCurrent=bool(self.filePath))
        self.status(
            'Annotation directory: %s | Save format: %s' %
            (self.defaultSaveDir, self.annotationFormatName()),
            10000)

    def changeSavedirDialog(self, _value=False):
        """Compatibility alias for older shortcuts and internal calls."""
        return self.openAnnotationDirDialog(_value)

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath, resumeFilePath=None):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None

        # Preserve the last explicitly selected annotation directory.  Only
        # fall back to saving beside the images when no valid saved directory
        # is available (for example on the very first launch).
        if not self.defaultSaveDir or not os.path.isdir(self.defaultSaveDir):
            self.defaultSaveDir = dirpath

        imglist = self.scanAllImages(dirpath)
        self.fileModel.setStringList(
            imglist, self.dirname, self.defaultSaveDir,
            self.annotationFormat)
        self.setWindowTitle(__appname__ + ' ' + self.dirname)
        resumeFilePath = os.path.abspath(resumeFilePath) if resumeFilePath else None
        if resumeFilePath in imglist:
            resumeIndex = self.fileModel.index(imglist.index(resumeFilePath))
            self.filesm.setCurrentIndex(resumeIndex, QItemSelectionModel.SelectCurrent)
            self.fileListView.scrollTo(resumeIndex)
        else:
            self.openNextImg()

    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
         if self.filePath is not None:
            if self.annotationFormat != FORMAT_PASCALVOC:
                # YOLO text formats have no Pascal VOC-style verified field.
                # Treat Verify as an explicit save so the action remains safe.
                self.canvas.verified = True
                self.fileModel.setData(
                    self.filesm.currentIndex(), len(self.canvas.shapes),
                    Qt.BackgroundRole)
                self.saveFile()
                self.status(
                    '%s saved (YOLO formats do not store a verified flag).' %
                    self.annotationFormatName(),
                    8000)
                return
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                self.labelFile.toggleVerify()

            self.fileModel.setData(self.filesm.currentIndex(), len(self.canvas.shapes), Qt.BackgroundRole)
            self.canvas.verified = self.labelFile.verified
            self.paintCanvas()
            self.saveFile()

    def openPrevImg(self, _value=False):
        currIndex = self.filesm.currentIndex()
        if currIndex.row() - 1 < 0:
            return False
        
        prevIndex = self.fileModel.index(currIndex.row() - 1)
      
        self.filesm.setCurrentIndex(prevIndex, QItemSelectionModel.SelectCurrent)

        return self.filesm.currentIndex() == prevIndex

    def openNextImg(self, _value=False):
        currIndex = self.filesm.currentIndex()
        if currIndex.row() + 1 >= self.fileModel.rowCount():
            return False

        nextIndex = self.fileModel.index(currIndex.row() + 1)      
        self.filesm.setCurrentIndex(nextIndex, QItemSelectionModel.SelectCurrent)

        return self.filesm.currentIndex() == nextIndex

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(self.filePath) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)

            if self.filePath is not None:
                imglist = [self.filePath]
                self.fileModel.setStringList(imglist)
                if self.fileModel.rowCount() > 0:
                    curIndex = self.fileModel.index(0)
                    self.filesm.blockSignals(True)
                    self.filesm.setCurrentIndex(curIndex, QItemSelectionModel.SelectCurrent)
                    self.filesm.blockSignals(False)

    def saveLocal(self, file_path):
        imgFileDir = os.path.dirname(file_path)
        imgFileName = os.path.basename(file_path)
        savedFileName = os.path.splitext(imgFileName)[0]
        savedPath = os.path.join(imgFileDir, savedFileName)
        return self._saveFile(savedPath)

    def annotationExtension(self):
        return (XML_EXT if self.annotationFormat == FORMAT_PASCALVOC
                else YOLO_EXT)

    def annotationBasePathForImage(self, imageFilePath):
        if not self.defaultSaveDir:
            return os.path.splitext(imageFilePath)[0]

        if self.dirname and os.path.isdir(self.dirname):
            try:
                relativePath = os.path.relpath(imageFilePath, self.dirname)
            except ValueError:
                relativePath = None
            if relativePath is not None:
                parentPrefix = os.pardir + os.sep
                if (relativePath != os.pardir and
                        not relativePath.startswith(parentPrefix) and
                        not os.path.isabs(relativePath)):
                    return os.path.join(
                        self.defaultSaveDir,
                        os.path.splitext(relativePath)[0])

        return os.path.join(
            self.defaultSaveDir,
            os.path.splitext(os.path.basename(imageFilePath))[0])

    def annotationPathWithExtension(self, annotationFilePath):
        expectedExtension = self.annotationExtension()
        root, currentExtension = os.path.splitext(annotationFilePath)
        if currentExtension.lower() in (XML_EXT, YOLO_EXT):
            return root + expectedExtension
        return annotationFilePath + expectedExtension

    def saveFile(self, _value=False):
        if not self.filePath:
            return False
        if self.defaultSaveDir is not None and len(self.defaultSaveDir):
            return self._saveFile(
                self.annotationBasePathForImage(self.filePath))
        return self.saveLocal(self.filePath)
            
    def removeFile(self):
        if not self.filePath:
            return False
        if self.defaultSaveDir is not None and len(self.defaultSaveDir):
            savedPath = self.annotationBasePathForImage(self.filePath)
        else:
            imgFileDir = os.path.dirname(self.filePath)
            imgFileName = os.path.basename(self.filePath)
            savedFileName = os.path.splitext(imgFileName)[0]
            savedPath = os.path.join(imgFileDir, savedFileName)
        savedPath = self.annotationPathWithExtension(savedPath)
        if os.path.exists(savedPath):
            os.remove(savedPath)
            return True
        return False

    def saveFileAndRenderList(self, _value=False):
        if self.saveFile(_value=_value):
            cur = self.filesm.currentIndex()
            self.fileModel.setData(
                cur, len(self.canvas.shapes), Qt.BackgroundRole)

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        return self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        extension = self.annotationExtension()
        caption = '%s - Save %s Annotation' % (
            __appname__, self.annotationFormatName())
        filters = '%s File (*%s)' % (
            self.annotationFormatName(), extension)
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(extension[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension + extension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            return dlg.selectedFiles()[0]
        return ''

    def _saveFile(self, annotationFilePath):
        if not annotationFilePath:
            return False

        annotationFilePath = self.annotationPathWithExtension(
            annotationFilePath)

        # Images may be opened recursively from a subdirectory (for example
        # dataset/image.jpg) while annotations are stored under another root.
        # Create the matching annotation subdirectory before writing labels.
        annotationDir = os.path.dirname(os.path.abspath(annotationFilePath))
        try:
            os.makedirs(annotationDir, exist_ok=True)
            if not self.saveLabels(annotationFilePath):
                return False
        except Exception as error:
            self.status(u'标签保存失败：%s' % error, 10000)
            self.errorMessage(
                u'标签保存失败',
                u'无法保存到：<br>%s<br><br>%s' %
                (annotationFilePath, error))
            return False

        self.setClean()
        self.statusBar().showMessage(
            'Saved %s to %s' %
            (self.annotationFormatName(), annotationFilePath))
        self.statusBar().show()
        return True

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def deleteSelectedShape(self):
        self.beginUndoOperation()
        deleted = self.canvas.deleteSelected()
        if deleted:
            for shape in deleted:
                self.remLabel(shape)
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)
                self.resetBackSample()
        else:
            self.cancelUndoOperation()

    def labelAsBackground(self):
        self.beginUndoOperation()
        self.remAllLabels()
        self.setBackSample()
        self.setDirty()

    def deleteLabel(self):
        self.beginUndoOperation()
        self.remAllLabels()
        self.resetBackSample()
        self.setDirty()

    def copyShape(self):
        self.beginUndoOperation()
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.beginUndoOperation()
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return None
        if os.path.isfile(xmlPath) is False:
            return None

        try:
            tVocParseReader = PascalVocReader(xmlPath)
        except Exception as error:
            self.errorMessage(
                u'Error opening Pascal VOC labels',
                u'<p><b>%s</b></p><p>The XML file was not loaded.</p>' %
                str(error))
            self.status('Error reading %s' % xmlPath)
            return None
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified
        return tVocParseReader

    def loadYOLOByFilename(self, txtPath):
        if self.filePath is None or not os.path.isfile(txtPath):
            return None

        try:
            reader = YoloReader(
                txtPath,
                self.image.width(),
                self.image.height(),
                self.labelHist)
        except (OSError, UnicodeError, YoloError) as error:
            self.errorMessage(
                u'Error opening YOLO labels',
                u'<p><b>%s</b></p><p>The TXT file was not loaded.</p>' %
                str(error))
            self.status('Error reading %s' % txtPath)
            return None

        self.loadLabels(reader.getShapes())
        self.canvas.verified = False
        detectedFormat = reader.annotation_format or 'empty YOLO TXT'
        self.status(
            'Loaded %s labels from %s.' %
            (detectedFormat, os.path.basename(txtPath)),
            8000)
        return reader

    def loadYOLOOBBByFilename(self, txtPath):
        """Compatibility alias for code using the previous method name."""
        return self.loadYOLOByFilename(txtPath)

    def togglePaintLabelsOption(self):
        paintLabelsOptionChecked = self.paintLabelsOption.isChecked()
        for shape in self.canvas.shapes:
            shape.paintLabel = paintLabelsOptionChecked

    def exportAsYOLOImpl(self, obb=False):
        annotation_dir = self.defaultSaveDir
        if not annotation_dir or not os.path.isdir(annotation_dir):
            annotation_dir = self.dirname
        if not annotation_dir or not os.path.isdir(annotation_dir):
            self.errorMessage(
                u'Export failed',
                u'Please open an image folder and select the XML save folder first.'
            )
            return

        xml_files = find_xml_files(annotation_dir)
        if not xml_files:
            QMessageBox.warning(
                self,
                u'Export failed',
                u'No XML annotation files were found in:\n%s' % annotation_dir
            )
            return

        export_title = (u'%s - Select YOLO OBB label output directory' % __appname__
                        if obb else
                        u'%s - Select YOLO label output directory' % __appname__)
        save_dir_path = QFileDialog.getExistingDirectory(
            self,
            export_title,
            annotation_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not save_dir_path:
            return

        # Class IDs follow the current preset order, keeping the mapping stable.
        label_map = {}
        for label_name in self.labelHist:
            if label_name and label_name not in label_map:
                label_map[label_name] = len(label_map)

        all_shapes_map = {}
        try:
            for xml_path in xml_files:
                voc_reader = PascalVocReader(xml_path)
                image_width, image_height, _image_depth = voc_reader.getSize()
                if image_width <= 0 or image_height <= 0:
                    raise ValueError(u'Cannot read a valid image size from %s' % xml_path)

                relative_xml_path = os.path.relpath(xml_path, annotation_dir)
                image_annotation = {
                    "height": image_height,
                    "width": image_width,
                    "bboxes": []
                }

                for shape in voc_reader.getShapes():
                    label_name = shape[0]
                    points = shape[1]
                    if len(points) != 4:
                        raise ValueError(
                            u'Annotation does not contain four points: %s' % xml_path
                        )
                    if label_name not in label_map:
                        label_map[label_name] = len(label_map)

                    image_annotation["bboxes"].append({
                        "class": label_name,
                        "x0": points[0][0],
                        "y0": points[0][1],
                        "x1": points[1][0],
                        "y1": points[1][1],
                        "x2": points[2][0],
                        "y2": points[2][1],
                        "x3": points[3][0],
                        "y3": points[3][1],
                    })

                all_shapes_map[relative_xml_path] = image_annotation

            exported_files = cvt_xml_annotations_to_yolo(
                all_shapes_map,
                label_map,
                save_dir_path,
                format='rotbox' if obb else 'box'
            )
        except (IOError, OSError, ValueError) as error:
            self.errorMessage(u'Export failed', str(error))
            return

        format_name = u'YOLO OBB' if obb else u'YOLO'
        self.statusBar().showMessage(
            u'Exported %d %s label files to %s' %
            (len(exported_files), format_name, save_dir_path),
            10000
        )
        QMessageBox.information(
            self,
            u'Export complete',
            u'Converted %d XML files to %s .txt labels.\n\nOutput: %s\n\n'
            u'Only label .txt files were generated.' %
            (len(exported_files), format_name, save_dir_path)
        )
    def exportAsYOLO(self, _value=False):
        self.exportAsYOLOImpl(obb=False)


    def exportAsYOLOOBB(self, _value=False):
        self.exportAsYOLOImpl(obb=True)


def find_xml_files(annotation_dir):
    result = []
    for root, _dirs, files in os.walk(annotation_dir):
        for filename in files:
            if filename.lower().endswith(XML_EXT):
                result.append(os.path.join(root, filename))
    return sorted(result, key=lambda path: path.casefold())


def find_matching_files(dir_a, dir_b):
    supported_extensions = tuple(['.%s' % fmt.data().decode("ascii").lower() for fmt 
                                  in QImageReader.supportedImageFormats()])
    xml_files = set()
    for file in os.listdir(dir_b):
        if file.endswith(".xml"):
            xml_files.add(os.path.splitext(file)[0])

    result = []
    for file in os.listdir(dir_a):
        if os.path.splitext(file)[0] in xml_files and file.lower().endswith(supported_extensions):
            result.append(os.path.splitext(file)[0] + ".xml")  # 添加对应的xml文件名到结果列表

    return result

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("tag-black-shape.svg"))
    
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(
                         os.path.dirname(sys.argv[0]),
                         'data', 'predefined_classes.txt'),
                     argv[3] if len(argv) >= 4 else None)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())

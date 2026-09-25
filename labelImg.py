#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-only
# LabelImg2 Custom is distributed under GNU AGPL v3.0. Upstream portions
# retain the MIT terms in LICENSE-MIT-UPSTREAM.
from __future__ import absolute_import

import math
import os
import platform
import re
import sys
import subprocess
from collections import Counter
from functools import partial

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

# Add internal libs
from libs.constants import *
from libs.version import __version__
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.pascal_voc_io import PascalVocReader, XML_EXT
from libs.yolo_obb_io import (YoloReader, YoloError, YOLO_EXT,
                              inspect_yolo_file, save_yolo_annotations)
from libs.annotation_converter import (AnnotationConversionError,
                                       convert_annotation_file)
from libs.auto_annotation import AutoAnnotationThread
from libs.annotation_scan import AnnotationScanner, iter_annotation_files
from libs.labelShortcutDialog import (LabelShortcutDialog,
                                      LabelShortcutValidationError,
                                      canonical_shortcut,
                                      validate_label_shortcuts)
from libs.classFileDialog import (ClassFileDialog, ClassFileError,
                                  read_class_file)
from libs.trash_utils import TrashError, move_to_trash
from libs.ui_geometry import available_screen_geometry

from libs.labelView import (CLabelView, HashableQStandardItem,
                            label_search_keys)
from libs.fileView import CFileView, natural_path_key

__appname__ = 'labelImg2'
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
            addActions(toolbar, actions)
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

        # Load the last selected class.txt. Keep the bundled file as a safe
        # fallback when a moved history item no longer exists.
        self.bundledClassFile = (os.path.abspath(defaultPrefdefClassFile)
                                 if defaultPrefdefClassFile else '')
        savedClassFile = settings.get(SETTING_CLASS_FILE, '')
        self.classFileHistory = ClassFileDialog.normalizeHistory(
            [savedClassFile, self.bundledClassFile] + list(
                settings.get(SETTING_CLASS_FILE_HISTORY, []) or []))
        self.classFilePath = (os.path.abspath(savedClassFile)
                              if savedClassFile else self.bundledClassFile)
        if not self.loadPredefinedClasses(self.classFilePath):
            self.classFilePath = self.bundledClassFile
            self.loadPredefinedClasses(self.classFilePath)
        self.predefinedClasses = tuple(self.labelHist)
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
        self._shapeClipboardIsCut = False
        self._undoStack = []
        self._undoPendingSnapshot = None
        self._undoRestoring = False
        self._singleAutoAnnotationUndoContext = None
        self.labelShortcutMappings = settings.get(
            SETTING_LABEL_SHORTCUTS, [])
        self.labelShortcutActions = []
        self._labelEditorActive = False
        self._labelShortcutEditorStates = None
        self._pendingLabelShortcut = None
        # Counts boxes created during this application run only.  It is
        # intentionally not persisted in Settings, so reopening starts at 0.
        self.sessionLabelCount = 0
        self._sessionShapeRegistry = {}
        self._pendingAutoSessionCounts = {}
        self.autoAnnotationThread = None
        self.autoAnnotationModelPath = settings.get(
            SETTING_AUTO_ANNOTATION_MODEL, '')
        self.autoAnnotationConfidence = self.normalizeAutoAnnotationConfidence(
            settings.get(SETTING_AUTO_ANNOTATION_CONFIDENCE, 0.25))
        self.autoAnnotationExistingCount = 0
        self.autoAnnotationMode = None
        self.annotationScanTimer = QTimer(self)
        self.annotationScanTimer.setInterval(0)
        self.annotationScanTimer.timeout.connect(
            self.processAnnotationScanBatch)
        self.annotationScanner = None
        self.annotationScanIterator = None
        self.annotationScanMode = None
        self.annotationScanDone = 0
        self.annotationScanTotal = 0
        self.annotationScanShowWarnings = False
        self.annotationScanLastStatus = QElapsedTimer()

        labellistLayout = QVBoxLayout()
        labellistLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for edit and diffc button
        self.diffcButton = QCheckBox(u'difficult')
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classFileButton = QToolButton()
        self.classFileButton.setObjectName('classFileButton')
        self.classFileButton.setIcon(newIcon('tags.svg'))
        self.classFileButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.classFileButton.clicked.connect(self.openClassFileManager)
        self.labelShortcutSettingsButton = QToolButton()
        self.labelShortcutSettingsButton.setObjectName(
            'labelShortcutSettingsButton')
        self.labelShortcutSettingsButton.setText(u'标签快捷键设置...')
        self.labelShortcutSettingsButton.setIcon(newIcon('settings.svg'))
        self.labelShortcutSettingsButton.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon)
        self.labelShortcutSettingsButton.clicked.connect(
            self.openLabelShortcutSettings)

        labellistLayout.addWidget(self.editButton)
        labellistLayout.addWidget(self.classFileButton)
        labellistLayout.addWidget(self.labelShortcutSettingsButton)
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

        labellistLayout.addWidget(self.labelList, 1)

        self.labelStatisticsGroup = QGroupBox(u'标签统计')
        self.labelStatisticsGroup.setObjectName('labelStatisticsGroup')
        statisticsLayout = QGridLayout()
        statisticsLayout.setContentsMargins(8, 6, 8, 6)
        statisticsLayout.setHorizontalSpacing(12)
        statisticsLayout.setVerticalSpacing(4)

        self.projectLabelCount = QLabel('0')
        self.projectLabelCount.setObjectName('projectLabelCount')
        self.currentImageLabelCount = QLabel('0')
        self.currentImageLabelCount.setObjectName('currentImageLabelCount')
        self.sessionLabelCountDisplay = QLabel('0')
        self.sessionLabelCountDisplay.setObjectName(
            'sessionLabelCountDisplay')
        countDisplays = (
            self.projectLabelCount,
            self.currentImageLabelCount,
            self.sessionLabelCountDisplay,
        )
        for display in countDisplays:
            display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            display.setMinimumWidth(48)

        statisticsLayout.addWidget(QLabel(u'项目总标签数：'), 0, 0)
        statisticsLayout.addWidget(self.projectLabelCount, 0, 1)
        statisticsLayout.addWidget(QLabel(u'当前图片标签数：'), 1, 0)
        statisticsLayout.addWidget(self.currentImageLabelCount, 1, 1)
        statisticsLayout.addWidget(QLabel(u'本次工作已打标签数：'), 2, 0)
        statisticsLayout.addWidget(self.sessionLabelCountDisplay, 2, 1)
        self.labelStatisticsGroup.setLayout(statisticsLayout)
        labellistLayout.addWidget(self.labelStatisticsGroup, 0)

        self.dock = QDockWidget(u'Box Labels', self)
        self.dock.setObjectName(u'Labels')
        self.dock.setWidget(labelListContainer)

        self.labelList.toggleEdit.connect(self.toggleExtraEditing)

        self.fileListView = CFileView()
        

        self.fileModel = self.fileListView.model()
        savedFlags = settings.get(SETTING_FLAGGED_IMAGES, [])
        self.fileModel.setFlaggedPaths(
            savedFlags if isinstance(savedFlags, (list, tuple, set)) else [])
        self._suppressFileListCenter = False
        self.filesm = self.fileListView.selectionModel()
        self.filesm.currentChanged.connect(self.fileCurrentChanged)


        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)

        self.prevButton = QToolButton()
        self.nextButton = QToolButton()
        self.playButton = QToolButton()
        self.refreshButton = QToolButton()
        self.prevButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.nextButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.playButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.refreshButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.controlButtonsLayout = QHBoxLayout()
        self.controlButtonsLayout.setAlignment(Qt.AlignLeft)
        self.controlButtonsLayout.addWidget(self.prevButton)
        self.controlButtonsLayout.addWidget(self.nextButton)
        self.controlButtonsLayout.addWidget(self.playButton)
        self.controlButtonsLayout.addWidget(self.refreshButton)

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
        self.canvas.imageNavigationRequested.connect(
            self.navigateImageByOffset)

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

        selectClassFile = action(
            u'选择类别文件...', self.openClassFileManager,
            None, 'tags.svg', u'预览、选择或切换 class.txt 类别文件')

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
        createEmptyAnnotation = action(
            u'生成空标签', self.createEmptyAnnotation,
            None, 'tag-black-shape.svg',
            u'按当前 Annotation Format 为当前图片生成空标签',
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

        deleteImage = action(
            u'删除图片及对应标签...',
            self.deleteSelectedImageAndAnnotations,
            None, 'cancel2.svg',
            u'将 File List 中选中的图片及同名 XML/TXT 标签移入回收站',
            enabled=False)

        flagImage = action(
            u'标记该图（待确认）', self.toggleSelectedImageFlag,
            None, 'tags.svg',
            u'将当前图片标为待确认，或取消待确认标记')

        resetAll = action('&ResetAll', self.resetAll, None, 'reset.svg', u'Reset all')

        create = action('Create\nRectBox', self.createShape,
                        None, 'rect.png', u'Draw a new Box', enabled=False)

        createSo = action('Create\nSolidRectBox', self.createSoShape,
                          None, 'rect.png', None, enabled=False)
        createSo.setVisible(False)

        createRo = action('Create\nRotatedRBox', self.createRoShape,
                        None, 'rectRo.png', u'Draw a new RotatedRBox', enabled=False)

        self.boxTypeComboBox = QComboBox(self)
        self.boxTypeComboBox.setObjectName('boxTypeComboBox')
        self.boxTypeComboBox.addItem(u'框型：普通框', 'rect')
        self.boxTypeComboBox.addItem(u'框型：OBB', 'obb')
        self.boxTypeComboBox.setCurrentIndex(1)
        self.boxTypeComboBox.setSizeAdjustPolicy(
            QComboBox.AdjustToContents)
        self.boxTypeComboBox.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.boxTypeComboBox.setToolTip(
            u'选择按 E 绘制的框类型；旁边的画框按钮仍可直接使用。')
        boxTypeControl = QWidgetAction(self)
        boxTypeControl.setObjectName('boxTypeControl')
        boxTypeControl.setDefaultWidget(self.boxTypeComboBox)

        drawSelectedBox = action(
            u'按所选类型画框', self.drawSelectedBox,
            'e', None, u'按 E 绘制工具栏选中的普通框或 OBB；再按 E 退出',
            enabled=False)
        
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
        cutToClipboard = action('Cut Box', self.cutShapeToClipboard,
                                'Ctrl+X', 'copy.svg',
                                u'Cut selected Box', enabled=False)
        pasteFromClipboard = action('Paste Box', self.pasteShapeFromClipboard,
                                    'Ctrl+V', 'copy.svg',
                                    u'Paste copied Box', enabled=False)
        undo = action('Undo Last Operation', self.undoLastOperation,
                      'Ctrl+Z', None,
                      u'Undo the last box operation', enabled=False)

        showInfo = action('&About', self.showInfoDialog, None, 'info.svg', u'About')

        self.autoAnnotationConfidenceSpinBox = QDoubleSpinBox(self)
        self.autoAnnotationConfidenceSpinBox.setObjectName(
            'autoAnnotationConfidenceSpinBox')
        self.autoAnnotationConfidenceSpinBox.setDecimals(2)
        self.autoAnnotationConfidenceSpinBox.setRange(0.01, 1.00)
        self.autoAnnotationConfidenceSpinBox.setSingleStep(0.05)
        self.autoAnnotationConfidenceSpinBox.setValue(
            self.autoAnnotationConfidence)
        self.autoAnnotationConfidenceSpinBox.setPrefix(u'置信度 ')
        self.autoAnnotationConfidenceSpinBox.setMinimumWidth(
            self.autoAnnotationConfidenceSpinBox.sizeHint().width() + 8)
        self.autoAnnotationConfidenceSpinBox.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.autoAnnotationConfidenceSpinBox.setToolTip(
            u'模型置信度阈值（0.01–1.00）；数值越高，保留的预测框通常越少。')
        self.autoAnnotationConfidenceSpinBox.valueChanged.connect(
            self.autoAnnotationConfidenceChanged)
        autoAnnotationConfidenceControl = QWidgetAction(self)
        autoAnnotationConfidenceControl.setObjectName(
            'autoAnnotationConfidenceControl')
        autoAnnotationConfidenceControl.setDefaultWidget(
            self.autoAnnotationConfidenceSpinBox)

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
                             'a', 'previous.svg',
                             u'Open Prev (A / Up Arrow)')

        openNextImg = action('&Next Image', self.openNextImg,
                             'd', 'next.svg',
                             u'Open Next (D / Down Arrow)')
        
        play = action('Play', self.playStart,
                    'Ctrl+Shift+P', 'play.svg', u'auto next',
                    checkable=True, enabled=True)

        refreshProject = action(
            u'刷新图片和标签', self.refreshProjectDirectories,
            'F5', 'reset.svg',
            u'重新扫描当前图片文件夹和标签文件夹（F5）',
            enabled=False)
        
        self.prevButton.setDefaultAction(openPrevImg)
        self.nextButton.setDefaultAction(openNextImg)
        self.playButton.setDefaultAction(play)
        self.refreshButton.setDefaultAction(refreshProject)

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
        self.actions = struct(save=save, saveAs=saveAs, open=open, close=close,
                              deleteImage=deleteImage, flagImage=flagImage,
                              resetAll = resetAll,
                              create=create, createSo=createSo, createRo=createRo,
                              drawSelectedBox=drawSelectedBox,
                              boxTypeControl=boxTypeControl, delete=delete,
                              labelAsBack=labelAsBack, deleteLabel=deleteLabel, edit=edit, copy=copy,
                              copyToClipboard=copyToClipboard,
                              cutToClipboard=cutToClipboard,
                              pasteFromClipboard=pasteFromClipboard,
                              undo=undo,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                               fitWindow=fitWindow, fitWidth=fitWidth, play=play,
                               refreshProject=refreshProject,
                               openPrevImg=openPrevImg, openNextImg=openNextImg,
                               openAnnotationDir=openAnnotationDir,
                               selectClassFile=selectClassFile,
                               selectAutoAnnotationModel=selectAutoAnnotationModel,
                               autoAnnotate=autoAnnotate,
                               singleAutoAnnotate=singleAutoAnnotate,
                               autoAnnotationConfidenceControl=(
                                   autoAnnotationConfidenceControl),
                               createEmptyAnnotation=createEmptyAnnotation,
                               formatXml=formatXml, formatYolo=formatYolo,
                               formatYoloObb=formatYoloObb,
                               zoomActions=zoomActions,
                              fileMenuActions=(
                                  open, opendir, save, saveAs, close, resetAll, quit),
                              beginner=(),
                              editMenu=(undo, None, edit,
                                        cutToClipboard, copyToClipboard,
                                        pasteFromClipboard,
                                        copy, delete,
                                        None),
                              beginnerContext=(undo, None,
                                               cutToClipboard, copyToClipboard,
                                               pasteFromClipboard, None,
                                               create, createSo, createRo, copy,
                                               delete, labelAsBack, deleteLabel),
                              onLoadActive=(
                                  close, create, drawSelectedBox,
                                  singleAutoAnnotate,
                                  createEmptyAnnotation),
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
            annotationFormat=QMenu('Annotation Format'),
            labelList=labelMenu)

        self.fileListContextMenu = QMenu(self.fileListView)
        addActions(self.fileListContextMenu, (flagImage, deleteImage))
        self.fileListView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fileListView.customContextMenuRequested.connect(
            self.showFileListContextMenu)
        self.fileListView.deleteImageRequested.connect(
            self.deleteSelectedImageWithoutConfirmation)

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction("Auto Saving", self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, True))
        
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
                   (open, opendir, openAnnotationDir, selectClassFile,
                     selectAutoAnnotationModel, singleAutoAnnotate,
                    autoAnnotate, None,
                    self.menus.annotationFormat,
                    self.menus.recentFiles,
                    save, saveAs, close, resetAll, quit))

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
        self.editTools = self.toolbar('Drawing')
        self._toolbarLayoutPending = False
        self.actions.beginner = (open, opendir, openAnnotationDir,
            singleAutoAnnotate, autoAnnotate,
            autoAnnotationConfidenceControl, verify, save,
            createEmptyAnnotation)
        self.actions.drawingToolbar = (
            boxTypeControl, create, createSo, createRo, copy, delete, None,
            zoomIn, zoom, zoomOut, zoomOrg, fitWindow, fitWidth)

        self.setLabelShortcutMappings(
            self.labelShortcutMappings, persist=False,
            discardInvalid=True)
        self.updateClassFileButton()

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

        available = available_screen_geometry(self)
        defaultSize = QSize(
            min(1200, max(760, int(available.width() * 0.86))),
            min(820, max(520, int(available.height() * 0.85))))
        size = settings.get(SETTING_WIN_SIZE, defaultSize)
        if not isinstance(size, QSize):
            size = defaultSize
        size = QSize(
            min(available.width(), max(min(760, available.width()),
                                       size.width())),
            min(available.height(), max(min(520, available.height()),
                                        size.height())))
        position = settings.get(SETTING_WIN_POSE)
        if not isinstance(position, QPoint) or not available.contains(
                QRect(position, size)):
            position = available.center() - QPoint(
                size.width() // 2, size.height() // 2)
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

        # If only a saved labels directory is available, inspect its format in
        # the background. When an image directory is restored, its own scan
        # starts shortly and provides counts plus the same format detection.
        if (self.defaultSaveDir and os.path.isdir(self.defaultSaveDir) and
                not (self.lastOpenDir and os.path.isdir(self.lastOpenDir)) and
                not (self.filePath and os.path.isdir(self.filePath))):
            QTimer.singleShot(0, partial(
                self.startAnnotationScan, [], False))

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

    def noShapes(self):
        return not self.ItemShapeDict

    def currentImageFileModelIndex(self):
        """Return the file-list index matching the loaded image."""
        if not self.filePath:
            return QModelIndex()

        target = os.path.normcase(os.path.abspath(self.filePath))
        current = self.filesm.currentIndex()
        if current.isValid():
            currentPath = self.fileModel.data(current, Qt.EditRole)
            if (currentPath and os.path.normcase(os.path.abspath(
                    str(currentPath))) == target):
                return current

        for row in range(self.fileModel.rowCount()):
            index = self.fileModel.index(row)
            path = self.fileModel.data(index, Qt.EditRole)
            if (path and os.path.normcase(os.path.abspath(str(path))) ==
                    target):
                return index
        return QModelIndex()

    def centerFileListIndex(self, index):
        """Keep the active image vertically centered in File List."""
        if index is not None and index.isValid():
            self.fileListView.scrollTo(
                index, QAbstractItemView.PositionAtCenter)

    def updateLabelStatistics(self):
        """Refresh project, current-image and current-session box counts."""
        if not hasattr(self, 'projectLabelCount'):
            return

        currentCount = (len(self.canvas.shapes)
                        if self.filePath and hasattr(self, 'canvas') else 0)
        projectCount = self.fileModel.totalAnnotationCount()
        currentIndex = self.currentImageFileModelIndex()
        if currentIndex.isValid():
            projectCount -= self.fileModel.annotationCount(currentIndex)
            projectCount += currentCount
        elif self.filePath:
            # A directly opened image may not yet be represented by the file
            # list, but its boxes still belong in the visible project total.
            projectCount += currentCount

        self.projectLabelCount.setText(str(max(0, projectCount)))
        self.currentImageLabelCount.setText(str(currentCount))
        self.sessionLabelCountDisplay.setText(
            str(max(0, self.sessionLabelCount)))

    def recordSessionLabels(self, count):
        """Adjust the net number of session-created boxes."""
        count = int(count or 0)
        self.sessionLabelCount = max(0, self.sessionLabelCount + count)
        self.updateLabelStatistics()

    def imageSessionKey(self, imagePath=None):
        imagePath = imagePath or self.filePath
        if not imagePath:
            return None
        return os.path.normcase(os.path.abspath(imagePath))

    def sessionShapeSignature(self, shape):
        """Build a reload-stable signature without saving private metadata."""
        if isinstance(shape, dict):
            label = shape.get('label', '')
            points = shape.get('points', [])
        else:
            label = shape.label
            points = shape.points

        normalizedPoints = []
        for point in points:
            if isinstance(point, QPointF):
                x, y = point.x(), point.y()
            else:
                x, y = point
            normalizedPoints.append((int(round(x)), int(round(y))))
        if not normalizedPoints:
            return str(label), ()
        xs = [point[0] for point in normalizedPoints]
        ys = [point[1] for point in normalizedPoints]
        # The outer bounds survive XML, YOLO and YOLO OBB reloads.  Standard
        # YOLO intentionally drops rotation, so rotation cannot be part of a
        # stable runtime provenance signature.
        return str(label), (min(xs), min(ys), max(xs), max(ys))

    def rememberCurrentSessionShapes(self):
        """Remember runtime provenance before a save, reload or image switch."""
        if not hasattr(self, 'canvas'):
            return
        imageKey = self.imageSessionKey()
        if not imageKey:
            return
        signatures = Counter(
            self.sessionShapeSignature(shape)
            for shape in self.canvas.shapes
            if getattr(shape, 'sessionCreated', False))
        if signatures:
            self._sessionShapeRegistry[imageKey] = signatures
        else:
            self._sessionShapeRegistry.pop(imageKey, None)

    def restoreCurrentSessionShapes(self):
        """Restore runtime provenance after reading annotations from disk."""
        imageKey = self.imageSessionKey()
        if not imageKey:
            return

        remembered = Counter(self._sessionShapeRegistry.get(imageKey, {}))
        rememberedCount = sum(remembered.values())
        matchedCount = 0
        for shape in self.canvas.shapes:
            shape.sessionCreated = False
            signature = self.sessionShapeSignature(shape)
            if remembered[signature] > 0:
                shape.sessionCreated = True
                remembered[signature] -= 1
                matchedCount += 1

        # Batch automatic annotation only writes previously unlabelled
        # images, so every resulting box in that image belongs to this run.
        pendingCount = self._pendingAutoSessionCounts.pop(imageKey, 0)
        if pendingCount > 0:
            for shape in self.canvas.shapes:
                if pendingCount <= 0:
                    break
                if not shape.sessionCreated:
                    shape.sessionCreated = True
                    pendingCount -= 1

        # If session-created boxes disappeared during a reload (for example,
        # model overwrite or discarding unsaved changes), keep the total in
        # sync with what still exists.
        missingCount = ((rememberedCount - matchedCount) + pendingCount)
        if missingCount > 0:
            self.sessionLabelCount = max(
                0, self.sessionLabelCount - missingCount)
        self.rememberCurrentSessionShapes()
        self.updateLabelStatistics()

    def markGeneratedSessionShapes(self, generatedShapes):
        """Mark single-image model results after their file is reloaded."""
        wanted = Counter(
            self.sessionShapeSignature(shape) for shape in generatedShapes)
        # Appended model results are saved after existing boxes, so search
        # backwards to avoid marking an identical older box first.
        markedCount = 0
        for shape in reversed(self.canvas.shapes):
            signature = self.sessionShapeSignature(shape)
            if wanted[signature] > 0:
                if not shape.sessionCreated:
                    markedCount += 1
                shape.sessionCreated = True
                wanted[signature] -= 1
        self.rememberCurrentSessionShapes()
        return markedCount

    def populateModeActions(self):
        tool, menu = self.actions.beginner, self.actions.beginnerContext
        self.tools.clear()
        self.editTools.clear()
        addActions(self.tools, tool)
        addActions(self.editTools, self.actions.drawingToolbar)
        self.scheduleToolbarLayout()
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.drawSelectedBox, self.actions.create,
                   self.actions.createSo, self.actions.createRo)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def scheduleToolbarLayout(self):
        if not self._toolbarLayoutPending:
            self._toolbarLayoutPending = True
            QTimer.singleShot(0, self.updateToolbarLayout)

    def updateToolbarLayout(self):
        self._toolbarLayoutPending = False
        if not self.tools.actions() or not self.editTools.actions():
            return
        required = (self.tools.sizeHint().width() +
                    self.editTools.sizeHint().width() + 16)
        shouldBreak = self.width() < required
        if shouldBreak != self.toolBarBreak(self.editTools):
            if shouldBreak:
                self.insertToolBarBreak(self.editTools)
            else:
                self.removeToolBarBreak(self.editTools)

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
            'session_label_count': self.sessionLabelCount,
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
        self.pushUndoSnapshot(previous)
        self.rememberCurrentSessionShapes()

    def pushUndoSnapshot(self, snapshot):
        self._undoStack.append(snapshot)
        if len(self._undoStack) > self.UNDO_LIMIT:
            del self._undoStack[:-self.UNDO_LIMIT]
        self.updateUndoAction()

    def prepareSingleAutoAnnotationUndo(self):
        """Preserve undo history across the reload performed after inference."""
        self.finishUndoOperation()
        self._singleAutoAnnotationUndoContext = {
            'file_key': self.clipboardImageKey(),
            'history': list(self._undoStack),
            'snapshot': self.captureUndoSnapshot(),
        }
        self.actions.undo.setEnabled(False)

    def restoreSingleAutoAnnotationUndo(self):
        context = self._singleAutoAnnotationUndoContext
        self._singleAutoAnnotationUndoContext = None
        if context is None:
            self.updateUndoAction()
            return False
        if (not self.filePath or
                self.clipboardImageKey() != context['file_key']):
            self.updateUndoAction()
            return False

        self._undoStack = list(context['history'])
        previous = context['snapshot']
        current = self.captureUndoSnapshot()
        changed = (self.undoSnapshotSignature(previous) !=
                   self.undoSnapshotSignature(current))
        if changed:
            self.pushUndoSnapshot(previous)
        else:
            self.updateUndoAction()
        return changed

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
            self.sessionLabelCount = int(snapshot.get(
                'session_label_count', self.sessionLabelCount))

            for actionItem in self.actions.onShapesPresent:
                actionItem.setEnabled(bool(shapes))
            self.dirty = True
            self.actions.save.setEnabled(True)
            self.canvas.update()
            self.rememberCurrentSessionShapes()
            self.updateLabelStatistics()
        finally:
            self._undoRestoring = False
            self._undoPendingSnapshot = None
            self.updateUndoAction()

        self.status(
            u'已撤销上一步操作；请按 Ctrl+S 保存撤销结果。',
            8000)
        return True

    def setDirty(self):
        self.finishUndoOperation()
        self.dirty = True
        self.actions.save.setEnabled(True)
        self.rememberCurrentSessionShapes()
        self.updateLabelStatistics()

    def setCanvasDirty(self):
        """Mark an in-progress canvas gesture dirty; commit on release."""
        self.dirty = True
        self.actions.save.setEnabled(True)
        self.updateLabelStatistics()

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
        self._pendingLabelShortcut = None
        self.rememberCurrentSessionShapes()
        self.resetUndoHistory()
        self.labelModel.clear()
        self.labelModel.setHorizontalHeaderLabels(["Label", "Extra Info"])
        self.ShapeItemDict.clear()
        self.ItemShapeDict.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.loadedAnnotationPath = None
        self.loadedAnnotationFormat = None
        self.canvas.resetState()
        self.actions.pasteFromClipboard.setEnabled(False)
        self.labelCoordinates.clear()
        self.imageDim.clear()
        self.updateLabelStatistics()

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
        self.canvas.update()
        
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
        self.boxTypeComboBox.setCurrentIndex(0)
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
        self.boxTypeComboBox.setCurrentIndex(1)
        # The toolbar button also toggles its own drawing mode.
        if self.canvas.drawing() and self.canvas.canDrawRotatedRect:
            self.cancelBoxDrawing()
            return

        self.canvas.setEditing(0)
        self.canvas.canDrawRotatedRect = True
        self.actions.create.setEnabled(False)
        self.actions.createSo.setEnabled(False)
        # Keep this button enabled so clicking it again can leave drawing mode.
        self.actions.createRo.setEnabled(True)

    def drawSelectedBox(self):
        """Toggle drawing with the box type chosen in the toolbar."""
        if self.canvas.drawing() or self.canvas.continueDrawing():
            self.cancelBoxDrawing()
            return
        if self.boxTypeComboBox.currentData() == 'rect':
            self.createShape()
        else:
            self.createRoShape()
        self.canvas.setFocus(Qt.ShortcutFocusReason)

    def cancelBoxDrawing(self):
        self.canvas.current = None
        self.canvas.line.points = []
        self.canvas.setHiding(False)
        self.canvas.update()
        self.createCancel()
        
    def createCancel(self):
        self._pendingLabelShortcut = None
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

    def showFileListContextMenu(self, position):
        """Open the image menu for the row that was right-clicked."""
        index = self.fileListView.indexAt(position)
        if not index.isValid():
            return
        if index != self.filesm.currentIndex():
            # Selecting a row normally centers it, but doing that here moves
            # the row away from the mouse just before its menu opens.
            self._suppressFileListCenter = True
            try:
                self.filesm.setCurrentIndex(
                    index, QItemSelectionModel.SelectCurrent)
            finally:
                self._suppressFileListCenter = False
        if self.filesm.currentIndex() != index:
            return
        self.actions.flagImage.setText(
            u'取消待确认标记' if self.fileModel.isFlagged(index)
            else u'标记该图（待确认）')
        self.actions.deleteImage.setEnabled(True)
        # The signal position is only for looking up the list row.  On some
        # Windows/Qt display setups, converting it with mapToGlobal places
        # the popup far from the actual right-click.  Use the mouse's global
        # position directly for the popup anchor.
        self.fileListContextMenu.exec_(QCursor.pos())

    def toggleSelectedImageFlag(self, _checked=False):
        index = self.filesm.currentIndex()
        if not index.isValid():
            return False
        flagged = not self.fileModel.isFlagged(index)
        self.fileModel.setFlagged(index, flagged)
        self.settings[SETTING_FLAGGED_IMAGES] = self.fileModel.flaggedPaths()
        self.settings.save()
        self.status(
            u'已标记当前图片，稍后可继续确认标签。' if flagged
            else u'已取消当前图片的待确认标记。', 5000)
        return True

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
        self._labelEditorActive = bool(active)
        # Plain-letter window shortcuts must yield to the class combo box
        # while it is accepting first-letter searches.
        navigation_actions = (self.actions.openPrevImg,
                              self.actions.openNextImg,
                              self.actions.createRo,
                              self.actions.drawSelectedBox)
        if active:
            if self._labelNavigationStates is None:
                self._labelNavigationStates = [
                    item.isEnabled() for item in navigation_actions
                ]
            for item in navigation_actions:
                item.setEnabled(False)
            if self._labelShortcutEditorStates is None:
                self._labelShortcutEditorStates = [
                    item.isEnabled()
                    for item in self.labelShortcutActions]
            for item in self.labelShortcutActions:
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
        if not active and self._labelShortcutEditorStates is not None:
            for item, wasEnabled in zip(
                    self.labelShortcutActions,
                    self._labelShortcutEditorStates):
                item.setEnabled(wasEnabled)
            self._labelShortcutEditorStates = None

    def rememberDefaultLabel(self, label):
        if label not in self.labelHist:
            return
        self.default_label = label
        self.settings[SETTING_DEFAULT_LABEL] = label
        self.settings.save()

    def updateClassFileButton(self):
        path = self.classFilePath or ''
        filename = os.path.basename(path) if path else u'未选择'
        self.classFileButton.setText(
            u'类别文件：%s（%d）' % (filename, len(self.predefinedClasses)))
        self.classFileButton.setToolTip(
            u'当前类别文件：%s\n共 %d 个预设类别。点击可预览或切换。' %
            (path or u'未选择', len(self.predefinedClasses)))

    def applyClassFile(self, path, classNames=None, historyPaths=None,
                       persist=True):
        """Apply a class file without modifying any existing annotations."""
        absolute = os.path.abspath(str(path or ''))
        if classNames is None:
            classNames = read_class_file(absolute)
        classNames = list(classNames)
        if not classNames:
            raise ClassFileError(u'类别文件中没有可用类别。')

        # Existing boxes may contain a class which is not in the newly chosen
        # project preset. Keep those names available for editing/saving, while
        # predefinedClasses remains exactly the selected class.txt content.
        existingLabels = []
        for shape in getattr(self.canvas, 'shapes', ()):
            label = getattr(shape, 'label', None)
            if label and label not in classNames and label not in existingLabels:
                existingLabels.append(label)

        self.classFilePath = absolute
        self.classFileHistory = ClassFileDialog.normalizeHistory(
            [absolute] + list(historyPaths or self.classFileHistory))
        self.predefinedClasses = tuple(classNames)
        self.labelHist = classNames + existingLabels
        for label in self.labelHist:
            self.labelUsage.setdefault(label, {'count': 0, 'last': 0})

        if self.default_label not in self.predefinedClasses:
            self.default_label = classNames[0]
        self.labelDialog.default_label = self.default_label
        self.labelDialog.updateListItems(self.labelHist)
        self.refreshLabelSelectionOrder()

        oldShortcutCount = len(self.labelShortcutMappings)
        self.setLabelShortcutMappings(
            self.labelShortcutMappings, persist=False, discardInvalid=True)
        removedShortcutCount = oldShortcutCount - len(
            self.labelShortcutMappings)
        self.updateClassFileButton()

        if persist:
            self.settings[SETTING_CLASS_FILE] = self.classFilePath
            self.settings[SETTING_CLASS_FILE_HISTORY] = self.classFileHistory
            self.settings[SETTING_DEFAULT_LABEL] = self.default_label
            self.settings[SETTING_LABEL_SHORTCUTS] = self.labelShortcutMappings
            self.settings.save()
        return removedShortcutCount

    def openClassFileManager(self, _checked=False):
        dialog = ClassFileDialog(
            self.classFilePath, self.classFileHistory, self)
        if not dialog.exec_():
            return False
        try:
            removed = self.applyClassFile(
                dialog.selectedPath, dialog.classNames,
                dialog.historyPaths)
        except ClassFileError as error:
            self.errorMessage(u'类别文件无效', str(error))
            return False

        message = u'已切换类别文件：%s，共 %d 个类别。' % (
            os.path.basename(self.classFilePath),
            len(self.predefinedClasses))
        if removed:
            message += u' 已移除 %d 个不再适用的类别快捷键。' % removed
        self.status(message, 10000)
        return True

    def labelShortcutReservedKeys(self):
        """Collect menu, toolbar and direct canvas keyboard bindings."""
        reserved = {}
        customActions = set(self.labelShortcutActions)
        for shortcutAction in self.findChildren(QAction):
            if shortcutAction in customActions:
                continue
            description = shortcutAction.text().replace('&', '').replace(
                '\n', ' ')
            for sequence in shortcutAction.shortcuts():
                shortcut = canonical_shortcut(sequence)
                if shortcut:
                    reserved.setdefault(shortcut, description)

        canvasKeys = (
            (Qt.Key_Escape, u'取消当前画框/选择'),
            (Qt.Key_Return, u'确认或编辑标签'),
            (Qt.Key_Enter, u'确认或编辑标签'),
            (Qt.Key_Up, u'向上移动框'),
            (Qt.Key_Down, u'向下移动框'),
            (Qt.Key_Z, u'旋转框'),
            (Qt.Key_X, u'旋转框'),
            (Qt.Key_C, u'旋转框'),
            (Qt.Key_V, u'旋转框'),
            (Qt.Key_F, u'旋转框 90°'),
            (Qt.Key_R, u'显示/隐藏旋转框'),
            (Qt.Key_N, u'显示/隐藏普通框'),
            (Qt.Key_O, u'切换越界模式'),
            (Qt.Key_B, u'显示/隐藏中心点'),
            (Qt.Key_Tab, u'切换界面焦点'),
            (Qt.Key_Backtab, u'切换界面焦点'),
        )
        for key, description in canvasKeys:
            shortcut = canonical_shortcut(QKeySequence(key))
            if shortcut:
                reserved.setdefault(shortcut, description)
        return reserved

    def setLabelShortcutMappings(self, mappings, persist=True,
                                 discardInvalid=False):
        """Validate, install and optionally persist label shortcuts."""
        if isinstance(mappings, dict):
            candidates = [
                {'shortcut': shortcut, 'label': label}
                for shortcut, label in mappings.items()]
        elif isinstance(mappings, (list, tuple)):
            candidates = [mapping for mapping in mappings
                          if isinstance(mapping, dict)]
        else:
            candidates = []

        reserved = self.labelShortcutReservedKeys()
        if discardInvalid:
            normalized = []
            for mapping in candidates:
                try:
                    normalized = validate_label_shortcuts(
                        normalized + [mapping], self.predefinedClasses,
                        reserved)
                except LabelShortcutValidationError:
                    continue
        else:
            normalized = validate_label_shortcuts(
                candidates, self.predefinedClasses, reserved)

        for shortcutAction in self.labelShortcutActions:
            self.removeAction(shortcutAction)
            shortcutAction.deleteLater()
        self.labelShortcutActions = []
        self.labelShortcutMappings = normalized
        self.labelList.updateShortcutMappings(normalized)

        for mapping in normalized:
            shortcut = mapping['shortcut']
            label = mapping['label']
            shortcutAction = QAction(
                u'标签快捷键：%s → %s' % (shortcut, label), self)
            shortcutAction.setObjectName('labelShortcutAction')
            shortcutAction.setShortcut(QKeySequence(shortcut))
            shortcutAction.setShortcutContext(Qt.WindowShortcut)
            shortcutAction.triggered.connect(partial(
                self.activateLabelShortcut, shortcut, label))
            shortcutAction.setEnabled(not self._labelEditorActive)
            self.addAction(shortcutAction)
            self.labelShortcutActions.append(shortcutAction)

        self.updateLabelShortcutSettingsButton()
        if persist or normalized != candidates:
            self.settings[SETTING_LABEL_SHORTCUTS] = normalized
            self.settings.save()
        return normalized

    def updateLabelShortcutSettingsButton(self):
        count = len(self.labelShortcutMappings)
        self.labelShortcutSettingsButton.setText(
            u'标签快捷键设置...（%d）' % count)
        if count:
            details = '\n'.join(
                u'%s → %s' % (mapping['shortcut'], mapping['label'])
                for mapping in self.labelShortcutMappings)
        else:
            details = u'尚未设置标签快捷键。'
        self.labelShortcutSettingsButton.setToolTip(details)

    def openLabelShortcutSettings(self, _value=False):
        previousStates = [
            shortcutAction.isEnabled()
            for shortcutAction in self.labelShortcutActions]
        for shortcutAction in self.labelShortcutActions:
            shortcutAction.setEnabled(False)
        dialog = LabelShortcutDialog(
            self.labelShortcutMappings,
            self.predefinedClasses,
            self.labelShortcutReservedKeys(),
            self)
        if dialog.exec_():
            self.setLabelShortcutMappings(dialog.validatedMappings)
            self.status(u'标签快捷键设置已保存。', 8000)
            return True
        for shortcutAction, wasEnabled in zip(
                self.labelShortcutActions, previousStates):
            shortcutAction.setEnabled(wasEnabled)
        return False

    def activateLabelShortcut(self, shortcut, label, _checked=False):
        if self._labelEditorActive or label not in self.predefinedClasses:
            return False
        if label not in self.labelHist:
            self.labelHist.append(label)
            self.refreshLabelSelectionOrder()
        self.rememberDefaultLabel(label)
        self._pendingLabelShortcut = label

        if (not self.filePath or self.canvas.pixmap is None or
                self.canvas.pixmap.isNull()):
            self.status(
                u'快捷键 %s 已选择默认类别 %s；打开图片后请再次按快捷键开始画框。' %
                (shortcut, label), 8000)
            return True

        if not self.canvas.drawing():
            self.canvas.setEditing(0)
        self.canvas.canDrawRotatedRect = True
        self.actions.create.setEnabled(False)
        self.actions.createSo.setEnabled(False)
        self.actions.createRo.setEnabled(True)
        self.canvas.setFocus(Qt.ShortcutFocusReason)
        self.status(
            u'快捷键 %s → %s：请绘制一个 OBB 框。' %
            (shortcut, label), 8000)
        return True

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
            pinyin = label_search_keys(label)[1]
            initial = pinyin[:1] if pinyin else label[:1].casefold()
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
                    if not (self._suppressFileListCenter or
                            self.fileListView.rightClickSelectionInProgress):
                        self.centerFileListIndex(previous)
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
        if not (self._suppressFileListCenter or
                self.fileListView.rightClickSelectionInProgress):
            self.centerFileListIndex(current)

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
        self.actions.cutToClipboard.setEnabled(selected)

    def addLabel(self, shape, sessionCreated=False):
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
        if sessionCreated:
            shape.sessionCreated = True
            self.recordSessionLabels(1)
            self.rememberCurrentSessionShapes()
        else:
            self.updateLabelStatistics()

    def remLabel(self, shape):
        if shape is None:
            return

        item0 = self.ShapeItemDict[shape]
        index = self.labelModel.indexFromItem(item0)
        
        self.labelModel.removeRows(index.row(), 1)
        del self.ShapeItemDict[shape]
        del self.ItemShapeDict[item0]
        if getattr(shape, 'sessionCreated', False):
            shape.sessionCreated = False
            self.recordSessionLabels(-1)
        self.rememberCurrentSessionShapes()
        self.updateLabelStatistics()

    def remAllLabels(self):
        removedSessionCount = sum(
            1 for shape in self.canvas.shapes
            if getattr(shape, 'sessionCreated', False))
        self.canvas.deleteAll()
        self.labelModel.clear()
        self.ShapeItemDict.clear()
        self.ItemShapeDict.clear()
        if removedSessionCount:
            self.recordSessionLabels(-removedSessionCount)
        self.rememberCurrentSessionShapes()
        self.updateLabelStatistics()


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
        self.restoreCurrentSessionShapes()
        self.updateLabelStatistics()

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
            self.addLabel(shape, sessionCreated=True)
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
        self._shapeClipboardIsCut = False
        self.actions.pasteFromClipboard.setEnabled(
            self.canvas.pixmap is not None and not self.canvas.pixmap.isNull())
        self.status('Copied %d Box(es)' % len(self._shapeClipboard))

    def cutShapeToClipboard(self):
        shapes = (list(self.canvas.selectedShapes)
                  if self.canvas.selectedShapes
                  else ([self.canvas.selectedShape]
                        if self.canvas.selectedShape else []))
        if not shapes:
            return
        cutCount = len(shapes)
        self.copyShapeToClipboard()
        self._shapeClipboardIsCut = True
        self.deleteSelectedShape()
        self.status('Cut %d Box(es)' % cutCount)

    def pasteShapeFromClipboard(self):
        if (not self._shapeClipboard or self.canvas.pixmap is None or
                self.canvas.pixmap.isNull()):
            return

        sameSourceImage = (
            self.clipboardImageKey() == self._shapeClipboardSourceFile)
        cutPaste = self._shapeClipboardIsCut
        if cutPaste:
            # A cut-paste should restore the original coordinates. If an undo
            # already restored the source boxes, overlap avoidance below will
            # find a nearby free position instead.
            target = None
            offset = QPointF(0, 0)
        elif not sameSourceImage:
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
            self.addLabel(
                shape,
                sessionCreated=(not cutPaste or bool(getattr(
                    shape, 'sessionCreated', False))))
        self.shapeSelectionChanged(True)
        self.setDirty()
        if cutPaste:
            self._shapeClipboardIsCut = False
            self._clipboardPasteCount = 0
        self.status('Pasted %d Box(es)' % len(newShapes))

    def clipboardImageKey(self):
        if not self.filePath:
            return None
        return os.path.normcase(os.path.abspath(self.filePath))

    def copyShapeByDragging(self, shape):
        self.addLabel(shape, sessionCreated=True)
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
        shortcutLabel = self._pendingLabelShortcut
        self._pendingLabelShortcut = None
        extra_text = ""
        if text is not None:
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color, extra_text)
            shape.alwaysShowCorner=self.drawCorner.isChecked()

            self.addLabel(shape, sessionCreated=True)
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
                    if shortcutLabel == text:
                        self.canvas.setFocus(Qt.OtherFocusReason)
                        self.status(u'已创建 %s 标签框。' % text, 5000)
                    else:
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

            annotationCandidates = self.annotationCandidatesForImage(
                self.filePath)

            for annotationPath, annotationKind in annotationCandidates:
                if annotationKind == 'xml':
                    vocReader = self.loadPascalXMLByFilename(annotationPath)
                    loadedReader = vocReader
                    loadedFormat = FORMAT_PASCALVOC
                else:
                    loadedReader = self.loadYOLOByFilename(annotationPath)
                    loadedFormat = (
                        loadedReader.annotation_format
                        if loadedReader is not None and
                        loadedReader.annotation_format is not None
                        else (self.annotationFormat
                              if self.annotationFormat != FORMAT_PASCALVOC
                              else None))
                if loadedReader is None:
                    continue
                self.loadedAnnotationPath = annotationPath
                self.loadedAnnotationFormat = loadedFormat
                break

            if vocReader is not None:
                vocWidth, vocHeight, _ = vocReader.getSize()
                if self.image.width() != vocWidth or self.image.height() != vocHeight:
                    #self.errorMessage("Image info not matched", "The width or height of annotation file is not matched with that of the image")
                    self.saveFile()

            self.updateLabelStatistics()
            self.canvas.setFocus(True)
            return True
        return False

    def resizeEvent(self, event):
        if getattr(self, 'canvas', None) and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)
        if hasattr(self, 'editTools'):
            self.scheduleToolbarLayout()

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

    @staticmethod
    def normalizeAutoAnnotationConfidence(value):
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.25
        if not math.isfinite(confidence):
            confidence = 0.25
        return round(max(0.01, min(1.00, confidence)), 2)

    def autoAnnotationConfidenceChanged(self, value):
        confidence = self.normalizeAutoAnnotationConfidence(value)
        self.autoAnnotationConfidence = confidence
        self.settings[SETTING_AUTO_ANNOTATION_CONFIDENCE] = confidence
        self.settings.save()
        self.status(u'自动标注置信度已设为 %.2f。' % confidence, 5000)

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
                u'请先通过“File > 选择类别文件...”加载项目 class.txt。')
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
        self.prepareSingleAutoAnnotationUndo()
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
                u'请先通过“File > 选择类别文件...”加载项目 class.txt。')
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
        self.autoAnnotationConfidence = self.normalizeAutoAnnotationConfidence(
            self.autoAnnotationConfidenceSpinBox.value())
        self.autoAnnotationProgress.setRange(0, len(jobs))
        self.autoAnnotationProgress.setValue(0)
        if mode == 'single':
            self.autoAnnotationStatus.setText(
                u'加载模型…（当前图片，置信度 %.2f）' %
                self.autoAnnotationConfidence)
        else:
            self.autoAnnotationStatus.setText(
                u'加载模型…（待标注 %d 张，置信度 %.2f）' %
                (len(jobs), self.autoAnnotationConfidence))
        self.autoAnnotationStatus.setToolTip(
            u'%s\n置信度：%.2f' %
            (self.autoAnnotationModelPath, self.autoAnnotationConfidence))
        self.autoAnnotationCancelButton.setEnabled(True)
        self.autoAnnotationCancelButton.setText(u'中止')
        self.setAutoAnnotationWidgetsVisible(True)
        self.actions.autoAnnotate.setEnabled(False)
        self.actions.singleAutoAnnotate.setEnabled(False)
        self.actions.selectAutoAnnotationModel.setEnabled(False)
        self.actions.refreshProject.setEnabled(False)
        self.autoAnnotationConfidenceSpinBox.setEnabled(False)
        self.actions.undo.setEnabled(False)
        self.fileListView.setEnabled(False)
        self.canvas.setEnabled(False)

        thread = AutoAnnotationThread(
            self.autoAnnotationModelPath,
            jobs,
            self.labelHist,
            confidence=self.autoAnnotationConfidence,
            parent=self)
        thread.modelLoaded.connect(self.autoAnnotationModelLoaded)
        thread.progressChanged.connect(self.autoAnnotationProgressChanged)
        thread.completed.connect(self.autoAnnotationCompleted)
        thread.failed.connect(self.autoAnnotationFailed)
        thread.finished.connect(self.autoAnnotationThreadFinished)
        self.autoAnnotationThread = thread
        thread.start()

    def autoAnnotationModelLoaded(self, annotation_format, mapping_details):
        # Model output selects its required save format without converting the
        # user's existing dataset. Dataset conversion is only a manual menu
        # action.
        self.setAnnotationFormat(
            annotation_format, convertExisting=False)
        # Switching format can reload the current image; keep editing disabled
        # until the background batch has finished.
        self.canvas.setEnabled(False)
        mapping_text = '\n'.join(
            '%s -> %s (%.1f%%)' %
            (item['model_name'], item['project_name'], item['score'] * 100.0)
            for item in mapping_details)
        self.autoAnnotationStatus.setText(
            u'模型已加载：%s（置信度 %.2f）' %
            (self.annotationFormatName(annotation_format),
             self.autoAnnotationConfidence))
        self.autoAnnotationStatus.setToolTip(
            u'置信度：%.2f\n%s' %
            (self.autoAnnotationConfidence, mapping_text))

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
        if state == 'saved' and self.autoAnnotationMode == 'batch':
            imageKey = self.imageSessionKey(image_path)
            self._pendingAutoSessionCounts[imageKey] = int(object_count)
        self.autoAnnotationStatus.setText(text)
        self.autoAnnotationStatus.setToolTip(
            u'%s\n置信度：%.2f' %
            (image_path, self.autoAnnotationConfidence))

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
        self.recordSessionLabels(summary.get('objects', 0))
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
            u'置信度：%.2f' % summary.get(
                'confidence', self.autoAnnotationConfidence),
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
        self.status(
            message_lines[2] + u'；' + message_lines[3] +
            u'；' + message_lines[1],
            15000)

    def singleAutoAnnotationCompleted(self, summary):
        results = summary.get('job_results', [])
        result = results[0] if results else None
        errors = summary.get('errors', [])
        if result is not None:
            self.resetBackSample()
        self.finishAutoAnnotationUi()
        self.refreshAnnotationFileList(reloadCurrent=bool(self.filePath))
        if result is not None:
            generatedShapes = result.get('generated_shapes', [])
            markedCount = self.markGeneratedSessionShapes(generatedShapes)
            self.recordSessionLabels(markedCount)
        undo_available = self.restoreSingleAutoAnnotationUndo()
        if summary.get('cancelled'):
            if undo_available:
                message = (u'当前图片已经写入模型标签。\n'
                           u'可按 Ctrl+Z 撤销，再按 Ctrl+S 保存撤销结果。')
            else:
                message = u'当前图片没有写入新的模型标签。'
            QMessageBox.information(
                self,
                u'单张自动标注已中止',
                message)
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
            u'置信度：%.2f' % summary.get(
                'confidence', self.autoAnnotationConfidence),
            u'模型新增：%d 个框' % generated_count,
            u'当前图片最终：%d 个框' % final_count,
            u'保存位置：%s' % result.get('annotation_path', ''),
        ]
        if undo_available:
            message_lines.append(
                u'可按 Ctrl+Z 撤销，再按 Ctrl+S 保存撤销结果。')
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
        if self.autoAnnotationMode == 'single':
            self.restoreSingleAutoAnnotationUndo()
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
        self.actions.refreshProject.setEnabled(
            bool(self.dirname and os.path.isdir(self.dirname)))
        self.autoAnnotationConfidenceSpinBox.setEnabled(True)
        self.fileListView.setEnabled(True)
        self.canvas.setEnabled(bool(self.filePath))
        self.setAutoAnnotationWidgetsVisible(False)
        self.updateUndoAction()

    def autoAnnotationThreadFinished(self):
        thread = self.sender()
        if thread is self.autoAnnotationThread:
            self.autoAnnotationThread = None
            self.autoAnnotationMode = None
        thread.deleteLater()

    def closeEvent(self, event):
        self.annotationScanTimer.stop()
        self.annotationScanIterator = None
        self.annotationScanner = None
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
        settings[SETTING_LABEL_SHORTCUTS] = self.labelShortcutMappings
        settings[SETTING_CLASS_FILE] = self.classFilePath
        settings[SETTING_CLASS_FILE_HISTORY] = self.classFileHistory
        settings[SETTING_AUTO_ANNOTATION_CONFIDENCE] = (
            self.autoAnnotationConfidence)
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
        def sort_key(path):
            relativePath = os.path.relpath(path, folderPath)
            return natural_path_key(relativePath)
        return sorted(images, key=sort_key)

    def annotationCandidatesForImage(self, imagePath):
        """Return existing labels newest-first, regardless of stale format."""
        annotationBasePath = self.annotationBasePathForImage(imagePath)
        candidates = []
        for path, kind, annotationFormat in (
                (annotationBasePath + XML_EXT, 'xml', FORMAT_PASCALVOC),
                (annotationBasePath + YOLO_EXT, 'txt', None)):
            if not os.path.isfile(path):
                continue
            detectedFormat = annotationFormat
            if kind == 'txt':
                try:
                    detectedFormat, _count = inspect_yolo_file(path)
                except (OSError, UnicodeError, YoloError):
                    detectedFormat = None
            candidates.append((path, kind, detectedFormat))

        candidates.sort(
            key=lambda item: (
                os.path.getmtime(item[0]),
                item[2] == self.annotationFormat),
            reverse=True)
        return [(path, kind) for path, kind, _format in candidates]

    def inspectAnnotationDirectory(self, dirpath):
        """Inspect XML/TXT formats without changing any annotation file."""
        result = {
            'counts': Counter(),
            'newest_format': None,
            'newest_mtime': None,
            'empty_txt': 0,
            'errors': [],
        }
        if not dirpath or not os.path.isdir(dirpath):
            return result

        for root, _dirs, files in os.walk(dirpath):
            for filename in files:
                path = os.path.join(root, filename)
                extension = os.path.splitext(filename)[1].lower()
                annotationFormat = None
                if extension == XML_EXT:
                    annotationFormat = FORMAT_PASCALVOC
                elif extension == YOLO_EXT:
                    try:
                        annotationFormat, objectCount = inspect_yolo_file(path)
                        if annotationFormat is None and objectCount == 0:
                            result['empty_txt'] += 1
                    except (OSError, UnicodeError, YoloError) as error:
                        result['errors'].append((path, str(error)))
                        continue
                else:
                    continue

                if annotationFormat is None:
                    continue
                result['counts'][annotationFormat] += 1
                modified = os.path.getmtime(path)
                if (result['newest_mtime'] is None or
                        modified > result['newest_mtime']):
                    result['newest_mtime'] = modified
                    result['newest_format'] = annotationFormat
        return result

    def applyAnnotationFormatWithoutConversion(self, annotationFormat):
        """Select a detected project format without rewriting its labels."""
        if annotationFormat not in SUPPORTED_ANNOTATION_FORMATS:
            return False
        self.annotationFormat = annotationFormat
        if hasattr(self, 'annotationFormatActions'):
            self.annotationFormatActions[annotationFormat].setChecked(True)
        self.settings[SETTING_ANNOTATION_FORMAT] = annotationFormat
        self.settings.save()
        return True

    def applyDetectedAnnotationDirectoryFormat(self, dirpath,
                                               showWarnings=True):
        """Apply a directory's actual format instead of a stale global one."""
        inspection = self.inspectAnnotationDirectory(dirpath)
        self.applyAnnotationInspection(inspection, showWarnings)
        return inspection

    def applyAnnotationInspection(self, inspection, showWarnings=True):
        """Apply results produced by either synchronous or background scan."""
        detectedFormats = list(inspection['counts'])
        if len(detectedFormats) == 1:
            self.applyAnnotationFormatWithoutConversion(detectedFormats[0])
        elif len(detectedFormats) > 1:
            preferredFormat = inspection['newest_format']
            if preferredFormat is not None:
                self.applyAnnotationFormatWithoutConversion(preferredFormat)
            if showWarnings:
                details = ', '.join(
                    '%s：%d' %
                    (self.annotationFormatName(annotationFormat), count)
                    for annotationFormat, count in
                    sorted(inspection['counts'].items()))
                QMessageBox.warning(
                    self,
                    u'检测到混合标签格式',
                    u'该标签目录包含多种格式：%s。\n\n'
                    u'已按最近修改的标签选择 %s。读取同名双文件时也会'
                    u'优先使用较新的版本；下次保存会清理该图片的旧格式'
                    u'副本。\n\n如需立即统一整个目录，请在 Annotation '
                    u'Format 中选择目标格式。' %
                    (details, self.annotationFormatName()))

        if inspection['errors'] and showWarnings:
            QMessageBox.warning(
                self,
                u'部分标签无法识别',
                u'有 %d 个 TXT 文件无法识别格式。它们不会被自动修改，'
                u'请检查文件内容。' % len(inspection['errors']))

    def startAnnotationScan(self, imagePaths=None, showWarnings=False):
        """Read a few labels per event-loop turn to keep the GUI responsive."""
        self.annotationScanTimer.stop()
        paths = list(imagePaths or [])
        self.annotationScanner = AnnotationScanner(
            self.dirname, self.defaultSaveDir, self.annotationFormat)
        if paths:
            self.annotationScanMode = 'images'
            self.annotationScanIterator = iter(enumerate(paths))
            self.annotationScanTotal = len(paths)
        else:
            self.annotationScanMode = 'directory'
            self.annotationScanIterator = iter_annotation_files(
                self.defaultSaveDir)
            self.annotationScanTotal = 0
        self.annotationScanDone = 0
        self.annotationScanShowWarnings = bool(showWarnings)
        self.annotationScanLastStatus.start()
        self.annotationScanTimer.start()
        return self.annotationScanTimer

    def processAnnotationScanBatch(self):
        if self.annotationScanIterator is None or self.annotationScanner is None:
            self.annotationScanTimer.stop()
            return

        budget = QElapsedTimer()
        budget.start()
        processed = 0
        updatedCounts = False
        finished = False
        while processed < 64 and budget.elapsed() < 12:
            try:
                item = next(self.annotationScanIterator)
            except StopIteration:
                finished = True
                break

            if self.annotationScanMode == 'images':
                row, imagePath = item
                count = self.annotationScanner.inspectImage(imagePath)
                self.fileModel.updateAnnotationCount(
                    row, imagePath, count)
                updatedCounts = True
            else:
                self.annotationScanner.inspectStandaloneFile(item)
            processed += 1
            self.annotationScanDone += 1

        if updatedCounts:
            self.updateLabelStatistics()
        if (self.annotationScanLastStatus.elapsed() >= 400 and
                not finished):
            if self.annotationScanTotal:
                self.status(
                    u'正在分批读取标签：%d/%d（界面可继续操作）' %
                    (self.annotationScanDone, self.annotationScanTotal),
                    1500)
            else:
                self.status(
                    u'正在分批识别标签格式：已检查 %d 个文件…' %
                    self.annotationScanDone, 1500)
            self.annotationScanLastStatus.restart()
        if finished:
            self.finishAnnotationScan()

    def finishAnnotationScan(self):
        self.annotationScanTimer.stop()
        scanner = self.annotationScanner
        showWarnings = self.annotationScanShowWarnings
        self.annotationScanIterator = None
        self.annotationScanner = None
        if scanner is None:
            return
        self.applyAnnotationInspection(scanner.inspection, showWarnings)
        self.updateLabelStatistics()
        self.status(
            u'标签目录读取完成：%s；项目共 %s 个标签框。' %
            (self.annotationFormatName(),
             self.projectLabelCount.text()), 10000)

    def annotationFormatName(self, annotationFormat=None):
        annotationFormat = annotationFormat or self.annotationFormat
        return {
            FORMAT_PASCALVOC: 'Pascal VOC XML',
            FORMAT_YOLO: 'YOLO',
            FORMAT_YOLO_OBB: 'YOLO OBB',
        }.get(annotationFormat, annotationFormat)

    def refreshAnnotationFileList(self, reloadCurrent=False,
                                  showWarnings=False):
        if not self.dirname or not os.path.isdir(self.dirname):
            if reloadCurrent and self.filePath:
                currentFile = self.filePath
                self.loadFile(currentFile)
            self.startAnnotationScan([], showWarnings)
            return

        currentFile = self.filePath
        # Changing only the labels directory must not walk the (possibly very
        # large) image tree again. Reuse the current ordered image list.
        imglist = list(self.fileModel.stringList())
        if not imglist:
            imglist = self.scanAllImages(self.dirname)
        self.filesm.blockSignals(True)
        try:
            if imglist == list(self.fileModel.stringList()):
                self.fileModel.resetAnnotationCounts()
            else:
                self.fileModel.setStringList(
                    imglist, self.dirname, self.defaultSaveDir,
                    self.annotationFormat, scanAnnotations=False)
            if currentFile in imglist:
                currentIndex = self.fileModel.index(imglist.index(currentFile))
                self.filesm.setCurrentIndex(
                    currentIndex, QItemSelectionModel.SelectCurrent)
                self.centerFileListIndex(currentIndex)
        finally:
            self.filesm.blockSignals(False)

        self.updateLabelStatistics()

        if reloadCurrent and currentFile and currentFile in imglist:
            self.loadFile(currentFile)
        self.startAnnotationScan(imglist, showWarnings)

    def refreshProjectDirectories(self, _checked=False):
        """Rescan both the image tree and the selected annotation tree."""
        if (self.autoAnnotationThread is not None and
                self.autoAnnotationThread.isRunning()):
            QMessageBox.information(
                self, u'自动标注进行中',
                u'请先中止自动标注，再刷新图片和标签。')
            return False
        if not self.dirname or not os.path.isdir(self.dirname):
            self.actions.refreshProject.setEnabled(False)
            self.status(u'当前没有可刷新的图片文件夹。', 8000)
            return False

        # Preserve unsaved work before reloading the current annotation.
        if self.dirty:
            self.labelList.earlyCommit()
            if self.autoSaving.isChecked() and self.defaultSaveDir:
                if self.canvas.shapes or self.back_sample:
                    if not self.saveFile():
                        self.status(u'当前标签保存失败，已取消刷新。', 10000)
                        return False
                else:
                    self.removeFile()
                    self.setClean()
            elif not self.mayContinue():
                return False

        currentFile = (os.path.abspath(self.filePath)
                       if self.filePath else None)
        currentIndex = self.currentImageFileModelIndex()
        previousRow = currentIndex.row() if currentIndex.isValid() else 0

        self.status(u'正在刷新图片文件夹和标签文件夹…', 3000)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            imagePaths = self.scanAllImages(self.dirname)
        finally:
            QApplication.restoreOverrideCursor()

        self.annotationScanTimer.stop()
        self.filesm.blockSignals(True)
        try:
            self.fileModel.setStringList(
                imagePaths, self.dirname, self.defaultSaveDir,
                self.annotationFormat, scanAnnotations=False)
            targetIndex = QModelIndex()
            if imagePaths:
                if currentFile in imagePaths:
                    targetRow = imagePaths.index(currentFile)
                else:
                    targetRow = min(previousRow, len(imagePaths) - 1)
                targetIndex = self.fileModel.index(targetRow)
                self.filesm.setCurrentIndex(
                    targetIndex, QItemSelectionModel.SelectCurrent)
        finally:
            self.filesm.blockSignals(False)

        if targetIndex.isValid():
            targetPath = self.fileModel.data(targetIndex, Qt.EditRole)
            self.loadFile(targetPath)
            self.centerFileListIndex(targetIndex)
            self.fileListView.setFocus(Qt.OtherFocusReason)
            self.statFile.setText('{0}/{1}'.format(
                targetIndex.row() + 1, self.fileModel.rowCount()))
        else:
            self.filePath = None
            self.resetState()
            self.setClean()
            self.toggleActions(False)
            self.canvas.setEnabled(False)
            self.actions.saveAs.setEnabled(False)
            self.statFile.clear()

        self.updateLabelStatistics()
        self.startAnnotationScan(imagePaths, True)
        self.status(
            u'刷新完成：找到 %d 张图片，正在后台读取标签文件夹。' %
            len(imagePaths), 10000)
        return True

    def annotationImagesForConversion(self):
        if self.dirname and os.path.isdir(self.dirname):
            return self.scanAllImages(self.dirname)
        if self.filePath and os.path.isfile(self.filePath):
            return [self.filePath]
        return []

    def annotationSourcePathForImage(self, imagePath):
        basePath = self.annotationBasePathForImage(imagePath)
        xmlPath = basePath + XML_EXT
        txtPath = basePath + YOLO_EXT
        candidates = [path for path in (xmlPath, txtPath)
                      if os.path.isfile(path)]
        if not candidates:
            return None
        expectedExtension = self.annotationExtension()
        return max(
            candidates,
            key=lambda path: (
                os.path.getmtime(path),
                os.path.splitext(path)[1].lower() == expectedExtension))

    def collectAnnotationConversionJobs(self):
        jobs = []
        seenSources = set()
        for imagePath in self.annotationImagesForConversion():
            sourcePath = self.annotationSourcePathForImage(imagePath)
            if not sourcePath:
                continue
            sourceKey = os.path.normcase(os.path.abspath(sourcePath))
            if sourceKey in seenSources:
                continue
            seenSources.add(sourceKey)
            jobs.append((imagePath, sourcePath))
        return jobs

    def convertExistingAnnotations(self, targetFormat):
        jobs = self.collectAnnotationConversionJobs()
        summary = {
            'total': len(jobs),
            'converted': 0,
            'objects': 0,
            'cancelled': False,
            'errors': [],
        }
        if not jobs:
            return summary

        progress = QProgressDialog(
            u'准备修改标签格式…', u'中止', 0, len(jobs), self)
        progress.setWindowTitle(u'修改 Annotation Format')
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()

        for index, (imagePath, sourcePath) in enumerate(jobs, 1):
            QApplication.processEvents()
            if progress.wasCanceled():
                summary['cancelled'] = True
                break
            progress.setLabelText(
                u'正在修改标签格式（%d/%d）\n%s' %
                (index, len(jobs), os.path.basename(imagePath)))
            progress.setValue(index - 1)
            QApplication.processEvents()
            try:
                _targetPath, objectCount = convert_annotation_file(
                    imagePath, sourcePath, targetFormat, self.labelHist)
                summary['converted'] += 1
                summary['objects'] += objectCount
            except AnnotationConversionError as error:
                summary['errors'].append((sourcePath, str(error)))
            progress.setValue(index)

        progress.close()
        return summary

    def showAnnotationFormatResult(self, targetFormat, summary):
        formatName = self.annotationFormatName(targetFormat)
        if summary['total'] == 0:
            QMessageBox.information(
                self,
                u'修改格式成功',
                u'当前数据集还没有标签。\n后续标签将保存为：%s' %
                formatName)
            return

        message = [
            u'目标格式：%s' % formatName,
            u'成功修改：%d/%d 个标签文件，共 %d 个框' %
            (summary['converted'], summary['total'], summary['objects']),
        ]
        if summary['cancelled']:
            message.append(u'操作已中止；尚未处理的标签保留原格式。')
        if summary['errors']:
            message.append(u'修改失败：%d 个文件（原文件已保留）' %
                           len(summary['errors']))
            for path, error in summary['errors'][:8]:
                message.append(u'%s：%s' % (os.path.basename(path), error))
            if len(summary['errors']) > 8:
                message.append(u'……其余 %d 个失败文件略。' %
                               (len(summary['errors']) - 8))

        if summary['cancelled'] or summary['errors']:
            QMessageBox.warning(
                self, u'标签格式修改未全部完成', u'\n'.join(message))
        else:
            QMessageBox.information(
                self, u'修改格式成功', u'\n'.join(message))

    def setAnnotationFormat(self, annotationFormat, checked=True,
                            convertExisting=True):
        if not checked or annotationFormat not in SUPPORTED_ANNOTATION_FORMATS:
            return False
        changed = annotationFormat != self.annotationFormat
        if not changed:
            self.annotationFormatActions[annotationFormat].setChecked(True)
            return True

        previousFormat = self.annotationFormat
        conversionSummary = None
        if convertExisting:
            # Persist unsaved current boxes in the old format first, so they
            # participate in the same dataset-wide conversion.
            if self.dirty and self.filePath and not self.saveFile():
                self.annotationFormatActions[previousFormat].setChecked(True)
                return False
            conversionSummary = self.convertExistingAnnotations(
                annotationFormat)

        self.applyAnnotationFormatWithoutConversion(annotationFormat)

        self.refreshAnnotationFileList(
            reloadCurrent=bool(self.filePath) and not self.dirty)
        self.status(
            'Annotation format: %s' %
            self.annotationFormatName(annotationFormat),
            8000)
        if conversionSummary is not None:
            self.showAnnotationFormatResult(
                annotationFormat, conversionSummary)
        return True

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

        self.refreshAnnotationFileList(
            reloadCurrent=bool(self.filePath), showWarnings=True)
        self.status(
            u'标签目录已打开，正在后台读取标签数量和格式：%s' %
            self.defaultSaveDir,
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
        self.actions.refreshProject.setEnabled(True)
        self.filePath = None

        # Preserve the last explicitly selected annotation directory.  Only
        # fall back to saving beside the images when no valid saved directory
        # is available (for example on the very first launch).
        if not self.defaultSaveDir or not os.path.isdir(self.defaultSaveDir):
            self.defaultSaveDir = dirpath

        imglist = self.scanAllImages(dirpath)
        self.fileModel.setStringList(
            imglist, self.dirname, self.defaultSaveDir,
            self.annotationFormat, scanAnnotations=False)
        self.updateLabelStatistics()
        self.startAnnotationScan(imglist, False)
        self.setWindowTitle(__appname__ + ' ' + self.dirname)
        resumeFilePath = os.path.abspath(resumeFilePath) if resumeFilePath else None
        if resumeFilePath in imglist:
            resumeIndex = self.fileModel.index(imglist.index(resumeFilePath))
            self.filesm.setCurrentIndex(resumeIndex, QItemSelectionModel.SelectCurrent)
            self.centerFileListIndex(resumeIndex)
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
        changed = self.filesm.currentIndex() == prevIndex
        if changed:
            # loadFile() focuses the canvas. Keyboard image navigation should
            # instead leave File List active so an immediate Del removes the
            # newly opened image without requiring a mouse click first.
            self.fileListView.setFocus(Qt.ShortcutFocusReason)
        return changed

    def navigateImageByOffset(self, offset):
        """Handle Up/Down image navigation requested by the canvas."""
        if offset < 0:
            return self.openPrevImg()
        if offset > 0:
            return self.openNextImg()
        return False

    def openNextImg(self, _value=False):
        currIndex = self.filesm.currentIndex()
        if currIndex.row() + 1 >= self.fileModel.rowCount():
            return False

        nextIndex = self.fileModel.index(currIndex.row() + 1)      
        self.filesm.setCurrentIndex(nextIndex, QItemSelectionModel.SelectCurrent)
        changed = self.filesm.currentIndex() == nextIndex
        if changed:
            self.fileListView.setFocus(Qt.ShortcutFocusReason)
        return changed

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
                self.updateLabelStatistics()

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

    def staleAnnotationSibling(self, annotationFilePath):
        """Return the other-format sibling for a saved XML/TXT label."""
        root, extension = os.path.splitext(annotationFilePath)
        extension = extension.lower()
        if extension == XML_EXT:
            return root + YOLO_EXT
        if extension == YOLO_EXT:
            return root + XML_EXT
        return None

    def saveFile(self, _value=False):
        if not self.filePath:
            return False
        if self.defaultSaveDir is not None and len(self.defaultSaveDir):
            return self._saveFile(
                self.annotationBasePathForImage(self.filePath))
        return self.saveLocal(self.filePath)

    def annotationSidecarPathsForImage(self, imagePath):
        """Return every existing XML/TXT label paired with one image."""
        if not imagePath:
            return []
        annotationBasePath = self.annotationBasePathForImage(imagePath)
        return [path for path in (
            annotationBasePath + XML_EXT,
            annotationBasePath + YOLO_EXT,
        ) if os.path.isfile(path)]

    def deleteSelectedImageWithoutConfirmation(self):
        """Delete the File List selection immediately for the Del key."""
        return self.deleteSelectedImageAndAnnotations(
            requireConfirmation=False)

    def deleteSelectedImageAndAnnotations(
            self, _value=False, requireConfirmation=True):
        """Delete the File List selection and all matching label formats."""
        selectedIndex = self.filesm.currentIndex()
        if not selectedIndex.isValid():
            return False
        selectedPath = self.fileModel.data(selectedIndex, Qt.EditRole)
        if not selectedPath or not os.path.isfile(str(selectedPath)):
            return False
        if (self.autoAnnotationThread is not None and
                self.autoAnnotationThread.isRunning()):
            QMessageBox.information(
                self, u'自动标注进行中',
                u'请先中止自动标注，再删除图片。')
            return False

        imagePath = os.path.abspath(str(selectedPath))
        currentPath = (os.path.abspath(self.filePath)
                       if self.filePath else None)
        deletingCurrent = (
            currentPath is not None and
            os.path.normcase(currentPath) == os.path.normcase(imagePath))

        annotationPaths = self.annotationSidecarPathsForImage(imagePath)
        if requireConfirmation:
            if annotationPaths:
                annotationSummary = u'\n'.join(
                    u'  • %s' % path for path in annotationPaths)
            else:
                annotationSummary = u'  • 未找到对应的 XML/TXT 标签文件'
            message = (
                u'将选中的图片移入回收站：\n%s\n\n'
                u'同时将对应标签移入回收站：\n%s\n\n'
                u'之后可以从系统回收站恢复，是否继续？' %
                (imagePath, annotationSummary))
            answer = QMessageBox.question(
                self, u'移入回收站', message,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return False

        selectedRow = selectedIndex.row()
        imageKey = self.imageSessionKey(imagePath)
        deletedSessionCount = 0
        if deletingCurrent:
            deletedSessionCount = sum(
                1 for shape in self.canvas.shapes
                if getattr(shape, 'sessionCreated', False))

        # Move the image first. If this fails, keep every label untouched.
        try:
            move_to_trash([imagePath])
        except TrashError as error:
            self.errorMessage(
                u'移入回收站失败',
                u'图片未能移入回收站，标签文件未作改动：'
                u'<br>%s<br><br>%s' %
                (imagePath, error))
            return False

        labelTrashErrors = []
        trashedLabelCount = 0
        for annotationPath in annotationPaths:
            try:
                move_to_trash([annotationPath])
                trashedLabelCount += 1
            except TrashError as error:
                labelTrashErrors.append((annotationPath, str(error)))

        self.sessionLabelCount = max(
            0, self.sessionLabelCount - deletedSessionCount)
        self._sessionShapeRegistry.pop(imageKey, None)
        self._pendingAutoSessionCounts.pop(imageKey, None)
        self.recentFiles = [
            path for path in self.recentFiles
            if os.path.normcase(os.path.abspath(str(path))) != imageKey]
        self.fileModel.setFlagged(selectedIndex, False)
        self.settings[SETTING_FLAGGED_IMAGES] = self.fileModel.flaggedPaths()
        self.settings.save()

        scanWasActive = self.annotationScanTimer.isActive()
        self.annotationScanTimer.stop()
        remainingImages = list(self.fileModel.stringList())
        del remainingImages[selectedRow]

        # Rebuild only the in-memory list. Existing counts and green states are
        # preserved below, avoiding a synchronous scan in very large projects.
        remainingDisplay = [
            list(info) for row, info in enumerate(self.fileModel.dispList)
            if row != selectedRow]
        self.filesm.blockSignals(True)
        try:
            self.fileModel.dispList = remainingDisplay
            self.fileModel._totalAnnotationCount = sum(
                info[1] for info in remainingDisplay
                if isinstance(info[1], int) and info[1] > 0)
            QStringListModel.setStringList(
                self.fileModel, remainingImages)
            nextIndex = QModelIndex()
            if remainingImages:
                nextIndex = self.fileModel.index(
                    min(selectedRow, len(remainingImages) - 1))
                self.filesm.setCurrentIndex(
                    nextIndex, QItemSelectionModel.SelectCurrent)
        finally:
            self.filesm.blockSignals(False)

        if deletingCurrent or not self.filePath:
            # Avoid recording deleted current-image shapes during resetState.
            self.filePath = None
            self.resetState()
            if remainingImages:
                nextPath = self.fileModel.data(nextIndex, Qt.EditRole)
                self.loadFile(nextPath)
                self.centerFileListIndex(nextIndex)
            else:
                self.setClean()
                self.toggleActions(False)
                self.canvas.setEnabled(False)
                self.actions.saveAs.setEnabled(False)
        elif self.filePath in remainingImages:
            currentRow = remainingImages.index(self.filePath)
            currentIndex = self.fileModel.index(currentRow)
            self.filesm.blockSignals(True)
            self.filesm.setCurrentIndex(
                currentIndex, QItemSelectionModel.SelectCurrent)
            self.filesm.blockSignals(False)

        if self.fileModel.rowCount():
            current = self.filesm.currentIndex()
            self.statFile.setText('{0}/{1}'.format(
                current.row() + 1, self.fileModel.rowCount()))
        else:
            self.statFile.clear()
        self.actions.deleteImage.setEnabled(
            self.filesm.currentIndex().isValid())
        self.updateLabelStatistics()

        if scanWasActive and remainingImages:
            self.fileModel.resetAnnotationCounts()
            self.startAnnotationScan(remainingImages, False)
        else:
            self.annotationScanIterator = None
            self.annotationScanner = None

        if labelTrashErrors:
            details = u'\n'.join(
                u'%s：%s' % item for item in labelTrashErrors)
            QMessageBox.warning(
                self, u'部分标签未移入回收站',
                u'图片已进入回收站，但以下标签文件未能移动：\n%s' %
                details)
            self.status(
                u'图片已进入回收站；有 %d 个标签文件移动失败。' %
                len(labelTrashErrors), 10000)
        else:
            self.status(
                u'图片及 %d 个对应标签文件已移入回收站。' %
                trashedLabelCount, 10000)
        return True
            
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
            index = self.currentImageFileModelIndex()
            if index.isValid():
                self.fileModel.setData(index, None, Qt.BackgroundRole)
            self.updateLabelStatistics()
            return True
        return False

    def saveFileAndRenderList(self, _value=False):
        if self.saveFile(_value=_value):
            cur = self.filesm.currentIndex()
            self.fileModel.setData(
                cur, len(self.canvas.shapes), Qt.BackgroundRole)

    def createEmptyAnnotation(self, _value=False):
        """Create an empty annotation for the current image and format."""
        if (not self.filePath or self.image.isNull() or
                self.canvas.pixmap is None or self.canvas.pixmap.isNull()):
            self.status(u'请先打开一张图片。', 8000)
            return False

        objectCount = len(self.canvas.shapes)
        formatName = self.annotationFormatName()
        if objectCount:
            answer = QMessageBox.question(
                self,
                u'生成空标签',
                u'当前图片有 %d 个标签框。\n\n'
                u'继续会清空这些框，并按 %s 格式保存为空标签。\n'
                u'是否继续？' % (objectCount, formatName),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)
            if answer != QMessageBox.Yes:
                self.status(u'已取消生成空标签。', 5000)
                return False

        # Reuse the background-sample and normal save paths so XML keeps its
        # image metadata, TXT remains a true zero-byte YOLO/YOLO OBB file, and
        # the operation can still be undone with Ctrl+Z.
        self.labelAsBackground()
        if not self.saveFile():
            restored = self.undoLastOperation()
            if restored:
                self.status(u'空标签保存失败，已恢复原标签。', 10000)
            return False

        annotationBase = self.annotationBasePathForImage(self.filePath)
        annotationPath = self.annotationPathWithExtension(annotationBase)
        self.status(
            u'已生成当前图片的 %s 空标签：%s' %
            (formatName, annotationPath),
            10000)
        return True

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

        # A successful save is also a safe format conversion for this image.
        # Remove only the same-stem alternate extension, after the new file is
        # fully written, so XML and TXT cannot silently diverge again.
        stalePath = self.staleAnnotationSibling(annotationFilePath)
        if stalePath and os.path.isfile(stalePath):
            try:
                os.remove(stalePath)
            except OSError as error:
                self.status(
                    u'标签已保存，但旧格式文件清理失败：%s' % error,
                    10000)
                QMessageBox.warning(
                    self,
                    u'旧格式标签未清理',
                    u'新标签已经安全保存，但无法删除旧格式文件：\n%s\n\n%s' %
                    (stalePath, error))

        self.loadedAnnotationPath = annotationFilePath
        self.loadedAnnotationFormat = self.annotationFormat

        self.setClean()
        index = self.currentImageFileModelIndex()
        if index.isValid():
            self.fileModel.setData(
                index, len(self.canvas.shapes), Qt.BackgroundRole)
        self.updateLabelStatistics()
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
        program = (sys.executable if getattr(sys, 'frozen', False)
                   else os.path.abspath(__file__))
        proc.startDetached(program)

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
        self.addLabel(self.canvas.selectedShape, sessionCreated=True)
        self.setDirty()

    def moveShape(self):
        self.beginUndoOperation()
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        self.labelHist = []
        try:
            self.labelHist.extend(read_class_file(predefClassesFile))
        except ClassFileError:
            return False
        return True

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
        self.canvas.update()


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
    if QApplication.instance() is None:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("tag-black-shape.svg"))
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(
                         app_dir, 'data', 'predefined_classes.txt'),
                     argv[3] if len(argv) >= 4 else None)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())

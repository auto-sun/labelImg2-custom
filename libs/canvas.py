# -*- coding: utf-8 -*-
from __future__ import absolute_import

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from .shape import Shape
from .lib import distance
from libs.labelFile import LabelFile
from .shortcut_input import disable_ime_for_shortcuts
import math

CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    panRequest = pyqtSignal(int, int)
    newShape = pyqtSignal(bool)
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    shapeCopied = pyqtSignal(object)
    shapeChangeStarted = pyqtSignal()
    shapeChangeFinished = pyqtSignal()
    shapeVisibilityChanged = pyqtSignal(object, bool)
    drawingPolygon = pyqtSignal(bool)
    imageNavigationRequested = pyqtSignal(int)

    hideRRect = pyqtSignal(bool)
    hideNRect = pyqtSignal(bool)
    status = pyqtSignal(str)

    cancelDraw = pyqtSignal()

    toggleEdit = pyqtSignal(bool)

    #CREATE, EDIT = list(range(2))
    CREATE = 0
    EDIT = 1
    CONTINUECREATE = 2

    epsilon = 7.0
    VERTEX_HIT_RADIUS = 12.0
    WHEEL_SHAPE_SCALE_STEP = 1.02
    MIN_SHAPE_EDGE = 2.0
    NUDGE_STEP = 5.0

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selectedShape = None  # save the selected shape here
        self.selectedShapes = []    # multi-selection list
        self.selectedShapeCopy = None
        self.drawingLineColor = QColor(0, 0, 255)
        self.drawingRectColor = QColor(0, 0, 255) 
        self.line = Shape(line_color=self.drawingLineColor)
        self.prevPoint = QPointF()
        self.offsets = QPointF(), QPointF()
        self._altPressed = False
        self._panning = False
        # Keep the drag anchor in screen coordinates. Scrolling the canvas
        # changes its local coordinate system under the pointer.
        self._panLastGlobalPos = QPoint()
        self.panViewportHeight = 0
        self.panViewportWidth = 0
        self.panMargin = 0
        self.panHorizontalMargin = 0
        self.resetPanView = True
        self._marqueeStart = None
        self._marqueeEnd = None
        self._marqueeStartWidget = QPoint()
        self._marqueeDragging = False
        self._marqueeAdditive = False
        self._marqueeBaseSelection = []
        self._ctrlCopySource = None
        self._ctrlCopyShape = None
        self._ctrlCopyStart = QPointF()
        self._ctrlCopyStartWidget = QPoint()
        self.contextMenuPos = None
        self.contextMenuActive = False
        self.scale = 1.0
        self.pixmap = QPixmap()
        
        #self.localScalePixmap = QPixmap()

        self.visible = {}
        self._hideBackround = False
        self.hideBackround = False
        self.hShape = None
        self.hVertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        disable_ime_for_shortcuts(self)
        self.verified = False

        self.canDrawRotatedRect = True
        self.hideRotated = False
        self.hideNormal = False
        # Geometry editing must never place an annotation outside the image.
        # Retain the attribute for compatibility with older call sites, but
        # do not allow the old O-key escape hatch to weaken this invariant.
        self.canOutOfBounding = False
        self.showCenter = False
        
        #self.setAttribute(Qt.WA_PaintOnScreen)


        

    def setDrawingColor(self, qColor):
        self.drawingLineColor = qColor
        self.drawingRectColor = qColor

    def enterEvent(self, ev):
        self.overrideCursor(self._cursor)

    def leaveEvent(self, ev):
        self.restoreCursor()

    def focusOutEvent(self, ev):
        self.shapeChangeFinished.emit()
        self._altPressed = False
        self._panning = False
        self._clearMarqueeSelection()
        self._clearCtrlCopyDrag()
        self.restoreCursor()

    def focusInEvent(self, ev):
        super(Canvas, self).focusInEvent(ev)
        disable_ime_for_shortcuts(self)

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def continueDrawing(self):
        return self.mode == self.CONTINUECREATE

    def editing(self):
        return self.mode == self.EDIT

    def setDrawCornerState(self, enabled):
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            shape.alwaysShowCorner=enabled
        self.repaint()
        self.update()

    def setEditing(self, value=1):
        self._clearMarqueeSelection()
        self.mode = value
        if value == self.CREATE or value == self.CONTINUECREATE:  # Create
            self.unHighlight()
            self.deSelectShape()
        self.prevPoint = QPointF()
        self.repaint()

    def unHighlight(self):
        if self.hShape:
            self.hShape.highlightClear()
        self.hVertex = self.hShape = None

    def updateVertexHit(self, pos):
        """Refresh corner hit state from the actual mouse-press position.

        Qt may not deliver a hover/move event after an image is switched while
        the pointer stays still.  Recomputing here prevents a stale handle
        from the previous image from swallowing the first corner drag.
        """
        previous_shape = self.hShape
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            index = shape.nearestVertex(pos, self.vertexHitRadius())
            if index is None:
                continue
            if previous_shape is not None and previous_shape is not shape:
                previous_shape.highlightClear()
            self.hVertex, self.hShape = index, shape
            shape.highlightCorner = True
            shape.highlightVertex(index, shape.MOVE_VERTEX)
            return True

        if previous_shape is not None:
            previous_shape.highlightClear()
        self.hVertex = self.hShape = None
        return False

    def selectedVertex(self):
        return self.hVertex is not None

    # reserve function
    def updateLocalScaleMap(self, x, y):
        pass
        #if self.pixmap is None:
        #    return

        #rz = 15
        #x0 = int(x) - rz
        #x1 = int(x) + rz
        #y0 = int(y) - rz
        #y1 = int(y) + rz

        #self.localScalePixmap = self.pixmap.copy(x0, y0, x1 - x0 + 1, y1 - y0 + 1) #self.grab(QRect(x0, y0, x1 - x0 + 1, y1 - y0 + 1))
        ##self.localScalePixmap.grabWidget(self, pos.x(), pos.y(), 30, 30) # TODO: pyQt4
        #w = self.localScalePixmap.width()
        #h = self.localScalePixmap.height()
        #self.localScalePixmap = self.localScalePixmap.scaled(w * 5, h * 5, Qt.KeepAspectRatio)

    def _panToGlobal(self, global_pos):
        delta = self._panLastGlobalPos - global_pos
        self._panLastGlobalPos = QPoint(global_pos)
        if not delta.isNull():
            self.panRequest.emit(delta.x(), delta.y())

    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates."""
        if self._panning and Qt.LeftButton & ev.buttons():
            self._panToGlobal(ev.globalPos())
            self.overrideCursor(CURSOR_MOVE)
            ev.accept()
            return

        if self._altPressed or bool(ev.modifiers() & Qt.AltModifier):
            self.overrideCursor(CURSOR_GRAB)
            ev.accept()
            return

        pos = self.transformPos(ev.pos())

        if self._ctrlCopySource is not None and Qt.LeftButton & ev.buttons():
            if self._ctrlCopyShape is None:
                drag_distance = (ev.pos() - self._ctrlCopyStartWidget).manhattanLength()
                if drag_distance < QApplication.startDragDistance():
                    self.overrideCursor(CURSOR_GRAB)
                    ev.accept()
                    return

                copies = [shape.copy() for shape in self._ctrlCopySource]
                self.shapes.extend(copies)
                self.unHighlight()
                self._setSelectedShapes(copies)
                self._ctrlCopyShape = copies
                self.prevPoint = QPointF(self._ctrlCopyStart)
                self.shapeCopied.emit(copies)

            self.overrideCursor(CURSOR_MOVE)
            delta = self._boundedTranslation(
                self._ctrlCopyShape, pos - self.prevPoint)
            self.prevPoint = QPointF(pos)
            if not delta.isNull():
                for shape in self._ctrlCopyShape:
                    shape.moveBy(delta)
                    shape.close()
                self.shapeMoved.emit()
            self.updateLocalScaleMap(pos.x(), pos.y())
            self.repaint()
            ev.accept()
            return

        if self._marqueeStart is not None and Qt.LeftButton & ev.buttons():
            if ((ev.pos() - self._marqueeStartWidget).manhattanLength() >=
                    QApplication.startDragDistance()):
                self._marqueeDragging = True
            pos = self.transformPos(ev.pos())
            # Marquee selection is a canvas operation, not an image edit:
            # keep the pointer in canvas coordinates so a drag may cross the
            # image from one outside margin to another without snapping.
            self._marqueeEnd = pos
            self.overrideCursor(CURSOR_DRAW)
            self.repaint()
            ev.accept()
            return

        # Update coordinates in status bar if image is opened
        window = self.parent().window()
        if window.filePath is not None:
            self.parent().window().labelCoordinates.setText(
                'X: %d; Y: %d' % (pos.x(), pos.y()))

        # Polygon drawing.
        if self.drawing():
            self.overrideCursor(CURSOR_DRAW)
            if self.current:
                color = self.drawingLineColor
                if len(self.current) > 1 and self.outOfPixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Project the point to the pixmap's edges.
                    pos = self.intersectionPoint(self.current[-1], pos)
                elif len(self.current) > 1 and self.closeEnough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:
                    pos = self.current[0]
                    color = self.current.line_color
                    self.overrideCursor(CURSOR_POINT)
                    self.current.highlightVertex(0, Shape.NEAR_VERTEX)
                self.line[1] = pos
                self.line.line_color = color
                self.prevPoint = QPointF()
                self.current.highlightClear()
            else:
                self.prevPoint = pos
            
            self.updateLocalScaleMap(pos.x(), pos.y())
            
            self.repaint()
            return

        if self.continueDrawing():
            self.prevPoint = pos
            self.repaint()
            return

        # Polygon copy moving.
        if Qt.RightButton & ev.buttons():
            #if self.selectedShapeCopy and self.prevPoint:
            #    self.overrideCursor(CURSOR_MOVE)
            #    self.boundedMoveShape(self.selectedShapeCopy, pos)
            #    self.repaint()
            #elif self.selectedShape:
            #    self.selectedShapeCopy = self.selectedShape.copy()
            #    self.repaint()
            if self.selectedVertex() and self.selectedShape.isRotated:
                self.boundedRotateShape(pos)
                self.shapeMoved.emit()
                self.selectedShape.highlightCorner = True
                self.repaint()

            self.status.emit("(%d,%d)." % (pos.x(), pos.y()))
            return

        # Polygon/Vertex moving.
        if Qt.LeftButton & ev.buttons():
            if self.selectedVertex():
                self.boundedMoveVertex(pos)
                self.shapeMoved.emit()
                if self.selectedShape:
                    self.selectedShape.highlightCorner = True
            elif self.selectedShape and self.prevPoint:
                self.overrideCursor(CURSOR_MOVE)
                # Move all selected shapes together
                if len(self.selectedShapes) > 1:
                    dp = pos - self.prevPoint
                    if dp:
                        dp = self._boundedTranslation(
                            self.selectedShapes, dp)
                        for sh in self.selectedShapes:
                            sh.moveBy(dp)
                            sh.close()
                        self.prevPoint = pos
                else:
                    self.boundedMoveShape(self.selectedShape, pos)
                self.shapeMoved.emit()
            self.updateLocalScaleMap(pos.x(), pos.y())
            self.repaint()
            return

        # Just hovering over the canvas, 2 posibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearestVertex(pos, self.vertexHitRadius())
            if index is not None:
                if self.hShape is not None and self.hShape is not shape:
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = index, shape
                shape.highlightCorner = True
                shape.highlightVertex(index, shape.MOVE_VERTEX)
                self.overrideCursor(CURSOR_POINT)
                
                
                self.setToolTip("Click & drag to move point")
                #self.setStatusTip(self.toolTip())
                self.updateLocalScaleMap(pos.x(), pos.y())

                self.update()
                break
            elif shape.containsPoint(pos):
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = None, shape
                shape.highlightCorner = True
                # TODO: optimize here
                if shape.isRotated:
                    # rotbox = LabelFile.convertPoints2RotatedBndBox(shape)
                    # print(rotbox)
                    w = math.sqrt((shape.points[0].x()-shape.points[1].x()) ** 2 +
                        (shape.points[0].y()-shape.points[1].y()) ** 2)

                    h = math.sqrt((shape.points[2].x()-shape.points[1].x()) ** 2 +
                        (shape.points[2].y()-shape.points[1].y()) ** 2)
                    tooltip_str = "%s\n xywhr: (%f, %f, %f, %f, %f)" % (shape.label, shape.center.x(), shape.center.y(), w, h, 
                                                                        (shape.direction * 180 / math.pi) % 360)
                    # print(shape.direction  * 180 / math.pi)
                else:
                    tooltip_str = "%s\n X: (%f, %f)\nY: (%f, %f)" % (shape.label, shape.points[0].x(), shape.points[2].x(), shape.points[0].y(), shape.points[2].y())

                self.setToolTip(tooltip_str)
                #self.setStatusTip(self.toolTip())
                self.overrideCursor(CURSOR_GRAB)
                
                self.updateLocalScaleMap(pos.x(), pos.y())

                self.update()
                break
        else:  # Nothing found, clear highlights, reset state.
            self.setToolTip("Background")
            if self.hShape:
                self.hShape.highlightClear()
                #self.hShape.highlightCorner=False

                self.updateLocalScaleMap(pos.x(), pos.y())
                self.update()
            else:
                self.updateLocalScaleMap(pos.x(), pos.y())
                self.repaint()
            self.hVertex, self.hShape = None, None
            self.overrideCursor(CURSOR_DEFAULT)


    def mousePressEvent(self, ev):
        alt_pressed = self._altPressed or bool(ev.modifiers() & Qt.AltModifier)
        if ev.button() == Qt.LeftButton and alt_pressed:
            self._panning = True
            self._panLastGlobalPos = ev.globalPos()
            self.overrideCursor(CURSOR_MOVE)
            ev.accept()
            return

        pos = self.transformPos(ev.pos())

        if (self.editing() and ev.button() in
                (Qt.LeftButton, Qt.RightButton)):
            self.updateVertexHit(pos)

        if (ev.button() == Qt.LeftButton and self.editing() and
                bool(ev.modifiers() & Qt.ControlModifier)):
            shape = self._shapeAt(pos)
            if shape is not None:
                self.shapeChangeStarted.emit()
                self._ctrlCopySource = (
                    list(self.selectedShapes)
                    if shape in self.selectedShapes else [shape])
                self._ctrlCopyShape = None
                self._ctrlCopyStart = QPointF(pos)
                self._ctrlCopyStartWidget = QPoint(ev.pos())
                self.prevPoint = QPointF(pos)
                self.calculateOffsets(shape, pos)
                self.overrideCursor(CURSOR_GRAB)
                ev.accept()
                return

        if (ev.button() == Qt.LeftButton and self.editing() and
                self._shapeAt(pos) is None and
                not self.selectedVertex()):
            additive = bool(
                ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
            )
            self._startMarqueeSelection(pos, ev.pos(), additive)
            ev.accept()
            return

        if ev.button() == Qt.LeftButton:
            if self.drawing():
                self.handleDrawing(pos)
            if self.continueDrawing():
                pass
            else:
                self.selectShapePoint(pos, ev.modifiers())
                self.prevPoint = pos
                if self.editing() and self.selectedShape is not None:
                    self.shapeChangeStarted.emit()
                self.repaint()
        elif ev.button() == Qt.RightButton and self.editing():
            self.selectShapePoint(pos, ev.modifiers())
            self.prevPoint = pos
            if self.selectedVertex() and self.selectedShape.isRotated:
                self.shapeChangeStarted.emit()
            self.repaint()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._panning:
            self._panToGlobal(ev.globalPos())
            self._panning = False
            alt_pressed = self._altPressed or bool(
                QApplication.keyboardModifiers() & Qt.AltModifier
            )
            self.overrideCursor(CURSOR_GRAB if alt_pressed else CURSOR_DEFAULT)
            ev.accept()
            return

        if ev.button() == Qt.LeftButton and self._ctrlCopySource is not None:
            copied = self._ctrlCopyShape is not None
            pos = self.transformPos(ev.pos())
            self._clearCtrlCopyDrag()
            if not copied:
                # Preserve the existing Ctrl-click multi-selection behaviour.
                self.selectShapePoint(pos, Qt.ControlModifier)
                self.prevPoint = pos
            self.overrideCursor(CURSOR_GRAB if self.selectedShape else CURSOR_DEFAULT)
            self.repaint()
            self.shapeChangeFinished.emit()
            ev.accept()
            return

        if ev.button() == Qt.LeftButton and self._marqueeStart is not None:
            if self._marqueeDragging:
                self._marqueeEnd = self.transformPos(ev.pos())
                self._finishMarqueeSelection()
            self._clearMarqueeSelection()
            self.overrideCursor(CURSOR_GRAB if self.selectedShape else CURSOR_DEFAULT)
            self.repaint()
            ev.accept()
            return

        if ev.button() == Qt.RightButton:
            if self.selectedVertex() and self.selectedShape.isRotated:
                self.shapeChangeFinished.emit()
                return
            menu = self.menus[bool(self.selectedShapeCopy)]
            self.restoreCursor()
            self.contextMenuPos = self.transformPos(ev.pos())
            self.contextMenuActive = True
            try:
                menu.exec_(self.mapToGlobal(ev.pos()))
            finally:
                self.contextMenuActive = False
            #if not menu.exec_(self.mapToGlobal(ev.pos())) and self.selectedShapeCopy:
            #    # Cancel the move by deleting the shadow copy.
            #    self.selectedShapeCopy = None
            #    self.repaint()
        elif ev.button() == Qt.LeftButton and self.selectedShape and self.editing():
            if self.selectedVertex():
                self.overrideCursor(CURSOR_POINT)
            else:
                self.overrideCursor(CURSOR_GRAB)
        elif ev.button() == Qt.LeftButton:
            pos = self.transformPos(ev.pos())
            if self.drawing():
                self.handleDrawing(pos)

            if self.continueDrawing():
                self.handleClickDrawing(pos)

        self.shapeChangeFinished.emit()

    def _shapeAt(self, point):
        for shape in reversed(self.shapes):
            if self.isVisible(shape) and shape.containsPoint(point):
                return shape
        return None

    def _boundedPixmapPoint(self, point):
        if self.pixmap is None or self.pixmap.isNull():
            return QPointF(point)
        return QPointF(
            min(max(0.0, point.x()), float(self.pixmap.width())),
            min(max(0.0, point.y()), float(self.pixmap.height()))
        )

    def _startMarqueeSelection(self, pos, widget_pos, additive=False):
        self._marqueeStart = QPointF(pos)
        self._marqueeEnd = QPointF(pos)
        self._marqueeStartWidget = QPoint(widget_pos)
        self._marqueeDragging = False
        self._marqueeAdditive = bool(additive)
        self._marqueeBaseSelection = (
            list(self.selectedShapes) if additive else []
        )
        self.unHighlight()
        if not additive:
            self.deSelectShape()
        self.overrideCursor(CURSOR_DRAW)
        self.update()

    def _marqueeRect(self):
        if self._marqueeStart is None or self._marqueeEnd is None:
            return QRectF()
        return QRectF(self._marqueeStart, self._marqueeEnd).normalized()

    def _setSelectedShapes(self, shapes):
        selected = []
        for shape in shapes:
            if (shape in self.shapes and self.isVisible(shape) and
                    shape not in selected):
                selected.append(shape)

        selected_set = set(selected)
        for shape in self.shapes:
            shape.selected = shape in selected_set
        self.selectedShapes = selected
        self.selectedShape = selected[-1] if selected else None
        self.setHiding(bool(selected))
        self.selectionChanged.emit(bool(selected))
        self.update()

    def _finishMarqueeSelection(self):
        rect = self._marqueeRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        selection_path = QPainterPath()
        selection_path.addRect(rect)
        matched = []
        for shape in self.shapes:
            if not self.isVisible(shape) or not shape.points:
                continue
            shape_path = shape.makePath()
            shape_path.closeSubpath()
            center = (shape.center if shape.center is not None else
                      shape.boundingRect().center())
            if (selection_path.contains(center) or
                    selection_path.intersects(shape_path)):
                matched.append(shape)

        selected = (self._marqueeBaseSelection + matched
                    if self._marqueeAdditive else matched)
        self._setSelectedShapes(selected)
        self.status.emit("Selected %d Box(es)" % len(self.selectedShapes))

    def _clearMarqueeSelection(self):
        self._marqueeStart = None
        self._marqueeEnd = None
        self._marqueeStartWidget = QPoint()
        self._marqueeDragging = False
        self._marqueeAdditive = False
        self._marqueeBaseSelection = []

    def _clearCtrlCopyDrag(self):
        self._ctrlCopySource = None
        self._ctrlCopyShape = None
        self._ctrlCopyStart = QPointF()
        self._ctrlCopyStartWidget = QPoint()

    def endMove(self, copy=False):
        assert self.selectedShape and self.selectedShapeCopy
        shape = self.selectedShapeCopy
        #del shape.fill_color
        #del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selectedShape.selected = False
            self.selectedShape = shape
            self.repaint()
        else:
            self.selectedShape.points = [p for p in shape.points]
        self.selectedShapeCopy = None

    def hideBackroundShapes(self, value):
        self.hideBackround = value
        if self.selectedShape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.setHiding(True)
            self.repaint()

    def handleDrawing(self, pos):
        if self.current and self.current.reachMaxPoints() is False:
            self.current.highlightCorner=True
            initPos = self.current[0]
            minX = initPos.x()
            minY = initPos.y()
            targetPos = self.line[1]
            maxX = targetPos.x()
            maxY = targetPos.y()
            self.current.addPoint(QPointF(maxX, minY))
            self.current.addPoint(targetPos)
            self.current.addPoint(QPointF(minX, maxY))
            pos_diff = self.current.points[2] - self.current.points[0]
            if pos_diff.y() < 0:
                self.current.direction = math.pi
            self.finalise()
        else:
            self.current = Shape()
            self.current.highlightCorner=True
            self.current.addPoint(pos)
            self.line.points = [pos, pos]
            self.setHiding()
            self.drawingPolygon.emit(True)
            self.update()

    def handleClickDrawing(self, pos):
        if not self.outOfPixmap(pos):
            self.current = Shape()
            self.current.highlightCorner=True
            minX = pos.x() - 30
            maxX = pos.x() + 30
            minY = pos.y() - 38
            maxY = pos.y() + 38
            self.current.addPoint(QPointF(minX, minY))
            self.current.addPoint(QPointF(maxX, minY))
            self.current.addPoint(QPointF(maxX, maxY))
            self.current.addPoint(QPointF(minX, maxY))
            self.finalise(continous=True)

    def setHiding(self, enable=True):
        self._hideBackround = self.hideBackround if enable else False

    def canCloseShape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.canCloseShape() and len(self.current) > 3:
            self.current.popPoint()
            self.finalise()

    def selectShape(self, shape):
        self.deSelectShape()
        shape.selected = True
        self.selectedShape = shape
        if shape not in self.selectedShapes:
            self.selectedShapes.append(shape)
        self.setHiding()
        self.selectionChanged.emit(True)
        self.update()

    def selectShapePoint(self, point, modifiers=None):
        """Select the first shape created which contains this point."""
        if modifiers is not None:
            multiSelectPressed = modifiers & (
                Qt.ControlModifier | Qt.ShiftModifier
            )
        else:
            multiSelectPressed = QApplication.keyboardModifiers() & (
                Qt.ControlModifier | Qt.ShiftModifier
            )

        if self.selectedVertex():  # A vertex is marked for selection.
            if not multiSelectPressed:
                self.deSelectShape()
            index, shape = self.hVertex, self.hShape
            shape.highlightVertex(index, shape.MOVE_VERTEX)
            if multiSelectPressed:
                self._addToSelection(shape)
            else:
                self.selectShape(shape)
            return

        for shape in reversed(self.shapes):
            if self.isVisible(shape) and shape.containsPoint(point):
                if multiSelectPressed:
                    # Toggle shape in/out of multi-selection
                    if shape in self.selectedShapes:
                        self._removeFromSelection(shape)
                    else:
                        self._addToSelection(shape)
                else:
                    # If this shape is already in a multi-selection, keep the group selected
                    if shape in self.selectedShapes and len(self.selectedShapes) > 1:
                        self.selectedShape = shape
                    else:
                        self.deSelectShape()
                        self.selectShape(shape)
                self.calculateOffsets(shape, point)
                return

        # Clicked on empty area
        if not multiSelectPressed:
            self.deSelectShape()

    def _addToSelection(self, shape):
        """Add a shape to the multi-selection list."""
        shape.selected = True
        if shape not in self.selectedShapes:
            self.selectedShapes.append(shape)
        self.selectedShape = shape
        self.setHiding()
        self.selectionChanged.emit(True)
        self.update()

    def _removeFromSelection(self, shape):
        """Remove a shape from the multi-selection list."""
        shape.selected = False
        if shape in self.selectedShapes:
            self.selectedShapes.remove(shape)
        # Update selectedShape to the last remaining selection, or None
        if self.selectedShapes:
            self.selectedShape = self.selectedShapes[-1]
        else:
            self.selectedShape = None
        self.selectionChanged.emit(bool(self.selectedShapes))
        self.update()

    def calculateOffsets(self, shape, point):
        rect = shape.boundingRect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def boundedMoveVertex(self, pos):
        index, shape = self.hVertex, self.hShape
        if self.pixmap is None or self.pixmap.isNull():
            return
        # A corner that lies on an image edge is still draggable. Clamp the
        # pointer to the image instead of rejecting the whole drag when the
        # pointer moves a little outside the canvas image area.
        if not self.canOutOfBounding:
            pos = self._boundedPixmapPoint(pos)

        # Legacy XML rounded angles to six decimals. Recover exact cardinal
        # directions within that quantization interval before resizing.
        direction = shape.direction
        cardinal = round(direction / (math.pi / 2)) * (math.pi / 2)
        if abs(direction - cardinal) <= 5e-7:
            direction = cardinal % (2 * math.pi)
        point = QPointF(shape[index])
        opposite = QPointF(shape[(index + 2) % 4])

        if self.canOutOfBounding and self.outOfPixmap((pos + opposite) / 2):
            return

        def resized_points(corner, anchor):
            p2, p3, p4 = self.getAdjointPoints(
                direction, anchor, corner, index)
            if not self.canOutOfBounding:
                p2, p3, p4 = [
                    self._snapPixmapBoundaryRoundoff(point)
                    for point in (p2, p3, p4)]
            points = list(shape.points)
            points[index] = QPointF(corner)
            points[(index + 1) % 4] = p2
            points[(index + 2) % 4] = p3
            points[(index + 3) % 4] = p4
            return points

        # A saved box may already be outside the image: the old fallback
        # rejected an invalid baseline, so only moving the whole box unlocked
        # its corners. Fit the rectangle as one unit on this edit, preserving
        # its angle. Merely loading annotations does not change their geometry.
        original_points = resized_points(point, opposite)
        if not self.canOutOfBounding:
            original_points = self._fitResizeBaseline(original_points)
        point = original_points[index]
        opposite = original_points[(index + 2) % 4]

        new_points = resized_points(pos, opposite)
        if not self.canOutOfBounding and any(
                self.outOfPixmap(candidate) for candidate in new_points):
            # For a rotated box, clamping the dragged corner alone can still
            # push an adjacent corner outside the image. Back off along the
            # drag path to the furthest valid rectangle instead of making the
            # handle appear unresponsive at an edge.
            original = QPointF(point)
            delta = pos - original
            low, high = 0.0, 1.0
            best_points = original_points
            for _ in range(24):
                fraction = (low + high) / 2.0
                candidate = original + delta * fraction
                candidate_points = resized_points(candidate, opposite)
                if any(self.outOfPixmap(vertex)
                       for vertex in candidate_points):
                    high = fraction
                else:
                    low = fraction
                    best_points = candidate_points
            new_points = best_points

        if new_points == shape.points:
            return
        shape.points = new_points
        shape.direction = direction
        shape.close()
        # lshift = None
        # rshift = None
        # if index % 2 == 0:
        #     rshift = QPointF(shiftPos.x(), 0)
        #     lshift = QPointF(0, shiftPos.y())
        # else:
        #     lshift = QPointF(shiftPos.x(), 0)
        #     rshift = QPointF(0, shiftPos.y())
        # shape.moveVertexBy(rindex, rshift)
        # shape.moveVertexBy(lindex, lshift)

    def _fitResizeBaseline(self, points):
        """Fit an existing rectangle by translation/uniform scale on edit."""
        if not any(self.outOfPixmap(point) for point in points):
            return points
        width, height = float(self.pixmap.width()), float(self.pixmap.height())
        left = min(point.x() for point in points)
        right = max(point.x() for point in points)
        top = min(point.y() for point in points)
        bottom = max(point.y() for point in points)
        factor = min(1.0,
                     width / (right - left) if right > left else 1.0,
                     height / (bottom - top) if bottom > top else 1.0)
        center = QPointF((left + right) / 2, (top + bottom) / 2)
        fitted = [center + (point - center) * factor for point in points]
        left = min(point.x() for point in fitted)
        right = max(point.x() for point in fitted)
        top = min(point.y() for point in fitted)
        bottom = max(point.y() for point in fitted)
        delta = QPointF(min(max(0.0, -left), width - right),
                        min(max(0.0, -top), height - bottom))
        return [self._snapPixmapBoundaryRoundoff(point + delta)
                for point in fitted]

    def _snapPixmapBoundaryRoundoff(self, point):
        """Remove tiny floating-point overshoots at exact image edges."""
        width = float(self.pixmap.width())
        height = float(self.pixmap.height())
        tolerance = 1e-7
        x, y = point.x(), point.y()
        if -tolerance <= x < 0:
            x = 0.0
        elif width < x <= width + tolerance:
            x = width
        if -tolerance <= y < 0:
            y = 0.0
        elif height < y <= height + tolerance:
            y = height
        return QPointF(x, y)

    def getAdjointPoints(self, theta, p3, p1, index):
        # Orthogonal projection avoids the near-vertical tan()/intersection
        # singularity and keeps the opposite corner fixed.
        cos_theta, sin_theta = math.cos(theta), math.sin(theta)
        if abs(cos_theta) < 1e-12:
            cos_theta = 0.0
        if abs(sin_theta) < 1e-12:
            sin_theta = 0.0
        axis = QPointF(cos_theta, sin_theta)
        diagonal = p3 - p1
        along = axis * (diagonal.x() * axis.x() + diagonal.y() * axis.y())
        across = diagonal - along
        p2, p4 = p1 + along, p1 + across
        if index % 2:
            p2, p4 = p4, p2
        return p2, p3, p4

    def getCrossPoint(self,a1,b1,a2,b2):
        x = (b2-b1)/(a1-a2)
        y = (a1*b2 - a2*b1)/(a1-a2)
        return QPointF(x,y)

    def boundedRotateShape(self, pos):
        # print("Rotate Shape2")          
        # judge if some vertex is out of pixma
        index, shape = self.hVertex, self.hShape
        point = shape[index]

        angle = self.getAngle(shape.center ,pos,point)
        # for i, p in enumerate(shape.points):
        #     if self.outOfPixmap(shape.rotatePoint(p,angle)):
        #         # print("out of pixmap")
        #         return
        if not self.rotateOutOfBound(angle):
            shape.rotate(angle)
            self.prevPoint = pos

    def getAngle(self, center, p1, p2):
        dx1 = p1.x() - center.x()
        dy1 = p1.y() - center.y()

        dx2 = p2.x() - center.x()
        dy2 = p2.y() - center.y()

        c = math.sqrt(dx1*dx1 + dy1*dy1) * math.sqrt(dx2*dx2 + dy2*dy2)
        if c == 0: return 0
        y = (dx1*dx2+dy1*dy2)/c
        if y>1: return 0
        angle = math.acos(y)

        if (dx1*dy2-dx2*dy1)>0:   
            return angle
        else:
            return -angle

    def boundedMoveShape(self, shape, pos):
        if self.pixmap is None or self.pixmap.isNull():
            return False
        dp = self._boundedTranslation([shape], pos - self.prevPoint)
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        #self.calculateOffsets(self.selectedShape, pos)
        if dp:
            shape.moveBy(dp)
            shape.close()
        self.prevPoint = pos
        return bool(dp)

    def _boundedTranslation(self, shapes, delta):
        """Clamp a translation so every selected vertex stays on the image."""
        shapes = [shape for shape in shapes if shape is not None]
        if not shapes or self.pixmap is None or self.pixmap.isNull():
            return QPointF()
        points = [point for shape in shapes for point in shape.points]
        if not points:
            return QPointF()
        left = min(point.x() for point in points)
        right = max(point.x() for point in points)
        top = min(point.y() for point in points)
        bottom = max(point.y() for point in points)
        dx = min(max(float(delta.x()), -left),
                 float(self.pixmap.width()) - right)
        dy = min(max(float(delta.y()), -top),
                 float(self.pixmap.height()) - bottom)
        return QPointF(dx, dy)

    def boundedMoveShape2(self, shape, pos):
        if self.outOfPixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.outOfPixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.outOfPixmap(o2):
            pos += QPointF(min(0, self.pixmap.width() - o2.x()),
                           min(0, self.pixmap.height() - o2.y()))
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        #self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prevPoint
        if dp:
            shape.moveBy(dp)
            self.prevPoint = pos
            shape.close()
            return True
        return False

    def deSelectShape(self):
        for sh in self.selectedShapes:
            sh.selected = False
        self.selectedShapes = []
        if self.selectedShape:
            self.selectedShape = None
            self.setHiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def deleteSelected(self):
        if self.selectedShapes:
            deleted = list(self.selectedShapes)
            for sh in deleted:
                if sh in self.shapes:
                    self.shapes.remove(sh)
                sh.selected = False
            self.selectedShapes = []
            self.selectedShape = None
            self.update()
            return deleted
        elif self.selectedShape:
            shape = self.selectedShape
            self.shapes.remove(self.selectedShape)
            self.selectedShape = None
            self.update()
            return [shape]
        return []
        
    def deleteAll(self):
        self.shapes.clear()
        self.selectedShape = None
        self.selectedShapes = []
        self.update()

    def copySelectedShape(self):
        if self.selectedShapes:
            shapesToCopy = list(self.selectedShapes)
            self.deSelectShape()
            newShapes = []
            for original in shapesToCopy:
                shape = original.copy()
                self.shapes.append(shape)
                shape.selected = True
                self.selectedShapes.append(shape)
                self.boundedShiftShape(shape)
                newShapes.append(shape)
            self.selectedShape = newShapes[-1] if newShapes else None
            return newShapes
        elif self.selectedShape:
            shape = self.selectedShape.copy()
            self.deSelectShape()
            self.shapes.append(shape)
            shape.selected = True
            self.selectedShape = shape
            self.selectedShapes.append(shape)
            self.boundedShiftShape(shape)
            return [shape]
        return []

    def pasteShapes(self, templates, target=None, offset=None,
                    constrainToCanvas=True, avoidExactOverlap=False):
        if (not templates or self.pixmap is None or self.pixmap.isNull()):
            return []

        newShapes = [template.copy() for template in templates]
        allPoints = [point for shape in newShapes for point in shape.points]
        if not allPoints:
            return []

        minX = min(point.x() for point in allPoints)
        maxX = max(point.x() for point in allPoints)
        minY = min(point.y() for point in allPoints)
        maxY = max(point.y() for point in allPoints)

        if target is not None:
            sourceCenter = QPointF((minX + maxX) / 2.0,
                                   (minY + maxY) / 2.0)
            delta = target - sourceCenter
        else:
            delta = QPointF(offset if offset is not None else QPointF(10, 10))

        def boundedDelta(candidate):
            candidate = QPointF(candidate)
            if not constrainToCanvas:
                return candidate
            # Keep the pasted group visible without changing size or angle.
            maxCanvasX = self.pixmap.width() - 1
            maxCanvasY = self.pixmap.height() - 1
            if maxX - minX <= maxCanvasX:
                if minX + candidate.x() < 0:
                    candidate.setX(-minX)
                elif maxX + candidate.x() > maxCanvasX:
                    candidate.setX(maxCanvasX - maxX)
            if maxY - minY <= maxCanvasY:
                if minY + candidate.y() < 0:
                    candidate.setY(-minY)
                elif maxY + candidate.y() > maxCanvasY:
                    candidate.setY(maxCanvasY - maxY)
            return candidate

        def exactlyOverlapsExisting(candidate):
            tolerance = 0.01
            for template in newShapes:
                translated = [point + candidate for point in template.points]
                for existing in self.shapes:
                    if len(existing.points) != len(translated):
                        continue
                    if all(distance(old - new) <= tolerance
                           for old, new in zip(existing.points, translated)):
                        return True
            return False

        delta = boundedDelta(delta)
        if avoidExactOverlap and exactlyOverlapsExisting(delta):
            # Try nearby diagonal positions until the copy is visibly separate.
            for step in range(1, 101):
                for shift in ((10 * step, 10 * step),
                              (-10 * step, 10 * step),
                              (10 * step, -10 * step),
                              (-10 * step, -10 * step)):
                    candidate = boundedDelta(
                        delta + QPointF(shift[0], shift[1]))
                    if not exactlyOverlapsExisting(candidate):
                        delta = candidate
                        break
                else:
                    continue
                break

        self.deSelectShape()
        for shape in newShapes:
            shape.moveBy(delta)
            shape.close()
            shape.selected = True
            self.shapes.append(shape)
        self.selectedShapes = list(newShapes)
        self.selectedShape = newShapes[-1]
        self.setHiding()
        self.selectionChanged.emit(True)
        self.repaint()
        return newShapes

    def boundedShiftShape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculateOffsets(shape, point)
        self.prevPoint = point
        if not self.boundedMoveShape(shape, point - offset):
            self.boundedMoveShape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        
        #ur = event.rect()
        #tmppix = QPixmap(ur.size())
        #p = QPainter(tmppix)
        #p.translate(-ur.x(), -ur.y())
        ##p.begin(self)

        p.begin(self)



        #p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.HighQualityAntialiasing)
        if self.scale < 1.0:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            
        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())

        p.drawPixmap(0, 0, self.pixmap)
        Shape.scale = self.scale
        for shape in self.shapes:
            if (shape.selected or not self._hideBackround) and self.isVisible(shape):
                if (shape.isRotated and not self.hideRotated) or (not shape.isRotated and not self.hideNormal):
                    shape.fill = shape.selected or shape == self.hShape
                    shape.highlightCorner = (
                        shape.alwaysShowCorner or shape.selected or
                        shape is self.hShape)
                    shape.paint(p)
                elif self.showCenter:
                    shape.fill = shape.selected or shape == self.hShape
                    shape.paintNormalCenter(p) #shape.paint(p)
        if self.current:
            self.current.paint(p)
            self.line.paint(p)
        if self.selectedShapeCopy:
            self.selectedShapeCopy.paint(p)

        if self._marqueeStart is not None and self._marqueeDragging:
            p.save()
            p.setPen(QPen(QColor(0, 170, 255), 1.5 / self.scale, Qt.DashLine))
            p.setBrush(QBrush(QColor(0, 170, 255, 45)))
            p.drawRect(self._marqueeRect())
            p.restore()

        # Paint rect
        # Paint rect
        if self.current is not None and len(self.line) == 2:
            leftTop = self.line[0]
            rightBottom = self.line[1]
            rectWidth = rightBottom.x() - leftTop.x()
            rectHeight = rightBottom.y() - leftTop.y()
            p.setPen(self.drawingRectColor)
            brush = QBrush(Qt.BDiagPattern)
            p.setBrush(brush)
            # p.drawRect(leftTop.x(), leftTop.y(), rectWidth, rectHeight)
            p.drawRect(int(leftTop.x()), int(leftTop.y()), int(rectWidth), int(rectHeight))


        if (self.drawing() or self.continueDrawing()) and not self.prevPoint.isNull() and not self.outOfPixmap(self.prevPoint):
            oldmode = p.compositionMode()
            p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
            p.setPen(QPen(QColor(255,255,255), 1/self.scale)) # TODO : limit pen width

            # p.drawLine(self.prevPoint.x(), 0, self.prevPoint.x(), self.pixmap.height())
            p.drawLine(int(self.prevPoint.x()), 0, int(self.prevPoint.x()), int(self.pixmap.height()))
            # p.drawLine(0, self.prevPoint.y(), self.pixmap.width(), self.prevPoint.y())
            p.drawLine(0, int(self.prevPoint.y()), self.pixmap.width(), int(self.prevPoint.y()))
            p.setCompositionMode(oldmode)

        #p.translate(-self.offsetToCenter())
        #p.scale(1/self.scale, 1/self.scale)
        #if self.localScalePixmap is not None:
        #    p0 = QPoint(0, 0)
        #    p1 = self.mapFromParent(p0)
        #    if p1.x() > 0:
        #        p0.setX(p1.x())
        #    if p1.y() > 0:
        #        p0.setY(p1.y())
            
        #    p.drawPixmap(p0.x(), p0.y(), self.localScalePixmap)

        p.end()

        #pp = self._painter
        #pp.begin(self)
        #pp.drawPixmap(0,0,tmppix)
        #pp.end()
        

    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offsetToCenter()

    def offsetToCenter(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def outOfPixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    def finalise(self, continous=False):
        if self.current is None:
            return
        if self.pixmap is not None and not self.pixmap.isNull():
            self.current.points = [
                self._boundedPixmapPoint(point)
                for point in self.current.points]
            self.current.close()
            bounds = self.current.boundingRect()
            if (bounds.width() < self.MIN_SHAPE_EDGE or
                    bounds.height() < self.MIN_SHAPE_EDGE):
                self.current = None
                self.drawingPolygon.emit(False)
                self.update()
                return
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return

        self.current.isRotated = self.canDrawRotatedRect
        self.current.close()
        self.shapeChangeStarted.emit()
        self.shapes.append(self.current)
        self.current = None
        self.setHiding(False)
        self.newShape.emit(continous) # TODO:
        self.shapeChangeFinished.emit()
        self.update()

    def closeEnough(self, p1, p2):
        #d = distance(p1 - p2)
        #m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    def vertexHitRadius(self):
        """Return a constant screen-space corner hit radius in image units."""
        return self.VERTEX_HIT_RADIUS / max(float(self.scale), 0.01)

    def intersectionPoint(self, p1, p2):
        # Cycle through each image edge in clockwise fashion,
        # and find the one intersecting the current line segment.
        # http://paulbourke.net/geometry/lineline2d/
        size = self.pixmap.size()
        points = [(0, 0),
                  (size.width(), 0),
                  (size.width(), size.height()),
                  (0, size.height())]
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QPointF(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QPointF(min(max(0, x2), max(x3, x4)), y3)
        return QPointF(x, y)

    def intersectingEdges(self, x1y1, x2y2, points):
        """For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen."""
        x1, y1 = x1y1
        x2, y2 = x2y2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                # This covers two cases:
                #   nua == nub == 0: Coincident
                #   otherwise: Parallel
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QPointF((x3 + x4) / 2, (y3 + y4) / 2)
                d = distance(m - QPointF(x2, y2))
                yield d, i, (x, y)

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            size = self.scale * self.pixmap.size()
            size.setWidth(max(size.width(), self.panViewportWidth) +
                          2 * self.panHorizontalMargin)
            size.setHeight(max(size.height(), self.panViewportHeight) +
                           2 * self.panMargin)
            return size
        return super(Canvas, self).minimumSizeHint()

    def setPanViewportSize(self, size):
        width = max(0, int(size.width()))
        height = max(0, int(size.height()))
        if (width == self.panViewportWidth and
                height == self.panViewportHeight):
            return False
        self.panViewportWidth = width
        self.panViewportHeight = height
        self.panHorizontalMargin = width // 3
        self.panMargin = height // 3
        self.updateGeometry()
        self.adjustSize()
        return True

    def _selectedShapesForWheelResize(self):
        shapes = []
        for shape in self.selectedShapes:
            if shape is not None and shape.selected and shape not in shapes:
                shapes.append(shape)
        if (self.selectedShape is not None and self.selectedShape.selected and
                self.selectedShape not in shapes):
            shapes.append(self.selectedShape)
        return shapes

    def resizeSelectedShapesByWheel(self, wheel_delta):
        """Scale selected boxes around their centres without zooming the image."""
        shapes = self._selectedShapesForWheelResize()
        if not shapes or not wheel_delta:
            return False

        # A normal mouse-wheel notch is 120 units. Limiting one event prevents
        # unusually large touchpad deltas from making a box jump in size.
        notches = max(-10.0, min(10.0, float(wheel_delta) / 120.0))
        factor = math.pow(self.WHEEL_SHAPE_SCALE_STEP, notches)
        candidates = []

        for shape in shapes:
            if len(shape.points) < 2:
                return False
            center = (QPointF(shape.center) if shape.center is not None else
                      shape.boundingRect().center())

            if factor < 1.0:
                edge_lengths = [
                    distance(shape.points[(index + 1) % len(shape.points)] - point)
                    for index, point in enumerate(shape.points)
                ]
                if (not edge_lengths or
                        min(edge_lengths) * factor < self.MIN_SHAPE_EDGE):
                    return False

            new_points = []
            for point in shape.points:
                offset = point - center
                new_point = QPointF(
                    center.x() + offset.x() * factor,
                    center.y() + offset.y() * factor
                )
                new_points.append(new_point)

            if (not self.canOutOfBounding and
                    any(self.outOfPixmap(point) for point in new_points)):
                return False
            candidates.append((shape, new_points))

        self.shapeChangeStarted.emit()
        for shape, new_points in candidates:
            shape.points = new_points
            shape.close()

        self.shapeMoved.emit()
        self.shapeChangeFinished.emit()
        self.update()
        return True

    def wheelEvent(self, ev):
        qt_version = 4 if hasattr(ev, "delta") else 5
        if qt_version == 4:
            if ev.orientation() == Qt.Vertical:
                v_delta = ev.delta()
                h_delta = 0
            else:
                h_delta = ev.delta()
                v_delta = 0
        else:
            delta = ev.angleDelta()
            h_delta = delta.x()
            v_delta = delta.y()

        zoom_delta = v_delta if v_delta else h_delta
        if zoom_delta:
            # Selected box: resize the box only. No selected box: preserve the
            # existing wheel-to-image-zoom behaviour. Even at a resize limit,
            # consume the event so the image never zooms unexpectedly.
            if self._selectedShapesForWheelResize():
                self.resizeSelectedShapesByWheel(zoom_delta)
            else:
                self.zoomRequest.emit(zoom_delta)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if (ev.modifiers() & Qt.ControlModifier and
                key in (Qt.Key_Z, Qt.Key_X, Qt.Key_C, Qt.Key_V)):
            ev.ignore()
            return
        if key == Qt.Key_Escape and self._marqueeStart is not None:
            self._clearMarqueeSelection()
            self.overrideCursor(CURSOR_DEFAULT)
            self.update()
            ev.accept()
            return
        elif key == Qt.Key_Alt:
            self._altPressed = True
            self.overrideCursor(CURSOR_GRAB)
            ev.accept()
            return
        elif key == Qt.Key_Escape and self.current:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Escape and self.current is None:
            if self.drawing() or self.continueDrawing():
                self.cancelDraw.emit()
            self.finalise()
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            if self.canCloseShape():
                self.finalise()
            if self.selectedShape:
                self.toggleEdit.emit(True)
            else:
                if len(self.shapes) > 0:
                    self.selectShape(self.shapes[0])
        elif key == Qt.Key_Left and self.selectedShape:
            self.moveOnePixel('Left')
            ev.accept()
            return
        elif key == Qt.Key_Right and self.selectedShape:
            self.moveOnePixel('Right')
            ev.accept()
            return
        elif key == Qt.Key_Up:
            if self.selectedShape:
                self.moveOnePixel('Up')
            elif self.editing():
                self.imageNavigationRequested.emit(-1)
            ev.accept()
            return
        elif key == Qt.Key_Down:
            if self.selectedShape:
                self.moveOnePixel('Down')
            elif self.editing():
                self.imageNavigationRequested.emit(1)
            ev.accept()
            return
        elif key == Qt.Key_Z and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(0.1):
            self.shapeChangeStarted.emit()
            self.selectedShape.rotate(0.1)
            self.shapeMoved.emit() 
            self.shapeChangeFinished.emit()
            self.update()  
        elif key == Qt.Key_X and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(0.01):
            self.shapeChangeStarted.emit()
            self.selectedShape.rotate(0.01) 
            self.shapeMoved.emit()
            self.shapeChangeFinished.emit()
            self.update()  
        elif key == Qt.Key_C and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(-0.01):
            self.shapeChangeStarted.emit()
            self.selectedShape.rotate(-0.01) 
            self.shapeMoved.emit()
            self.shapeChangeFinished.emit()
            self.update()  
        elif key == Qt.Key_V and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(-0.1):
            self.shapeChangeStarted.emit()
            self.selectedShape.rotate(-0.1)
            self.shapeMoved.emit()
            self.shapeChangeFinished.emit()
            self.update()
        elif key == Qt.Key_F and self.selectedShape and\
             self.selectedShape.isRotated and not self.rotateOutOfBound(-math.pi/2):
            self.shapeChangeStarted.emit()
            self.selectedShape.rotate(-math.pi/2)
            self.shapeMoved.emit()
            self.shapeChangeFinished.emit()
            self.update()
        elif key == Qt.Key_N:
            self.hideNormal = not self.hideNormal
            self.hideNRect.emit(self.hideNormal)
            self.update()
        elif key == Qt.Key_B:
            self.showCenter = not self.showCenter
            self.update()

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Alt:
            self._altPressed = False
            if not self._panning:
                self.overrideCursor(CURSOR_DRAW if self.drawing() else CURSOR_DEFAULT)
            ev.accept()
            return
        super(Canvas, self).keyReleaseEvent(ev)

    def rotateOutOfBound(self, angle):
        if self.canOutOfBounding:
            return False
        for i, p in enumerate(self.selectedShape.points):
            if self.outOfPixmap(self.selectedShape.rotatePoint(p,angle)):
                return True
        return False

    def moveOnePixel(self, direction):
        # Keep the legacy method name for callers; nudge by image pixels.
        dirMap = {
            'Left': QPointF(-self.NUDGE_STEP, 0),
            'Right': QPointF(self.NUDGE_STEP, 0),
            'Up': QPointF(0, -self.NUDGE_STEP),
            'Down': QPointF(0, self.NUDGE_STEP),
        }
        step = dirMap.get(direction)
        if step is None:
            return
        shapesToMove = self.selectedShapes if self.selectedShapes else ([self.selectedShape] if self.selectedShape else [])
        if not shapesToMove:
            return
        step = self._boundedTranslation(shapesToMove, step)
        if step.isNull():
            return
        self.shapeChangeStarted.emit()
        for sh in shapesToMove:
            for i in range(len(sh.points)):
                sh.points[i] += step
            sh.center += step
        self.shapeMoved.emit()
        self.shapeChangeFinished.emit()
        self.repaint()

    def moveOutOfBound(self, step):
        # Kept for backward compatibility
        if self.selectedShape:
            points = [p1+p2 for p1, p2 in zip(self.selectedShape.points, [step]*4)]
            return True in map(self.outOfPixmap, points)
        return False

    def setLastLabel(self, text, line_color  = None, fill_color = None, extra_text=''):
        assert text
        self.shapes[-1].label = text
        self.shapes[-1].extra_label = extra_text
        if line_color:
            self.shapes[-1].line_color = line_color
        
        if fill_color:
            self.shapes[-1].fill_color = fill_color

        return self.shapes[-1]

    def undoLastLine(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def resetAllLines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def loadPixmap(self, pixmap):
        self._clearMarqueeSelection()
        self.unHighlight()
        self.pixmap = pixmap
        self.resetPanView = True
        self.shapes = []
        self.visible.clear()
        self.selectedShapes = []
        self.selectedShape = None
        self.repaint()

    def loadShapes(self, shapes):
        self.shapes = list(shapes)
        self.current = None
        self.repaint()

    def setShapeVisible(self, shape, value):
        value = bool(value)
        self.visible[shape] = value
        self.shapeVisibilityChanged.emit(shape, value)
        self.repaint()

    @property
    def verified(self):
        return self._verified

    @verified.setter
    def verified(self, value):
        self._verified = bool(value)
        color = (QColor(184, 239, 38, 128) if value else
                 QColor(232, 232, 232, 255))
        palette = self.palette()
        if palette.color(self.backgroundRole()) != color:
            palette.setColor(self.backgroundRole(), color)
            self.setPalette(palette)
        self.setAutoFillBackground(True)

    def currentCursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def overrideCursor(self, cursor):
        self._cursor = cursor
        current = self.currentCursor()
        if current == cursor:
            return
        if current is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restoreCursor(self):
        QApplication.restoreOverrideCursor()

    def resetState(self):
        self._clearMarqueeSelection()
        self.restoreCursor()
        self.pixmap = None
        #self.localScalePixmap = None
        self.update()

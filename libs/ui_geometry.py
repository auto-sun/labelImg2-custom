#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Screen-aware sizes for the application's dialogs and main window."""

from PyQt5.QtCore import QRect, QSize
from PyQt5.QtGui import QCursor, QGuiApplication


def available_screen_geometry(widget=None):
    parent = widget.parentWidget() if widget is not None else None
    if parent is not None:
        anchor = parent.mapToGlobal(parent.rect().center())
    elif widget is not None and widget.isVisible():
        anchor = widget.mapToGlobal(widget.rect().center())
    else:
        anchor = QCursor.pos()
    screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen else QRect(0, 0, 1024, 768)


def screen_work_areas():
    return [screen.availableGeometry() for screen in QGuiApplication.screens()]


def recover_window_frame(frame, work_areas, owner_area, preferred=QSize(860, 530)):
    """Fit a lost frame to a single monitor, not to the virtual desktop union."""
    areas = [area for area in work_areas if area.isValid()]
    if any(area.contains(frame) for area in areas) and frame.isValid():
        return QRect(frame)

    # Qt can have gaps between screen rectangles when DPI factors differ.
    # Count real overlap with a screen; coordinates in a gap pick the owner.
    def overlap(area):
        visible = area.intersected(frame)
        return visible.width() * visible.height()

    overlapping = max(areas, key=overlap, default=QRect())
    preserve_size = (overlap(overlapping) > 0 and frame.isValid()
                     and frame.width() <= overlapping.width()
                     and frame.height() <= overlapping.height())
    destination = overlapping if preserve_size else owner_area
    if not destination.isValid():
        destination = areas[0] if areas else QRect(0, 0, 1024, 768)
    safe = destination.adjusted(12, 12, -12, -12)
    if not safe.isValid():
        safe = destination
    if not preserve_size:
        size = preferred.boundedTo(safe.size())
        result = QRect(safe.topLeft(), size)
        result.moveCenter(safe.center())
        return result

    size = frame.size().boundedTo(safe.size())
    x = max(safe.left(), min(frame.x(), safe.right() - size.width() + 1))
    y = max(safe.top(), min(frame.y(), safe.bottom() - size.height() + 1))
    return QRect(x, y, size.width(), size.height())


def responsive_dialog_size(available, preferred=QSize(980, 700),
                           minimum_desired=QSize(720, 540), margin=48):
    """Return a useful initial size without exceeding the active screen."""
    width = min(
        max(1, available.width() - margin),
        preferred.width(),
        max(minimum_desired.width(), int(available.width() * 0.72)))
    height = min(
        max(1, available.height() - margin),
        preferred.height(),
        max(minimum_desired.height(), int(available.height() * 0.78)))
    return QSize(width, height)

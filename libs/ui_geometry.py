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

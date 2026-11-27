"""Check and recover this app's own windows in Win32 desktop coordinates."""

import ctypes
from ctypes import wintypes
from functools import lru_cache
from typing import NamedTuple

from PyQt5.QtCore import QRect, QSize

from .ui_geometry import reachable_window_title


class _MonitorInfo(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                ('work', wintypes.RECT), ('flags', wintypes.DWORD)]


class WindowGeometry(NamedTuple):
    frame: QRect
    work_area: QRect
    scale: float
    title_reachable: bool
    maximized: bool


def _rect(rect):
    return QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


@lru_cache(maxsize=1)
def windows_window_placement():
    try:
        return _WindowPlacement()
    except (AttributeError, OSError):
        return None


class _WindowPlacement:
    def __init__(self):
        user32 = ctypes.WinDLL('user32')

        def bind(name, result, *args):
            function = getattr(user32, name)
            function.restype = result
            function.argtypes = args
            return function

        hwnd = wintypes.HWND
        self._dpi_context = bind('SetThreadDpiAwarenessContext', ctypes.c_void_p, ctypes.c_void_p)
        self._dpi = bind('GetDpiForWindow', wintypes.UINT, hwnd)
        self._get_rect = bind('GetWindowRect', wintypes.BOOL, hwnd, ctypes.POINTER(wintypes.RECT))
        self._is_zoomed = bind('IsZoomed', wintypes.BOOL, hwnd)
        self._monitor_from_rect = bind('MonitorFromRect', wintypes.HMONITOR,
                                      ctypes.POINTER(wintypes.RECT), wintypes.DWORD)
        self._monitor_from_window = bind('MonitorFromWindow', wintypes.HMONITOR, hwnd, wintypes.DWORD)
        self._info = bind('GetMonitorInfoW', wintypes.BOOL, wintypes.HMONITOR,
                          ctypes.POINTER(_MonitorInfo))
        self._position = bind('SetWindowPos', wintypes.BOOL, hwnd, hwnd,
                              ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
        self._key_state = bind('GetAsyncKeyState', ctypes.c_short, ctypes.c_int)

    def _work_area(self, monitor):
        info = _MonitorInfo(size=ctypes.sizeof(_MonitorInfo))
        return _rect(info.work) if monitor and self._info(monitor, ctypes.byref(info)) else QRect()

    def geometry(self, window):
        # Do not compare Qt logical coordinates with Windows' physical pixels.
        old_context = self._dpi_context(-4)  # PER_MONITOR_AWARE_V2
        try:
            native = wintypes.RECT()
            if not self._get_rect(window, ctypes.byref(native)):
                return None
            frame = _rect(native)
            scale = (self._dpi(window) or 96) / 96
            title_height = round(36 * scale)
            native.bottom = min(native.bottom, native.top + title_height)
            monitor = self._monitor_from_rect(ctypes.byref(native), 0)  # no match for a lost window
            title_area = self._work_area(monitor)
            reachable = reachable_window_title(frame, [title_area], title_height,
                                               round(96 * scale), round(12 * scale))
            work_area = self._work_area(self._monitor_from_window(window, 2))
            return WindowGeometry(frame, work_area, scale, reachable, bool(self._is_zoomed(window)))
        finally:
            if old_context:
                self._dpi_context(old_context)

    def title_reachable(self, window):
        geometry = self.geometry(window)
        return geometry.title_reachable if geometry is not None else None

    def dragging(self):
        # Qt does not always see the button while Windows is handling a title-bar drag.
        return bool(self._key_state(1) & 0x8000)

    def center_on_window_screen(self, window, reference, preferred):
        old_context = self._dpi_context(-4)
        try:
            monitor = self._monitor_from_window(reference, 2)
            area = self._work_area(monitor)
            if not area.isValid():
                return False
            target_dpi = self._dpi(reference) or 96
            original_dpi = self._dpi(window)
            scale = target_dpi / 96
            margin = round(12 * scale)
            safe = area.adjusted(margin, margin, -margin, -margin)
            if not safe.isValid():
                safe = area
            size = QSize(round(preferred.width() * scale),
                         round(preferred.height() * scale)).boundedTo(safe.size())
            frame = QRect(safe.topLeft(), size)
            frame.moveCenter(safe.center())
            # Preserve activation/stacking. Explicitly opening the window handles focus.
            flags = 0x0010 | 0x0004 | 0x0200  # NOACTIVATE | NOZORDER | NOOWNERZORDER
            placement = (window, None, frame.x(), frame.y(), frame.width(), frame.height(), flags)
            if not self._position(*placement):
                return False
            # WM_DPICHANGED can rescale the first placement as it moves between
            # monitors. Apply the intended pixel size once the destination DPI
            # is active, without repeating the cross-monitor transition.
            if original_dpi != target_dpi and self._dpi(window) == target_dpi:
                self._position(*placement)
            return True
        finally:
            if old_context:
                self._dpi_context(old_context)

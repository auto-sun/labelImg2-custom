# -*- coding: utf-8 -*-
"""Keep shortcut-only widgets independent of the active Chinese IME."""
from __future__ import absolute_import

import sys

from PyQt5.QtCore import Qt


def disable_ime_for_shortcuts(widget):
    """Disable composition on a non-text widget, without changing the IME globally."""
    widget.setAttribute(Qt.WA_InputMethodEnabled, False)
    widget.setInputMethodHints(Qt.ImhLatinOnly)
    if sys.platform != 'win32':
        return

    # QWidget's input-method attribute alone does not prevent Windows IMEs
    # from opening their candidate window before Qt receives shortcut keys.
    # A native handle has its own IME context, so text editors elsewhere in
    # the application continue to use the user's selected input method.
    import ctypes
    imm32 = ctypes.windll.imm32
    imm32.ImmAssociateContext.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    imm32.ImmAssociateContext.restype = ctypes.c_void_p
    imm32.ImmAssociateContext(int(widget.winId()), None)

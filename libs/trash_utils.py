# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os


class TrashError(Exception):
    pass


def move_to_trash(paths):
    """Move one or more existing files to the operating-system trash."""
    normalized = [os.path.abspath(str(path)) for path in paths
                  if path and os.path.exists(str(path))]
    if not normalized:
        return
    try:
        from send2trash import send2trash
    except ImportError:
        raise TrashError(
            '缺少 Send2Trash，请运行 pip install -r requirements.txt')
    try:
        send2trash(normalized)
    except Exception as error:
        raise TrashError(str(error))

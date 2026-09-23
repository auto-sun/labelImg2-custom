# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from libs.trash_utils import TrashError, move_to_trash


class TrashUtilsTests(unittest.TestCase):
    def test_existing_absolute_paths_are_forwarded_to_send2trash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'image.jpg')
            with open(path, 'wb') as stream:
                stream.write(b'image')
            sender = mock.Mock()
            module = types.SimpleNamespace(send2trash=sender)

            with mock.patch.dict(sys.modules, {'send2trash': module}):
                move_to_trash([path])

            sender.assert_called_once_with([os.path.abspath(path)])

    def test_backend_failure_is_reported_as_trash_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'image.jpg')
            with open(path, 'wb') as stream:
                stream.write(b'image')
            module = types.SimpleNamespace(
                send2trash=mock.Mock(side_effect=OSError('failed')))

            with mock.patch.dict(sys.modules, {'send2trash': module}):
                with self.assertRaises(TrashError):
                    move_to_trash([path])


if __name__ == '__main__':
    unittest.main()

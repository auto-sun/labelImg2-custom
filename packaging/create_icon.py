#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render the project's existing SVG icon into a Windows .ico file."""
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
from PyQt5.QtCore import QBuffer, QIODevice, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication


def main():
    root = Path(__file__).resolve().parent.parent
    source = root / 'img' / 'tag-black-shape.svg'
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        root / 'build' / 'LabelImg2Custom.ico')
    destination.parent.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError('The project SVG icon cannot be rendered.')

    raster = QImage(256, 256, QImage.Format_ARGB32)
    raster.fill(Qt.transparent)
    painter = QPainter(raster)
    renderer.render(painter)
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not raster.save(buffer, 'PNG'):
        raise RuntimeError('The project icon could not be rasterized.')
    image = Image.open(BytesIO(bytes(buffer.data()))).convert('RGBA')
    image.save(
        str(destination), format='ICO',
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
               (128, 128), (256, 256)])
    print(destination)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

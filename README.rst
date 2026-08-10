LabelImg2 Custom
================

Documentation: English | `简体中文 <README_zh-CN.md>`_

This repository is a modified fork of
`chinakook/labelImg2 <https://github.com/chinakook/labelImg2>`_, a graphical
image annotation tool written in Python and PyQt5.

The original project and this modified version are distributed under the MIT
License. The original copyright notice and license text are preserved in
``LICENSE``. See ``NOTICE.md`` for attribution and ``MODIFICATIONS.md`` for a
detailed list of changes.

Why this fork is more convenient
--------------------------------

The custom workflow removes many repeated operations from day-to-day OBB
annotation:

================================  ============================================
Common interruption               Improved workflow
================================  ============================================
Reopen folders and find progress  Restore the last folder and exact image
Repeatedly enter drawing mode     ``E`` quickly enters or leaves OBB mode
Reopen the label editor manually  Open it automatically after drawing a box
Cycle duplicate initials slowly   Put frequently used matching labels first
Redraw similar objects            Copy/paste boxes, including across images
Edit boxes one at a time          Marquee-select and transform a whole group
Remember separate wheel controls  Resize selected boxes; otherwise zoom image
Clean old export artefacts        Export only same-name YOLO/OBB label files
================================  ============================================

The result is a shorter loop: draw an OBB, type a label initial, adjust it,
save, and move to the next image without repeatedly switching tools or
reselecting directories.

Main additions
--------------

* Rotated bounding-box (OBB) focused annotation workflow.
* Mouse-wheel image zoom, and mouse-wheel resizing for selected boxes.
* ``Alt + left drag`` canvas panning.
* Marquee multi-selection with group move, resize, copy and delete.
* ``Ctrl+C`` / ``Ctrl+V`` box clipboard across images.
* Automatic label editor after drawing a box.
* Frequently used labels are prioritised when cycling by initial letter.
* Persistent image directory, current image, annotation directory and default
  label.
* Natural numeric image ordering (for example, ``2.jpg`` before ``10.jpg``).
* Direct Pascal VOC XML to YOLO or YOLO OBB ``.txt`` conversion, without
  copying images, splitting datasets or generating YAML files.

Installation
------------

Python 3.8 or newer is recommended.

.. code:: console

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python labelImg.py

To load a predefined class file:

.. code:: console

   python labelImg.py "" "path\to\classes.txt"

The bundled fallback class list is ``data/predefined_classes.txt``.

Key controls
------------

==============================  =============================================
Control                         Behaviour
==============================  =============================================
``E``                           Enter/leave rotated OBB drawing mode
Mouse wheel, no box selected    Zoom the image
Mouse wheel, box selected       Resize the selected box or selected group
``Alt + left drag``             Pan the canvas
Left drag on empty image area   Marquee-select boxes
``Ctrl/Shift + marquee``        Add boxes to the current selection
``Ctrl + click``                Toggle a box in the multi-selection
Drag a selected box             Move the selected box or selected group
``Ctrl + drag a box``           Copy and move that box
``Ctrl+C`` / ``Ctrl+V``         Copy/paste selected boxes
``Ctrl+D``                      Duplicate selected boxes
``Delete``                      Delete selected boxes
``A`` / left arrow              Previous image
``D`` / right arrow             Next image
``Z`` / ``X``                   Rotate counter-clockwise (large/small step)
``C`` / ``V``                   Rotate clockwise (small/large step)
``F``                           Rotate 90 degrees clockwise
``Ctrl+S``                      Save annotations
==============================  =============================================

The old ``W`` shortcut for creating an axis-aligned box is intentionally
disabled to reduce accidental activation.

Annotation formats
------------------

LabelImg2 loads matching annotations from the selected annotation directory
with the same relative subdirectory as each image. Pascal VOC ``.xml`` is
preferred; when no matching XML exists, standard YOLO OBB ``.txt`` is loaded:

``class_id x1 y1 x2 y2 x3 y3 x4 y4``

The OBB coordinates are normalized and class IDs follow the current
predefined-class order. Editing a loaded TXT annotation saves the result as
Pascal VOC XML, leaving the source TXT unchanged. If matching XML and TXT files
both exist, the XML file is loaded.

Annotations are edited and saved as Pascal VOC XML. The export menu supports:

* YOLO box: ``class_id cx cy width height``
* YOLO OBB: ``class_id x1 y1 x2 y2 x3 y3 x4 y4``

Export creates only same-name ``.txt`` label files. It does not copy images,
create train/validation/test splits, or generate dataset YAML/list files.
Class IDs follow the current predefined-class order.

Licence and attribution
-----------------------

MIT License. See ``LICENSE``.

Original project: Chinakook, LabelImg2
https://github.com/chinakook/labelImg2

This repository contains independent modifications to the upstream project;
it is not presented as an official upstream release.

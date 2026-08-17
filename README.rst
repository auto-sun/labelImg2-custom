LabelImg2 Custom
================

Documentation: English | `简体中文主页 <README.md>`_

This is an independently maintained derivative of
`chinakook/labelImg2 <https://github.com/chinakook/labelImg2>`_, a graphical
image annotation tool written in Python and PyQt5. The repository has left
GitHub's fork network without concealing or changing its upstream provenance.

The original project is distributed under the MIT License; its original
copyright notice and licence text are preserved in
``LICENSE-MIT-UPSTREAM``. The current combined modified distribution,
including its Ultralytics integration, is released under GNU AGPL v3.0 in
``LICENSE``. See ``NOTICE.md`` for attribution and ``MODIFICATIONS.md`` for a
detailed list of changes.

Interface preview
-----------------

.. image:: docs/images/labelimg2-interface-redacted.png
   :alt: LabelImg2 Custom annotation interface

Downloads
---------

* **v2.2.0 (recommended, undo and exact class matching):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.2.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.2.0.tar.gz>`__
* **v2.1.0 (current-image automatic annotation):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.1.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.1.0.tar.gz>`__
* **v2.0.2 (standalone repository and all earlier custom features):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.2.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.2.tar.gz>`__
* **v2.0.1 (AGPL-3.0 licensing update):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.1.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.1.tar.gz>`__
* **v2.0.0 (first automatic-annotation release):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.0.tar.gz>`__
* **v1.5.0 (isolated Conda/venv launcher):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.5.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.5.0.tar.gz>`__
* **v1.4.0 (direct XML, YOLO and YOLO OBB I/O):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.4.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.4.0.tar.gz>`__
* **v1.3.0 (fast OBB workflow):**
  `ZIP <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.3.0.zip>`__ |
  `TAR.GZ <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.3.0.tar.gz>`__

See `all releases <https://github.com/auto-sun/labelImg2-custom/releases>`__,
`all tags <https://github.com/auto-sun/labelImg2-custom/tags>`__, and the
`changelog <CHANGELOG.md>`__. Tags v1.0 through v1.2 are inherited upstream
history and do not contain the complete custom feature set.

Why this derivative is more convenient
---------------------------------------

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
Convert formats after annotation  Batch-convert from ``Annotation Format``
Manage two annotation commands    One ``Open Annotation Dir`` command
Avoid duplicate conversion menus  One bidirectional format workflow
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
* ``Ctrl+C`` / ``Ctrl+X`` / ``Ctrl+V`` box clipboard across images.
* Automatic label editor after drawing a box.
* Multiple persistent custom ``key -> class.txt label`` bindings can be set
  from ``Box Labels``. Conflicting keys are rejected, and a binding starts one
  OBB for that class without reopening the label picker.
* Frequently used labels are prioritised when cycling by initial letter.
* A panel below ``Box Labels`` shows project, current-image and current-session
  box totals in real time. Adding, deleting and undoing session-created boxes
  updates the net session total; it resets when the application restarts.
* Persistent image directory, current image, annotation directory and default
  label.
* Auto Saving is enabled on first launch and remembers later manual changes.
* Persistent XML, YOLO or YOLO OBB output-format selection.
* Automatic XML / 5-column YOLO / 9-column YOLO OBB input detection.
* Background automatic annotation using a local YOLO or YOLO OBB ``.pt``
  model, with progress, cancellation and fuzzy project-class mapping.
* Natural numeric image ordering (for example, ``2.jpg`` before ``10.jpg``).
* Bidirectional dataset-wide XML, YOLO and YOLO OBB conversion with visible
  progress and safe retention of failed files.

Installation
------------

Python 3.8 or newer is recommended.

.. code:: console

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python labelImg.py

The Windows launcher supports both a project virtual environment and Conda:

.. code:: console

   labelImg.bat             Auto-select a usable environment
   labelImg.bat --venv     Force the project .venv
   labelImg.bat --conda    Force the Conda environment named labelimg2
   labelImg.bat --check    Print the selected environment without launching

Auto mode tries the project ``.venv``, the Conda environment named
``labelimg2``, then another currently active Conda environment. It does
not use the Windows ``py/pyw`` launcher registry.

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
``Ctrl+C/X/V``                  Copy/cut/paste selected boxes
``Ctrl+Z``                      Undo the last box operation (up to 50 steps)
``Ctrl+D``                      Duplicate selected boxes
``Delete``                      Delete selected boxes
``A`` / left arrow              Previous image
``D`` / right arrow             Next image
``Z`` / ``X``                   Rotate counter-clockwise (large/small step)
``C`` / ``V``                   Rotate clockwise (small/large step)
``F``                           Rotate 90 degrees clockwise
``Ctrl+S``                      Save annotations
``Ctrl+R``                      Open the annotation directory
==============================  =============================================

The old ``W`` shortcut for creating an axis-aligned box is intentionally
disabled to reduce accidental activation.

Automatic annotation
--------------------

Open the image root and annotation root, then click the ``自动标注`` toolbar
action. The first run asks for a local Ultralytics YOLO detection or YOLO OBB
``.pt`` model. OBB models automatically select nine-column YOLO OBB output;
regular detection models select five-column YOLO output.

Inference runs in the background. The status bar shows the current image and
overall progress, and its cancel button stops after the current inference
finishes. Model class names are fuzzily mapped to the most similar current
project class. The completion dialog lists every mapping for review. Images
that already have XML or TXT annotations are skipped and never overwritten.
The default confidence threshold is ``0.25``.

An exact full class-name match always takes priority over fuzzy shared-token
matches, so ``pipe_row`` cannot be redirected to ``Drill_pipe``.

The ``标注当前图`` toolbar action runs the model only on the currently open
image. If that image already has labels, a dialog offers three explicit
choices: overwrite the current boxes, append model boxes to them, or cancel.
The result is reloaded immediately after saving. Model output is written as
YOLO/YOLO OBB TXT; an alternate same-name XML file is not deleted.
The complete current-image result is one ``Ctrl+Z`` undo step. Use ``Ctrl+S``
after undoing to write the restored labels back to disk.

No model weights are distributed with this repository. Use only models you
trained or are licensed to use; ``.pt`` files are ignored by Git.

Annotation formats
------------------

Choose the output type from ``File > Annotation Format``:

* Pascal VOC XML: ``.xml``
* YOLO box: ``class_id cx cy width height`` in ``.txt``
* YOLO OBB: ``class_id x1 y1 x2 y2 x3 y3 x4 y4`` in ``.txt``

The choice is remembered across restarts. Manually selecting another format
converts all matching annotations in the current image dataset. A progress
dialog shows each file and can cancel the remaining work. The old file is
removed only after its replacement is written successfully; failed or
unprocessed files retain their original labels. When no labels exist, the
format changes immediately without opening a progress dialog.

``Ctrl+R`` or
``File > Open Annotation Dir`` selects the single directory used both to load
and save annotations. Labels match images recursively through the same
relative subdirectory structure.

TXT input is detected automatically: five values mean YOLO box and nine values
mean YOLO OBB. If both XML and TXT exist, the selected output family is tried
first (XML when XML is selected, otherwise TXT); the other file is used as a
fallback when the preferred file is absent. The file list counts all three
supported formats, and an empty label file is displayed as ``[BG]``.

Coordinates in both YOLO formats are normalized and class IDs follow the
current predefined-class order. Saving writes the currently selected format
directly. Because standard YOLO cannot represent rotation, saving a rotated box
as standard YOLO writes its enclosing axis-aligned rectangle. YOLO and YOLO
OBB share the ``.txt`` extension, and switching between them rewrites each file
from five-column to nine-column records or vice versa. Automatic model-format
selection does not batch-convert existing manual annotations.

Licence and attribution
-----------------------

The combined current distribution is licensed under GNU AGPL v3.0; see
``LICENSE``. Original LabelImg2 portions retain their MIT notice and terms in
``LICENSE-MIT-UPSTREAM``.

Original project: Chinakook, LabelImg2
https://github.com/chinakook/labelImg2

This repository contains independent modifications to the upstream project;
it is not presented as an official upstream release.

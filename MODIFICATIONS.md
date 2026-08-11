# Modifications in this derivative project

[简体中文](MODIFICATIONS_zh-CN.md)

This file summarises the main differences from the upstream
`chinakook/labelImg2` project.

See [CHANGELOG.md](CHANGELOG.md) for the version-by-version release history.

## Local-model automatic annotation

- Local Ultralytics YOLO detection and YOLO OBB ``.pt`` models are supported.
- The model task is detected automatically and selects five-column YOLO or
  nine-column YOLO OBB output.
- Model class names are fuzzily mapped to the current project class preset.
- Inference runs in a background thread with status-bar progress and a cancel
  button.
- Existing XML/TXT annotations are skipped and never overwritten.
- A separate top-toolbar action annotates only the current image and prompts
  to overwrite, append or cancel when labels already exist.
- The completion dialog reports every model-to-project class mapping for
  manual review.

## Annotation workflow

- `E` toggles rotated OBB drawing mode.
- The `W` shortcut for axis-aligned drawing is disabled.
- Drawing one box returns to edit mode instead of continuing to draw.
- The new box is selected and its label editor opens automatically.
- Image navigation shortcuts are disabled while a label editor is active, so
  label initials such as `d` cannot switch images accidentally.

## Labels

- "Set as default" persists across application restarts.
- Repeated initial-letter selection cycles through matching labels in a
  usage-based order instead of alphabetical order.
- Label frequency and recency are stored in the local settings file.

## Canvas and selection

- Plain mouse wheel zooms the image when no box is selected.
- Mouse wheel resizes selected boxes around their centres while preserving OBB
  angles.
- `Alt + left drag` pans the canvas.
- Dragging on an empty image area creates a marquee multi-selection.
- Ctrl/Shift marquee adds to the current selection.
- Selected groups can be moved, resized, duplicated, copied, pasted and
  deleted together.

## Clipboard

- `Ctrl+C` and `Ctrl+V` copy and paste boxes, including across images.
- Same-image pastes are offset to avoid exact overlap.
- Cross-image pastes retain the original coordinates.
- Right-click copy and paste are supported.
- Ctrl-dragging an existing box creates and moves a duplicate.

## Navigation and persistence

- A/D and left/right arrow keys navigate between images.
- With auto-save disabled, navigating away from unsaved changes asks for
  confirmation instead of silently discarding boxes.
- Image filenames use natural numeric ordering.
- The last image directory, current image, annotation directory, default label
  and label usage data are restored at startup.
- Changing the image directory no longer overwrites an explicitly selected
  annotation directory.
- Nested annotation directories are created automatically before saving.
- The selected XML, YOLO or YOLO OBB save format is restored at startup.
- Invalid image and scale states are guarded to reduce crashes.
- Wheel zoom values are converted to Qt-compatible integers to prevent an
  application exit on current Python/PyQt5 versions.

## Annotation formats and directories

- Pascal VOC XML, standard YOLO and YOLO OBB can be selected as the direct
  per-image save format.
- "Change Save Dir" and single-file "Open Annotation" are replaced by one
  "Open Annotation Dir" action used for both loading and saving.
- XML and TXT lookup preserves the image directory's relative subdirectory
  structure.
- Five-column YOLO and nine-column YOLO OBB TXT records are detected
  automatically.
- When XML and TXT both exist, the selected output family is preferred and the
  other file is used as a fallback when the preferred file is absent.
- The file list counts XML and both TXT formats; empty files display as
  background images.
- Standard YOLO saves the enclosing axis-aligned rectangle for rotated boxes.
- Class IDs use the current predefined-class order.

## YOLO export

- Pascal VOC XML is converted directly to same-name YOLO or YOLO OBB `.txt`
  files.
- Export does not copy or re-encode images.
- Export does not create train/validation directories, list files or YAML.
- YOLO OBB records use normalised four-corner coordinates.
- Class IDs follow the current predefined-class order.

## Startup and documentation

- `labelImg.bat` supports active Conda, a project `.venv`, and the named
  Conda environment `labelimg2` without using Windows `py/pyw` registry
  entries.
- `--venv` and `--conda` force one environment family without fallback;
  `--check` reports the selected environment without launching the GUI.
- `Paint Labels` uses `Ctrl+Shift+L`, avoiding the existing
  `Ctrl+Shift+P` Play shortcut.
- GitHub uses the Chinese `README.md` as the main page while retaining
  `README.rst` as the English documentation entry.
- A separate Chinese first-time-user guide covers download, installation,
  class files, annotation and format conversion.

## Licensing

- Starting with v2.0.1, the combined modified distribution is released under
  GNU AGPL v3.0.
- The upstream LabelImg2 MIT copyright and licence notice is preserved
  separately in `LICENSE-MIT-UPSTREAM`.

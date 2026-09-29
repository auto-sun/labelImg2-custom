"""Stable image-to-label paths across opening a parent or child folder."""
import os


def relative_inside(path, root):
    if not root:
        return None
    try:
        relative = os.path.relpath(path, root)
    except (ValueError, TypeError):
        return None
    if relative == os.pardir or relative.startswith(os.pardir + os.sep) or os.path.isabs(relative):
        return None
    return relative


def annotation_base(image, opened, labels, bindings=None, unique_stems=None):
    if not labels:
        return os.path.splitext(image)[0]
    # Explicit remembered child-folder bindings take precedence over a newly
    # opened ancestor. Use only bindings to the currently selected label root.
    candidates = []
    for root, destination in (bindings or {}).items():
        if os.path.normcase(os.path.abspath(destination)) != os.path.normcase(os.path.abspath(labels)):
            continue
        relative = relative_inside(image, root)
        if relative is not None:
            candidates.append((len(os.path.abspath(root)), relative))
    relative = max(candidates)[1] if candidates else relative_inside(image, opened)
    if relative is None:
        relative = os.path.basename(image)
    base = os.path.join(labels, os.path.splitext(relative)[0])
    if any(os.path.isfile(base + ext) for ext in ('.xml', '.txt')):
        return base
    stem = os.path.splitext(os.path.basename(image))[0]
    # Legacy flat labels are safe only when the filename is unique in the
    # opened project. Never silently reuse a label for two different images.
    flat = os.path.join(labels, stem)
    if (unique_stems is not None and os.path.normcase(stem) in unique_stems
            and any(os.path.isfile(flat + ext) for ext in ('.xml', '.txt'))):
        return flat
    return base

import os


def _normalise(value, dimension):
    return float(value) / float(dimension)


def _format_number(value):
    """Write compact, stable floating-point values accepted by Ultralytics."""
    return "{:.8f}".format(value).rstrip("0").rstrip(".") or "0"


def _safe_output_path(output_dir, relative_xml_path):
    relative_txt_path = os.path.splitext(relative_xml_path)[0] + ".txt"
    output_root = os.path.abspath(output_dir)
    output_path = os.path.abspath(os.path.join(output_root, relative_txt_path))
    if os.path.commonpath([output_root, output_path]) != output_root:
        raise ValueError("Invalid annotation path: {}".format(relative_xml_path))
    return output_path


def cvt_xml_annotations_to_yolo(all_shapes_map, yolo_class_map,
                                output_dir, format="box"):
    """Convert parsed Pascal VOC annotations directly to YOLO text files.

    ``all_shapes_map`` maps an XML path relative to the annotation root to its
    image size and boxes. Only corresponding ``.txt`` files are written. Images,
    split folders, list files and YAML files are deliberately not generated.
    """
    if format not in ("box", "rotbox"):
        raise NotImplementedError("Unsupported YOLO format: {}".format(format))

    os.makedirs(output_dir, exist_ok=True)
    exported_files = []

    for relative_xml_path, image_annotation in all_shapes_map.items():
        image_width = float(image_annotation["width"])
        image_height = float(image_annotation["height"])
        if image_width <= 0 or image_height <= 0:
            raise ValueError(
                "Invalid image size in {}: {} x {}".format(
                    relative_xml_path, image_width, image_height
                )
            )

        output_path = _safe_output_path(output_dir, relative_xml_path)
        output_parent = os.path.dirname(output_path)
        if output_parent:
            os.makedirs(output_parent, exist_ok=True)

        lines = []
        for box in image_annotation["bboxes"]:
            class_name = box["class"]
            if class_name not in yolo_class_map:
                raise ValueError("Unknown class: {}".format(class_name))
            class_id = yolo_class_map[class_name]

            if format == "box":
                xs = [box["x0"], box["x1"], box["x2"], box["x3"]]
                ys = [box["y0"], box["y1"], box["y2"], box["y3"]]
                xmin, xmax = min(xs), max(xs)
                ymin, ymax = min(ys), max(ys)
                values = [
                    (xmin + xmax) / 2.0 / image_width,
                    (ymin + ymax) / 2.0 / image_height,
                    (xmax - xmin) / image_width,
                    (ymax - ymin) / image_height,
                ]
            else:
                values = [
                    _normalise(box["x0"], image_width),
                    _normalise(box["y0"], image_height),
                    _normalise(box["x1"], image_width),
                    _normalise(box["y1"], image_height),
                    _normalise(box["x2"], image_width),
                    _normalise(box["y2"], image_height),
                    _normalise(box["x3"], image_width),
                    _normalise(box["y3"], image_height),
                ]

            lines.append(
                "{} {}".format(
                    class_id, " ".join(_format_number(value) for value in values)
                )
            )

        with open(output_path, "w", encoding="utf-8", newline="\n") as label_file:
            if lines:
                label_file.write("\n".join(lines) + "\n")
        exported_files.append(output_path)

    return exported_files

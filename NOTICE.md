# Attribution Notice

[简体中文](NOTICE_zh-CN.md)

This repository is an independently maintained derivative of
[chinakook/labelImg2](https://github.com/chinakook/labelImg2). It has left
GitHub's fork network, but its upstream provenance remains fully documented.

The original project is distributed under the MIT License. Its copyright
notice and permission notice are preserved unchanged in
[`LICENSE-MIT-UPSTREAM`](LICENSE-MIT-UPSTREAM).

Copyright (C) 2026 auto-sun and LabelImg2 Custom contributors.

Beginning with v2.0.1, the combined modified distribution is released under
the [GNU Affero General Public License v3.0](LICENSE). This combined licence
choice does not remove or replace the MIT rights and attribution attached to
the original upstream code.

The modifications in this derivative include workflow, input handling, persistence,
multi-selection, clipboard, YOLO/YOLO OBB export, and local-model automatic
annotation changes. See
[`MODIFICATIONS.md`](MODIFICATIONS.md) for details.

Automatic annotation uses the separately installed third-party
[Ultralytics](https://github.com/ultralytics/ultralytics) package. The
installed package metadata identifies its licence as AGPL-3.0. Ultralytics is
not copied into this repository. The combined project is therefore published
as AGPL-3.0-compatible free and open-source software. Users choosing a
non-AGPL commercial arrangement for Ultralytics must obtain the appropriate
licence directly from Ultralytics.

No model weights are distributed in this repository or its release source
archives. Users are responsible for ensuring that every `.pt` model they
load is self-trained or appropriately licensed. Third-party packages and model
weights remain subject to their own licence terms.

This derivative is not an official release of the upstream project, and no
endorsement by the original authors is implied.

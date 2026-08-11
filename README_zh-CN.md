# LabelImg2 Custom 中文说明

[中文主页](README.md) | [English](README.rst) | 简体中文

第一次安装和使用请直接阅读：[小白首次使用流程](FIRST_USE_GUIDE_zh-CN.md)。

这是 [chinakook/labelImg2](https://github.com/chinakook/labelImg2) 的修改版，
主要针对高频 YOLO OBB 标注工作进行了操作优化。

这个版本没有把原项目包装成全新原创项目。原项目版权声明和 MIT 许可证完整保留在
[`LICENSE`](LICENSE) 中；中文项目来源和修改范围见
[`NOTICE_zh-CN.md`](NOTICE_zh-CN.md) 与
[`MODIFICATIONS_zh-CN.md`](MODIFICATIONS_zh-CN.md)。

## 版本下载

| 版本 | 适用情况 | 下载 |
| --- | --- | --- |
| **v2.0.0（推荐）** | 自动标注和全部自定义功能 | [ZIP](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.0.zip) / [TAR.GZ](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.0.0.tar.gz) |
| v1.5.0 | 独立 Conda/venv 启动器，不含自动标注 | [ZIP](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.5.0.zip) / [TAR.GZ](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.5.0.tar.gz) |
| v1.4.0 | XML、YOLO、YOLO OBB 直接读写 | [ZIP](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.4.0.zip) / [TAR.GZ](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.4.0.tar.gz) |
| v1.3.0 | OBB 快捷标注工作流 | [ZIP](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.3.0.zip) / [TAR.GZ](https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.3.0.tar.gz) |

[全部发行版本](https://github.com/auto-sun/labelImg2-custom/releases) ·
[全部标签](https://github.com/auto-sun/labelImg2-custom/tags) ·
[更新日志](CHANGELOG.md)

`v1.0–v1.2` 是上游历史标签，不包含当前完整的自定义功能。

## 这个修改版方便在哪里

修改的核心目标不是增加复杂菜单，而是减少每天标注时不断重复的操作。

| 常见操作负担 | 修改后的便捷操作 |
| --- | --- |
| 每次启动重新选择图片目录 | 自动恢复上次打开的数据集 |
| 重新寻找上次标到哪一张 | 自动定位到上次正在处理的图片 |
| Open Dir 后标签目录被重置 | 始终保留上次明确选择的标签目录 |
| `1、10、100、2` 顺序混乱 | 使用自然数字顺序排列图片 |
| 每画一个框都要重新双击类别 | 画完框自动打开类别选择器 |
| 相同首字母类别需要反复查找 | 优先显示最常用、最近使用的类别 |
| 输入类别字母 `d` 时跳到下一张 | 类别编辑期间暂时禁用图片切换快捷键 |
| 相似目标需要重新画框 | 支持拖动复制、Ctrl+C/Ctrl+V 和跨图片粘贴 |
| 多个框只能逐个调整 | 鼠标框选后可集体移动、缩放、复制和删除 |
| 图片缩放和框缩放需要不同复杂组合键 | 未选框时滚轮缩放图片，选中框时滚轮缩放框 |
| 标完 XML 后还要批量转换 | 可直接选择保存为 XML、YOLO 或 YOLO OBB |
| 未标注图片只能逐张手工画框 | 可加载本地 YOLO/YOLO OBB `.pt` 批量预标注 |
| 打开标签和设置保存目录是两个入口 | 合并为一个 `Open Annotation Dir` |
| 导出时生成重复图片、train/val 和 YAML | 只把 XML 转成同名 YOLO/YOLO OBB `.txt` |

## 推荐的快速标注流程

1. 打开图片文件夹，按 `Ctrl+R` 选择标签目录。
2. 在 `File > Annotation Format` 选择 XML、YOLO 或 YOLO OBB。
3. 按 `E` 进入 OBB 绘制状态。
4. 在图片上画一个旋转框。
5. 松开鼠标后程序自动退出连续绘制，并选中新框。
6. 类别下拉框自动打开，直接输入类别首字母。
7. 使用 `Z/X/C/V/F` 调整旋转角度。
8. 如果框大小不合适，保持选中并滚动鼠标滚轮。
9. 按 `Ctrl+S` 保存，使用 `D` 或右方向键进入下一张。
10. 再按 `E` 开始绘制下一个 OBB。

相较于原来的操作，这个流程不需要反复双击类别、切换工具、重新选择目录或寻找标注进度。

## 模型自动标注流程

1. 用 `Open Dir` 打开图片根目录。
2. 用 `Open Annotation Dir` 选择标签输出根目录。
3. 点击工具栏“自动标注”，首次使用时选择本地 Ultralytics YOLO 或 YOLO OBB `.pt`。
4. 程序自动识别普通检测或 OBB 模型。OBB 模型会自动选择 YOLO OBB 格式。
5. 状态栏显示进度、当前文件和框数量；点击“中止”会在当前图片推理完成后停止。
6. 完成后查看模型类别到项目类别的映射和相似度，并人工复核标签。

模型类别会在当前预设类别中选择字符串最相似的一项。例如 `apple` 可匹配
`apples`，`melon` 可匹配 `name_melon`。已有 XML 或 TXT 标签的图片会被跳过，
不会覆盖人工标注。默认置信度为 `0.25`。

项目不附带模型文件，请只使用自行训练或具有合法使用权的权重。`.pt` 已被 Git 忽略，
放在项目目录中也不会随正常提交上传。

## 安装和启动

建议使用 Python 3.8 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python labelImg.py
```

`labelImg.bat` 同时支持项目 `.venv` 和 Conda：

```bat
labelImg.bat             自动选择可用环境
labelImg.bat --venv     强制使用项目 .venv
labelImg.bat --conda    强制使用名为 labelimg2 的 Conda 环境
labelImg.bat --check    只检查并显示环境
```

自动模式依次尝试项目 `.venv`、名为 `labelimg2` 的 Conda、当前激活的其他 Conda 环境，并且不再依赖 Windows `py/pyw`。

如果需要指定自己的类别文件：

```powershell
python labelImg.py "" "路径\classes.txt"
```

仓库内的默认示例类别文件是：

```text
data/predefined_classes.txt
```

类别编号从 `0` 开始，按照类别文件中的行顺序确定。因此开始正式标注后，不建议随意调整类别顺序。

## 快捷键速查

| 操作 | 功能 |
| --- | --- |
| `E` | 进入或退出旋转框 OBB 绘制状态 |
| 鼠标滚轮（未选框） | 缩放图片 |
| 鼠标滚轮（已选框） | 以框中心等比例缩放选中框 |
| `Alt + 鼠标左键拖动` | 平移画布 |
| 图片空白处左键拖动 | 框选多个 Box |
| `Ctrl/Shift + 框选` | 把新框选结果追加到当前选择 |
| `Ctrl + 单击 Box` | 添加或取消单个 Box 的多选状态 |
| 拖动任意已选 Box | 集体平移所有选中框 |
| `Ctrl + 拖动 Box` | 复制并移动一个相同 Box |
| `Ctrl+C` | 复制全部选中框 |
| `Ctrl+V` | 粘贴全部已复制框 |
| `Ctrl+D` | 直接复制全部选中框 |
| `Delete` | 删除全部选中框 |
| `A` / 左方向键 | 上一张图片 |
| `D` / 右方向键 | 下一张图片 |
| 上 / 下方向键 | 将选中框移动一个像素 |
| `Z` / `X` | 逆时针大步/小步旋转 |
| `C` / `V` | 顺时针小步/大步旋转 |
| `F` | 顺时针旋转 90 度 |
| `Ctrl+S` | 按当前选择的格式保存标注 |
| `Ctrl+R` | 打开标签目录，同时作为读取和保存目录 |

为了防止误触，`W` 创建普通矩形框的快捷键已取消，但界面中的普通框按钮仍然保留。

## 多选和批量调整

在编辑状态下，从图片空白区域按住左键拖动，会显示蓝色虚线选择区域。

- 普通框选：用本次结果替换原选择。
- `Ctrl/Shift + 框选`：追加选择。
- 选中多个框后，拖动其中任意一个框即可集体平移。
- 滚轮会以每个框自己的中心为基准集体缩放，不改变 OBB 角度。
- `Ctrl+C`、`Ctrl+D` 和 `Delete` 都会作用于整组选中框。

该逻辑不会干扰：

- `Alt + 左键`画布平移；
- `Ctrl + 拖动已有框`复制单框；
- OBB 绘制状态。

## 复制和粘贴规则

### 同一张图片

粘贴时会自动产生偏移，避免新框与原框完全重叠。连续粘贴会继续增加偏移量。

### 不同图片

切换图片后粘贴，会保留复制框原来的：

- 类别；
- 大小；
- 倾斜角度；
- 四个顶点坐标。

这适合机位固定、目标位置变化较小的连续帧标注。

## 类别选择优化

画完 Box 后类别编辑器会自动打开，可以直接输入类别首字母。

当多个类别首字母相同时：

1. 使用次数更多的类别排在前面；
2. 使用次数相同，最近使用的类别排在前面；
3. 仍然相同，才按照原始类别文件顺序；
4. 1.2 秒内连续按同一个字母，会依次循环匹配类别。

点击 `set as default` 后，默认类别会保存到本地设置，下次启动仍然生效。

## 进度和目录恢复

程序退出时会记录：

- 图片目录；
- 当前图片；
- 标签读取/保存目录；
- XML、YOLO 或 YOLO OBB 保存格式；
- 默认类别；
- 类别使用频率与最近使用信息。

设置保存在程序目录旁的本地 `.pkl` 文件中，该文件已被 `.gitignore` 排除，不会上传到 GitHub。

## 保存格式与标签自动识别

在 `File > Annotation Format` 中可以选择：

| 选项 | 实际保存内容 |
| --- | --- |
| `Pascal VOC XML` | Pascal VOC `.xml`，支持普通框和旋转框 |
| `Ultralytics YOLO` | 5 列 `.txt`：`class_id cx cy width height` |
| `Ultralytics YOLO OBB` | 9 列 `.txt`：`class_id x1 y1 x2 y2 x3 y3 x4 y4` |

保存格式会记住，下次启动仍保持上次选择。

`Change Save Dir` 和原来的单文件 `Open Annotation` 已合并成：

```text
Open Annotation Dir    Ctrl+R
```

选中的目录既用于读取标签，也用于保存新标签。打开目录后会立即重新扫描右侧图片列表，并把当前图片对应的已有标签显示到画布上。

TXT 内容会自动识别：

- 每行 5 个值：普通 YOLO；
- 每行 9 个值：YOLO OBB；
- 空 TXT：背景图，右侧显示 `[BG]`；
- 同一个 TXT 内混用 5 列和 9 列会提示格式错误。

匹配和读取规则：

- 图片目录和标签目录按相同的相对子目录结构递归匹配；
- 选择 XML 保存时，同名 XML 优先；XML 不存在时再读取 TXT；
- 选择 YOLO 或 YOLO OBB 保存时，同名 TXT 优先；TXT 不存在时再读取 XML；
- YOLO 坐标按 `0～1` 的归一化坐标读取和保存；
- `class_id` 按当前类别预设文件中的类别顺序映射；
- 右侧图片列表会统计 XML、YOLO 和 YOLO OBB 的框数量。

例如图片为 `images/site_a/day/001.jpg`，图片根目录选择 `images`，标签目录选择 `labels`，程序会匹配：

```text
labels/site_a/day/001.xml
labels/site_a/day/001.txt
```

保存时直接写入当前选择的格式，不再强制先写 XML。需要注意：

- 普通 YOLO 不支持倾斜角度，因此把旋转框保存为普通 YOLO 时，会写成包住旋转框的最小轴对齐外接矩形；
- YOLO OBB 会保留四顶点和倾斜方向；
- 切换格式不会自动删除另一种扩展名的旧标签文件。

## YOLO 和 YOLO OBB 导出

除了直接选择 YOLO/YOLO OBB 保存，仍可从导出菜单批量转换已有 Pascal VOC XML。

普通 YOLO：

```text
class_id cx cy width height
```

YOLO OBB：

```text
class_id x1 y1 x2 y2 x3 y3 x4 y4
```

导出规则：

- 每个 XML 生成一个同名 `.txt`；
- 坐标归一化到 `0～1`；
- 保留 XML 的相对子目录结构；
- 不复制或重新编码图片；
- 不划分 train、val、test；
- 不生成 YAML；
- 不生成图片列表或其他附加文件。

数据集划分应在 XML 转换完成后使用单独的数据集划分脚本处理。

## 许可证和项目来源

本项目遵循 MIT License，详见 [`LICENSE`](LICENSE)。

原项目：Chinakook / LabelImg2

<https://github.com/chinakook/labelImg2>

本仓库是独立修改的派生版本，不代表上游项目的官方发布，也不暗示原作者为本修改版背书。

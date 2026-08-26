# LabelImg2 Custom 小白首次使用流程

本文按“第一次接触 Python 和 LabelImg2”的情况编写，从下载和安装开始，一直到保存 YOLO OBB 标签。

## 使用前注意

正式标注前请先了解下面几点：

1. YOLO 和 YOLO OBB 的 `class_id` 由类别文件的行顺序决定，开始正式标注后不要随意调整类别顺序。
2. `View > Auto Saving` 默认开启。手动关闭后，如果当前图片有未保存修改，切换图片会先询问是否放弃修改。
3. 当前推荐通过 `requirements.txt` 安装依赖后直接运行 `labelImg.py`，不要使用旧的 `setup.py` 安装。

## 一、准备 Python

建议安装 64 位 Python 3.10、3.11 或 3.12。安装 Python 时勾选 `Add Python to PATH`。

安装完成后打开 PowerShell，检查：

```powershell
python --version
```

能看到 Python 版本号即可继续。

## 二、下载项目

### 方法一：下载 ZIP

1. 推荐直接下载最新稳定版：
   <https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v2.3.2.zip>
2. 其他历史版本见：<https://github.com/auto-sun/labelImg2-custom/releases>
3. 解压到路径简单、自己有写入权限的位置，例如：

```text
D:\LabelImg2-custom
```

### 方法二：使用 Git

```powershell
git clone https://github.com/auto-sun/labelImg2-custom.git
cd labelImg2-custom
```

## 三、建立独立环境并安装依赖

在项目目录空白处按住 `Shift` 后点击鼠标右键，选择“在此处打开 PowerShell”，依次执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

这里直接使用虚拟环境中的 Python，不要求执行激活脚本，可以避开部分电脑的 PowerShell 执行策略问题。

`v2.3.2` 包含本地模型自动标注，因此会同时安装 Ultralytics 和 PyTorch，
下载体积和安装时间会比旧版本更大。只进行手工标注时仍可正常使用全部原有功能。

`v2.3.2` 整体使用 GNU AGPL v3.0 免费开源；上游 LabelImg2 的 MIT 许可证单独保留在
`LICENSE-MIT-UPSTREAM`。

## 四、准备类别文件

默认类别文件是：

```text
data\predefined_classes.txt
```

一行写一个类别，例如：

```text
Anthracnose
Brown_Stem_Spot
Soft_Rot
Stem_Canker
```

YOLO 和 YOLO OBB 的类别编号从 `0` 开始，严格按照这个文件的行顺序生成。正式标注开始后不要随意交换类别顺序。

如果不想修改仓库默认文件，也可以指定自己的类别文件：

```powershell
.\.venv\Scripts\python.exe labelImg.py "" "D:\my_dataset\classes.txt"
```

## 五、启动程序

```powershell
.\.venv\Scripts\python.exe labelImg.py
```

程序窗口标题显示 `labelImg2`，说明启动成功。

环境安装完成后可以直接双击项目根目录中的 `labelImg.bat`。启动器不会调用 Windows `py/pyw`，因此不受系统 Python 注册表影响。

自动选择顺序：

1. 项目目录中的 `.venv`；
2. 名为 `labelimg2` 的 Conda 环境；
3. 当前已经激活且依赖完整的其他 Conda 环境。

需要明确指定环境时：

```bat
labelImg.bat --venv
labelImg.bat --conda
```

只检查环境、不打开窗口：

```bat
labelImg.bat --check
labelImg.bat --check --venv
labelImg.bat --check --conda
```

显式指定模式时不会回退到另一种环境：`--venv` 缺失会直接提示创建 `.venv`，`--conda` 缺失会直接提示创建名为 `labelimg2` 的 Conda 环境。

## 六、第一次打开数据集

建议的数据结构：

```text
my_dataset\
├─ images\
│  ├─ train\
│  ├─ val\
│  └─ test\
└─ labels\
   ├─ train\
   ├─ val\
   └─ test\
```

操作顺序：

1. 点击 `File > Open Dir`，选择图片根目录，例如 `my_dataset\images`。
2. 点击 `File > Open Annotation Dir`，选择标签根目录，例如 `my_dataset\labels`。
3. 点击 `File > Annotation Format`，选择需要直接保存的格式：
   - `Pascal VOC XML`
   - `Ultralytics YOLO`
   - `Ultralytics YOLO OBB`
   如果标签目录中已经有标签，程序会显示进度并把全部对应标签转换成新格式；没有标签则直接提示修改成功。
4. `View > Auto Saving` 默认开启；如果手动关闭，切换未保存图片时程序会弹出确认提示。

图片和标签可以具有相同的多层子目录。程序会按相对路径递归对应，例如：

```text
images\train\day1\001.jpg
labels\train\day1\001.txt
```

打开标签目录后，程序会自动判断 `.txt` 内容：

- 每行 5 个值：YOLO 普通矩形框。
- 每行 9 个值：YOLO OBB 四点框。
- 空 `.txt`：背景图，文件列表显示 `[BG]`。
- XML 与 TXT 同时存在时，优先读取当前选择格式对应的文件。

## 七、推荐的 YOLO OBB 标注流程

1. 按 `E` 进入旋转框绘制状态；再次按 `E` 可以退出。
2. 在图片上拖出矩形框。
3. 松开鼠标后程序退出连续绘制，新框自动进入选中和类别编辑状态。
4. 输入类别首字母选择类别；同首字母类别按常用次数和最近使用顺序循环。
5. 使用 `Z`、`X`、`C`、`V`、`F` 调整倾斜角度。
6. 框处于选中状态时滚轮调整框大小。
7. 按 `Ctrl+S` 保存。
8. 按 `D` 或右方向键进入下一张；按 `A` 或左方向键返回上一张。
9. 再按 `E` 画下一个框。

## 八、使用模型自动标注（可选）

1. 先按第六节打开图片目录和标签目录。
2. 点击工具栏“自动标注”。第一次运行会要求选择本地 YOLO 或 YOLO OBB `.pt`。
3. 等待状态栏进度完成；需要停止时点击状态栏的“中止”。
4. 完成后查看类别映射结果，并逐张人工复核模型生成的框。

OBB 模型会自动选择 YOLO OBB 格式。模型自己的类别名会匹配到当前
`predefined_classes.txt` 中最相似的类别。已有 XML/TXT 的图片不会被覆盖。
完整同名类别始终优先；例如模型类别 `pipe_row` 会直接映射到预设中的 `pipe_row`。

只想处理当前图片时，点击顶部“标注当前图”。如果当前图已有标签，选择：

- `覆盖原标签`：仅保留本次模型框；
- `直接添加`：保留当前框并加入模型框；
- `取消`：不作修改。

单张结果保存为 YOLO/YOLO OBB TXT，同名 XML 不会自动删除。
如果结果不满意，按 `Ctrl+Z` 可撤销整次单张模型标注，再按 `Ctrl+S` 保存恢复结果。

仓库不提供模型权重，请使用自己训练或合法授权的模型。

## 九、复制、多选和平移

- `Ctrl+C`：复制当前选中的一个或多个框。
- `Ctrl+X`：剪切当前选中的一个或多个框；第一次粘贴保持原位置，剪切和粘贴都可撤销。
- `Ctrl+V`：粘贴框。
- `Ctrl+Z`：撤销上一步框操作，包括移动、粘贴、删除、缩放和旋转等；每张图片最多保留 50 步。
- 同一张图片粘贴时会自动偏移，防止与原框完全重叠。
- 切换到另一张图片再粘贴时，保留原位置、类别、大小和角度。
- `Ctrl + 拖动框`：直接复制并移动单个框。
- 从图片空白处按住左键拖动：框选多个框。
- `Ctrl/Shift + 框选`：追加选择。
- 拖动任意已选框：整体移动全部选中框。
- `Delete`：删除全部选中框。
- `Alt + 鼠标左键拖动`：平移画布。

## 十、保存格式说明

手动切换保存格式会同时转换当前数据集已有标签。新文件写入成功后才删除旧格式；失败文件仍保留原标签。进度窗口可中止，未处理文件不会改变。模型自动标注根据模型类型选择 YOLO 或 YOLO OBB 时，不会触发这项人工标签批量转换。

### Pascal VOC XML

每张图片生成同名 `.xml`，能够保存普通框和旋转框信息。

### Ultralytics YOLO

每行格式：

```text
class_id center_x center_y width height
```

旋转框保存为普通 YOLO 时，会变成包住旋转框的最小轴对齐外接矩形，倾斜角度不会保留。

### Ultralytics YOLO OBB

每行格式：

```text
class_id x1 y1 x2 y2 x3 y3 x4 y4
```

坐标均为 `0～1` 的归一化坐标，能够保留四个顶点和倾斜方向。

## 十一、批量转换已有标签

先打开图片目录和标签目录，再通过 `File > Annotation Format` 选择目标格式。程序会把当前数据集已有标签批量转换为 XML、YOLO 或 YOLO OBB，并显示进度。旧的 `Export to` 菜单已经移除，不再需要选择单独的导出目录。

## 十二、重新打开后的恢复

正常关闭 LabelImg2 后，下次启动会恢复：

- 上次打开的图片目录；
- 上次正在查看的图片；
- 上次选择的标签目录；
- XML、YOLO 或 YOLO OBB 保存格式；
- `set as default` 设置的默认类别；
- 类别使用次数和最近使用顺序。

设置保存在项目目录旁的 `labelImg2Settings3.pkl`。移动项目目录、删除这个文件或没有项目目录写入权限时，恢复记录会丢失。

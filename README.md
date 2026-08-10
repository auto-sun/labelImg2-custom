# LabelImg2 Custom

简体中文主页 | [English](README.rst)

这是 [chinakook/labelImg2](https://github.com/chinakook/labelImg2) 的修改版，主要针对高频 YOLO OBB 标注工作优化操作流程，并保留原项目的 MIT License 和版权声明。

第一次接触本项目，建议从这里开始：

> [小白首次下载、安装与完整标注流程](FIRST_USE_GUIDE_zh-CN.md)

更完整的功能说明见：[中文详细说明](README_zh-CN.md)。

## 主要改进

- 自动恢复上次打开的图片目录、当前进度、标签目录、保存格式和默认类别。
- 图片文件名按照自然数字顺序排列，例如 `1、2、10、20`。
- 支持相同子目录结构的图片与标签递归匹配。
- 可以直接保存 Pascal VOC XML、Ultralytics YOLO 或 Ultralytics YOLO OBB。
- 打开标签目录后自动识别 XML、YOLO 5 列 TXT、YOLO OBB 9 列 TXT 和空背景 TXT。
- `E` 进入或退出 OBB 绘制，画完自动选中新框并打开类别选择。
- 常用类别优先，减少同首字母类别的重复查找。
- 支持框的复制粘贴、跨图片原位置粘贴、框选多选、整体移动和批量删除。
- 未选框时滚轮缩放图片；选中框时滚轮只调整框大小。
- `Alt + 鼠标左键拖动`平移画布。
- 未开启自动保存时，切换含未保存修改的图片会先弹出确认提示。
- XML 批量转换只生成同名 YOLO/YOLO OBB `.txt`，不复制图片、不划分数据集、不生成 YAML。

## 快速安装

需要 64 位 Python 3.10、3.11 或 3.12。在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe labelImg.py
```

安装完成后可以直接双击 `labelImg.bat`。启动器不会使用 Windows `py/pyw` 注册信息，并按以下顺序自动选择：

1. 项目目录中的 `.venv`；
2. 名为 `labelimg2` 的 Conda 环境；
3. 当前已经激活且依赖完整的其他 Conda 环境。

也可以显式指定，两个环境互不影响：

```bat
labelImg.bat --venv
labelImg.bat --conda
labelImg.bat --check
```

`--venv` 只使用项目 `.venv`，`--conda` 只使用 Conda 的 `labelimg2` 环境，`--check` 只显示将使用的环境而不启动程序。

指定自己的类别文件：

```powershell
.\.venv\Scripts\python.exe labelImg.py "" "D:\my_dataset\classes.txt"
```

类别编号从 `0` 开始，按照类别文件的行顺序确定。正式标注后不要随意交换类别顺序。

## 推荐的 YOLO OBB 流程

1. 使用 `File > Open Dir` 选择图片根目录。
2. 使用 `File > Open Annotation Dir` 选择标签根目录。
3. 在 `File > Annotation Format` 中选择 `Ultralytics YOLO OBB`。
4. 建议在 `View` 菜单开启 `Auto Saving`。
5. 按 `E` 绘制旋转框，画完后直接输入类别首字母。
6. 使用 `Z / X / C / V / F` 调整角度，选中框时滚轮调整大小。
7. 按 `Ctrl+S` 保存，使用 `D` 或右方向键进入下一张。

## 常用快捷键

| 快捷键 | 功能 |
| --- | --- |
| `E` | 进入或退出 OBB 绘制 |
| `Ctrl+S` | 保存当前标签 |
| `A / D` | 上一张 / 下一张 |
| `左 / 右方向键` | 上一张 / 下一张 |
| `Ctrl+C / Ctrl+V` | 复制 / 粘贴选中框 |
| `Ctrl+D` | 直接复制选中框 |
| `Delete` | 删除全部选中框 |
| `Alt + 左键拖动` | 平移画布 |
| `Ctrl+R` | 打开标签读取与保存目录 |
| `Ctrl+Shift+L` | 显示或隐藏框上的标签文字 |

## 标签目录匹配示例

选择 `images` 作为图片根目录、`labels` 作为标签根目录后：

```text
images/site_a/day/001.jpg
```

会自动对应：

```text
labels/site_a/day/001.xml
labels/site_a/day/001.txt
```

## 许可证与项目来源

本项目遵循 [MIT License](LICENSE)。原项目版权声明和许可证均被保留。

- 原项目：<https://github.com/chinakook/labelImg2>
- 中文来源说明：[NOTICE_zh-CN.md](NOTICE_zh-CN.md)
- 修改功能清单：[MODIFICATIONS_zh-CN.md](MODIFICATIONS_zh-CN.md)

本仓库是独立维护的修改版，不代表上游项目的官方发布。

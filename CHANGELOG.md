# 更新日志

本项目从 `v1.3.0` 开始记录自定义版本。`v1.0`、`v1.1` 和 `v1.2`
是仓库继承的上游历史标签，不包含当前完整的自定义功能。

## [v2.0.0] - 2026-08-11

### 新增：本地模型自动标注

- 工具栏和 `File` 菜单增加“自动标注”。
- 支持加载本地 Ultralytics YOLO 检测或 YOLO OBB `.pt` 模型。
- 模型在后台线程逐张推理，界面状态栏显示文件名、框数量和总体进度。
- 状态栏提供“中止”按钮；中止请求会在当前图片推理完成后生效。
- 自动识别模型任务：普通检测模型保存为 5 列 YOLO，OBB 模型自动切换并保存为
  9 列 YOLO OBB。
- 使用模糊匹配把模型类别映射到项目类别预设，例如 `apple -> apples`、
  `org -> oranges_`、`melon -> name_melon`。
- 完成窗口显示模型类别到项目类别的映射和相似度，方便人工复核。
- 自动标注保留图片目录的相对子目录结构，并写入当前 `Open Annotation Dir`。
- 已存在 XML 或 TXT 标签的图片自动跳过，不覆盖人工标注。
- `.pt` 文件加入 Git 忽略列表；仓库和发行源码包不包含任何第三方模型权重。
- 增加 `ultralytics>=8.3` 运行依赖；未安装时不影响手工标注界面启动。

### 验证

- 通过类别模糊匹配、YOLO OBB 四点坐标转换、后台批量保存、标签重新载入、
  已有标签保护和中止流程测试。
- 通过 Python 语法编译及 Conda 启动器检查。

## [v1.5.0] - 2026-08-10

- 重写 Windows 启动器，支持项目 `.venv`、名为 `labelimg2` 的 Conda 环境和
  当前激活的 Conda 环境。
- 增加 `--venv`、`--conda` 和 `--check` 参数，各环境互不回退和污染。
- 移除对 Windows `py/pyw` 注册表启动路径的依赖。
- 完善中文小白安装教程和首次运行检查。

## [v1.4.0] - 2026-08-10

- 支持直接选择保存 Pascal VOC XML、普通 YOLO 或 YOLO OBB。
- 合并标签读取和保存目录入口为 `Open Annotation Dir`。
- 自动识别 5 列 YOLO 与 9 列 YOLO OBB TXT。
- 支持图片和标签按相同子目录结构递归匹配。
- XML 导出只转换同名 TXT，不复制图片、不划分数据集、不生成 YAML。

## [v1.3.0] - 2026-08-09

- 建立以 OBB 为主的快捷标注流程。
- 增加绘制状态切换、画完自动选择类别、常用类别优先、角度快捷键等功能。
- 增加框复制粘贴、多选、集体移动、滚轮缩放框和跨图片原位置粘贴。
- 增加自然数字排序、目录与标注进度恢复。

## 历史上游标签

- `v1.2`：上游历史版本。
- `v1.1`：上游历史版本。
- `v1.0`：上游历史版本。

[v2.0.0]: https://github.com/auto-sun/labelImg2-custom/releases/tag/v2.0.0
[v1.5.0]: https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.5.0.zip
[v1.4.0]: https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.4.0.zip
[v1.3.0]: https://github.com/auto-sun/labelImg2-custom/archive/refs/tags/v1.3.0.zip

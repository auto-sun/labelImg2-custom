# 项目来源与版权归属说明

本仓库是
[chinakook/labelImg2](https://github.com/chinakook/labelImg2) 的修改版 Fork。

原项目使用 MIT License 发布。原作者版权声明和完整许可证内容已原样保留在
[`LICENSE`](LICENSE) 中。

本 Fork 的修改范围主要包括：

- OBB 标注操作流程；
- 鼠标和键盘交互；
- 多框选择与批量操作；
- 跨图片复制粘贴；
- 标注进度和设置恢复；
- XML 到 YOLO/YOLO OBB 标签转换；
- 使用本地 YOLO/YOLO OBB 模型进行自动标注。

详细功能变化见 [`MODIFICATIONS_zh-CN.md`](MODIFICATIONS_zh-CN.md)。

自动标注功能调用由用户另外安装的第三方
[Ultralytics](https://github.com/ultralytics/ultralytics) 软件包。本机所安装版本的
包元数据将其许可证标为 AGPL-3.0。仓库没有复制 Ultralytics 源码；使用者应自行阅读
并遵守其许可证，或根据实际用途取得适当的商业许可。

本仓库及发行版源码压缩包均不包含任何模型权重。使用者应确保加载的 `.pt` 模型是
自行训练或已获得合法授权；第三方依赖和模型权重仍分别受其自身许可证约束。

本仓库不是上游项目的官方版本，也不表示原作者认可、维护或为本修改版提供担保。

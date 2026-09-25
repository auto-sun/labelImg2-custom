# Windows 安装包

`LabelImg2Custom-版本号-Setup.exe` 是适用于 64 位 Windows 的自包含安装包。
安装后从开始菜单启动，无需目标电脑安装 Python、Conda、PyQt5、PyTorch 或 Ultralytics。
安装包使用 CPU 版 PyTorch；本项目不分发用户的 `.pt` 模型权重，自动标注时需自行选择。

安装程序默认安装到当前用户的 `%LOCALAPPDATA%\Programs\LabelImg2 Custom`，
无需管理员权限。个人设置保存在 `%APPDATA%\LabelImg2Custom`，更新或卸载程序不会删除数据集或标签。
因为尚未提供代码签名，Windows SmartScreen 可能提示未知发布者；请先确认安装包来源。

## 开发者说明

Windows 打包脚本是 `build_windows.ps1`，安装向导定义为 `LabelImg2Custom.iss`。
简体中文 Inno Setup 语言文件的来源及维护者信息保留在
`ChineseSimplified.isl` 文件头部。普通用户只需下载安装包，不需要运行这些脚本。

打包必须使用一个独立、完整的 Python 环境（当前使用 Python 3.10.20），
不要通过 `PYTHONPATH` 混用另一个环境的 PyInstaller 或项目依赖。
脚本会检查主要依赖是否都来自同一个 `sys.prefix`，并在生成安装器前实际启动
打包后的 EXE，确认主窗口出现且没有“Unhandled exception”报错窗口。

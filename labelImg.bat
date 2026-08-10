@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "labelImg.py" %*
    exit /b 0
)

where pyw >nul 2>&1
if not errorlevel 1 (
    start "" pyw -3 "labelImg.py" %*
    exit /b 0
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "labelImg.py" %*
    exit /b 0
)

echo LabelImg2 could not find Python.
echo Run the installation commands in FIRST_USE_GUIDE_zh-CN.md first.
pause
exit /b 1

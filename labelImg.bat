@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "LABELIMG2_MODE=auto"
set "LABELIMG2_CHECK_ONLY=0"
set "LABELIMG2_CONDA_ENV=labelimg2"

:parse_options
if /I "%~1"=="--venv" (
    set "LABELIMG2_MODE=venv"
    shift
    goto parse_options
)
if /I "%~1"=="--conda" (
    set "LABELIMG2_MODE=conda"
    shift
    goto parse_options
)
if /I "%~1"=="--check" (
    set "LABELIMG2_CHECK_ONLY=1"
    shift
    goto parse_options
)
if /I "%~1"=="--help" goto show_help

if /I "%LABELIMG2_MODE%"=="venv" goto force_venv
if /I "%LABELIMG2_MODE%"=="conda" goto force_conda

rem Auto mode:
rem 1. The project-local .venv.
rem 2. A Conda environment named "labelimg2".
rem 3. A currently activated and usable Conda environment.
if exist "%~dp0.venv\Scripts\python.exe" if exist "%~dp0.venv\Scripts\pythonw.exe" (
    call :python_ready "%~dp0.venv\Scripts\python.exe"
    if not errorlevel 1 (
        set "LABELIMG2_SELECTED=project virtual environment: %~dp0.venv"
        set "LABELIMG2_PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
        goto launch_pythonw
    )
)

call :find_named_conda
if defined LABELIMG2_CONDA_PATH (
    call :python_ready "%LABELIMG2_CONDA_PATH%\python.exe"
    if not errorlevel 1 goto launch_named_conda
)

if defined CONDA_PREFIX (
    if exist "%CONDA_PREFIX%\python.exe" if exist "%CONDA_PREFIX%\pythonw.exe" (
        call :python_ready "%CONDA_PREFIX%\python.exe"
        if not errorlevel 1 (
            set "LABELIMG2_SELECTED=active Conda environment: %CONDA_PREFIX%"
            set "LABELIMG2_PYTHONW=%CONDA_PREFIX%\pythonw.exe"
            goto launch_pythonw
        )
    )
)

echo [LabelImg2] No usable Python environment was found.
echo.
echo Tried:
echo   1. "%~dp0.venv"
echo   2. Conda environment "%LABELIMG2_CONDA_ENV%"
echo   3. The currently activated Conda environment
echo.
echo Run FIRST_USE_GUIDE_zh-CN.md, or use:
echo   labelImg.bat --venv
echo   labelImg.bat --conda
if "%LABELIMG2_CHECK_ONLY%"=="0" pause
exit /b 1

:force_venv
if not exist "%~dp0.venv\Scripts\python.exe" goto venv_missing
if not exist "%~dp0.venv\Scripts\pythonw.exe" goto venv_missing
call :python_ready "%~dp0.venv\Scripts\python.exe"
if errorlevel 1 goto venv_dependencies_missing
set "LABELIMG2_SELECTED=project virtual environment: %~dp0.venv"
set "LABELIMG2_PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
goto launch_pythonw

:force_conda
call :find_named_conda
if not defined LABELIMG2_CONDA_PATH goto conda_missing
call :python_ready "%LABELIMG2_CONDA_PATH%\python.exe"
if errorlevel 1 goto conda_dependencies_missing
goto launch_named_conda

:launch_pythonw
echo [LabelImg2] Using %LABELIMG2_SELECTED%
if "%LABELIMG2_CHECK_ONLY%"=="1" exit /b 0
start "" "%LABELIMG2_PYTHONW%" "%~dp0labelImg.py" %*
exit /b 0

:launch_named_conda
echo [LabelImg2] Using Conda environment "%LABELIMG2_CONDA_ENV%": %LABELIMG2_CONDA_PATH%
if "%LABELIMG2_CHECK_ONLY%"=="1" exit /b 0
start "" "%LABELIMG2_CONDA_PATH%\pythonw.exe" "%~dp0labelImg.py" %*
exit /b 0

:python_ready
"%~1" -c "import PyQt5, lxml, cv2, yaml; import labelImg" >nul 2>&1
exit /b %errorlevel%

:find_named_conda
set "LABELIMG2_CONDA_PATH="
set "LABELIMG2_CONDA_EXE="
for /f "delims=" %%I in ('where conda.exe 2^>nul') do (
    if not defined LABELIMG2_CONDA_EXE set "LABELIMG2_CONDA_EXE=%%I"
)
if defined LABELIMG2_CONDA_EXE (
    for %%I in ("%LABELIMG2_CONDA_EXE%") do set "LABELIMG2_CONDA_SCRIPTS=%%~dpI"
    call :resolve_conda_base
)
if not defined LABELIMG2_CONDA_PATH if exist "%USERPROFILE%\.conda\envs\%LABELIMG2_CONDA_ENV%\python.exe" (
    set "LABELIMG2_CONDA_PATH=%USERPROFILE%\.conda\envs\%LABELIMG2_CONDA_ENV%"
)
if not defined LABELIMG2_CONDA_PATH if exist "%LOCALAPPDATA%\conda\conda\envs\%LABELIMG2_CONDA_ENV%\python.exe" (
    set "LABELIMG2_CONDA_PATH=%LOCALAPPDATA%\conda\conda\envs\%LABELIMG2_CONDA_ENV%"
)
exit /b 0

:resolve_conda_base
for %%I in ("%LABELIMG2_CONDA_SCRIPTS%..") do set "LABELIMG2_CONDA_BASE=%%~fI"
if exist "%LABELIMG2_CONDA_BASE%\envs\%LABELIMG2_CONDA_ENV%\python.exe" (
    set "LABELIMG2_CONDA_PATH=%LABELIMG2_CONDA_BASE%\envs\%LABELIMG2_CONDA_ENV%"
)
exit /b 0

:venv_missing
echo [LabelImg2] Project virtual environment was not found:
echo   "%~dp0.venv"
echo Create it by following FIRST_USE_GUIDE_zh-CN.md.
if "%LABELIMG2_CHECK_ONLY%"=="0" pause
exit /b 1

:venv_dependencies_missing
echo [LabelImg2] The project .venv exists, but required packages are missing.
echo Run:
echo   "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if "%LABELIMG2_CHECK_ONLY%"=="0" pause
exit /b 1

:conda_missing
echo [LabelImg2] Conda environment "%LABELIMG2_CONDA_ENV%" was not found.
echo Create that environment, or use a project .venv.
if "%LABELIMG2_CHECK_ONLY%"=="0" pause
exit /b 1

:conda_dependencies_missing
echo [LabelImg2] Conda environment "%LABELIMG2_CONDA_ENV%" was not found or is missing dependencies.
echo In Anaconda Prompt, run:
echo   conda activate %LABELIMG2_CONDA_ENV%
echo   pip install -r "%~dp0requirements.txt"
if "%LABELIMG2_CHECK_ONLY%"=="0" pause
exit /b 1

:show_help
echo LabelImg2 launcher
echo.
echo   labelImg.bat             Automatically select a usable environment
echo   labelImg.bat --venv     Force the project .venv
echo   labelImg.bat --conda    Force Conda environment "%LABELIMG2_CONDA_ENV%"
echo   labelImg.bat --check    Show the selected environment without launching
echo.
echo Options can be combined, for example:
echo   labelImg.bat --check --conda
exit /b 0

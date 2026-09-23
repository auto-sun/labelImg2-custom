param(
    [string]$PythonExe = 'python',
    [string]$InnoCompiler = ''
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:YOLO_AUTOINSTALL = 'false'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot

if (-not $InnoCompiler) {
    $compilerCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )
    $InnoCompiler = $compilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}
if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
    throw 'Inno Setup 6 compiler (ISCC.exe) was not found.'
}

& $PythonExe -c 'import sys; sys.exit(1 if sys.version_info[:3] == (3, 10, 0) else 0)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10.0 is not supported by this PyInstaller build; use Python 3.10.20 or a newer compatible release.'
}

& $PythonExe -c 'import PyInstaller, PyQt5, cv2, lxml, ultralytics, torch, pypinyin, send2trash, yamlloader'
if ($LASTEXITCODE -ne 0) {
    throw 'The build Python environment is missing a required dependency.'
}

$iconPath = Join-Path $projectRoot 'build\LabelImg2Custom.ico'
& $PythonExe (Join-Path $projectRoot 'packaging\create_icon.py') $iconPath
if ($LASTEXITCODE -ne 0) {
    throw 'Could not generate the application icon.'
}

& $PythonExe -m PyInstaller --noconfirm `
    --distpath (Join-Path $projectRoot 'dist') `
    --workpath (Join-Path $projectRoot 'build\pyinstaller') `
    (Join-Path $projectRoot 'packaging\LabelImg2Custom.spec')
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller failed.'
}

$appVersion = & $PythonExe -c 'from libs.version import __version__; print(__version__)'
if ($LASTEXITCODE -ne 0 -or -not $appVersion) {
    throw 'Could not read the application version.'
}

& $InnoCompiler "/DAppVersion=$appVersion" `
    (Join-Path $projectRoot 'packaging\LabelImg2Custom.iss')
if ($LASTEXITCODE -ne 0) {
    throw 'Inno Setup compilation failed.'
}

$installerPath = Join-Path $projectRoot (
    "dist\installer\LabelImg2Custom-$appVersion-Setup.exe")
if (-not (Test-Path -LiteralPath $installerPath)) {
    throw 'The installer was not created at the expected path.'
}
Write-Output "Installer ready: $installerPath"

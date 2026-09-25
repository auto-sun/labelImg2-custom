param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Packaged executable not found: $ExePath"
}

# Use isolated settings so the test never opens or changes the user's dataset.
$testAppData = Join-Path $env:TEMP (
    'LabelImg2Custom-smoke-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testAppData | Out-Null
$previousAppData = $env:APPDATA
$previousPythonPath = $env:PYTHONPATH
$env:APPDATA = $testAppData
$env:PYTHONPATH = $null
$process = $null
try {
    $process = Start-Process -FilePath $ExePath `
        -WorkingDirectory (Split-Path -Parent $ExePath) `
        -WindowStyle Hidden -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $healthy = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $process.Refresh()
        if ($process.HasExited) {
            throw "Packaged application exited early: $($process.ExitCode)"
        }
        $title = $process.MainWindowTitle
        if ($title -match 'Unhandled exception|Failed to execute|Traceback') {
            throw "Packaged application opened an error dialog: $title"
        }
        if ($title -match 'labelImg2') {
            $healthy = $true
            break
        }
    }
    if (-not $healthy) {
        throw 'Packaged application did not open its main window in 30 seconds.'
    }
    Write-Output "Startup smoke test passed: $($process.MainWindowTitle)"
}
finally {
    if ($process -and -not $process.HasExited) {
        $process.CloseMainWindow() | Out-Null
        if (-not $process.WaitForExit(5000)) {
            Stop-Process -Id $process.Id -Force
        }
    }
    $env:APPDATA = $previousAppData
    $env:PYTHONPATH = $previousPythonPath
}

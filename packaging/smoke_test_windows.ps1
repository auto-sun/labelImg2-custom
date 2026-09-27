param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Packaged executable not found: $ExePath"
}

Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class LabelImg2WindowProbe {
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    public static string[] GetVisibleTitlesForProcess(int targetProcessId) {
        var titles = new List<string>();
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
            uint processId;
            GetWindowThreadProcessId(hWnd, out processId);
            if (processId == (uint)targetProcessId && IsWindowVisible(hWnd)) {
                var text = new StringBuilder(1024);
                GetWindowText(hWnd, text, text.Capacity);
                if (text.Length > 0) titles.Add(text.ToString());
            }
            return true;
        }, IntPtr.Zero);
        return titles.ToArray();
    }
}
'@

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
        $titles = [LabelImg2WindowProbe]::GetVisibleTitlesForProcess($process.Id)
        $title = $titles -join ' | '
        if ($title -match 'Unhandled exception|Failed to execute|Traceback') {
            throw "Packaged application opened an error dialog: $title"
        }
        if ($title -match '(?i)labelImg2') {
            $healthy = $true
            break
        }
    }
    if (-not $healthy) {
        throw 'Packaged application did not open its main window in 30 seconds.'
    }
    Write-Output "Startup smoke test passed: $title"
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

# Run by Setup before replacing any application files.
# Exit codes: 0 ready, 10 the GUI did not close, 11 MCP locked/restarted, 12 unable to verify.
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [ValidateRange(1, 45)][int]$CloseWaitSeconds = 20
)

$ErrorActionPreference = 'Stop'

function Get-InstalledProcesses([string]$Name) {
    $expected = Join-Path $root "$Name.exe"
    foreach ($process in (Get-Process -Name $Name -ErrorAction SilentlyContinue)) {
        $path = $process.Path
        if (-not $path -and -not $process.HasExited) {
            # Path may be unavailable via Get-Process when Setup's host has a
            # different bitness. Do not act on the image name alone.
            $record = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
            $path = $record.ExecutablePath
        }
        if (-not $path) {
            if (-not $process.HasExited) {
                throw "Cannot verify executable path of $Name (PID $($process.Id))."
            }
            continue
        }
        if ([string]::Equals([IO.Path]::GetFullPath($path), $expected,
                             [StringComparison]::OrdinalIgnoreCase)) {
            $process
        }
    }
}

try {
    $root = [IO.Path]::GetFullPath($InstallDir)
    $sentClose = @{}
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $gui = @(Get-InstalledProcesses 'LabelImg2Custom')
        if ($gui.Count -eq 0) { break }
        if ($timer.Elapsed.TotalSeconds -ge $CloseWaitSeconds) { exit 10 }
        foreach ($process in $gui) {
            if (-not $process.HasExited -and -not $sentClose.ContainsKey($process.Id)) {
                # Let the main application run its normal save/cancel flow.
                # A disabled/modal window can refuse CloseMainWindow.
                if ($process.CloseMainWindow()) { $sentClose[$process.Id] = $true }
            }
        }
        Start-Sleep -Milliseconds 200
    }

    # The MCP bridge is a console stdio client. It has no save or close
    # dialog of its own, and the GUI that writes labels is now shut down.
    $bridges = @(Get-InstalledProcesses 'LabelImg2MCP')
    foreach ($process in $bridges) {
        if (@(Get-InstalledProcesses 'LabelImg2Custom').Count -ne 0) { exit 10 }
        if (-not $process.HasExited) {
            try {
                $process.Kill()
                if (-not $process.WaitForExit(4000)) { exit 11 }
            } catch {
                if (-not $process.HasExited) { exit 11 }
            }
        }
    }
    if ($bridges.Count -gt 0) { Start-Sleep -Milliseconds 850 }
    if (@(Get-InstalledProcesses 'LabelImg2Custom').Count -ne 0) { exit 10 }
    # A client may automatically start the bridge again. Do not keep killing
    # it or replace files while it is still connected.
    if (@(Get-InstalledProcesses 'LabelImg2MCP').Count -ne 0) { exit 11 }
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 12
}

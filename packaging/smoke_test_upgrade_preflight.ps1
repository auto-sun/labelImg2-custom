# Exercise installer process matching without touching a real installation.
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot 'prepare_upgrade.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$cmd = Join-Path $env:SystemRoot 'System32\cmd.exe'
$root = New-Item -ItemType Directory -Path (
    Join-Path $env:TEMP ("LabelImg2 upgrade smoke " + [Guid]::NewGuid().ToString('N')))
$target = New-Item -ItemType Directory -Path (Join-Path $root.FullName 'test install')
$other = New-Item -ItemType Directory -Path (Join-Path $root.FullName 'other install')
$children = @()
$files = @(
    (Join-Path $target.FullName 'LabelImg2MCP.exe'),
    (Join-Path $other.FullName 'LabelImg2MCP.exe'),
    (Join-Path $target.FullName 'LabelImg2Custom.exe')
)

function Start-FixtureProcess([string]$File) {
    Copy-Item -LiteralPath $cmd -Destination $File
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $File
    $info.Arguments = '/D /Q /K'
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.CreateNoWindow = $true
    [Diagnostics.Process]::Start($info)
}

function Invoke-Preflight {
    $arguments = @('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',$helper,'-InstallDir',(Join-Path $target.FullName '.'),'-CloseWaitSeconds','1')
    & $powershell @arguments
    $LASTEXITCODE
}

try {
    $bridge = Start-FixtureProcess $files[0]
    $children += $bridge
    $unrelated = Start-FixtureProcess $files[1]
    $children += $unrelated
    # A process without a closable window models a GUI that does not
    # cooperate with CloseMainWindow. It must never be killed by Setup.
    $gui = Start-FixtureProcess $files[2]
    $children += $gui
    if ((Invoke-Preflight) -ne 10 -or $gui.HasExited -or $bridge.HasExited) {
        throw 'Preflight did not leave an unclosed GUI and its bridge alone.'
    }

    $gui.Kill()
    if (-not $gui.WaitForExit(5000)) { throw 'Could not close the fixture.' }
    if ((Invoke-Preflight) -ne 0 -or -not $bridge.HasExited -or $unrelated.HasExited) {
        throw 'Preflight did not stop only the same-installation bridge.'
    }
    Write-Output 'Upgrade preflight smoke test passed: no forced GUI close and exact-path MCP cleanup.'
} finally {
    foreach ($child in $children) {
        if (-not $child.HasExited) {
            $child.Kill()
            [void]$child.WaitForExit(5000)
        }
        $child.Dispose()
    }
    foreach ($file in $files) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
    Remove-Item -LiteralPath $target.FullName
    Remove-Item -LiteralPath $other.FullName
    Remove-Item -LiteralPath $root.FullName
}

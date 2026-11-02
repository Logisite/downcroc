param(
    [string]$Wheel = "",
    [string]$Version = "1.2.2",
    [string]$Prefix = "$env:LOCALAPPDATA\downcroc",
    [switch]$NoInit
)

$ErrorActionPreference = "Stop"
if ($Version -notmatch "^[0-9A-Za-z.+_-]+$") {
    Write-Error "invalid version: $Version"
    exit 2
}
$ReleaseWheel = "https://github.com/Logisite/downcroc/releases/download/v$Version/downcroc-$Version-py3-none-any.whl"

function Find-Python {
    foreach ($candidate in @("py -3.14", "python3.14", "python3", "python")) {
        $parts = $candidate.Split(" ")
        $command = Get-Command $parts[0] -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        $arguments = @()
        if ($parts.Length -gt 1) { $arguments += $parts[1..($parts.Length - 1)] }
        $arguments += @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)")
        & $command.Source @args 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Command = $command.Source; Args = $parts[1..($parts.Length - 1)] }
        }
    }
    return $null
}

$python = Find-Python
if ($null -eq $python) {
    Write-Error "Python 3.14 or newer is required"
    exit 1
}

if ($Wheel -ne "" -and -not (Test-Path $Wheel)) {
    Write-Error "wheel not found: $Wheel"
    exit 1
}

New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
$Prefix = (Resolve-Path $Prefix).Path
$Venv = Join-Path $Prefix "venv"
$Bin = Join-Path $Prefix "bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

& $python.Command @($python.Args) -m venv $Venv
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvDowncroc = Join-Path $Venv "Scripts\downcroc.exe"

if ($Wheel -ne "") {
    & $VenvPython -m pip install --upgrade $Wheel
} else {
    $Source = if ($env:DOWNCROC_WHEEL_URL) { $env:DOWNCROC_WHEEL_URL } else { $ReleaseWheel }
    & $VenvPython -m pip install --upgrade $Source
}

$Launcher = Join-Path $Bin "downcroc.cmd"
"@echo off`r`n`"$VenvDowncroc`" %*" | Set-Content -Encoding Ascii $Launcher

Write-Host ""
& $VenvDowncroc --version
Write-Host "installed  $Launcher"

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if (($UserPath -split ";") -notcontains $Bin) {
    Write-Host "add to PATH: $Bin"
}

if (-not $NoInit) {
    Write-Host "next: downcroc init"
}

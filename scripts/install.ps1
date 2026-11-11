param(
    [string]$Wheel = "",
    [string]$Version = "",
    [string]$Prefix = "$env:LOCALAPPDATA\downcroc",
    [switch]$NoInit
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

if ($Version -eq "" -and $Wheel -eq "" -and -not $env:DOWNCROC_WHEEL_URL) {
    try {
        $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/Logisite/downcroc/releases/latest" -Headers @{ "User-Agent" = "downcroc-installer" }
        $Version = $latest.tag_name.TrimStart("v")
    } catch {
        Write-Error "could not resolve the latest release"
        exit 1
    }
}
if ($Version -ne "" -and $Version -notmatch "^[0-9A-Za-z.+_-]+$") {
    Write-Error "invalid version: $Version"
    exit 2
}
$ReleaseWheel = "https://github.com/Logisite/downcroc/releases/download/v$Version/downcroc-$Version-py3-none-any.whl"

function Find-Python {
    foreach ($candidate in @("py -3.14", "py -3", "python3.14", "python3", "python")) {
        $parts = $candidate.Split(" ")
        $command = Get-Command $parts[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $command) { continue }
        $launcherArgs = @()
        if ($parts.Length -gt 1) { $launcherArgs = @($parts[1..($parts.Length - 1)]) }
        $probeArgs = $launcherArgs + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)")
        & $command.Source @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Command = $command.Source; Args = $launcherArgs }
        }
    }
    return $null
}

function Update-SessionPath {
    $env:PATH = @(
        $env:PATH
        [Environment]::GetEnvironmentVariable("PATH", "Machine")
        [Environment]::GetEnvironmentVariable("PATH", "User")
    ) -join ";"
}

function Install-LatestPython {
    $winget = Get-Command winget -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $winget) {
        Write-Host "installing Python with winget..."
        try {
            & $winget.Source install --id Python.Python.3 --source winget --silent --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -eq 0) {
                Update-SessionPath
                if ($null -ne (Find-Python)) { return }
                Write-Warning "winget installed Python, but no 3.14+ interpreter was found; trying python.org"
            }
        } catch {
            Write-Warning "winget failed: $($_.Exception.Message)"
        }
        Write-Warning "winget could not install Python; trying python.org"
    }

    $index = (Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/" -TimeoutSec 30).Content
    $version = [regex]::Matches($index, 'href="(?<version>\d+\.\d+\.\d+)/"') |
        ForEach-Object { $_.Groups["version"].Value } |
        Sort-Object { [version]$_ } -Descending |
        Select-Object -First 1
    if (-not $version) { throw "could not resolve the latest Python release" }

    $machine = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    $arch = if ($machine -eq "ARM64") { "arm64" } elseif ($machine -eq "x86") { "" } else { "amd64" }
    $name = if ($arch) { "python-$version-$arch.exe" } else { "python-$version.exe" }
    $url = "https://www.python.org/ftp/python/$version/$name"
    $installer = Join-Path $env:TEMP $name

    Write-Host "installing Python $version from python.org..."
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $installer
    Unblock-File -Path $installer -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1"
    )
    Remove-Item $installer -Force -ErrorAction SilentlyContinue
    if ($process.ExitCode -notin @(0, 3010, 1638)) {
        throw "Python installer exited with $($process.ExitCode)"
    }
}

Write-Host "checking for Python 3.14 or newer..."
$python = Find-Python
if ($null -eq $python) {
    Install-LatestPython
    Update-SessionPath
    $python = Find-Python
}
if ($null -eq $python) {
    Write-Error "Python 3.14 or newer is required; open a new terminal and run the installer again"
    exit 1
}
Write-Host "using $((@($python.Command) + @($python.Args)) -join ' ')"

if ($Wheel -ne "" -and -not (Test-Path $Wheel)) {
    Write-Error "wheel not found: $Wheel"
    exit 1
}

New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
$Prefix = (Resolve-Path $Prefix).Path
$Venv = Join-Path $Prefix "venv"
$Bin = Join-Path $Prefix "bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

Write-Host "creating the virtual environment..."
$venvArgs = @($python.Args) + @("-m", "venv", $Venv)
& $python.Command @venvArgs
if ($LASTEXITCODE -ne 0) { throw "could not create the virtual environment at $Venv" }
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvDowncroc = Join-Path $Venv "Scripts\downcroc.exe"

Write-Host "installing downcroc..."
if ($Wheel -ne "") {
    & $VenvPython -m pip install --upgrade $Wheel
} else {
    $Source = if ($env:DOWNCROC_WHEEL_URL) { $env:DOWNCROC_WHEEL_URL } else { $ReleaseWheel }
    & $VenvPython -m pip install --upgrade $Source
}
if ($LASTEXITCODE -ne 0) { throw "the downcroc wheel could not be installed" }

$Launcher = Join-Path $Bin "downcroc.cmd"
"@echo off`r`n`"%~dp0..\venv\Scripts\downcroc.exe`" %*" | Set-Content -Encoding Ascii $Launcher

Write-Host ""
& $VenvDowncroc --version
if ($LASTEXITCODE -ne 0) { throw "downcroc was installed but could not run" }
Write-Host "installed  $Launcher"

Write-Host "checking PATH..."
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$PersistentPath = @((@($UserPath, $MachinePath) -join ";") -split ";" | Where-Object { $_ -ne "" })
$BinKey = $Bin.TrimEnd("\")
$OnPersistentPath = $PersistentPath | Where-Object { $_.TrimEnd("\") -eq $BinKey }
if (-not $OnPersistentPath) {
    $NewUserPath = ((@($UserPath -split ";" | Where-Object { $_ -ne "" }) + $Bin) -join ";")
    [Environment]::SetEnvironmentVariable("PATH", $NewUserPath, "User")
    Write-Host "added to PATH: $Bin"
} else {
    Write-Host "already on PATH: $Bin"
}
$OnSessionPath = ($env:PATH -split ";") | Where-Object { $_.TrimEnd("\") -eq $BinKey }
if (-not $OnSessionPath) {
    $env:PATH = "$env:PATH;$Bin"
}

if (-not $NoInit) {
    Write-Host "next: downcroc init"
}

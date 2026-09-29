$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

$distDir = Join-Path $root "dist"
if (Test-Path $distDir) {
    $packaged = Get-ChildItem -Path $distDir -Recurse -Filter "*.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "_internal" } |
        Select-Object -First 1
    if ($packaged) {
        Write-Step "正在启动已打包程序: $($packaged.Name)"
        Start-Process -FilePath $packaged.FullName
        exit 0
    }
}

function Get-PythonLauncher {
    $candidates = @()
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $candidates += ,@($python.Source, @())
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $candidates += ,@($py.Source, @("-3"))
    }
    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $localPython) {
        Get-ChildItem -Path $localPython -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName |
            ForEach-Object { $candidates += ,@($_, @()) }
    }
    foreach ($candidate in $candidates) {
        $launcher = $candidate[0]
        $argsList = $candidate[1]
        if (-not (Test-Path $launcher)) {
            continue
        }
        & $launcher @argsList -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Launcher = $launcher; Args = $argsList }
        }
    }
    return $null
}

$launcherInfo = Get-PythonLauncher
if (-not $launcherInfo) {
    Write-Step "未检测到 Python，尝试使用 winget 自动安装 Python 3.12..."
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        & $winget.Source install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
        $launcherInfo = Get-PythonLauncher
    }
}
if (-not $launcherInfo) {
    Write-Host ""
    Write-Host "未检测到 Python 3.10+，且自动安装失败。"
    Write-Host "请从 https://www.python.org/downloads/ 安装，或使用已打包的发布版本。"
    exit 1
}

$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Step "正在创建虚拟环境..."
    $launcherArgs = @($launcherInfo.Args)
    & $launcherInfo.Launcher @launcherArgs -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "虚拟环境创建失败。"
        exit 1
    }
}

$requirements = Join-Path $root "requirements.txt"
if (-not (Test-Path $requirements)) {
    Write-Host "requirements.txt 不存在。"
    exit 1
}

Write-Step "正在安装/检查 Python 依赖..."
& $venvPython -m pip install --disable-pip-version-check -r $requirements
if ($LASTEXITCODE -ne 0) {
    Write-Host "依赖安装失败。"
    exit 1
}

$modelConfig = Join-Path $root "data\models\bge-small-zh-v1.5\config.json"
if (-not (Test-Path $modelConfig)) {
    Write-Step "正在下载本地嵌入模型..."
    & $venvPython (Join-Path $root "scripts\download_models.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "模型下载失败；应用仍会启动，后续可重新下载。"
    }
}

Write-Step "正在启动应用..."
& $venvPython (Join-Path $root "main.py")
exit $LASTEXITCODE
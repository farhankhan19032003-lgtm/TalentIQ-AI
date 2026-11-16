# Starts the TalentIQ AI backend (port 8000) and frontend (port 5173).
#   .\start.ps1            start both and open the browser
#   .\start.ps1 -NoBrowser start both without opening the browser
#   .\start.ps1 -Stop      stop both
param(
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$logs = Join-Path $env:TEMP "talentiq"
New-Item -ItemType Directory -Path $logs -Force | Out-Null

function Stop-Port([int]$port) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "port ${port}: nothing listening"; return }
    foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        Write-Host "port ${port}: stopping $($p.ProcessName) (pid $procId)"
        Stop-Process -Id $procId -Force
    }
}

function Wait-Url([string]$url, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true } catch { Start-Sleep -Milliseconds 700 }
    }
    return $false
}

if ($Stop) {
    Stop-Port 8000
    Stop-Port 5173
    return
}

# Prerequisites -------------------------------------------------------------------------
if (-not (Test-Path $python)) {
    throw "Backend venv not found at $python. Run: cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
$nodeDir = "C:\Program Files\nodejs"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    if (Test-Path "$nodeDir\npm.cmd") { $env:Path = "$nodeDir;$env:Path" } else { throw "Node.js not found. Install it first (winget install OpenJS.NodeJS.LTS)." }
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    throw "Frontend dependencies missing. Run: cd frontend; npm install"
}
foreach ($port in 8000, 5173) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Run .\start.ps1 -Stop first."
    }
}

# Environment ---------------------------------------------------------------------------
# Windows Application Control blocks SQLAlchemy's compiled extension on this machine.
$env:DISABLE_SQLALCHEMY_CEXT_RUNTIME = "1"
# Tesseract (OCR for scanned PDFs), if installed.
$tess = "C:\Program Files\Tesseract-OCR"
if (Test-Path "$tess\tesseract.exe") { $env:Path = "$tess;$env:Path" }
# TF-IDF is the default similarity method; uncomment to force or change it.
# $env:EMBEDDING_BACKEND = "tfidf"

# Start ---------------------------------------------------------------------------------
Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
    -WorkingDirectory $backend -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs "backend.out") -RedirectStandardError (Join-Path $logs "backend.err")
Start-Process -FilePath (Get-Command npm.cmd).Source -ArgumentList "run", "dev" `
    -WorkingDirectory $frontend -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs "frontend.out") -RedirectStandardError (Join-Path $logs "frontend.err")

$beOk = Wait-Url "http://localhost:8000/api/docs" 40
$feOk = Wait-Url "http://localhost:5173" 40
Write-Host ("Backend : " + $(if ($beOk) { "http://localhost:8000  (API docs: /api/docs)" } else { "NOT responding, see $logs\backend.err" }))
Write-Host ("Frontend: " + $(if ($feOk) { "http://localhost:5173" } else { "NOT responding, see $logs\frontend.err" }))
Write-Host "Stop with: .\start.ps1 -Stop"

if ($feOk -and -not $NoBrowser) { Start-Process "http://localhost:5173" }

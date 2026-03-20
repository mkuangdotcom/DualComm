param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
if (-not $repoRoot) {
    $repoRoot = (Get-Location).Path
}

Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Error "Python virtual environment not found at '$pythonExe'. Create it first with: python -m venv ..\.venv"
}

if (-not (Test-Path (Join-Path $repoRoot "node_modules"))) {
    Write-Error "node_modules not found. Run 'npm install' first."
}

$pythonArgs = @(
    "-m", "uvicorn",
    "app.main:app",
    "--app-dir", "python_bridge",
    "--host", $HostAddress,
    "--port", $Port,
    "--reload"
)

Write-Host "Starting Python bridge on http://127.0.0.1:$Port ..."
$pythonProcess = Start-Process -FilePath $pythonExe -ArgumentList $pythonArgs -WorkingDirectory $repoRoot -PassThru

Start-Sleep -Seconds 2
if ($pythonProcess.HasExited) {
    Write-Error "Python bridge exited early. Check your Python dependencies and .env."
}

Write-Host "Starting Node bridge ..."

try {
    $env:PYTHON_AGENT_BASE_URL = "http://127.0.0.1:$Port"
    Write-Host "Using PYTHON_AGENT_BASE_URL=$($env:PYTHON_AGENT_BASE_URL)"
    npm run dev
}
finally {
    if ($pythonProcess -and -not $pythonProcess.HasExited) {
        Write-Host "Stopping Python bridge (PID $($pythonProcess.Id)) ..."
        Stop-Process -Id $pythonProcess.Id -Force
    }
}

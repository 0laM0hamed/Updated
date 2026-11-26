param(
    [int]$Port = 8000
)

$projectPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $projectPython)) {
    $projectPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $projectPython)) {
    Write-Error "No project virtual environment found. Create one and install requirements.txt."
    exit 1
}

& $projectPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload

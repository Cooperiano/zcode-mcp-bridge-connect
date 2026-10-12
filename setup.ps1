param([switch]$Test, [string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required. Pass -Python with its executable path."
}
& $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 'Error: Python 3.11+ is required.')"
if ($LASTEXITCODE -ne 0) { throw "Python version check failed." }
Write-Host "Checking Python sources (standard library only)..."
& $Python -m compileall -q .
if ($LASTEXITCODE -ne 0) { throw "Source compilation failed." }
if ($Test) {
    Write-Host "Running offline fixture tests..."
    & $Python -m unittest discover -s tests -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw "Fixture tests failed." }
}
Write-Host "Setup complete. Register server.py in your MCP client using the README template."
Write-Host "Keep your existing ZCode installation and login on this device."
Write-Host "See AGENTS.md for development commands."

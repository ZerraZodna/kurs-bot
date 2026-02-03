# PowerShell script to run all pytest tests in the project
# Test database setup is handled by conftest.py

. .venv\Scripts\Activate.ps1

Write-Host "Running tests..." -ForegroundColor Cyan
pytest --maxfail=3 --disable-warnings --tb=short -v

# Show result
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Some tests failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
}

exit $LASTEXITCODE

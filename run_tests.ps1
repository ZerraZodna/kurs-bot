# PowerShell script to run all pytest tests in the project
# Always uses a separate test database to avoid affecting production/dev data

. .venv\Scripts\Activate.ps1

# Set test database environment variable
$env:DATABASE_URL = 'sqlite:///./src/data/test.db'

# Run pytest with test database
Write-Host "🧪 Running tests with test database: src/data/test.db" -ForegroundColor Cyan
pytest --maxfail=3 --disable-warnings --tb=short -v

# Show result
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Some tests failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
}

exit $LASTEXITCODE

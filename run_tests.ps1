# PowerShell script to run all pytest tests in the project
. .venv\Scripts\Activate.ps1
pytest --maxfail=3 --disable-warnings --tb=short

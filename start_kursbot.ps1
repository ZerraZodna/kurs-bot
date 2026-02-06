# Windows PowerShell startup script for Kurs Bot
# This script activates the Python virtual environment, starts the FastAPI app, and launches ngrok.

# Need account at: https://dashboard.ngrok.com/get-started/setup/windows

# Activate virtual environment
. .venv\Scripts\Activate.ps1

# Start FastAPI app (run in this window to see logs)
Write-Host "To run the FastAPI app in the foreground (show logs here), execute:"
Write-Host "uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --log-level debug"

# Start ngrok (in a new terminal window)
Start-Process powershell -ArgumentList '"C:\Users\steen\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000'
# Manual start:
#& "C:\Users\steen\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000

Write-Host "Kurs Bot helper started. Start uvicorn in this window to view logs, or run it separately as preferred."

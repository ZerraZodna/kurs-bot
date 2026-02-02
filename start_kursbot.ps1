# Windows PowerShell startup script for Kurs Bot
# This script activates the Python virtual environment, starts the FastAPI app, and launches ngrok.

# Activate virtual environment
. .venv\Scripts\Activate.ps1

# Start FastAPI app (in a new terminal window)
Start-Process powershell -ArgumentList 'uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000'

# Start ngrok (in a new terminal window)
Start-Process powershell -ArgumentList '"C:\Users\steen\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000'
# Manual start:
#& "C:\Users\steen\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000

Write-Host "Kurs Bot services started. Check the new terminal windows for logs."

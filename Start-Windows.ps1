$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptRoot

$uvicornCmd = "uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
$ngrokCmd = "ngrok http 8000"

$activateWindows = Join-Path $scriptRoot ".venv/Scripts/Activate.ps1"

function Start-WindowedProcess {
    param(
        [string]$Title,
        [string]$ActivatePath,
        [string]$Command
    )

    $psExe = "powershell.exe"
    $wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
    $wrapperContent = "& '$ActivatePath'; $Command"
    Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8
    Start-Process -FilePath $psExe -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot -WindowStyle Normal
    Write-Output "Started $Title in new PowerShell window"
}

# Start services in new PowerShell windows
Start-WindowedProcess -Title 'uvicorn' -ActivatePath $activateWindows -Command $uvicornCmd
Start-WindowedProcess -Title 'ngrok' -ActivatePath $activateWindows -Command $ngrokCmd

Write-Output 'Spawn requests sent (Windows).'

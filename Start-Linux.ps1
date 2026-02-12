$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptRoot

# Commands
$uvicornCmd = "uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
$ngrokCmd = "ngrok http 8000"

$activateLinux = Join-Path $scriptRoot ".venv/bin/Activate.ps1"

function Start-WindowedProcess {
    param(
        [string]$Title,
        [string]$ActivatePath,
        [string]$Command
    )

    # Prefer launching a graphical terminal if available
    $terminals = @('gnome-terminal','konsole','xfce4-terminal','mate-terminal','tilix','xterm')
    $found = $null
    foreach ($t in $terminals) {
        if (Get-Command $t -ErrorAction SilentlyContinue) { $found = $t; break }
    }

    $wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
    $wrapperContent = "& '$ActivatePath'; $Command"
    Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8

    if ($found) {
        switch ($found) {
            'gnome-terminal' { Start-Process $found -ArgumentList '--', '--title', $Title, '--', 'pwsh', '-NoExit', '-File', $wrapper }
            'konsole' { Start-Process $found -ArgumentList '-p', "tabtitle=$Title", '-e', 'pwsh', '-NoExit', '-File', $wrapper }
            'xfce4-terminal' { Start-Process $found -ArgumentList '--title', $Title, '-e', 'pwsh', '-NoExit', '-File', $wrapper }
            'mate-terminal' { Start-Process $found -ArgumentList '--title', $Title, '--', 'pwsh', '-NoExit', '-File', $wrapper }
            'tilix' { Start-Process $found -ArgumentList '--title', $Title, '--', 'pwsh', '-NoExit', '-File', $wrapper }
            'xterm' { Start-Process $found -ArgumentList '-T', $Title, '-e', 'pwsh', '-NoExit', '-File', $wrapper }
            default { Start-Process $found -ArgumentList '-e', 'pwsh', '-NoExit', '-File', $wrapper }
        }
        Write-Output "Started $Title in $found"
        return
    }

    # No graphical terminal: start pwsh detached and log output
    $log = Join-Path $scriptRoot ("$Title.log")
    try {
        Start-Process -FilePath 'pwsh' -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot -RedirectStandardOutput $log -RedirectStandardError $log
        Write-Output "Started $Title detached (logs: $log)"
    } catch {
        Write-Output "Failed to start detached; running $Title inline"
        & pwsh -NoExit -File $wrapper
    }
}

# Start services (graphical terminal if available, otherwise detached)
Start-WindowedProcess -Title 'uvicorn' -ActivatePath $activateLinux -Command $uvicornCmd
Start-WindowedProcess -Title 'ngrok' -ActivatePath $activateLinux -Command $ngrokCmd

Write-Output 'Spawn requests sent (Linux).'

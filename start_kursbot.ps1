
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptRoot

# Robust platform detection (works in Windows PowerShell and pwsh)
$IsWindows = $false
if ($env:OS -eq 'Windows_NT') { $IsWindows = $true }
$IsLinux = $false
if ($env:OS -eq 'Linux') { $IsLinux = $true }

$uvicornCmd = "uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
$ngrokCmd = "ngrok http 8000"

$activateLinux = Join-Path $scriptRoot ".venv/bin/Activate.ps1"
$activateWindows = Join-Path $scriptRoot ".venv/Scripts/Activate.ps1"

function Start-WindowedProcess {
	param(
		[string]$Title,
		[string]$ActivatePath,
		[string]$Command
	)

	if ($IsWindows) {
		$psExe = "powershell.exe"
		$wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
		$wrapperContent = "& '$ActivatePath'; $Command"
		Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8
		Start-Process -FilePath $psExe -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot -WindowStyle Normal
		Write-Output "Started $Title in new PowerShell window"
		return
	}

	if ($IsLinux) {
		# Prefer launching a graphical terminal if available
		$terminals = @('gnome-terminal','konsole','xfce4-terminal','mate-terminal','tilix','xterm')
		$found = $null
		foreach ($t in $terminals) {
			if (Get-Command $t -ErrorAction SilentlyContinue) { $found = $t; break }
		}

		if ($found) {
			$wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
			$wrapperContent = "& '$ActivatePath'; $Command"
			Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8
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

		# No graphical terminal: start pwsh directly (detached from this host shell)
		$log = Join-Path $scriptRoot ("$Title.log")
		$wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
		$wrapperContent = "& '$ActivatePath'; $Command"
		Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8
		try {
			Start-Process -FilePath 'pwsh' -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot -RedirectStandardOutput $log -RedirectStandardError $log
			Write-Output "Started $Title detached (logs: $log)"
		} catch {
			Write-Output "Failed to start detached; running $Title inline"
			& pwsh -NoExit -File $wrapper
		}
		return
	}

	# Unknown platform: try available shell, otherwise run inline
	Write-Output "Platform not specifically supported; attempting available shell for $Title"
	$wrapper = Join-Path $scriptRoot ("start-$Title.ps1")
	$wrapperContent = "& '$ActivatePath'; $Command"
	Set-Content -Path $wrapper -Value $wrapperContent -Encoding UTF8
	if (Get-Command pwsh -ErrorAction SilentlyContinue) {
		Start-Process -FilePath 'pwsh' -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot
	} elseif (Get-Command powershell.exe -ErrorAction SilentlyContinue) {
		Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit', '-File', $wrapper -WorkingDirectory $scriptRoot
	} else {
		Write-Output "No suitable shell found; running $Title inline"
		& $ActivatePath
		Invoke-Expression $Command
	}
}

if ($IsWindows) { $activate = $activateWindows } else { $activate = $activateLinux }

# Start services in their own windows (or detached on headless Linux)
Start-WindowedProcess -Title 'uvicorn' -ActivatePath $activate -Command $uvicornCmd
Start-WindowedProcess -Title 'ngrok' -ActivatePath $activate -Command $ngrokCmd

Write-Output 'Spawn requests sent.'
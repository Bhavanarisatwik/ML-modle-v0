#requires -RunAsAdministrator
<#
.SYNOPSIS
Installs the DecoyVerse Network Edge Agent on a Windows machine via WSL2.

.DESCRIPTION
This script automatically:
1. Installs Python 3 if not present on the Windows host.
2. Enables Windows Subsystem for Linux (WSL) and Virtual Machine Platform.
3. Installs a lightweight Ubuntu distribution silently.
4. Installs Zeek inside WSL.
5. Configures Zeek to write conn.log to a shared Windows mount (C:\ProgramData\DecoyVerse\logs).
6. Registers the Agent as a scheduled task to run silently on boot.
#>

$ErrorActionPreference = "Stop"
$LogPath = "$env:TEMP\DecoyVerse_Zeek_Install.log"
$AgentDir = "$env:ProgramData\DecoyVerse"
$LogMountDir = "$AgentDir\logs"

Function Write-Log {
    Param([string]$Message)
    $Stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $LogMsg = "[$Stamp] $Message"
    Write-Host $LogMsg
    Add-Content -Path $LogPath -Value $LogMsg
}

Write-Log "Starting DecoyVerse WSL & Zeek Automated Installation..."

# 1. Setup Directories
if (-not (Test-Path $AgentDir)) {
    New-Item -ItemType Directory -Path $AgentDir | Out-Null
}
if (-not (Test-Path $LogMountDir)) {
    New-Item -ItemType Directory -Path $LogMountDir | Out-Null
}
Write-Log "Agent directories configured at $AgentDir"

# 2. Check/Install Python on Host
$pythonInstalled = $false
try {
    $pyVersion = python --version 2>&1
    if ($pyVersion -match "Python 3") {
        Write-Log "Host Python 3 is already installed: $pyVersion"
        $pythonInstalled = $true
    }
} catch {
    Write-Log "Host Python not found in PATH."
}

if (-Not $pythonInstalled) {
    Write-Log "Installing Python 3 on Windows via Winget..."
    try {
        Start-Process -FilePath "winget" -ArgumentList "install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements" -Wait -NoNewWindow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        Write-Log "Warning: Failed to install Python via Winget. Please install manually if agent fails."
    }
}

# 3. Check/Install WSL & Ubuntu
Write-Log "Checking WSL status..."
$wslStatus = wsl --status 2>&1
$wslInstalled = ($wslStatus -match "Default Version: 2" -or $wslStatus -match "WSL 2")

if (-not $wslInstalled) {
    Write-Log "WSL not found or not default. Installing WSL with Ubuntu..."
    try {
        # This will install Ubuntu by default and requires a reboot usually, but we try to do it unattended
        Start-Process -FilePath "wsl.exe" -ArgumentList "--install -d Ubuntu --web-download" -Wait -NoNewWindow
        Write-Log "NOTE: WSL installation may require a system reboot before Zeek can run."
    } catch {
        Write-Log "ERROR: Failed to install WSL. Ensure virtualization is enabled in BIOS."
    }
} else {
    Write-Log "WSL is already installed."
}

# 4. Bootstrap Zeek inside WSL
# We write a bash script, execute it inside WSL, and map the logs to the mounted C: drive
$mntPath = "/mnt/c/ProgramData/DecoyVerse/logs"
$bashScriptPath = "$env:TEMP\install_zeek.sh"

$bashScript = @"
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

echo "Updating APT..."
sudo apt-get update -qq

echo "Installing Zeek Dependencies..."
sudo apt-get install -y -qq curl gnupg2 wget ca-certificates lsb-release

echo "Adding Zeek Repository..."
echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_22.04/ /' | sudo tee /etc/apt/sources.list.d/security:zeek.list
curl -fsSL https://download.opensuse.org/repositories/security:zeek/xUbuntu_22.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/security_zeek.gpg > /dev/null

sudo apt-get update -qq
echo "Installing Zeek..."
sudo apt-get install -y -qq zeek

echo "Configuring Zeek to output to Windows Mount..."
# Zeek natively outputs to current working dir, or we can configure zeekctl
# For real-time, we will create a cronjob or startup script that runs zeek against eth0, outputting to C:
mkdir -p $mntPath

# Create the startup runner script
cat << 'EOF' > /usr/local/bin/start_zeek_bridge.sh
#!/bin/bash
INTERFACE=\$(ip route get 8.8.8.8 | grep -Po '(?<=dev )(\S+)')
cd $mntPath
/opt/zeek/bin/zeek -i \$INTERFACE -C local
EOF

chmod +x /usr/local/bin/start_zeek_bridge.sh

echo "Installation complete inside WSL!"
"@

Set-Content -Path $bashScriptPath -Value $bashScript -Encoding UTF8

Write-Log "Executing Zeek Bootstrap inside WSL Ubuntu..."
# Convert Windows path to WSL path 
$wslScriptPath = "$(wsl wslpath -u $bashScriptPath)".Trim()
wsl -d Ubuntu -u root bash $wslScriptPath

Write-Log "Zeek installation inside WSL complete."

# 5. Copy Python Agent Files
$sourceDir = $PSScriptRoot
Write-Log "Copying Python Agent files to $AgentDir..."
Copy-Item -Path "$sourceDir\*" -Destination $AgentDir -Recurse -Force

# 6. Install Python Dependencies
Write-Log "Installing Python dependencies..."
Set-Location -Path $AgentDir
try {
    Start-Process -FilePath "python" -ArgumentList "-m pip install requests watchdog psutil" -Wait -NoNewWindow
} catch {
    Write-Log "Warning: PIP install encountered an error."
}

# 7. Setup Background Services
Write-Log "Registering Zeek WSL Background Runner..."
# A scheduled task to start Zeek inside WSL on boot
$taskZeek = "DecoyVerse_Zeek_Sensor"
$actionZeek = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d Ubuntu -u root bash /usr/local/bin/start_zeek_bridge.sh" 
$triggerZeek = New-ScheduledTaskTrigger -AtStartup
$principalZeek = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settingsZeek = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $taskZeek -Action $actionZeek -Trigger $triggerZeek -Principal $principalZeek -Settings $settingsZeek -Force | Out-Null
Start-ScheduledTask -TaskName $taskZeek

Write-Log "Registering DecoyVerse Python Agent..."
$taskAgent = "DecoyVerse_Agent"
$actionAgent = New-ScheduledTaskAction -Execute "python.exe" -Argument "$AgentDir\agent.py" -WorkingDirectory $AgentDir
$triggerAgent = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName $taskAgent -Action $actionAgent -Trigger $triggerAgent -Principal $principalZeek -Settings $settingsZeek -Force | Out-Null
Start-ScheduledTask -TaskName $taskAgent

Write-Log "======================================="
Write-Log "Installation Complete!"
Write-Log "Zeek is sniffing the WSL interface and outputting to $LogMountDir"
Write-Log "The Python Agent is monitoring those files and sending to the ML API."
Write-Log "======================================="

#!/usr/bin/env pwsh
# PUI PowerShell Shim - Cross-platform entry point for Windows
# Usage: .\scripts\pui.ps1 [command] [options]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ParentDir = Split-Path -Parent $ScriptDir

# Find Python executable
function Find-Python {
    $pythonCommands = @("python3", "python", "py")
    
    foreach ($cmd in $pythonCommands) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            return $found.Source
        }
    }
    
    Write-Error "Python not found. Please install Python 3.9+ and ensure it's in PATH"
    exit 1
}

$Python = Find-Python

# Check Python version
$VersionInfo = & $Python --version 2>&1
$VersionMatch = $VersionInfo -match "Python\s+(\d+)\.(\d+)"
if (-not $VersionMatch) {
    Write-Error "Could not determine Python version"
    exit 1
}

$Major = [int]$Matches[1]
$Minor = [int]$Matches[2]

if ($Major -lt 3 -or ($Major -eq 3 -and $Minor -lt 9)) {
    Write-Error "Python 3.9+ required, found $Major.$Minor"
    exit 1
}

# Set up environment
$env:PUI_SCRIPT_DIR = $ScriptDir
$env:PUI_PARENT_DIR = $ParentDir

# Check for virtual environment
$VenvPaths = @(
    "$ParentDir\.venv\Scripts\Activate.ps1",
    "$ParentDir\venv\Scripts\Activate.ps1"
)

foreach ($VenvPath in $VenvPaths) {
    if (Test-Path $VenvPath) {
        & $VenvPath
        break
    }
}

# Run PUI
& $Python -m scripts.pui @Arguments

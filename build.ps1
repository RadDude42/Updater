# GitHub Script Updater - Build Script (PowerShell)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Script Updater - Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found"
    }
    Write-Host "[1/5] Python found - checking version..." -ForegroundColor Green
    Write-Host "Python version: $($pythonVersion -replace 'Python ', '')" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://python.org" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Setup virtual environment
Write-Host "[2/6] Setting up virtual environment..." -ForegroundColor Green
try {
    # Check if virtual environment already exists and remove it
    if (Test-Path "build_env") {
        Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "build_env"
    }
    
    Write-Host "Creating fresh virtual environment..." -ForegroundColor White
    python -m venv build_env
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
    
    Write-Host "Activating virtual environment..." -ForegroundColor White
    & "build_env\Scripts\Activate.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment activation failed" }
    
    Write-Host ""
} catch {
    Write-Host "ERROR: Failed to setup virtual environment" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install dependencies
Write-Host "[3/6] Installing/upgrading required packages..." -ForegroundColor Green
try {
    Write-Host "Installing PyInstaller..." -ForegroundColor White
    python -m pip install --upgrade pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller installation failed" }
    
    Write-Host "Installing application dependencies..." -ForegroundColor White
    python -m pip install --upgrade customtkinter requests pillow
    if ($LASTEXITCODE -ne 0) { throw "Dependencies installation failed" }
    Write-Host ""
} catch {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Clean previous build files
Write-Host "[4/6] Cleaning previous build files..." -ForegroundColor Green
$foldersToClean = @("build", "dist", "__pycache__")
foreach ($folder in $foldersToClean) {
    if (Test-Path $folder) {
        Remove-Item -Recurse -Force $folder
    }
}
Write-Host "Previous build files cleaned." -ForegroundColor White
Write-Host ""

# Build executable
Write-Host "[5/6] Building executable with PyInstaller..." -ForegroundColor Green
Write-Host "This may take a few minutes..." -ForegroundColor Yellow
try {
    python -m PyInstaller ScriptUpdaterApp.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    Write-Host ""
} catch {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    Write-Host "Check the output above for error details" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify build
Write-Host "[6/6] Verifying build..." -ForegroundColor Green
$exePath = "dist\ScriptUpdaterApp.exe"
if (Test-Path $exePath) {
    Write-Host "✓ Build successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable created: $exePath" -ForegroundColor White
    
    # Get file size
    $fileSize = (Get-Item $exePath).Length
    $sizeMB = [math]::Round($fileSize / 1MB, 1)
    Write-Host "File size: $sizeMB MB" -ForegroundColor White
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "BUILD COMPLETE" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "The executable is ready for distribution." -ForegroundColor Green
    Write-Host "Location: $((Get-Location).Path)\dist\ScriptUpdaterApp.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now:" -ForegroundColor White
    Write-Host "- Test the executable by running it" -ForegroundColor White
    Write-Host "- Distribute the .exe file (no Python required)" -ForegroundColor White
    Write-Host "- Upload to GitHub releases" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "ERROR: Executable not found after build" -ForegroundColor Red
    Write-Host "Build may have failed silently" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Clean up temporary files
Write-Host "Cleaning up temporary files..." -ForegroundColor Green
$tempFoldersToClean = @("build", "build_env")
foreach ($folder in $tempFoldersToClean) {
    if (Test-Path $folder) {
        Remove-Item -Recurse -Force $folder
    }
}
Write-Host ""

Write-Host "Press Enter to exit..." -ForegroundColor Yellow
Read-Host 
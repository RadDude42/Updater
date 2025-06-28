@echo off
echo ========================================
echo GitHub Script Updater - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/5] Python found - checking version...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%
echo.

echo [2/6] Setting up virtual environment...
REM Check if virtual environment already exists and remove it
if exist "build_env" (
    echo Removing existing virtual environment...
    rmdir /s /q "build_env"
)

echo Creating fresh virtual environment...
python -m venv build_env
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo Activating virtual environment...
call build_env\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo [3/6] Installing/upgrading required packages...
echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

echo Installing application dependencies...
python -m pip install --upgrade customtkinter requests pillow
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo [4/6] Cleaning previous build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"
echo Previous build files cleaned.
echo.

echo [5/6] Building executable with PyInstaller...
echo This may take a few minutes...
python -m PyInstaller ScriptUpdaterApp.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed
    echo Check the output above for error details
    pause
    exit /b 1
)
echo.

echo [6/6] Verifying build...
if exist "dist\ScriptUpdaterApp.exe" (
    echo ✓ Build successful!
    echo.
    echo Executable created: dist\ScriptUpdaterApp.exe
    
    REM Get file size
    setlocal enabledelayedexpansion
    for %%A in ("dist\ScriptUpdaterApp.exe") do (
        set /a "size_mb=%%~zA / 1024 / 1024"
        echo File size: !size_mb! MB
    )
    endlocal
    
    echo.
    echo ========================================
    echo BUILD COMPLETE
    echo ========================================
    echo.
    echo The executable is ready for distribution.
    echo Location: %CD%\dist\ScriptUpdaterApp.exe
    echo.
    echo You can now:
    echo - Test the executable by running it
    echo - Distribute the .exe file ^(no Python required^)
    echo - Upload to GitHub releases
    echo.
    goto :cleanup
) else (
    echo ERROR: Executable not found after build
    echo Build may have failed silently
    exit /b 1
)

:cleanup

echo Cleaning up temporary files...
if exist "build" rmdir /s /q "build"
if exist "build_env" rmdir /s /q "build_env"
echo.

echo Press any key to exit...
pause >nul 
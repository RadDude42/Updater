# Building GitHub Script Updater from Source

This document explains how to build the GitHub Script Updater application from source code.

## Quick Build (Recommended)

### Windows - Choose Your Preferred Method

**Option 1: Batch Script (Classic)**
1. **Double-click `build.bat`** - This will automatically handle everything!

**Option 2: PowerShell Script (Modern)**
1. **Right-click `build.ps1` → "Run with PowerShell"**
2. Or open PowerShell and run: `.\build.ps1`

Both scripts will:
- Check for Python installation
- Create a clean virtual environment (`build_env`)
- Install required dependencies in isolation
- Build the executable using PyInstaller
- Clean up temporary files and virtual environment
- Verify the build was successful
- Display colored output for better readability

**Benefits of Virtual Environment:**
- ✅ No interference with your existing Python packages
- ✅ Clean, isolated build environment every time
- ✅ Prevents version conflicts with your development setup
- ✅ Automatically cleaned up after build completion

### Result
- **Executable**: `dist/ScriptUpdaterApp.exe`
- **Size**: ~27 MB
- **Dependencies**: None (standalone executable)

---

## Manual Build Process

If you prefer to build manually or need to customize the process:

### Prerequisites

1. **Python 3.8+** installed with pip
2. **Git** (to clone the repository)

### Step 1: Setup Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv build_env

# Activate virtual environment
# On Windows:
build_env\Scripts\activate
# On macOS/Linux:
source build_env/bin/activate

# Install dependencies in virtual environment
pip install pyinstaller customtkinter requests pillow
```

**Alternative: Global Installation (Not Recommended)**
```bash
# Install PyInstaller globally
pip install pyinstaller

# Install application dependencies globally
pip install customtkinter requests pillow
```

### Step 2: Build with PyInstaller

```bash
# Using the spec file (recommended)
pyinstaller ScriptUpdaterApp.spec --clean --noconfirm

# Or using command line options
pyinstaller --onefile --windowed --icon=icon.ico --name=ScriptUpdaterApp script_updater_app.py
```

### Step 3: Verify Build

Check that `dist/ScriptUpdaterApp.exe` was created successfully.

### Step 4: Cleanup (Optional)

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment (optional)
# On Windows:
rmdir /s build_env
# On macOS/Linux:
rm -rf build_env
```

---

## Build Configuration

### PyInstaller Spec File (`ScriptUpdaterApp.spec`)

The spec file includes:
- **Main script**: `script_updater_app.py`
- **Data files**: `community_scripts.json`, `icon.ico`, `README.md`
- **Hidden imports**: All required modules
- **Icon**: Custom application icon
- **Console**: Disabled (windowed application)
- **UPX compression**: Enabled for smaller file size

### Key Features Included

✅ **Debug Mode**: File logging with toggle  
✅ **GitHub Token Auth**: API rate limit solution  
✅ **Version Management**: Smart deduplication system  
✅ **Search/Filter**: Real-time script filtering  
✅ **Help System**: Comprehensive usage guide  
✅ **Window Memory**: Persistent size/position  
✅ **Community Scripts**: Curated script collection  

---

## Troubleshooting

### Common Issues

**"Python not found"**
- Install Python from [python.org](https://python.org)
- Make sure "Add Python to PATH" is checked during installation

**"Module not found" errors**
- Run: `pip install --upgrade customtkinter requests pillow`
- Ensure you're using the same Python version for pip and PyInstaller

**Build fails silently**
- Check the PyInstaller output for specific error messages
- Try building with `--debug=all` flag for verbose output

**Large executable size**
- This is normal for PyInstaller builds (~27 MB)
- The executable includes Python runtime and all dependencies

### Build Environment

**Tested on:**
- Windows 10/11
- Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
- PyInstaller 6.0+

**Required packages:**
- `customtkinter` - Modern UI framework
- `requests` - HTTP client for GitHub API
- `pillow` - Image processing (CustomTkinter dependency)

---

## Distribution

### For End Users
- Distribute only the `ScriptUpdaterApp.exe` file
- No Python installation required
- Include `README.md` for usage instructions

### For Developers
- Include source code and build files
- `ScriptUpdaterApp.spec` for consistent builds
- `build.bat` for easy compilation
- `requirements.txt` for dependency management

---

## Development Setup

For development (not building):

```bash
# Clone repository
git clone https://github.com/YourUsername/Updater.git
cd Updater

# Install dependencies
pip install -r requirements.txt

# Run from source
python script_updater_app.py
```

---

## File Structure

```
Updater/
├── script_updater_app.py      # Main application
├── config_manager.py          # Configuration management
├── github_handler.py          # GitHub API interactions
├── logger_setup.py           # Logging system
├── community_scripts.json    # Curated scripts list
├── icon.ico                  # Application icon
├── ScriptUpdaterApp.spec     # PyInstaller configuration
├── build.bat                 # Automated build script (Batch)
├── build.ps1                 # Automated build script (PowerShell)
├── requirements.txt          # Python dependencies
├── BUILD.md                  # This file
└── README.md                 # User documentation
```

For questions or issues with building, please open an issue on GitHub. 
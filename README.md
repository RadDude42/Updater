# GitHub Script Updater

A Python application with a graphical user interface (GUI) to manage scripts from GitHub repositories.

This will only work for scripts added by the program. Strongly recommend you backup your current scripts folder before implementing this as your script manager

## Features

### Core Functionality
- Add scripts by providing a GitHub repository URL and a specific folder path
- Explicit category selection when adding scripts (Activities, Class Rotations, Programs, Utilities)
- List of curated community scripts for easy access
- Save scripts to a user-defined local directory
- Check for updates to added scripts
- Update scripts to their latest versions from GitHub with two update methods:
  - **Overwrite**: Complete file replacement (original behavior)
  - **Differential**: Only updates changed files, preserving customizations
- Delete managed scripts
- User-friendly interface with organized tabs

### Advanced Features
- **Automatic Self-Update**: The application automatically checks for new versions of itself on startup. If an update is found, it will prompt you to install it.
- **Update Methods**: Choose between two update strategies for your scripts:
  - **Overwrite**: Completely replaces all files with the new version (ensures clean installation).
  - **Differential**: Only updates files that have actually changed (faster, preserves user modifications).
- **Search and Filter**: Quickly find specific scripts using the filter bar
- **Version Management**: Automatic archiving of old versions when updating scripts
  - Previous versions are saved in an "Older Versions" folder
  - Restore any previous version through the "Manage Versions" button
  - "Older Versions" folder is always preserved regardless of update method
- **Debug Mode**: Optional logging to app.log file for troubleshooting
  - Enable/disable with the Debug Mode checkbox
  - Detailed operation logs and file-by-file update progress when enabled
- **Help System**: Built-in help accessible via the "?" button
- **Enhanced UI**: Improved layout with better organization and visual feedback

### How to Use

#### Adding a Script
1. Paste the full GitHub repository URL (e.g., `https://github.com/user/repo`)
2. (Optional) Specify a folder path within the repository. If left blank, the whole repository is downloaded
3. Click "Browse" to choose where to save the script on your computer
4. Click "Add Script" and select a category for your script

#### Managing Scripts
- Check the box next to one or more scripts to enable action buttons
- Choose your preferred update method from the "Update Method" dropdown:
  - **Overwrite**: For clean installations and when you want to ensure no old files remain
  - **Differential**: For faster updates that preserve your custom modifications
- Use "Update Selected" to update checked scripts using your chosen method
- Use "GitHub" to open the repository page for a selected script
- Use "Delete Selected" to remove scripts from management
- Use "Manage Versions" to view and restore previous versions of a script

#### Community Scripts
- Click "Community Scripts" to browse curated scripts
- Check desired scripts and click "Add Selected to Managed" to download them

#### Search and Filter
- Use the "Filter scripts..." box to quickly find specific scripts in your managed list
- Type any part of the script name to filter the display

#### Debug Mode
- Enable "Debug Mode" to create detailed logs in app.log for troubleshooting
- Shows file-by-file comparison details during differential updates
- Disable during normal use to avoid creating large log files

#### Version Management
- When you update a script, the old version is automatically saved
- Select a single script and click "Manage Versions" to view available versions
- Choose any previous version and click "Restore" to roll back
- The "Older Versions" folder is preserved during all types of updates

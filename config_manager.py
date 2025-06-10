import json
import os
import sys

# Determine base path for config files
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running as a PyInstaller bundle (e.g., one-file exe)
    # sys.executable is the path to the .exe
    application_path = os.path.dirname(sys.executable)
else:
    # Running as a normal Python script
    # os.path.abspath(__file__) is the absolute path to this script (config_manager.py)
    # os.path.dirname() gets the directory containing this script.
    application_path = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(application_path, 'managed_scripts.json')
SETTINGS_FILE = os.path.join(application_path, 'app_settings.json')

def load_scripts_config():
    """Loads the managed scripts configuration from the JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []  # Return empty list if file is corrupted
    return []

def save_scripts_config(scripts):
    """Saves the managed scripts configuration to the JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(scripts, f, indent=4)

def add_script_to_config(script_info):
    """Adds a new script to the configuration."""
    scripts = load_scripts_config()
    # Prevent duplicates based on a unique identifier, e.g., repo_url + folder_path
    # For now, we'll just append. Duplicate handling can be added later.
    scripts.append(script_info)
    save_scripts_config(scripts)

def remove_script_from_config(script_to_remove):
    """Removes a script from the configuration.
       script_to_remove is the dictionary of the script to be removed.
    """
    scripts = load_scripts_config()
    # Filter out the script that matches all key fields of script_to_remove.
    # A simple equality check on dictionaries works if they are identical.
    # For more robustness, one might compare specific unique keys if available (e.g., a generated ID or combination of repo_url+local_path).
    initial_length = len(scripts)
    updated_scripts = [s for s in scripts if s != script_to_remove]
    
    if len(updated_scripts) < initial_length:
        save_scripts_config(updated_scripts)
        return True # Script was found and removed
    return False # Script not found

def update_script_config(repo_url, updates):
    scripts = load_scripts_config()
    for script in scripts:
        if script['repo_url'] == repo_url:
            script.update(updates)
            break
    save_scripts_config(scripts)



# --- App Settings Management ---

def load_settings():
    """Loads application settings from the settings file."""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[ERROR] Could not read settings file {SETTINGS_FILE}: {e}")
        return {}

def save_settings(settings):
    """Saves application settings to the settings file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except IOError as e:
        print(f"[ERROR] Could not write to settings file {SETTINGS_FILE}: {e}")

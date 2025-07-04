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

def update_script_config(repo_url, folder_path, updates):
    scripts = load_scripts_config()
    for script in scripts:
        # Match script based on both repo_url and folder_path for uniqueness
        if script.get('repo_url') == repo_url and script.get('folder_path', '') == folder_path:
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

def get_debug_mode():
    """Gets the debug mode setting from app settings."""
    settings = load_settings()
    return settings.get('debug_mode', False)

def set_debug_mode(enabled):
    """Sets the debug mode setting in app settings."""
    settings = load_settings()
    settings['debug_mode'] = enabled
    save_settings(settings)

def get_github_token():
    """Gets the GitHub personal access token from app settings."""
    settings = load_settings()
    return settings.get('github_token', '')

def set_github_token(token):
    """Sets the GitHub personal access token in app settings."""
    settings = load_settings()
    settings['github_token'] = token.strip() if token else ''
    save_settings(settings)

def get_window_size():
    """Gets the saved window size from app settings."""
    settings = load_settings()
    return settings.get('window_size', {'width': 1000, 'height': 700})

def set_window_size(width, height):
    """Sets the window size in app settings."""
    settings = load_settings()
    settings['window_size'] = {'width': width, 'height': height}
    save_settings(settings)

def get_update_method():
    """Gets the update method setting from app settings."""
    settings = load_settings()
    return settings.get('update_method', 'overwrite')

def set_update_method(method):
    """Sets the update method setting in app settings."""
    settings = load_settings()
    settings['update_method'] = method
    save_settings(settings)

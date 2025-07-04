import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import sys
import os
import queue
import webbrowser
import shutil
import subprocess
import requests

# Helper function for PyInstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

import config_manager
import github_handler
import datetime
import threading
import queue
import json
from logger_setup import setup_logger, get_logger

logger = get_logger(__name__)

APP_VERSION = "1.1.0"

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class ScriptUpdaterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GitHub Script Updater")
        
        # Load saved window size
        window_size = config_manager.get_window_size()
        self.geometry(f"{window_size['width']}x{window_size['height']}")
        
        # Bind window resize event to save size
        self.bind("<Configure>", self.on_window_resize)

        self.scripts_data = config_manager.load_scripts_config()
        self.community_scripts_data = self.load_community_scripts_config()
        self.current_view = "main" # To track current view: "main" or "community"

        # Main container frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.settings = config_manager.load_settings()

        # Initialize logger based on debug mode setting
        debug_mode = config_manager.get_debug_mode()
        setup_logger(debug_mode)
        logger.info("Application started")

        # Clean up after update
        self.cleanup_after_update()

        # --- Input Frame ---
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(pady=10, padx=10, fill="x")

        self.label_repo_url = ctk.CTkLabel(self.input_frame, text="GitHub Repo URL:")
        self.label_repo_url.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_repo_url = ctk.CTkEntry(self.input_frame, width=250)
        self.entry_repo_url.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Add debug mode checkbox next to repo URL
        self.debug_mode_var = ctk.BooleanVar(value=config_manager.get_debug_mode())
        self.debug_checkbox = ctk.CTkCheckBox(self.input_frame, text="Debug Mode", 
                                            variable=self.debug_mode_var, command=self.toggle_debug_mode)
        self.debug_checkbox.grid(row=0, column=3, padx=5, pady=5)

        self.label_folder_path = ctk.CTkLabel(self.input_frame, text="Folder Path in Repo (optional):")
        self.label_folder_path.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_folder_path = ctk.CTkEntry(self.input_frame, width=250)
        self.entry_folder_path.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.entry_folder_path.insert(0, "") # Default to empty (repo root or user must specify)

        self.label_local_path = ctk.CTkLabel(self.input_frame, text="Local Save Directory:")
        self.label_local_path.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_local_path = ctk.CTkEntry(self.input_frame, width=250)
        self.entry_local_path.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        # Load and set the last used local path
        last_local_path = self.settings.get('last_local_path', '')
        if last_local_path:
            self.entry_local_path.insert(0, last_local_path)
        self.button_browse_local_path = ctk.CTkButton(self.input_frame, text="Browse", command=self.browse_local_path)
        self.button_browse_local_path.grid(row=2, column=3, padx=5, pady=5)
        
        # Add help button next to Browse button
        self.button_help = ctk.CTkButton(self.input_frame, text="?", width=30, command=self.show_help)
        self.button_help.grid(row=2, column=4, padx=5, pady=5)

        # Add GitHub token input
        self.label_github_token = ctk.CTkLabel(self.input_frame, text="GitHub Token (optional):")
        self.label_github_token.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.entry_github_token = ctk.CTkEntry(self.input_frame, width=250, show="*", placeholder_text="ghp_xxxxxxxxxxxxxxxxxxxx")
        self.entry_github_token.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Load existing token
        existing_token = config_manager.get_github_token()
        if existing_token:
            self.entry_github_token.insert(0, existing_token)
        
        # Add save token button
        self.button_save_token = ctk.CTkButton(self.input_frame, text="Save Token", width=100, command=self.save_github_token)
        self.button_save_token.grid(row=3, column=3, padx=5, pady=5)
        
        # Add clear token button
        self.button_clear_token = ctk.CTkButton(self.input_frame, text="Clear", width=60, command=self.clear_github_token)
        self.button_clear_token.grid(row=3, column=4, padx=5, pady=5)

        self.button_add_script = ctk.CTkButton(self.input_frame, text="Add Script", command=self.add_script)
        self.button_add_script.grid(row=4, column=0, columnspan=5, pady=10, sticky="ew") # Updated to span 5 columns
        
        self.input_frame.columnconfigure(1, weight=1) # Make entry fields expand

        # --- Scripts List Frame ---
        self.scripts_list_frame = ctk.CTkFrame(self.main_frame)
        self.scripts_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Add search/filter bar
        self.search_frame = ctk.CTkFrame(self.scripts_list_frame)
        self.search_frame.pack(pady=5, padx=5, fill="x")
        
        self.search_label = ctk.CTkLabel(self.search_frame, text="Filter scripts:")
        self.search_label.pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Type to filter...")
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", self.on_search_changed)

        # Add update method toggle
        self.update_method_label = ctk.CTkLabel(self.search_frame, text="Update Method:")
        self.update_method_label.pack(side="right", padx=(10, 5))
        
        # Get current update method
        current_method = config_manager.get_update_method()
        self.update_method_var = ctk.StringVar(value=current_method)
        
        self.update_method_menu = ctk.CTkOptionMenu(
            self.search_frame, 
            values=["overwrite", "differential"], 
            variable=self.update_method_var,
            command=self.on_update_method_changed,
            width=120
        )
        self.update_method_menu.pack(side="right", padx=5)

        # NEW: Managed Scripts TabView
        # The command will call _on_managed_tab_change when a tab is selected
        self.managed_scripts_tab_view = ctk.CTkTabview(self.scripts_list_frame, command=self._on_managed_tab_change) 
        self.managed_scripts_tab_view.pack(pady=5, padx=5, fill="both", expand=True)

        self.managed_script_categories = ["All", "Activities", "Class Rotations", "Programs", "Utilities"]
        self.managed_tab_scrollable_frames = {} # To store scrollable frames for each tab

        for category_name in self.managed_script_categories:
            tab = self.managed_scripts_tab_view.add(category_name)
            scrollable_frame = ctk.CTkScrollableFrame(tab, label_text="") # No individual label text
            scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)
            self.managed_tab_scrollable_frames[category_name] = scrollable_frame
        
        # Ensure 'All' tab is selected initially. The tabview's command will handle the button state.
        self.managed_scripts_tab_view.set("All")

        # --- Community Scripts Tab View (initially hidden) ---
        self.community_tab_view = ctk.CTkTabview(self.scripts_list_frame)
        # self.community_tab_view.pack(pady=5, padx=5, fill="both", expand=True) # Packed in show_community_view

        # Define categories including "All"
        self.community_script_categories = ["All", "Activities", "Class Rotations", "Programs", "Utilities"]
        self.community_script_widgets_by_tab = {category: [] for category in self.community_script_categories}
        self.community_script_checkbox_vars = {} # To store shared IntVars for community scripts
        self.tab_frames = {}

        # Create tabs and their scrollable frames
        for category_name in self.community_script_categories:
            tab = self.community_tab_view.add(category_name)
            scrollable_frame = ctk.CTkScrollableFrame(tab, label_text="") # No individual label text
            self.tab_frames[category_name] = scrollable_frame
    
        # Ensure 'All' tab is selected initially if view is switched (though populate handles content)
        # self.community_tab_view.set("All") # This might be better handled in show_community_view

        for category, frame in self.tab_frames.items():
            frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.populate_community_script_tabs()

        self.script_widgets = [] # To store {'checkbox': widget, 'script_data': dict, 'frame': widget} for managed scripts

        # --- Action Buttons Frame ---
        self.action_buttons_frame = ctk.CTkFrame(self.main_frame)
        self.action_buttons_frame.pack(pady=10, padx=10, fill="x") 

        self.button_update_selected = ctk.CTkButton(self.action_buttons_frame, text="Update Selected", command=self.update_selected_scripts, state="disabled")
        self.button_update_selected.pack(side="left", padx=5)

        self.button_open_github = ctk.CTkButton(self.action_buttons_frame, text="GitHub", command=self.open_script_github_page, state="disabled")
        self.button_open_github.pack(side="left", padx=5)
        
        self.button_delete_selected = ctk.CTkButton(self.action_buttons_frame, text="Delete Selected", command=self.delete_selected_script, state="disabled")
        self.button_delete_selected.pack(side="left", padx=5)

        self.button_manage_versions = ctk.CTkButton(self.action_buttons_frame, text="Manage Versions", command=self.manage_versions, state="disabled")
        self.button_manage_versions.pack(side="left", padx=5)

        self.button_show_community_view = ctk.CTkButton(self.action_buttons_frame, text="Community Scripts", command=self.show_community_view)
        self.button_show_community_view.pack(side="right", padx=5) # Moved to action_buttons_frame



        # --- Status Bar ---
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=5, pady=2)

        self.update_queue = queue.Queue()

        self.refresh_scripts_display() # Initial display before check

        # Start the startup check in a separate thread to keep UI responsive
        self.status_bar.configure(text="Checking all scripts for updates on startup...")
        thread = threading.Thread(
            target=self.perform_startup_update_check_worker, 
            args=(self.scripts_data.copy(), self.update_queue), # Pass a copy to avoid race conditions
            daemon=True
        )
        thread.start()

        # Start polling the queue for updates from the worker thread
        self.process_queue()

        # Start the app update check
        self.after(1000, self.start_app_update_check)

    def cleanup_after_update(self):
        """Deletes the old executable after an update."""
        if not hasattr(sys, 'frozen'):
            return # Only run when compiled
            
        exe_path = os.path.dirname(sys.executable)
        old_exe_path = os.path.join(exe_path, "ScriptUpdaterApp.exe.old")
        if os.path.exists(old_exe_path):
            try:
                os.remove(old_exe_path)
                logger.info(f"Successfully removed old executable: {old_exe_path}")
            except OSError as e:
                logger.error(f"Failed to remove old executable: {e}")

    def start_app_update_check(self):
        """Starts the application update check in a separate thread."""
        update_thread = threading.Thread(target=self.check_and_prompt_for_update, daemon=True)
        update_thread.start()

    def check_and_prompt_for_update(self):
        """Checks for updates and prompts the user if a new version is found."""
        logger.info("Checking for application updates...")
        new_version, download_url = github_handler.check_for_app_update(APP_VERSION)
        
        if new_version and download_url:
            self.status_bar.configure(text=f"New version {new_version} available!")
            
            user_choice = messagebox.askyesno(
                "Update Available",
                f"A new version ({new_version}) of the Script Updater is available.\n\n"
                f"Would you like to download and install it now?"
            )
            
            if user_choice:
                self.apply_update(download_url)

    def apply_update(self, download_url):
        """Downloads and applies the application update."""
        if not hasattr(sys, 'frozen'):
            messagebox.showinfo("Update Info", "Auto-update is only available for the compiled application.")
            return

        try:
            exe_dir = os.path.dirname(sys.executable)
            new_exe_path = os.path.join(exe_dir, "ScriptUpdaterApp.new.exe")
            old_exe_path = os.path.join(exe_dir, "ScriptUpdaterApp.exe.old")
            current_exe_path = sys.executable
            
            self.status_bar.configure(text="Downloading update...")
            self.update_idletasks()
            
            # Download the new executable
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            with open(new_exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.status_bar.configure(text="Download complete. Preparing to update...")
            
            # Create the helper batch script
            updater_script_path = os.path.join(exe_dir, "update.bat")
            with open(updater_script_path, 'w') as f:
                f.write(f'''@echo off
echo Updating Script Updater...
echo Waiting for application to close...
timeout /t 2 /nobreak > nul
if exist "{old_exe_path}" del "{old_exe_path}"
echo Backing up current version...
move /Y "{current_exe_path}" "{old_exe_path}"
echo Installing new version...
move /Y "{new_exe_path}" "{current_exe_path}"
echo Relaunching application...
start "" "{current_exe_path}"
echo Cleaning up...
del "%~f0"
''')

            # Launch the updater script and exit
            subprocess.Popen(updater_script_path, creationflags=subprocess.DETACHED_PROCESS, shell=True)
            self.destroy()

        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            messagebox.showerror("Update Failed", f"An error occurred during the update process: {e}")
            self.status_bar.configure(text="Update failed.")

    def _get_author_from_url(self, repo_url):
        if not repo_url or not isinstance(repo_url, str):
            return "N/A"
        try:
            # Standard HTTPS URL: https://github.com/username/repository
            if repo_url.startswith("https://github.com/"):
                parts = repo_url.split('/')
                if len(parts) >= 5: # https: / / github.com / username / repository ...
                    return parts[3]
            # SSH URL: git@github.com:username/repository.git
            elif repo_url.startswith("git@github.com:"):
                return repo_url.split(':')[1].split('/')[0]
            # Less common but possible: http://github.com/username/repository
            elif repo_url.startswith("http://github.com/"):
                parts = repo_url.split('/')
                if len(parts) >= 5:
                    return parts[3]
            return "Unknown" # If URL format is not recognized
        except Exception as e:
            print(f"Error parsing author from URL '{repo_url}': {e}")
            return "Error"

    def browse_local_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_local_path.delete(0, tk.END)
            self.entry_local_path.insert(0, directory)
        # Save the selected path as the new default
        self.settings['last_local_path'] = directory
        config_manager.save_settings(self.settings)

    def _perform_add_script(self, repo_url, folder_path, local_path, category, script_name_override=None, is_community_script=False):
        cleaned_repo_url = repo_url.strip().rstrip('/') if repo_url else ''
        folder_path_cleaned = folder_path.strip() if folder_path else ''

        if not cleaned_repo_url or not local_path:
            messagebox.showerror("Input Error", "Repository URL and Local Save Directory cannot be empty.")
            self.status_bar.configure(text="Error: Missing required inputs.")
            return False

        if not cleaned_repo_url.lower().startswith("https://github.com/"):
            messagebox.showerror("Input Error", "Invalid GitHub repository URL.")
            self.status_bar.configure(text="Error: Invalid GitHub URL format.")
            return False

        url_parts = cleaned_repo_url.split('/')
        if len(url_parts) < 5 or not url_parts[-1] or not url_parts[-2]:
            messagebox.showerror("Input Error", "Invalid GitHub repository URL structure.")
            self.status_bar.configure(text="Error: Invalid repository URL structure.")
            return False

        repo_name_from_url = url_parts[-1]
        effective_branch = github_handler.determine_effective_branch(cleaned_repo_url, None)
        if not effective_branch: # Should not happen with default 'main' but good to check
            messagebox.showerror("Error", "Could not determine repository branch.")
            self.status_bar.configure(text="Error: Could not determine repository branch.")
            return False

        if script_name_override:
            actual_final_folder_name = script_name_override
        elif folder_path_cleaned:
            # Use the last part of the folder_path_cleaned as the name
            # Strip trailing slashes to ensure basename works correctly
            temp_folder_name = os.path.basename(folder_path_cleaned.strip('/\\'))
            if not temp_folder_name: # If folder_path was something like "/" or "" after strip
                actual_final_folder_name = f"{repo_name_from_url}-{effective_branch}"
            else:
                actual_final_folder_name = temp_folder_name
        else:
            # Root of the repo, no specific folder_path, no override
            actual_final_folder_name = f"{repo_name_from_url}-{effective_branch}"

        script_dir_name = actual_final_folder_name # Use this for subsequent logic

        if not script_dir_name: # Should be redundant now but keep as a safeguard
            messagebox.showerror("Input Error", "Could not determine a script directory name.")
            self.status_bar.configure(text="Error: Could not determine script name.")
            return False

        if any(s.get('name') == script_dir_name for s in self.scripts_data):
            if is_community_script:
                if not messagebox.askyesno("Script Exists", f"The script '{script_dir_name}' already exists. Add anyway?"):
                    self.status_bar.configure(text=f"Skipped adding existing script: {script_dir_name}")
                    return False
            else:
                messagebox.showerror("Duplicate Script", f"A script named '{script_dir_name}' already exists.")
                self.status_bar.configure(text=f"Error: Script '{script_dir_name}' already exists.")
                return False

        try:
            author_name = self._get_author_from_url(cleaned_repo_url)
            script_name = script_dir_name

            if category == "Programs":
                final_local_path = os.path.join(local_path, "Programs", script_name)
            else:
                final_local_path = os.path.join(local_path, script_name)

            if os.path.exists(final_local_path):
                if not messagebox.askyesno("Directory Exists", f"The target directory '{final_local_path}' already exists. Overwrite?"):
                    self.status_bar.configure(text=f"Skipped adding script to existing directory: {script_dir_name}")
                    return False
            
            self.status_bar.configure(text=f"Adding '{script_dir_name}' from {cleaned_repo_url}...")
            self.update_idletasks()

            download_success, download_message, final_actual_local_path = github_handler.perform_update(
                cleaned_repo_url,
                folder_path_cleaned,
                final_local_path,
                category,
                branch=None
            )

            if download_success:
                latest_sha = github_handler.get_latest_commit_sha(cleaned_repo_url)
                determined_status = 'Up to date'
                if not latest_sha:
                    print(f"[WARNING] Could not retrieve latest commit SHA for {cleaned_repo_url}. Status will be 'Unknown'.")
                    determined_status = 'Unknown (fetch error)'

                script_info = {
                    "name": script_dir_name,
                    "repo_url": cleaned_repo_url,
                    "folder_path": folder_path_cleaned,
                    "local_path": final_actual_local_path,
                    "category": category,
                    "current_version_sha": latest_sha,
                    "latest_version_sha": latest_sha,
                    "last_checked": datetime.datetime.now().isoformat(),
                    "status": determined_status
                }

                config_manager.add_script_to_config(script_info)
                self.scripts_data = [s for s in self.scripts_data if s.get('name') != script_dir_name]
                self.scripts_data.append(script_info)
                self.refresh_scripts_display()
                self.status_bar.configure(text=f"Script '{script_dir_name}' added successfully.")
                return True
            else:
                messagebox.showerror("Add Script Error", f"Failed to add script '{script_dir_name}': {download_message}")
                self.status_bar.configure(text=f"Failed to add script '{script_dir_name}'.")
                return False

        except Exception as e_overall:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Unexpected Error", f"Unexpected error adding '{script_dir_name}': {e_overall}\nDetails:\n{error_details}")
            self.status_bar.configure(text="Unexpected error during script addition.")
            print(f"[ERROR] Unexpected error in _perform_add_script for '{script_dir_name}': {e_overall}\n{error_details}")

        return False

    def add_script(self):
        repo_url = self.entry_repo_url.get()
        folder_path = self.entry_folder_path.get()
        local_path = self.entry_local_path.get()
        
        # Show category selection dialog instead of using current tab
        if self.show_category_selection_dialog(repo_url, folder_path, local_path):
            self.entry_repo_url.delete(0, tk.END)
            self.entry_folder_path.delete(0, tk.END)
            # Keep the local path for convenience
            # Save the used local path as the new default
            self.settings['last_local_path'] = local_path
            config_manager.save_settings(self.settings)

    def update_selected_scripts(self):
        selected_scripts_data = []
        for item in self.script_widgets:
            # Access the IntVar associated with the checkbox using 'checkbox_var'
            if 'checkbox_var' in item and item['checkbox_var'].get() == 1:
                selected_scripts_data.append(item['script_data'])

        if not selected_scripts_data:
            messagebox.showinfo("No Scripts Selected", "Please select at least one script to update.")
            return

        self.status_bar.configure(text="Starting update process...")
        self.update_idletasks()
        
        updated_count = 0
        up_to_date_count = 0
        error_count = 0

        for script_data_ref in selected_scripts_data: # script_data_ref is a reference to an item in self.scripts_data
            script_name = script_data_ref.get('name', 'Unknown Script')
            self.status_bar.configure(text=f"Checking {script_name} for updates...")
            self.update_idletasks()

            try:
                latest_remote_sha = github_handler.get_latest_commit_sha(script_data_ref['repo_url'])
                current_local_sha = script_data_ref.get('current_version_sha')

                if not latest_remote_sha:
                    messagebox.showerror("Update Error", f"Could not fetch latest version for {script_name}. Skipping.")
                    error_count += 1
                    continue

                script_data_ref['last_checked'] = datetime.datetime.now().isoformat() # Update last_checked time

                if latest_remote_sha != current_local_sha:
                    self.status_bar.configure(text=f"Update available for {script_name}. Downloading...")
                    self.update_idletasks()
                    
                    # Archive current version before updating
                    current_sha_for_archive = current_local_sha if current_local_sha else "unknown"
                    archive_success = github_handler.archive_current_version(script_data_ref['local_path'], current_sha_for_archive)
                    if not archive_success:
                        logger.warning(f"Failed to archive current version of {script_name} before update")
                    
                    download_success, message, final_script_path = github_handler.perform_update(
                        script_data_ref['repo_url'], 
                        script_data_ref['folder_path'], 
                        script_data_ref['local_path'], 
                        script_data_ref['category'], 
                        branch=None
                    )

                    if download_success:
                        script_data_ref['current_version_sha'] = latest_remote_sha
                        script_data_ref['latest_version_sha'] = latest_remote_sha # Ensure latest_version_sha is also updated
                        script_data_ref['local_path'] = final_script_path # Update path if restructuring changed it
                        script_data_ref['name'] = os.path.basename(final_script_path) if final_script_path else script_name # Update name based on final path
                        script_data_ref['status'] = "Up to date"  # Set status to Up to date
                        script_data_ref['update_status_indicator'] = 'uptodate' # Sync indicator
                        updated_count += 1
                        self.status_bar.configure(text=f"{script_name} updated successfully.")
                        logger.info(f"{script_name} updated to SHA {latest_remote_sha}. New path: {final_script_path}")
                    else:
                        messagebox.showerror("Update Error", f"Failed to download update for {script_name}: {message}")
                        error_count += 1
                else: # SHAs match
                    script_data_ref['status'] = "Up to date"  # Set status to Up to date
                    script_data_ref['latest_version_sha'] = latest_remote_sha # Ensure latest_version_sha reflects current SHA
                    script_data_ref['update_status_indicator'] = 'uptodate' # Sync indicator
                    self.status_bar.configure(text=f"{script_name} is up to date.")
                    up_to_date_count += 1
                    print(f"[INFO] {script_name} is up to date (SHA: {current_local_sha[:7]}).")
            
            except Exception as e:
                messagebox.showerror("Update Error", f"An error occurred while updating {script_name}: {e}")
                error_count += 1
                print(f"[ERROR] Updating {script_name}: {e}")
            finally:
                self.update_idletasks()

        config_manager.save_scripts_config(self.scripts_data) # Save all changes to timestamps, SHAs, paths, etc.
        self.refresh_scripts_display() # Refresh the UI to show new names, etc.

        # Final summary message
        summary_message = f"Update process complete. Updated: {updated_count}, Up to date: {up_to_date_count}, Errors: {error_count}."
        self.status_bar.configure(text=summary_message)
        messagebox.showinfo("Update Complete", summary_message)

    def _on_managed_tab_change(self, selected_tab_name: str = None):
        """Called when the selected tab in the managed scripts view changes."""
        # Since we now use a category selection dialog, the Add Script button is always enabled
        # This method can be simplified or removed, but keeping it for potential future use
        pass

    def refresh_scripts_display(self, filter_text=""):
        # Clear existing widgets from all tab frames
        for tab_name, scrollable_frame in self.managed_tab_scrollable_frames.items():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
        self.script_widgets.clear()

        if not self.scripts_data:
            # Display message in 'All' tab if no scripts at all
            if "All" in self.managed_tab_scrollable_frames:
                all_frame = self.managed_tab_scrollable_frames["All"]
                if all_frame: # Ensure frame exists
                    ctk.CTkLabel(all_frame, text="No scripts managed yet.").pack(pady=10)
            # Display message in other category tabs
            for category, frame in self.managed_tab_scrollable_frames.items():
                if category != "All": # Check if frame exists before trying to pack into it
                    if frame: # Ensure frame is not None
                        ctk.CTkLabel(frame, text=f"No scripts found for {category}.").pack(pady=10)
            self.on_checkbox_toggle() # Update button states even if no scripts
            return

        status_order = {
            'available': 0,
            'check_failed': 1,
            'uptodate': 2,
            'Up to date': 2, # To handle older status values if any
            'Unknown (fetch error)': 3,
            'Unknown': 3,
            None: 4 # Should ideally not happen if status is always set
        }

        def get_sort_key(script):
            primary_status = script.get('update_status_indicator')
            secondary_status = script.get('status')
            # Prioritize update_status_indicator if available, otherwise use status
            chosen_status_for_sort = primary_status if primary_status is not None else secondary_status
            return (status_order.get(chosen_status_for_sort, 99), script.get('name', '').lower())

        try:
            # Sort scripts_data in place
            self.scripts_data.sort(key=get_sort_key)
        except Exception as e:
            print(f"[Error] Could not sort managed scripts: {e}")
            # Optionally, inform the user via status bar or messagebox

        # Filter scripts based on search text
        filtered_scripts = self.scripts_data
        if filter_text:
            filtered_scripts = [script for script in self.scripts_data 
                              if filter_text in script.get('name', '').lower()]

        scripts_added_to_category_tabs = {cat: False for cat in self.managed_script_categories if cat != "All"}

        for script_data_item in filtered_scripts: # Iterate over the filtered list
            checkbox_var = ctk.IntVar(value=0) # Default to unchecked

            self.script_widgets.append({
                'checkbox_var': checkbox_var,
                'script_data': script_data_item
            })

            # Create entry in 'All' tab
            all_tab_frame = self.managed_tab_scrollable_frames.get("All")
            if all_tab_frame:
                self._create_script_entry_ui(all_tab_frame, script_data_item, checkbox_var)

            # Create entry in specific category tab
            script_category = script_data_item.get('category', 'Utilities') # Default to Utilities
            category_tab_frame = self.managed_tab_scrollable_frames.get(script_category)

            if category_tab_frame and script_category != "All":
                self._create_script_entry_ui(category_tab_frame, script_data_item, checkbox_var)
                scripts_added_to_category_tabs[script_category] = True
            elif script_category != "All": # Only print warning if it's not 'All' and tab doesn't exist
                print(f"[WARNING] Managed script '{script_data_item.get('name')}' has unrecognized category '{script_category}'. Not adding to a specific category tab.")

        # For any category tab (not 'All') that didn't get any scripts, add a placeholder label
        for category, was_populated in scripts_added_to_category_tabs.items():
            if not was_populated:
                parent_frame = self.managed_tab_scrollable_frames.get(category)
                if parent_frame: # Ensure frame exists
                    ctk.CTkLabel(parent_frame, text=f"No scripts found for {category}.").pack(pady=10)
        
        self.on_checkbox_toggle()

    def _create_script_entry_ui(self, parent_container, script_data_item, shared_checkbox_var):
        entry_frame = ctk.CTkFrame(parent_container)
        entry_frame.pack(fill="x", pady=2, padx=2)

        checkbox = ctk.CTkCheckBox(entry_frame, text="", width=20, variable=shared_checkbox_var, command=self.on_checkbox_toggle)
        checkbox.grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="ns")

        status_indicator = script_data_item.get('update_status_indicator')
        initial_status = script_data_item.get('status', 'Unknown') # Fallback to 'status'
        status_text = ""
        if status_indicator == 'available':
            status_text = "🔄 Update Available"
        elif status_indicator == 'uptodate':
            status_text = "✅ Up to date"
        elif status_indicator == 'check_failed':
            status_text = "⚠️ Check Failed"
        else: # Fallback logic if update_status_indicator is not one of the expected values
            if initial_status == 'Up to date': # Check initial_status as well
                status_text = f"✅ {initial_status}"
            elif initial_status == 'Unknown (fetch error)':
                status_text = f"❔ {initial_status}"
            elif initial_status == 'Unknown':
                 status_text = f"❔ {initial_status}"
            elif initial_status: # Catch any other non-empty status
                status_text = f"ℹ️ {initial_status}"
            else: # Default if both are uninformative
                status_text = "❔ Status Unknown"
        
        script_display_name = script_data_item.get('name', 'N/A')
        if script_data_item.get('folder_path'): # Append folder_path if it exists
            script_display_name += f" ({script_data_item['folder_path']})"
        label_name = ctk.CTkLabel(entry_frame, text=script_display_name, anchor="w", font=ctk.CTkFont(weight="bold"))
        label_name.grid(row=0, column=1, sticky="w", padx=5)

        label_status = ctk.CTkLabel(entry_frame, text=status_text, anchor="e") # Removed bold for now, can be added back if desired
        label_status.grid(row=0, column=2, sticky="e", padx=5)

        repo_url = script_data_item.get('repo_url')
        author_name = self._get_author_from_url(repo_url)
        if not author_name: author_name = "N/A" # Ensure author_name is not None
        label_author = ctk.CTkLabel(entry_frame, text=f"Author: {author_name}", anchor="w", font=ctk.CTkFont(size=10))
        label_author.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)

        entry_frame.columnconfigure(0, weight=0) # Checkbox column
        entry_frame.columnconfigure(1, weight=1) # Name and Author column (stretchy)
        entry_frame.columnconfigure(2, weight=0) # Status column
        
        # No return needed as it modifies parent_container directly, but good practice to return frame if used
        return entry_frame

    def _create_community_script_entry_ui(self, parent_container, script_info, shared_checkbox_var, is_managed):
        """Creates UI elements for a single community script entry in a given tab."""
        item_frame = ctk.CTkFrame(parent_container)
        item_frame.pack(fill="x", pady=2, padx=2)

        # Configure grid columns for item_frame
        item_frame.columnconfigure(0, weight=0)  # Checkbox column
        item_frame.columnconfigure(1, weight=1)  # Text content column

        display_text = script_info.get("displayText", "Unnamed Script")
        repo_url = script_info.get('repo_url')
        # folder_path = script_info.get('folder_path') # Not directly used here but part of script identity

        current_display_text_for_label = display_text
        checkbox_state = "normal"
        text_color_for_label = None  # Default/theme color

        if is_managed:
            current_display_text_for_label += " (Added)"
            checkbox_state = "disabled"
            text_color_for_label = "gray70"  # Set text color to gray for managed scripts

        checkbox = ctk.CTkCheckBox(
            item_frame,
            text="",  # Text will be handled by a separate label for better layout control
            variable=shared_checkbox_var,
            onvalue=1,
            offvalue=0,
            command=self.on_community_checkbox_toggle,
            state=checkbox_state
        )
        # Checkbox spans two rows to align with display text and author text
        checkbox.grid(row=0, column=0, rowspan=2, padx=(5, 0), pady=2, sticky="w")

        label_display_text = ctk.CTkLabel(item_frame, text=current_display_text_for_label, anchor="w", text_color=text_color_for_label)
        label_display_text.grid(row=0, column=1, padx=(2, 5), pady=(2, 0), sticky="ew")

        author_name = self._get_author_from_url(repo_url)
        if not author_name:  # Fallback if author can't be parsed
            author_name = "N/A"

        label_author = ctk.CTkLabel(item_frame, text=f"Author: {author_name}", anchor="w", font=ctk.CTkFont(size=10))
        label_author.grid(row=1, column=1, padx=(2, 5), pady=(0, 2), sticky="ew")

        return item_frame

    def on_checkbox_toggle(self):
        """Called when a script checkbox is toggled. Updates action button states."""
        selected_count = 0
        if hasattr(self, 'script_widgets') and self.script_widgets:
            # Ensure item['checkbox_var'] exists and is not None before calling get()
            selected_count = sum(1 for item in self.script_widgets if item.get('checkbox_var') and item['checkbox_var'].get() == 1)
        
        # State for Update and Delete buttons
        action_button_state = "normal" if selected_count > 0 else "disabled"
        if hasattr(self, 'button_update_selected'): self.button_update_selected.configure(state=action_button_state)
        if hasattr(self, 'button_delete_selected'): self.button_delete_selected.configure(state=action_button_state)

        # State for GitHub button and Manage Versions button (both require exactly one selection)
        single_selection_state = "normal" if selected_count == 1 else "disabled"
        if hasattr(self, 'button_open_github'): # Check if button exists
            self.button_open_github.configure(state=single_selection_state)
        if hasattr(self, 'button_manage_versions'): # Check if button exists
            self.button_manage_versions.configure(state=single_selection_state)

    def process_queue(self):
        """Processes messages from the worker thread queue to update the UI."""
        try:
            message = self.update_queue.get_nowait()
            if isinstance(message, list): # Expected: list of script_data dicts
                print("[INFO] Received updated script data from worker thread.")
                self.scripts_data = message
                config_manager.save_scripts_config(self.scripts_data) # Persist the new statuses
                self.refresh_scripts_display()
                self.status_bar.configure(text="Startup update check complete.")
                print("[INFO] UI updated and startup check complete.")
            elif isinstance(message, str): # For simple status messages or errors from worker
                self.status_bar.configure(text=message)
                print(f"[INFO] Worker thread message: {message}")
            # Add handling for other message types if necessary
        except queue.Empty:
            pass # No message in queue, continue polling
        except Exception as e:
            print(f"[ERROR] Error processing queue: {e}")
        finally:
            # Check again after 100ms
            self.after(100, self.process_queue)

    @staticmethod
    def perform_startup_update_check_worker(scripts_data, q):
        """
        Worker function to be run in a separate thread.
        Checks all scripts for updates without blocking the UI.
        """
        print("[INFO] Worker thread started: Performing startup update check.")
        
        for script_data in scripts_data:
            script_name = script_data.get('name', 'Unknown Script')
            try:
                latest_remote_sha = github_handler.get_latest_commit_sha(script_data['repo_url'])
                current_local_sha = script_data.get('current_version_sha')
                script_data['last_checked'] = datetime.datetime.now().isoformat()

                if latest_remote_sha:
                    if current_local_sha is None:
                        script_data['update_status_indicator'] = 'available'
                    elif latest_remote_sha != current_local_sha:
                        script_data['update_status_indicator'] = 'available'
                    else:
                        script_data['update_status_indicator'] = 'uptodate'
                else:
                    script_data['update_status_indicator'] = 'check_failed'
            except Exception as e:
                script_data['update_status_indicator'] = 'check_failed'
                print(f"[ERROR] Worker thread: An unexpected error occurred while checking {script_name}: {e}")

        print("[INFO] Worker thread finished. Placing result in queue.")
        q.put(scripts_data)

    def delete_selected_script(self):
        selected_scripts_data = []
        for item in self.script_widgets:
            if item.get('checkbox_var') and item['checkbox_var'].get() == 1:
                selected_scripts_data.append(item['script_data'])

        if not selected_scripts_data:
            messagebox.showinfo("No Selection", "Please select at least one script to delete.")
            return

        confirm_delete = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {len(selected_scripts_data)} selected script(s)? This will remove local files.")
        if not confirm_delete:
            return

        deleted_count = 0
        scripts_to_keep = list(self.scripts_data) # Create a copy to modify

        for script_data_to_delete in selected_scripts_data:
            self.status_bar.configure(text=f"Deleting {script_data_to_delete.get('name', 'script')}...")
            self.update_idletasks()
            try:
                if os.path.exists(script_data_to_delete['local_path']):
                    shutil.rmtree(script_data_to_delete['local_path'])
                    print(f"Successfully deleted local directory: {script_data_to_delete['local_path']}")
                else:
                    print(f"Local directory not found, skipping deletion: {script_data_to_delete['local_path']}")
                
                # Attempt to remove from config file
                removed_from_config = config_manager.remove_script_from_config(script_data_to_delete)
                
                # Attempt to remove from in-memory list (which updates the UI upon refresh)
                removed_from_memory = False
                if script_data_to_delete in scripts_to_keep:
                    scripts_to_keep.remove(script_data_to_delete)
                    removed_from_memory = True
                
                if removed_from_memory:
                    deleted_count += 1
                    if not removed_from_config:
                        # Log that it wasn't in config, but UI cleanup is done, so no error to user.
                        print(f"Info: Script '{script_data_to_delete.get('name', 'script')}' was removed from UI but was not found in the configuration file (possibly already removed).")
                else:
                    # This case means the script selected in UI was not found in the internal self.scripts_data list.
                    # This would be an unexpected state.
                    messagebox.showerror("Internal Error", f"Could not remove script '{script_data_to_delete.get('name', 'script')}' from the application's internal list. Please restart the application.")
            except Exception as e:
                messagebox.showerror("Deletion Error", f"Error deleting script {script_data_to_delete.get('name', 'script')}: {e}")
    
        self.scripts_data = scripts_to_keep # Update the main data list
        config_manager.save_scripts_config(self.scripts_data) # Save the updated list to the config file
        self.refresh_scripts_display()
        self.populate_community_script_tabs() # Refresh community scripts view
        if deleted_count > 0:
            messagebox.showinfo("Deletion Complete", f"Successfully deleted {deleted_count} script(s).")
        self.status_bar.configure(text="Deletion process finished.")

    def open_script_github_page(self):
        selected_scripts_data = [
            widget_info['script_data'] 
            for widget_info in self.script_widgets 
            if widget_info.get('checkbox_var') and widget_info['checkbox_var'].get() == 1
            if widget_info['checkbox'].get() == 1
        ]
        if len(selected_scripts_data) == 1:
            script = selected_scripts_data[0]
            repo_url = script.get('repo_url')
            if repo_url:
                # Basic validation to ensure it's a github.com URL
                if "github.com" in repo_url and repo_url.startswith("https://"):
                    webbrowser.open_new_tab(repo_url)
                else:
                    messagebox.showwarning("Invalid URL", f"The URL '{repo_url}' does not appear to be a valid GitHub HTTPS URL.")
            else:
                messagebox.showwarning("GitHub URL Missing", "The selected script does not have a GitHub URL configured.")
        elif len(selected_scripts_data) > 1:
            messagebox.showinfo("Select One Script", "Please select only one script to open its GitHub page.")
        # If no scripts are selected, the button should be disabled by on_checkbox_toggle, 
        # so no explicit message needed here if len is 0.

    def show_community_view(self):
        if self.current_view == "community":
            return
        self.current_view = "community"

        self.managed_scripts_tab_view.pack_forget()

        # Hide specific input fields, keep Local Save Directory
        self.label_repo_url.grid_remove()
        self.entry_repo_url.grid_remove()
        self.label_folder_path.grid_remove()
        self.entry_folder_path.grid_remove()
        self.button_add_script.grid_remove() # Hide the main "Add Script" button from input_frame

        self.community_tab_view.pack(pady=5, padx=5, fill="both", expand=True)

        # Configure bottom action buttons for community view
        self.button_update_selected.configure(text="Add Selected Scripts", command=self.add_community_script)
        self.button_update_selected.pack(side="left", padx=5, before=self.button_open_github) # Ensure packed and order

        self.button_open_github.pack(side="left", padx=5) # Ensure GitHub button is packed

        self.button_delete_selected.pack_forget() # Hide delete button

        # Repurpose button_show_community_view to be "Return to Home"
        self.button_show_community_view.configure(text="Return to Home", command=self.show_main_view)
        self.button_show_community_view.pack(side="right", padx=5) # Ensure packed and on the right

        self.on_community_checkbox_toggle() # Update button state

    def show_main_view(self):
        if self.current_view == "main":
            return
        self.current_view = "main"

        self.community_tab_view.pack_forget()
        self.managed_scripts_tab_view.pack(pady=5, padx=5, fill="both", expand=True)

        # Restore specific input fields
        self.label_repo_url.grid()
        self.entry_repo_url.grid()
        self.label_folder_path.grid()
        self.entry_folder_path.grid()
        self.button_add_script.grid() # Restore the main "Add Script" button
        self.button_add_script.configure(text="Add Script", command=self.add_script) # Restore its original config

        # Restore bottom action buttons for main view
        self.button_update_selected.configure(text="Update Selected", command=self.update_selected_scripts)
        self.button_update_selected.pack(side="left", padx=5, before=self.button_open_github) # Ensure packed and order

        self.button_open_github.pack(side="left", padx=5) # Ensure GitHub button is packed

        self.button_delete_selected.pack(side="left", padx=5, before=self.button_show_community_view) # Ensure packed and order

        self.button_show_community_view.configure(text="Community Scripts", command=self.show_community_view)
        self.button_show_community_view.pack(side="right", padx=5)

        self.on_checkbox_toggle() # Refresh state of main view buttons

    def load_community_scripts_config(self):
        config_path = resource_path("community_scripts.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load community scripts config: {e}")
                return []
        return []

    def _is_script_managed(self, community_repo_url, community_folder_path):
        """Checks if a community script (identified by repo_url and folder_path) is already managed."""
        # Normalize folder_path for comparison (treat None and empty string as same for root)
        normalized_community_folder_path = community_folder_path if community_folder_path else ""

        for managed_script in self.scripts_data:
            managed_repo_url = managed_script.get('repo_url')
            managed_folder_path = managed_script.get('folder_path')
            # Normalize folder_path from managed_script as well
            normalized_managed_folder_path = managed_folder_path if managed_folder_path else ""

            if managed_repo_url == community_repo_url and \
               normalized_managed_folder_path == normalized_community_folder_path:
                return True
        return False

    def populate_community_script_tabs(self):
        # Clear existing widgets from all tab frames and reset shared vars
        for scrollable_frame in self.tab_frames.values():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
        self.community_script_checkbox_vars.clear()
        for category_key in self.community_script_widgets_by_tab:
            self.community_script_widgets_by_tab[category_key].clear()

        if not self.community_scripts_data:
            # Display message in 'All' tab if no scripts at all
            if "All" in self.tab_frames:
                all_frame = self.tab_frames["All"]
                if all_frame: # Ensure frame exists
                    ctk.CTkLabel(all_frame, text="No community scripts available.").pack(pady=10)
            # Display message in other category tabs
            for category, frame in self.tab_frames.items():
                if category != "All": # Check if frame exists before trying to pack into it
                    if frame: # Ensure frame is not None
                        ctk.CTkLabel(frame, text=f"No community scripts found for {category}.").pack(pady=10)
            return

        # Sort community scripts alphabetically by displayText
        try:
            self.community_scripts_data.sort(key=lambda x: x.get('displayText', '').lower())
        except Exception as e:
            print(f"[Error] Could not sort community scripts: {e}")
            # Optionally, inform the user via status bar or messagebox if sorting fails catastrophically

        scripts_added_to_category_tabs = {cat: False for cat in self.community_script_categories if cat != "All"}

        for script_info in self.community_scripts_data:
            repo_url = script_info.get('repo_url')
            folder_path = script_info.get('folder_path', '') # Ensure default for key creation
            script_key = (repo_url, folder_path)

            is_managed = self._is_script_managed(repo_url, folder_path)
            initial_checkbox_value = 1 if is_managed else 0
            
            # Get or create the shared checkbox variable
            if script_key not in self.community_script_checkbox_vars:
                shared_checkbox_var = ctk.IntVar(value=initial_checkbox_value)
                self.community_script_checkbox_vars[script_key] = shared_checkbox_var
            else:
                shared_checkbox_var = self.community_script_checkbox_vars[script_key]
                # Ensure its state reflects current managed status, in case it changed without a full refresh
                if shared_checkbox_var.get() != initial_checkbox_value:
                     shared_checkbox_var.set(initial_checkbox_value) 

            # Create entry in 'All' tab
            all_tab_frame = self.tab_frames.get("All")
            if all_tab_frame:
                entry_frame_all = self._create_community_script_entry_ui(all_tab_frame, script_info, shared_checkbox_var, is_managed)
                # Store widget info for 'All' tab
                self.community_script_widgets_by_tab["All"].append({
                    'script_data': script_info,
                    'frame': entry_frame_all, 
                    'checkbox_var': shared_checkbox_var
                })

            # Create entry in specific category tab
            category = script_info.get("category", "Utilities") # Default to Utilities if not specified
            category_tab_frame = self.tab_frames.get(category)
            if category_tab_frame and category != "All":
                entry_frame_cat = self._create_community_script_entry_ui(category_tab_frame, script_info, shared_checkbox_var, is_managed)
                scripts_added_to_category_tabs[category] = True
                # Store widget info for category tab
                self.community_script_widgets_by_tab[category].append({
                    'script_data': script_info,
                    'frame': entry_frame_cat,
                    'checkbox_var': shared_checkbox_var
                })
            elif category != "All": # Only print warning if it's not 'All' and tab doesn't exist
                print(f"[Warning] Community script '{script_info.get('displayText')}' has unknown category '{category}'. Not adding to a specific category tab.")

        # For any category tab (not 'All') that didn't get any scripts, add a placeholder label
        for category, was_populated in scripts_added_to_category_tabs.items():
            if not was_populated:
                parent_frame = self.tab_frames.get(category)
                if parent_frame: # Ensure frame exists
                    ctk.CTkLabel(parent_frame, text=f"No community scripts found for {category}.").pack(pady=10)

        self.on_community_checkbox_toggle() # Update button states after populating

    def on_community_checkbox_toggle(self):
        any_selected = False
        for category_key, category_widgets in self.community_script_widgets_by_tab.items():
            for item in category_widgets:
                if isinstance(item, dict) and 'checkbox_var' in item and item['checkbox_var'] is not None:
                    if item['checkbox_var'].get() == 1:
                        any_selected = True
                        break
                else:
                    print(f"[DEBUG] on_community_checkbox_toggle: Malformed item in category '{category_key}': {item}")
            if any_selected:
                break
        
        if self.current_view == "community":
            if any_selected:
                self.button_update_selected.configure(state="normal")
            else:
                self.button_update_selected.configure(state="disabled")

    def add_community_script(self):
        scripts_to_process = []
        added_count = 0
        failed_count = 0
        failed_or_skipped_vars = [] # Stores IntVars of scripts that failed or were skipped

        if not hasattr(self, 'community_scripts_data') or not self.community_scripts_data:
            messagebox.showinfo("No Scripts", "No community scripts loaded.")
            return

        # Identify selected and unmanaged scripts
        for script_info_item in self.community_scripts_data:
            repo_url = script_info_item.get('repo_url')
            folder_path = script_info_item.get('folder_path', '')
            script_key = (repo_url, folder_path)
            
            shared_var = self.community_script_checkbox_vars.get(script_key)
            if shared_var and shared_var.get() == 1: # If checkbox is selected
                if not self._is_script_managed(repo_url, folder_path): # And script is not already managed
                    scripts_to_process.append({'script_data': script_info_item, 'var': shared_var})
        
        if not scripts_to_process:
            messagebox.showinfo("No Actionable Selection", "Please select one or more new community scripts to add.\n(Note: Already added scripts or those with issues cannot be re-added this way.)")
            return

        local_save_dir = self.entry_local_path.get().strip()
        if not local_save_dir:
            messagebox.showerror("Error", "Local Save Directory is required. Please specify it in the main view first.")
            self.show_main_view()
            self.entry_local_path.focus_set()
            self.status_bar.configure(text="Error: Local Save Directory for community scripts not set.")
            return
        
        if not os.path.isdir(local_save_dir):
            if messagebox.askyesno("Create Directory?", f"The local save directory '{local_save_dir}' does not exist. Would you like to create it?"):
                try:
                    os.makedirs(local_save_dir, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not create directory '{local_save_dir}': {e}")
                    return
            else:
                self.status_bar.configure(text="Community script addition cancelled: Local directory not created.")
                return 

        # Process each selected script
        for item_to_process in scripts_to_process:
            script_info = item_to_process['script_data']
            shared_var_for_item = item_to_process['var'] 

            repo_url = script_info.get('repo_url')
            folder_path = script_info.get('folder_path', '') 
            name_override = script_info.get('name_override')
            original_display_text = script_info.get('displayText', 'Unknown Script') 
            script_category = script_info.get('category')
            if not script_category:
                print(f"[WARNING] Community script '{original_display_text}' is missing a category. Defaulting to 'Utilities'.")
                script_category = "Utilities"

            self.status_bar.configure(text=f"Attempting to add community script: {original_display_text}...")
            self.update_idletasks()

            if self._perform_add_script(repo_url, folder_path, local_save_dir, script_category, script_name_override=name_override, is_community_script=True):
                added_count += 1
                # UI for this specific script will be updated by populate_community_script_tabs
            else:
                failed_count += 1
                failed_or_skipped_vars.append(shared_var_for_item)
            self.update_idletasks() # For status bar updates per item

        # Uncheck scripts that failed or were skipped
        for var_to_uncheck in failed_or_skipped_vars:
            if var_to_uncheck:
                var_to_uncheck.set(0)

        # Refresh UIs if changes were made
        if added_count > 0:
            self.refresh_scripts_display()      # Refresh managed scripts view
            self.populate_community_script_tabs() # Refresh community scripts view to show 'Added' status & disable checkboxes
        elif failed_or_skipped_vars: # If only failures/skips, still need to update community tab for unchecking
             self.populate_community_script_tabs() 
        
        self.on_community_checkbox_toggle() # Always refresh button state based on current selections

        # Prepare and show summary message
        summary_parts = []
        if added_count > 0:
            summary_parts.append(f"Successfully added {added_count} community script(s).")
        if failed_count > 0:
            summary_parts.append(f"{failed_count} community script(s) failed to add or were skipped.")
        
        if not summary_parts and scripts_to_process: # If items were selected but none resulted in add/fail (e.g. all skipped by user choice in _perform_add_script)
             summary_parts.append("No new scripts were added. Check status messages for details.")
        # No need for 'elif not scripts_to_process' as it's covered by the early return

        if summary_parts:
            messagebox.showinfo("Community Scripts Processing Complete", "\n".join(summary_parts))
        
        final_status_text = "Community script processing finished."
        if added_count == 0 and failed_count == 0 and scripts_to_process: 
            final_status_text = "Community scripts processed; no changes made (e.g., all skipped or already exist)."
        self.status_bar.configure(text=final_status_text)

    def toggle_debug_mode(self):
        """Toggle debug mode and update logger."""
        debug_enabled = self.debug_mode_var.get()
        config_manager.set_debug_mode(debug_enabled)
        
        # Reconfigure the logger with the new debug setting
        setup_logger(debug_enabled)
        
        status_text = "Debug mode enabled" if debug_enabled else "Debug mode disabled"
        self.status_bar.configure(text=status_text)
        logger.info(status_text)

    def on_update_method_changed(self, selected_method):
        """Handle update method change."""
        config_manager.set_update_method(selected_method)
        status_text = f"Update method changed to: {selected_method}"
        self.status_bar.configure(text=status_text)
        logger.info(status_text)

    def save_github_token(self):
        """Save the GitHub personal access token."""
        token = self.entry_github_token.get().strip()
        config_manager.set_github_token(token)
        
        if token:
            logger.info("GitHub token saved successfully")
            self.status_bar.configure(text="GitHub token saved - API rate limit increased to 5,000/hour")
            messagebox.showinfo("Token Saved", "GitHub token saved successfully!\nAPI rate limit increased to 5,000 requests/hour.")
        else:
            logger.info("GitHub token cleared")
            self.status_bar.configure(text="GitHub token cleared - using unauthenticated API (60/hour)")
            messagebox.showinfo("Token Cleared", "GitHub token cleared.\nUsing unauthenticated API (60 requests/hour).")

    def clear_github_token(self):
        """Clear the GitHub personal access token."""
        self.entry_github_token.delete(0, tk.END)
        config_manager.set_github_token("")
        logger.info("GitHub token cleared")
        self.status_bar.configure(text="GitHub token cleared - using unauthenticated API (60/hour)")
        messagebox.showinfo("Token Cleared", "GitHub token cleared.\nUsing unauthenticated API (60 requests/hour).")

    def show_help(self):
        """Display help instructions in a popup window."""
        help_text = """How to Use the Script Updater

Automatic Application Updates:
• The application automatically checks for new versions of itself when you start it.
• If a new version is found, you will be prompted to download and install it.

Adding a Script:
1. Paste the full GitHub repository URL (e.g., https://github.com/user/repo).
2. (Optional) Specify a folder path within the repository. If left blank, the whole repository is downloaded.
3. Click "Browse" to choose where to save the script on your computer.
4. Click "Add Script" and select a category for your script.

Managing Scripts:
• Check the box next to one or more scripts to enable the action buttons.
• The application automatically checks for updates on startup. A green "Update Available" label will appear for scripts that can be updated.

Update Methods:
• Overwrite: Completely replaces all files with the new version (original behavior).
• Differential: Only updates files that have actually changed, preserving unchanged files and any custom modifications.
• Use the "Update Method" dropdown in the top-right to switch between methods.
• Differential updates are faster and preserve user customizations, but overwrite ensures a clean installation.

Action Buttons:
• Update Selected: Downloads and installs the latest version of checked scripts using your selected update method. Previous versions are automatically archived.
• GitHub: Opens the GitHub repository page for the selected script in your web browser (requires exactly one script selected).
• Delete Selected: Removes the checked scripts from management and deletes their local files.
• Manage Versions: View and restore previous versions of a script (requires exactly one script selected).

Community Scripts:
• Click the "Community Scripts" button to browse a curated list of scripts.
• Check the ones you want and click "Add Selected to Managed" to download them.

Search and Filter:
• Use the "Filter scripts..." box to quickly find specific scripts in your managed list.

Debug Mode:
• Enable "Debug Mode" to create detailed logs in app.log for troubleshooting.
• Disable it during normal use to avoid creating large log files.
• Debug mode applies to all application functions and shows detailed update progress.

GitHub Token (Optional):
• Add your GitHub Personal Access Token to increase API rate limits from 60 to 5,000 requests/hour.
• Create a token at: https://github.com/settings/tokens (no special permissions needed).
• Token format: ghp_xxxxxxxxxxxxxxxxxxxx
• Click "Save Token" to store it securely in your settings.

Version Management:
• When you update a script, the old version is automatically saved in an "Older Versions" folder.
• Select a single script and click "Manage Versions" to view and restore previous versions.
• The "Older Versions" folder is always preserved during updates regardless of update method."""

        # Create a new window for help
        help_window = ctk.CTkToplevel(self)
        help_window.title("Help - Script Updater")
        help_window.geometry("600x500")
        help_window.resizable(True, True)
        
        # Make it modal
        help_window.transient(self)
        help_window.grab_set()
        
        # Add text widget with proper wrapping
        text_widget = ctk.CTkTextbox(help_window, wrap="word")
        text_widget.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Insert the help text and make it read-only
        text_widget.insert("1.0", help_text)
        text_widget.configure(state="disabled")
        
        # Add close button
        close_button = ctk.CTkButton(help_window, text="Close", command=help_window.destroy)
        close_button.pack(pady=10)

    def on_search_changed(self, event=None):
        """Filter the managed scripts based on search text."""
        search_text = self.search_entry.get().lower().strip()
        self.refresh_scripts_display(filter_text=search_text)

    def show_category_selection_dialog(self, repo_url, folder_path, local_path):
        """Show a dialog to select category when adding a script."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Category")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        
        # Make it modal
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (200 // 2)
        dialog.geometry(f"400x200+{x}+{y}")
        
        # Variables to store result
        self.selected_category = None
        self.dialog_result = False
        
        # Content frame
        content_frame = ctk.CTkFrame(dialog)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Label
        label = ctk.CTkLabel(content_frame, text="Please select a category for this script:")
        label.pack(pady=(0, 10))
        
        # Category dropdown
        categories = ["Activities", "Class Rotations", "Programs", "Utilities"]
        category_var = ctk.StringVar(value="Utilities")
        category_dropdown = ctk.CTkOptionMenu(content_frame, variable=category_var, values=categories)
        category_dropdown.pack(pady=10)
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(content_frame)
        buttons_frame.pack(pady=(10, 0))
        
        def on_confirm():
            self.selected_category = category_var.get()
            self.dialog_result = True
            dialog.destroy()
        
        def on_cancel():
            self.dialog_result = False
            dialog.destroy()
        
        confirm_button = ctk.CTkButton(buttons_frame, text="Confirm", command=on_confirm)
        confirm_button.pack(side="left", padx=(0, 5))
        
        cancel_button = ctk.CTkButton(buttons_frame, text="Cancel", command=on_cancel)
        cancel_button.pack(side="left", padx=(5, 0))
        
        # Wait for dialog to close
        self.wait_window(dialog)
        
        if self.dialog_result and self.selected_category:
            # Proceed with adding the script
            return self._perform_add_script(repo_url, folder_path, local_path, self.selected_category)
        else:
            self.status_bar.configure(text="Script addition cancelled.")
            return False

    def show_version_management_window(self, script_data):
        """Show version management window for a selected script."""
        script_path = script_data.get('local_path')
        script_name = script_data.get('name', 'Unknown Script')
        
        if not script_path or not os.path.exists(script_path):
            messagebox.showerror("Error", "Script path not found or invalid.")
            return
        
        # Get available versions
        available_versions = github_handler.get_available_versions(script_path)
        
        # Create version management window
        version_window = ctk.CTkToplevel(self)
        version_window.title(f"Manage Versions - {script_name}")
        version_window.geometry("700x500")
        version_window.resizable(True, True)
        
        # Make it modal
        version_window.transient(self)
        version_window.grab_set()
        
        # Main frame
        main_frame = ctk.CTkFrame(version_window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text=f"Version History for: {script_name}", 
                                  font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=(0, 10))
        
        # Current version info
        current_frame = ctk.CTkFrame(main_frame)
        current_frame.pack(fill="x", pady=(0, 10))
        
        current_label = ctk.CTkLabel(current_frame, text="Current Version (Active)", 
                                   font=ctk.CTkFont(weight="bold"))
        current_label.pack(pady=5)
        
        if available_versions:
            # Versions list
            versions_frame = ctk.CTkFrame(main_frame)
            versions_frame.pack(fill="both", expand=True, pady=(0, 10))
            
            versions_label = ctk.CTkLabel(versions_frame, text="Available Previous Versions:", 
                                        font=ctk.CTkFont(weight="bold"))
            versions_label.pack(pady=(5, 0))
            
            # Scrollable frame for versions
            scrollable_frame = ctk.CTkScrollableFrame(versions_frame)
            scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            selected_version = ctk.StringVar()
            
            for version in available_versions:
                version_frame = ctk.CTkFrame(scrollable_frame)
                version_frame.pack(fill="x", pady=2)
                
                # Parse version info for better display
                display_text = version
                if "_from-github" in version:
                    display_text = version.replace("_from-github", " (GitHub Update)")
                elif "_before-restore" in version:
                    display_text = version.replace("_before-restore", " (Before Version Switch)")
                
                radio_button = ctk.CTkRadioButton(version_frame, text=display_text, 
                                                variable=selected_version, value=version)
                radio_button.pack(side="left", padx=10, pady=5)
            
            # Restore button
            def restore_selected_version():
                selected = selected_version.get()
                if not selected:
                    messagebox.showwarning("No Selection", "Please select a version to restore.")
                    return
                
                if messagebox.askyesno("Confirm Restore", 
                                     f"Are you sure you want to restore version '{selected}'?\n\n"
                                     "This will replace the current version with the selected one. "
                                     "The current version will be archived."):
                    
                    # Get current SHA if available
                    current_sha = script_data.get('current_version_sha')
                    success = github_handler.restore_version(script_path, selected, current_sha)
                    if success:
                        messagebox.showinfo("Success", f"Successfully restored version '{selected}'.")
                        self.refresh_scripts_display()  # Refresh the main view
                        version_window.destroy()
                    else:
                        messagebox.showerror("Error", f"Failed to restore version '{selected}'. Check the logs for details.")
            
            restore_button = ctk.CTkButton(main_frame, text="Restore Selected Version", 
                                         command=restore_selected_version)
            restore_button.pack(pady=5)
        else:
            # No versions available
            no_versions_label = ctk.CTkLabel(main_frame, text="No previous versions available.", 
                                           font=ctk.CTkFont(slant="italic"))
            no_versions_label.pack(pady=20)
        
        # Close button
        close_button = ctk.CTkButton(main_frame, text="Close", command=version_window.destroy)
        close_button.pack(pady=10)

    def manage_versions(self):
        """Handle the Manage Versions button click."""
        selected_scripts = []
        for item in self.script_widgets:
            if 'checkbox_var' in item and item['checkbox_var'].get() == 1:
                selected_scripts.append(item['script_data'])
        
        if len(selected_scripts) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one script to manage versions.")
            return
        
        self.show_version_management_window(selected_scripts[0])
    
    def on_window_resize(self, event):
        """Handle window resize events to save window size."""
        # Only save if the event is for the main window (not child widgets)
        if event.widget == self:
            width = self.winfo_width()
            height = self.winfo_height()
            # Only save if the window has a reasonable size (avoid saving during initialization)
            if width > 100 and height > 100:
                config_manager.set_window_size(width, height)


if __name__ == "__main__":
    app = ScriptUpdaterApp()
    app.mainloop()

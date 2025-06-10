import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import sys
import os
import queue
import webbrowser
import shutil

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

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class ScriptUpdaterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GitHub Script Updater")
        self.geometry("800x600")

        self.scripts_data = config_manager.load_scripts_config()
        self.community_scripts_data = self.load_community_scripts_config()
        self.current_view = "main" # To track current view: "main" or "community"

        # Main container frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.settings = config_manager.load_settings()


        # --- Input Frame ---
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(pady=10, padx=10, fill="x")

        self.label_repo_url = ctk.CTkLabel(self.input_frame, text="GitHub Repo URL:")
        self.label_repo_url.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_repo_url = ctk.CTkEntry(self.input_frame, width=300)
        self.entry_repo_url.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.label_folder_path = ctk.CTkLabel(self.input_frame, text="Folder Path in Repo (optional):")
        self.label_folder_path.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_folder_path = ctk.CTkEntry(self.input_frame, width=300)
        self.entry_folder_path.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.entry_folder_path.insert(0, "") # Default to empty (repo root or user must specify)

        self.label_local_path = ctk.CTkLabel(self.input_frame, text="Local Save Directory:")
        self.label_local_path.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_local_path = ctk.CTkEntry(self.input_frame, width=250)
        self.entry_local_path.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        # Load and set the last used local path
        last_local_path = self.settings.get('last_local_path', '')
        if last_local_path:
            self.entry_local_path.insert(0, last_local_path)
        self.button_browse_local_path = ctk.CTkButton(self.input_frame, text="Browse", command=self.browse_local_path)
        self.button_browse_local_path.grid(row=2, column=2, padx=5, pady=5)

        self.button_add_script = ctk.CTkButton(self.input_frame, text="Add Script", command=self.add_script)
        self.button_add_script.grid(row=3, column=0, columnspan=3, pady=10, sticky="ew") # Reverted to original grid placement
        
        self.input_frame.columnconfigure(1, weight=1) # Make entry fields expand

        # --- Scripts List Frame ---
        self.scripts_list_frame = ctk.CTkFrame(self.main_frame)
        self.scripts_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.view_title_label = ctk.CTkLabel(self.scripts_list_frame, text="Managed Scripts", font=ctk.CTkFont(size=16, weight="bold"))
        self.view_title_label.pack(pady=(5,0), padx=5, anchor="w")

        # NEW: Managed Scripts TabView
        # The command will call _on_managed_tab_change when a tab is selected
        self.managed_scripts_tab_view = ctk.CTkTabview(self.scripts_list_frame, command=self._on_managed_tab_change) 
        self.managed_scripts_tab_view.pack(pady=5, padx=5, fill="both", expand=True)

        self.managed_script_categories = ["All", "Activities", "Class Rotations", "Utilities"]
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
        self.community_script_categories = ["All", "Activities", "Class Rotations", "Utilities"]
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

        if not cleaned_repo_url:
            messagebox.showerror("Input Error", "Repository URL cannot be empty.")
            self.status_bar.configure(text="Error: Repository URL empty.")
            return False
        if not local_path: # This is the target_base_directory
            messagebox.showerror("Input Error", "Local save directory cannot be empty.")
            self.status_bar.configure(text="Error: Local save directory empty.")
            return False

        if not cleaned_repo_url.lower().startswith("https://github.com/"):
            messagebox.showerror("Input Error", "Invalid GitHub repository URL. Must start with 'https://github.com/' and be a valid repository path.")
            self.status_bar.configure(text="Error: Invalid GitHub URL format.")
            return False

        url_parts = cleaned_repo_url.split('/')
        if len(url_parts) < 5 or not url_parts[-1] or not url_parts[-2]: 
            messagebox.showerror("Input Error", "Invalid GitHub repository URL structure. Expected 'https://github.com/username/repositoryname'.")
            self.status_bar.configure(text="Error: Invalid repository URL structure.")
            return False
        
        if script_name_override:
            script_dir_name = script_name_override
        else:
            script_dir_name = url_parts[-1]
            if folder_path_cleaned:
                script_dir_name += "_" + folder_path_cleaned.replace('/', '_').replace('\\', '_')
        
        if not script_dir_name:
            messagebox.showerror("Input Error", "Could not determine a script directory name.")
            self.status_bar.configure(text="Error: Could not determine script name.")
            return False
        
        if any(s.get('name') == script_dir_name for s in self.scripts_data):
            if is_community_script:
                if not messagebox.askyesno("Script Exists", f"The script '{script_dir_name}' already exists in your managed scripts. Add anyway (may overwrite or duplicate)?"):
                    self.status_bar.configure(text=f"Skipped adding existing community script: {script_dir_name}")
                    return False 
            else:
                messagebox.showerror("Duplicate Script", f"A script named '{script_dir_name}' already exists in your managed scripts.")
                self.status_bar.configure(text=f"Error: Script '{script_dir_name}' already exists.")
                return False

        self.status_bar.configure(text=f"Adding '{script_dir_name}' from {cleaned_repo_url}...")
        self.update_idletasks()
        
        target_save_path_for_handler = os.path.join(local_path, script_dir_name)
        
        try:
            download_success, download_message, final_actual_local_path = github_handler.download_folder_from_github(
                cleaned_repo_url, 
                folder_path_cleaned, 
                target_save_path_for_handler 
            )

            if download_success:
                try:
                    latest_sha = github_handler.get_latest_commit_sha(cleaned_repo_url)
                    if not latest_sha:
                         raise Exception("Could not retrieve latest commit SHA.")
                    
                    # Use basename of the final actual path as the script's 'name' in config
                    final_script_name = os.path.basename(final_actual_local_path)

                    determined_status = 'Up to date'
                    if latest_sha is None:
                        determined_status = 'Unknown (fetch error)'

                    script_info = {
                        "name": final_script_name, 
                        "repo_url": cleaned_repo_url,
                        "folder_path": folder_path_cleaned,
                        "local_path": final_actual_local_path,
                        "category": category,
                        "current_version_sha": latest_sha,
                        "latest_version_sha": latest_sha, # For a new script, current is latest
                        "last_checked": datetime.datetime.now().isoformat(),
                        "status": determined_status
                    }
                    config_manager.add_script_to_config(script_info)
                    # Ensure no duplicate script_info object if it was a re-add
                    self.scripts_data = [s for s in self.scripts_data if s.get('name') != final_script_name] 
                    self.scripts_data.append(script_info)
                    self.refresh_scripts_display()
                    self.status_bar.configure(text=f"Script '{final_script_name}' added successfully.")
                    return True
                except Exception as e_post_download:
                    messagebox.showerror("Post-Download Error", f"Script downloaded to '{final_actual_local_path}', but failed post-processing (SHA/config): {e_post_download}")
                    self.status_bar.configure(text="Error in post-download steps.")
            else:
                messagebox.showerror("Add Script Error", f"Failed to add script '{script_dir_name}': {download_message}")
                self.status_bar.configure(text=f"Failed to add script '{script_dir_name}'.")
        
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
        current_managed_tab = self.managed_scripts_tab_view.get()
        # We've already ensured 'Add Script' is disabled if 'All' is selected, 
        # so current_managed_tab should be a valid category here.
        if self._perform_add_script(repo_url, folder_path, local_path, current_managed_tab, is_community_script=False):
            self.entry_repo_url.delete(0, tk.END)
            self.entry_folder_path.delete(0, tk.END)
            self.entry_local_path.delete(0, tk.END)
            # Save the used local path as the new default
            self.settings['last_local_path'] = local_path
            config_manager.save_settings(self.settings)

    def update_selected_scripts(self):
        selected_scripts_data = []
        for item in self.script_widgets:
            if item['checkbox'] and item['checkbox'].get() == 1:
                selected_scripts_data.append(item['script_data'])

        if not selected_scripts_data:
            messagebox.showinfo("No Scripts Selected", "Please select at least one script to update.")
            return

        self.status_bar.configure(text="Starting update process...")
        self.update_idletasks()
        
        updated_count = 0
        up_to_date_count = 0
        error_count = 0

        # Create a deep copy of scripts_data to modify, or find indices to update self.scripts_data directly
        # For simplicity here, we'll assume we find the script in self.scripts_data by a unique identifier (e.g., repo_url + folder_path)
        # and update it in place. If name/path changes, this needs careful handling.

        for script_data_ref in selected_scripts_data: # script_data_ref is a reference to an item in self.scripts_data
            script_name = script_data_ref.get('name', 'Unknown Script')
            self.status_bar.configure(text=f"Checking {script_name} for updates...")
            self.update_idletasks()

            try:
                # For now, assume default branch 'Main'. This could be stored per script later.
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
                    
                    # Determine the target path for the download operation. 
                    # This should be the original repo name in the parent directory of the current script.
                    parent_dir_of_current_script = os.path.dirname(script_data_ref['local_path'])
                    original_repo_name_part = script_data_ref['repo_url'].rstrip('/').split('/')[-1]
                    
                    # Construct the name that the folder would have if downloaded without considering prior restructuring, 
                    # but including user-specified subfolder_path if any.
                    base_download_name = original_repo_name_part
                    if script_data_ref['folder_path']:
                        cleaned_folder_path = script_data_ref['folder_path'].replace('/', '_').replace('\\', '_')
                        base_download_name += "_" + cleaned_folder_path

                    target_for_download_operation = os.path.join(parent_dir_of_current_script, base_download_name)

                    print(f"[DEBUG] Update: Script '{script_name}' current local_path: {script_data_ref['local_path']}")
                    print(f"[DEBUG] Update: Target for download op (before potential restructure): {target_for_download_operation}")

                    # Perform the download (which includes overwrite and restructuring)
                    dl_success, dl_message, final_actual_path = github_handler.download_folder_from_github(
                        script_data_ref['repo_url'], 
                        script_data_ref['folder_path'], 
                        target_for_download_operation # Pass the potentially 'unstructured' path name
                    )

                    if dl_success:
                        script_data_ref['current_version_sha'] = latest_remote_sha
                        script_data_ref['local_path'] = final_actual_path # Update path if restructuring changed it
                        script_data_ref['name'] = os.path.basename(final_actual_path) # Update name based on final path
                        updated_count += 1
                        self.status_bar.configure(text=f"{script_name} updated successfully.")
                        print(f"[INFO] {script_name} updated to SHA {latest_remote_sha}. New path: {final_actual_path}")
                    else:
                        messagebox.showerror("Update Error", f"Failed to download update for {script_name}: {dl_message}")
                        error_count += 1
                else: # SHAs match
                    self.status_bar.configure(text=f"{script_name} is up to date.")
                    up_to_date_count += 1
                    print(f"[INFO] {script_name} is up to date (SHA: {current_local_sha[:7]}).")
            
            except Exception as e:
                messagebox.showerror("Update Error", f"An error occurred while updating {script_name}: {e}")
                error_count += 1
                print(f"[ERROR] Updating {script_name}: {e}")
            finally:
                self.update_idletasks()

        config_manager.save_scripts_config(self.scripts_data) # Save all changes to timestamps, SHAs, paths
        self.refresh_scripts_display()
        
        summary_message = f"Update check finished. Updated: {updated_count}, Up-to-date: {up_to_date_count}, Errors: {error_count}."
        messagebox.showinfo("Update Complete", summary_message)
        self.status_bar.configure(text=summary_message)

    def _on_managed_tab_change(self, selected_tab_name: str = None):
        """Called when the selected tab in the managed scripts view changes."""
        # CTkTabview passes the name of the selected tab. If called manually, it might be None.
        current_tab = selected_tab_name if selected_tab_name is not None else self.managed_scripts_tab_view.get()
        if current_tab == "All":
            self.button_add_script.configure(state="disabled")
        else:
            self.button_add_script.configure(state="normal")

    def _create_script_entry_ui(self, parent_container, script_data_item, shared_checkbox_var):
        entry_frame = ctk.CTkFrame(parent_container)
        entry_frame.pack(fill="x", pady=2, padx=2)

        checkbox = ctk.CTkCheckBox(entry_frame, text="", width=20, variable=shared_checkbox_var, command=self.on_checkbox_toggle)
        checkbox.grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="ns")

        status_indicator = script_data_item.get('update_status_indicator')
        initial_status = script_data_item.get('status', 'Unknown')
        status_text = ""
        if status_indicator == 'available':
            status_text = "🔄 Update Available"
        elif status_indicator == 'uptodate':
            status_text = "✅ Up to date"
        elif status_indicator == 'check_failed':
            status_text = "⚠️ Check Failed"
        else:
            if initial_status == 'Up to date':
                status_text = f"✅ {initial_status}"
            elif initial_status == 'Unknown (fetch error)':
                status_text = f"❔ {initial_status}"
            elif initial_status == 'Unknown':
                status_text = f"❔ {initial_status}"
            elif initial_status:
                status_text = f"ℹ️ {initial_status}"
            else:
                status_text = "❔ Status Unknown"
        
        script_display_name = script_data_item.get('name', 'N/A')
        if script_data_item.get('folder_path'): 
            script_display_name += f" ({script_data_item['folder_path']})"
        label_name = ctk.CTkLabel(entry_frame, text=script_display_name, anchor="w", font=ctk.CTkFont(weight="bold"))
        label_name.grid(row=0, column=1, sticky="w", padx=5)

        label_status = ctk.CTkLabel(entry_frame, text=status_text, anchor="e", font=ctk.CTkFont(weight="bold"))
        label_status.grid(row=0, column=2, sticky="e", padx=5)

        repo_url = script_data_item.get('repo_url')
        author_name = self._get_author_from_url(repo_url)
        label_author = ctk.CTkLabel(entry_frame, text=f"Author: {author_name}", anchor="w", font=ctk.CTkFont(size=10))
        label_author.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)

        entry_frame.columnconfigure(0, weight=0)
        entry_frame.columnconfigure(1, weight=1)
        entry_frame.columnconfigure(2, weight=0)


    def _create_community_script_entry_ui(self, parent_container, script_info, shared_checkbox_var):
        """Creates UI elements for a single community script entry in a given tab."""
        item_frame = ctk.CTkFrame(parent_container)
        item_frame.pack(fill="x", pady=2, padx=2)

        display_text = script_info.get("displayText", "Unnamed Script")
        repo_url = script_info.get('repo_url')
        folder_path = script_info.get('folder_path')
        is_managed = self._is_script_managed(repo_url, folder_path)

        current_display_text = display_text
        checkbox_state = "normal"
        # The shared_checkbox_var's value should already be set correctly based on is_managed
        # when it was first created or retrieved in populate_community_script_tabs.

        if is_managed:
            current_display_text += " (Added)"
            checkbox_state = "disabled"
            # shared_checkbox_var.set(1) # This should be handled before calling this helper

        checkbox = ctk.CTkCheckBox(
            item_frame, 
            text=current_display_text, 
            variable=shared_checkbox_var, 
            onvalue=1, 
            offvalue=0, 
            command=self.on_community_checkbox_toggle, 
            state=checkbox_state
        )
        checkbox.pack(side="left", padx=5, pady=2)
        
        # Store a reference to this specific checkbox widget if needed for targeted updates,
        # though shared_checkbox_var is the primary state holder.
        # script_info[f'_widget_ref_{parent_container.winfo_name()}'] = checkbox 
        # This might be overly complex; direct updates via add_community_script might be better.

        return item_frame

    def refresh_scripts_display(self):
        for tab_name, scrollable_frame in self.managed_tab_scrollable_frames.items():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
        self.script_widgets.clear()

        if not self.scripts_data:
            no_scripts_label = ctk.CTkLabel(self.managed_tab_scrollable_frames["All"], text="No scripts managed yet.")
            no_scripts_label.pack(pady=10)
            self.on_checkbox_toggle()
            return

        status_order = {
            'available': 0, 
            'check_failed': 1, 
            'uptodate': 2, 
            'Up to date': 2, 
            'Unknown (fetch error)': 3,
            'Unknown': 3, 
            None: 4
        }
        
        def get_sort_key(script):
            primary_status = script.get('update_status_indicator')
            secondary_status = script.get('status')
            chosen_status_for_sort = primary_status if primary_status is not None else secondary_status
            return (status_order.get(chosen_status_for_sort, 4), script.get('name', '').lower())

        sorted_scripts = sorted(self.scripts_data, key=get_sort_key)
        self.scripts_data = sorted_scripts

        for i, script_data_item in enumerate(self.scripts_data):
            checkbox_var = ctk.IntVar(value=0)
            
            self.script_widgets.append({
                'checkbox_var': checkbox_var, 
                'script_data': script_data_item
            })

            self._create_script_entry_ui(self.managed_tab_scrollable_frames["All"], script_data_item, checkbox_var)

            script_category = script_data_item.get('category', 'Utilities')
            if script_category in self.managed_tab_scrollable_frames and script_category != "All":
                self._create_script_entry_ui(self.managed_tab_scrollable_frames[script_category], script_data_item, checkbox_var)
            elif script_category != "All":
                print(f"[WARNING] Script '{script_data_item.get('name')}' has unrecognized category '{script_category}'. Not adding to a specific category tab.")

        self.on_checkbox_toggle()

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

        # State for GitHub button
        github_button_state = "normal" if selected_count == 1 else "disabled"
        if hasattr(self, 'button_open_github'): # Check if button exists
            self.button_open_github.configure(state=github_button_state)

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

        self.view_title_label.pack_forget() # Hide label in community view
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

        self.view_title_label.configure(text="Managed Scripts")
        self.view_title_label.pack(pady=(5,0), padx=5, anchor="w") # Show label in main view
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
                ctk.CTkLabel(self.tab_frames["All"], text="No community scripts available.").pack(pady=10)
            # Display message in other category tabs
            for category, frame in self.tab_frames.items():
                if category != "All":
                    ctk.CTkLabel(frame, text=f"No community scripts found for {category}.").pack(pady=10)
            return

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
                if shared_checkbox_var.get() != initial_checkbox_value and is_managed:
                     shared_checkbox_var.set(initial_checkbox_value) 

            # Create entry in 'All' tab
            all_tab_frame = self.tab_frames.get("All")
            if all_tab_frame:
                entry_frame_all = self._create_community_script_entry_ui(all_tab_frame, script_info, shared_checkbox_var)
                # Store widget info for 'All' tab
                self.community_script_widgets_by_tab["All"].append({
                    'script_data': script_info,
                    'frame': entry_frame_all, # The frame returned by _create_community_script_entry_ui
                    'checkbox_var': shared_checkbox_var # The shared IntVar
                })

            # Create entry in specific category tab
            category = script_info.get("category", "Utilities") # Default to Utilities if not specified
            category_tab_frame = self.tab_frames.get(category)
            if category_tab_frame and category != "All":
                entry_frame_cat = self._create_community_script_entry_ui(category_tab_frame, script_info, shared_checkbox_var)
                scripts_added_to_category_tabs[category] = True
                # Store widget info for category tab
                self.community_script_widgets_by_tab[category].append({
                    'script_data': script_info,
                    'frame': entry_frame_cat,
                    'checkbox_var': shared_checkbox_var
                })
            elif category != "All":
                print(f"[Warning] Community script '{script_info.get('displayText')}' has unknown category '{category}'. Not adding to a specific category tab.")

        # For any category tab (not 'All') that didn't get any scripts, add a placeholder label
        for category, was_populated in scripts_added_to_category_tabs.items():
            if not was_populated:
                parent_frame = self.tab_frames.get(category)
                if parent_frame:
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


if __name__ == "__main__":
    app = ScriptUpdaterApp()
    app.mainloop()

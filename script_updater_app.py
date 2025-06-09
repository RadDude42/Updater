import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import config_manager
import github_handler
import os
import shutil
import datetime
import threading
import queue

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class ScriptUpdaterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GitHub Script Updater")
        self.geometry("800x600")

        self.scripts_data = config_manager.load_scripts_config()

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
        self.button_add_script.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.input_frame.columnconfigure(1, weight=1) # Make entry fields expand

        # --- Scripts List Frame ---
        self.scripts_list_frame = ctk.CTkFrame(self.main_frame)
        self.scripts_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.scrollable_scripts_frame = ctk.CTkScrollableFrame(self.scripts_list_frame, label_text="Managed Scripts", label_font=ctk.CTkFont(size=16, weight="bold"))
        self.scrollable_scripts_frame.pack(pady=5, padx=5, fill="both", expand=True)
        self.scrollable_scripts_frame.configure(height=200) # Set a fixed height or make it expand

        self.script_widgets = [] # To store {'checkbox': widget, 'script_data': dict, 'frame': widget}

        # --- Action Buttons Frame ---
        self.action_buttons_frame = ctk.CTkFrame(self.main_frame)
        self.action_buttons_frame.pack(pady=10, padx=10, fill="x") 

        self.button_update_selected = ctk.CTkButton(self.action_buttons_frame, text="Update Selected", command=self.update_selected_scripts, state="disabled")
        self.button_update_selected.pack(side="left", padx=5)
        
        self.button_delete_selected = ctk.CTkButton(self.action_buttons_frame, text="Delete Selected", command=self.delete_selected_script, state="disabled")
        self.button_delete_selected.pack(side="left", padx=5)

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

    def browse_local_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry_local_path.delete(0, tk.END)
            self.entry_local_path.insert(0, directory)
        # Save the selected path as the new default
        self.settings['last_local_path'] = directory
        config_manager.save_settings(self.settings)

    def add_script(self):
        raw_repo_url = self.entry_repo_url.get().strip()
        folder_path = self.entry_folder_path.get().strip() # Can be empty
        local_path = self.entry_local_path.get().strip()

        # --- Input Validation --- #
        if not raw_repo_url:
            messagebox.showerror("Input Error", "Repository URL cannot be empty.")
            self.status_bar.configure(text="Error: Repository URL empty.")
            return
        if not local_path:
            messagebox.showerror("Input Error", "Local save directory cannot be empty.")
            self.status_bar.configure(text="Error: Local save directory empty.")
            return

        # Clean the repo_url for parsing: remove trailing slash *before* splitting
        repo_url = raw_repo_url.rstrip('/')

        if not repo_url.lower().startswith("https://github.com/"):
            messagebox.showerror("Input Error", "Invalid GitHub repository URL. Must start with 'https://github.com/' and be a valid repository path.")
            self.status_bar.configure(text="Error: Invalid GitHub URL format.")
            return

        url_parts = repo_url.split('/')
        # Expect at least 5 parts: https: / / github.com / user / repo
        if len(url_parts) < 5 or not url_parts[-1] or not url_parts[-2]: 
            messagebox.showerror("Input Error", "Invalid GitHub repository URL structure. Expected 'https://github.com/username/repositoryname'.")
            self.status_bar.configure(text="Error: Invalid repository URL structure.")
            return
        
        script_dir_name = url_parts[-1] # This should now be the actual repo name
        if not script_dir_name: # Double check it's not empty after all cleaning
            messagebox.showerror("Input Error", "Could not derive a script directory name from the repository URL. Please check the URL format.")
            self.status_bar.configure(text="Error: Could not derive script name.")
            return
        
        # --- End Input Validation --- #

        self.status_bar.configure(text=f"Adding {repo_url}...") # Use the cleaned repo_url for status
        self.update_idletasks() # Ensure status bar updates immediately

        if folder_path:
            script_dir_name += "_" + folder_path.replace('/', '_').replace('\\', '_')
        
        target_save_path = os.path.join(local_path, script_dir_name)
        final_status_message = "Operation finished." # Default final message
        # Initialize final_local_path here for broader scope in case of early error
        final_local_path = target_save_path 

        try:
            # This part calls the download and potential restructuring
            download_success, download_message, final_local_path_from_handler = github_handler.download_folder_from_github(repo_url, folder_path, target_save_path)
            final_local_path = final_local_path_from_handler # Update with actual path after download/restructure

            if download_success:
                # Try to get SHA and save config only if download was successful
                try:
                    latest_sha = github_handler.get_latest_commit_sha(repo_url)
                    script_info = {
                        "name": script_dir_name,
                        "repo_url": repo_url,
                        "folder_path": folder_path,
                        "local_path": final_local_path,
                        "current_version_sha": latest_sha,
                        "last_checked": latest_sha # Use the fetched SHA for initial check timestamp
                    }
                    config_manager.add_script_to_config(script_info)
                    self.scripts_data.append(script_info)
                    self.refresh_scripts_display()
                    messagebox.showinfo("Success", download_message) # Show message from download/restructure
                    final_status_message = "Script added successfully."
                except Exception as e_post_download:
                    error_msg = f"Script downloaded to '{final_local_path}', but failed post-processing (getting SHA/saving config): {e_post_download}"
                    messagebox.showerror("Post-Download Error", error_msg)
                    final_status_message = "Error in post-download steps."
                    # Consider cleaning up final_local_path if it exists and post-processing fails
            else:
                # Download or restructuring itself failed
                messagebox.showerror("Add Script Error", f"Failed to add script: {download_message}")
                final_status_message = "Failed to add script."
        
        except Exception as e_overall:
            # Catch any other unexpected errors during the entire add_script process
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"An unexpected error occurred while adding script '{script_dir_name}' from '{repo_url}'.\nPath: '{final_local_path}'\nError: {e_overall}\n\nDetails:\n{error_details}"
            messagebox.showerror("Unexpected Error", error_msg)
            final_status_message = "Unexpected error during script addition."
            print(f"[ERROR] Unexpected error in add_script: {e_overall}")
            print(error_details)

        finally:
            self.status_bar.configure(text=final_status_message)
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

    def refresh_scripts_display(self):
        # Clear existing widgets
        for item in self.script_widgets:
            item['frame'].destroy()
        self.script_widgets.clear()

        if not self.scripts_data:
            no_scripts_label = ctk.CTkLabel(self.scrollable_scripts_frame, text="No scripts managed yet.")
            no_scripts_label.pack(pady=10)
            self.script_widgets.append({'frame': no_scripts_label, 'checkbox': None, 'script_data': None})
        else:
            # Sort scripts: 1. Update available, 2. Check failed, 3. Up to date, then alphabetically by name
            status_order = {'available': 0, 'check_failed': 1, 'uptodate': 2, None: 3} # None or other statuses last
            
            # Ensure all scripts have a default status if 'update_status_indicator' is missing
            for sd in self.scripts_data:
                if 'update_status_indicator' not in sd:
                    sd['update_status_indicator'] = None # Or 'unknown_status'

            sorted_scripts = sorted(
                self.scripts_data, 
                key=lambda x: (status_order.get(x.get('update_status_indicator'), 3), x.get('name', '').lower())
            )
            self.scripts_data = sorted_scripts # Update self.scripts_data to be the sorted list

            for i, script_data in enumerate(self.scripts_data):
                entry_frame = ctk.CTkFrame(self.scrollable_scripts_frame)
                entry_frame.pack(fill="x", pady=2, padx=2)

                checkbox = ctk.CTkCheckBox(entry_frame, text="", width=20, command=self.on_checkbox_toggle)
                checkbox.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="ns")

                status_indicator = script_data.get('update_status_indicator')
                status_text = ""
                if status_indicator == 'available':
                    status_text = "🔄 Update Available"
                elif status_indicator == 'uptodate':
                    status_text = "✅ Up to date"
                elif status_indicator == 'check_failed':
                    status_text = "⚠️ Check Failed"
                else:
                    status_text = "❔ Status Unknown" # Default or if indicator is None/missing
                
                label_status = ctk.CTkLabel(entry_frame, text=status_text, anchor="w", font=ctk.CTkFont(weight="bold"))
                label_status.grid(row=0, column=1, sticky="ew", padx=5)

                script_display_name = script_data.get('name', 'N/A')
                if script_data.get('folder_path'): # Add folder_path to name if it exists, for clarity
                    script_display_name += f" ({script_data['folder_path']})"
                label_name = ctk.CTkLabel(entry_frame, text=script_display_name, anchor="w")
                label_name.grid(row=1, column=1, sticky="ew", padx=5)
                
                version_sha = script_data.get('current_version_sha', 'Unknown')
                version_display = version_sha[:7] if version_sha != 'Unknown' and version_sha else 'Unknown'
                label_version = ctk.CTkLabel(entry_frame, text=f"Version: {version_display}", anchor="w")
                label_version.grid(row=2, column=1, sticky="ew", padx=5)
                
                entry_frame.columnconfigure(1, weight=1) # Make the text column expandable
                
                self.script_widgets.append({'checkbox': checkbox, 'script_data': script_data, 'frame': entry_frame})
        
        self.on_checkbox_toggle() # Update button states after refreshing

    def on_checkbox_toggle(self):
        """Called when a script checkbox is toggled. Updates action button states."""
        any_selected = any(item['checkbox'] and item['checkbox'].get() == 1 for item in self.script_widgets)
        if any_selected:
            self.button_update_selected.configure(state="normal")
            self.button_delete_selected.configure(state="normal")
        # 3. If different, re-download using github_handler.download_folder_from_github()
        # 4. Update current_version_sha in config_manager
        # 5. Refresh display

    def process_queue(self):
        """Processes messages from the worker thread queue to update the UI."""
        try:
            message = self.update_queue.get_nowait()
            if isinstance(message, list):
                # This is the updated scripts list from the worker
                print("[INFO] Received updated script data from worker thread.")
                self.scripts_data = message
                config_manager.save_scripts_config(self.scripts_data) # Persist the new statuses
                self.refresh_scripts_display()
                self.status_bar.configure(text="Startup update check complete.")
                print("[INFO] UI updated and startup check complete.")
        except queue.Empty:
            pass # No message in queue, continue polling
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
            if item['checkbox'] and item['checkbox'].get() == 1:
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
        self.refresh_scripts_display()
        if deleted_count > 0:
            messagebox.showinfo("Deletion Complete", f"Successfully deleted {deleted_count} script(s).")
        self.status_bar.configure(text="Deletion process finished.")



if __name__ == "__main__":
    app = ScriptUpdaterApp()
    app.mainloop()

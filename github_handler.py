import requests
import os
import shutil
import json
from zipfile import ZipFile
from io import BytesIO
import traceback
from logger_setup import get_logger
import config_manager
import hashlib
import tempfile
from packaging.version import parse as parse_version

logger = get_logger(__name__)

def check_for_app_update(current_version):
    """Checks for a new application release on GitHub."""
    try:
        repo_url = "https://api.github.com/repos/RadDude42/Updater/releases/latest"
        response = requests.get(repo_url, headers=get_github_headers())
        response.raise_for_status()
        release_data = response.json()

        if release_data.get("prerelease"):
            logger.info("Latest release is a pre-release, skipping.")
            return None, None

        latest_version_str = release_data.get("tag_name", "0.0.0").lstrip('v')
        current_v = parse_version(current_version)
        latest_v = parse_version(latest_version_str)

        if latest_v > current_v:
            logger.info(f"New version found: {latest_v} (current: {current_v})")
            for asset in release_data.get("assets", []):
                if asset['name'].lower() == 'scriptupdaterapp.exe':
                    return latest_v, asset['browser_download_url']
            logger.warning("New release found, but 'ScriptUpdaterApp.exe' asset is missing.")
            return None, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to check for app update: {e}")
    except Exception as e:
        logger.error(f"An error occurred during app update check: {e}")
    
    return None, None

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file."""
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating SHA256 for {file_path}: {e}")
        return None

def get_github_headers():
    """Get headers for GitHub API requests with optional authentication."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    token = config_manager.get_github_token()
    if token:
        headers['Authorization'] = f'token {token}'
        logger.debug("Using GitHub token authentication")
    else:
        logger.debug("Using unauthenticated GitHub API requests")
    
    return headers

def get_repo_api_url(repo_url):
    """Constructs the base API URL from a GitHub repository URL."""
    parts = repo_url.strip('/').split('/')
    if len(parts) < 5 or parts[2] != 'github.com':
        raise ValueError("Invalid GitHub repository URL format.")
    user = parts[3]
    repo_name = parts[4].split('/tree/')[0]
    return f"https://api.github.com/repos/{user}/{repo_name}"

def download_release_exe(repo_url, local_save_path):
    """Downloads .exe files from the latest release of a GitHub repository."""
    try:
        api_url = get_repo_api_url(repo_url)
        releases_url = f"{api_url}/releases/latest"
        response = requests.get(releases_url, headers=get_github_headers())
        response.raise_for_status()
        release_data = response.json()

        exe_assets = [asset for asset in release_data.get('assets', []) if asset['name'].lower().endswith('.exe')]

        if not exe_assets:
            return False, "No .exe files found in the latest release.", None

        if os.path.exists(local_save_path):
            shutil.rmtree(local_save_path)
        os.makedirs(local_save_path)

        for asset in exe_assets:
            asset_url = asset['browser_download_url']
            local_filename = os.path.join(local_save_path, asset['name'])
            logger.info(f"Downloading release asset: {asset['name']}")
            with requests.get(asset_url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        
        return True, f"Successfully downloaded {len(exe_assets)} .exe file(s) from the latest release.", local_save_path

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return False, "No releases found for this repository.", None
        return False, f"Failed to fetch releases: {e}", None
    except Exception as e:
        return False, f"An error occurred during release download: {e}", None

def download_repo_exes(repo_url, local_save_path):
    """Downloads all .exe files found in a GitHub repository's default branch."""
    try:
        api_url = get_repo_api_url(repo_url)
        repo_info = requests.get(api_url, headers=get_github_headers()).json()
        default_branch = repo_info.get('default_branch', 'main')
        
        trees_url = f"{api_url}/git/trees/{default_branch}?recursive=1"
        logger.debug(f"Getting repo tree from: {trees_url}")
        response = requests.get(trees_url, headers=get_github_headers())
        response.raise_for_status()
        tree_data = response.json()

        # Extensive logging to debug file finding
        logger.debug(f"Repo tree response status: {response.status_code}")
        logger.debug(f"Repo tree truncated: {tree_data.get('truncated')}")
        all_tree_items = tree_data.get('tree', [])
        logger.debug(f"Total items in tree: {len(all_tree_items)}")
        
        logger.debug("--- All Tree Items ---")
        for item in all_tree_items:
            logger.debug(f"Item: path={item.get('path')}, type={item.get('type')}, mode={item.get('mode')}")
        logger.debug("--- End of Tree Items ---")

        exe_files = [item for item in all_tree_items if item.get('path', '').lower().endswith('.exe') and item.get('type') == 'blob']
        logger.debug(f"Found {len(exe_files)} .exe files after filtering.")

        if not exe_files:
            return False, "No .exe files found in the repository based on tree scan.", None

        if os.path.exists(local_save_path):
            shutil.rmtree(local_save_path)
        os.makedirs(local_save_path)

        # Using contents API to get download URLs is more reliable
        for exe_file in exe_files:
            file_path = exe_file['path']
            contents_url = f"{api_url}/contents/{file_path}?ref={default_branch}"
            logger.debug(f"Getting contents for {file_path} from {contents_url}")
            
            contents_response = requests.get(contents_url, headers=get_github_headers())
            if contents_response.status_code != 200:
                logger.warning(f"Failed to get contents for {file_path}. Status: {contents_response.status_code}. Skipping.")
                continue
            
            download_url = contents_response.json().get('download_url')
            
            if not download_url:
                logger.warning(f"No download_url found for {file_path}. Skipping.")
                continue

            local_filename = os.path.join(local_save_path, os.path.basename(file_path))
            logger.info(f"Downloading repo file: {file_path}")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

        downloaded_count = len(os.listdir(local_save_path))
        if downloaded_count == 0:
            return False, "Found .exe files in repo data, but failed to download any of them.", None

        return True, f"Successfully downloaded {downloaded_count} .exe file(s) from the repository.", local_save_path

    except Exception as e:
        logger.error(f"An error occurred while scanning repository for .exe files: {e}")
        logger.debug(traceback.format_exc())
        return False, f"An error occurred while scanning repository for .exe files: {e}", None

def determine_effective_branch(repo_url, branch_hint=None):
    """Determines the effective branch from a repo URL and an optional hint."""
    parsed_branch_from_url = None
    if "/tree/" in repo_url:
        parts = repo_url.split('/tree/')
        if len(parts) > 1:
            branch_and_maybe_path = parts[1].split('/')
            parsed_branch_from_url = branch_and_maybe_path[0]
            logger.debug(f"Parsed branch '{parsed_branch_from_url}' from URL: {repo_url}")
    
    effective_branch = parsed_branch_from_url if parsed_branch_from_url else (branch_hint if branch_hint else 'main')
    logger.debug(f"Effective branch determined: {effective_branch}")
    return effective_branch

def download_from_github(repo_url, folder_path, local_save_path, category, branch=None):
    """Main function to download from GitHub, handling different categories."""
    if category == "Programs":
        logger.info("Program download detected. Checking for releases first.")
        success, message, path = download_release_exe(repo_url, local_save_path)
        if success:
            return True, message, path
        
        logger.info("No .exe in releases, scanning repository.")
        success, message, path = download_repo_exes(repo_url, local_save_path)
        if success:
            return True, message, path
        else:
            return False, "Could not find any .exe files in releases or repository.", None
    else:
        # Fallback to original folder download logic for other categories
        return download_folder_from_github(repo_url, folder_path, local_save_path, branch)

def download_folder_from_github(repo_url, folder_path, local_save_path, branch=None):
    """Downloads a specific folder from a GitHub repository.

    Args:
        repo_url (str): The URL of the GitHub repository (e.g., https://github.com/user/repo).
        folder_path (str): The path to the folder within the repository (e.g., 'src/my_folder' or '' for root).
        local_save_path (str): The local directory where the folder contents should be saved.
        branch (str): The branch to download from (defaults to 'Main').

    Returns:
        tuple: (bool, str, str) indicating (success_status, message, final_script_path).
    """
    try:
        effective_branch = determine_effective_branch(repo_url, branch)
        # The print for effective_branch is now inside determine_effective_branch

        api_url_base = repo_url.split('/tree/')[0] if "/tree/" in repo_url else repo_url
        
        user, repo_name = api_url_base.strip('/').split('/')[-2:]
        archive_url = f"https://api.github.com/repos/{user}/{repo_name}/zipball/{effective_branch}"

        zip_response = requests.get(archive_url, headers=get_github_headers(), stream=True)
        zip_response.raise_for_status()

        zip_content = BytesIO(zip_response.content)
        extracted_count = 0
        final_actual_path = local_save_path # Initialize with the original save path

        with ZipFile(zip_content) as zf:
            if not zf.namelist():
                return False, "Downloaded zip file is empty.", final_actual_path
            
            repo_root_dir_in_zip = zf.namelist()[0].split('/')[0] + '/'
            
            normalized_folder_path_for_zip = folder_path.strip('/').replace(os.sep, '/')
            if normalized_folder_path_for_zip:
                search_prefix_in_zip = repo_root_dir_in_zip + normalized_folder_path_for_zip + '/'
            else:
                search_prefix_in_zip = repo_root_dir_in_zip

            files_to_extract_from_zip = []
            for item_name in zf.namelist():
                if item_name.startswith(search_prefix_in_zip) and not item_name.endswith('/'): 
                    files_to_extract_from_zip.append(item_name)
            
            if not files_to_extract_from_zip:
                folder_exists_as_prefix_in_zip = any(name.startswith(search_prefix_in_zip) for name in zf.namelist())
                if folder_exists_as_prefix_in_zip:
                    if os.path.exists(local_save_path):
                        shutil.rmtree(local_save_path)
                    os.makedirs(local_save_path, exist_ok=True)
                    return True, f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully. It is empty or contains only subdirectories.", final_actual_path
                else:
                    return False, f"Folder '{folder_path if folder_path else 'root'}' not found in the repository archive (searched for prefix '{search_prefix_in_zip}').", final_actual_path

            # Preserve "Older Versions" folder if it exists
            older_versions_backup = None
            older_versions_path = os.path.join(local_save_path, "Older Versions")
            if os.path.exists(older_versions_path):
                older_versions_backup = tempfile.mkdtemp()
                shutil.copytree(older_versions_path, os.path.join(older_versions_backup, "Older Versions"))
                logger.debug(f"Backed up Older Versions to: {older_versions_backup}")
            
            if os.path.exists(local_save_path):
                shutil.rmtree(local_save_path)
            logger.debug(f"Creating directory for main extraction: {local_save_path}")
            os.makedirs(local_save_path, exist_ok=True)
            
            # Restore "Older Versions" folder if it was backed up
            if older_versions_backup and os.path.exists(os.path.join(older_versions_backup, "Older Versions")):
                shutil.copytree(os.path.join(older_versions_backup, "Older Versions"), older_versions_path)
                shutil.rmtree(older_versions_backup)  # Clean up temp directory
                logger.debug(f"Restored Older Versions folder")

            for file_path_in_zip in files_to_extract_from_zip:
                relative_path = file_path_in_zip[len(search_prefix_in_zip):]
                local_file_path = os.path.join(local_save_path, relative_path)
                
                parent_dir = os.path.dirname(local_file_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir)
                
                with open(local_file_path, 'wb') as f_out:
                    f_out.write(zf.read(file_path_in_zip))
                extracted_count += 1
        
        if extracted_count > 0:
            # --- Lua Script Restructuring Logic ---
            if not os.path.exists(os.path.join(local_save_path, "main.lua")):
                logger.debug(f"Restructure: main.lua not found in root of {local_save_path}. Checking subdirectories.")
                items_in_root = os.listdir(local_save_path)
                subdirs = [item for item in items_in_root if os.path.isdir(os.path.join(local_save_path, item))]
                
                if len(subdirs) == 1:
                    single_subdir_name = subdirs[0]
                    single_subdir_path = os.path.join(local_save_path, single_subdir_name)
                    if os.path.exists(os.path.join(single_subdir_path, "main.lua")):
                        logger.debug(f"Restructure: Found main.lua in single subdirectory '{single_subdir_name}'. Restructuring.")
                        temp_restructure_dir = local_save_path + "_temp_restructure_dir"
                        if os.path.exists(temp_restructure_dir):
                            shutil.rmtree(temp_restructure_dir)
                        os.makedirs(temp_restructure_dir)

                        for item in os.listdir(single_subdir_path):
                            shutil.move(os.path.join(single_subdir_path, item), os.path.join(temp_restructure_dir, item))
                        
                        shutil.rmtree(single_subdir_path) 
                        
                        for item in os.listdir(temp_restructure_dir):
                            shutil.move(os.path.join(temp_restructure_dir, item), os.path.join(local_save_path, item))
                        
                        shutil.rmtree(temp_restructure_dir) 
                        logger.debug(f"Restructure: Successfully moved contents from '{single_subdir_name}' to '{local_save_path}'.")
            # --- End of Lua Script Restructuring Logic ---
            return True, f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully. Extracted {extracted_count} files.", final_actual_path
        else:
            return False, f"Folder '{folder_path if folder_path else 'root'}' was processed, but no files were ultimately extracted.", final_actual_path

    except requests.exceptions.RequestException as e:
        return False, f"Error downloading repository: {e}", local_save_path # Fallback path
    except Exception as e:
        logger.error(f"An unexpected error occurred in download_folder_from_github: {e}")
        logger.debug(traceback.format_exc())
        return False, f"An unexpected error occurred in download_folder_from_github: {e}", local_save_path # Fallback path

def get_latest_commit_sha(repo_url, branch=None):
    """Fetches the SHA of the latest commit on a given branch of a GitHub repository."""
    parts = repo_url.strip('/').split('/')
    if len(parts) < 5 or parts[2] != 'github.com':
        raise ValueError("Invalid GitHub repository URL format.")
    user = parts[3]
    repo_name = parts[4].split('/tree/')[0] # Ensure repo_name is clean if URL had /tree/
    
    effective_branch = determine_effective_branch(repo_url, branch)
    # The print for effective_branch is now inside determine_effective_branch

    api_url = f"https://api.github.com/repos/{user}/{repo_name}/commits/{effective_branch}"
    try:
        response = requests.get(api_url, headers=get_github_headers())
        response.raise_for_status()
        return response.json()['sha']
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching latest commit SHA: {e}")
        return None
    except (KeyError, IndexError):
        logger.error(f"Error parsing commit SHA from API response for {api_url}")
        return None

def archive_current_version(script_path, commit_sha):
    """Archives the current version of a script before updating.
    
    Args:
        script_path (str): Path to the script folder
        commit_sha (str): The commit SHA for the current version
        
    Returns:
        bool: True if archiving was successful, False otherwise
    """
    try:
        if not os.path.exists(script_path):
            logger.warning(f"Script path does not exist: {script_path}")
            return False
        
        # Use smart archiving for GitHub updates
        return archive_current_version_smart(script_path, commit_sha, "from-github")
        
    except Exception as e:
        logger.error(f"Failed to archive current version: {e}")
        return False

def find_existing_archive_by_sha(older_versions_dir, sha_short):
    """Find an existing archive folder that contains the specified SHA.
    
    Args:
        older_versions_dir (str): Path to the Older Versions directory
        sha_short (str): Short SHA (8 characters) to search for
        
    Returns:
        str or None: Name of the existing archive folder, or None if not found
    """
    if not os.path.exists(older_versions_dir):
        return None
    
    for folder_name in os.listdir(older_versions_dir):
        if sha_short in folder_name:
            return folder_name
    return None

def archive_current_version_smart(script_path, commit_sha, context):
    """Archive current version with smart deduplication.
    
    Args:
        script_path (str): Path to the script folder
        commit_sha (str): The commit SHA for the current version
        context (str): Context suffix like "from-github" or "before-restore"
        
    Returns:
        bool: True if archiving was successful, False otherwise
    """
    try:
        older_versions_dir = os.path.join(script_path, "Older Versions")
        
        # Check if this SHA already exists
        existing_archive = find_existing_archive_by_sha(older_versions_dir, commit_sha[:8])
        if existing_archive:
            logger.info(f"SHA {commit_sha[:8]} already archived in: {existing_archive}")
            return True  # No need to create duplicate
        
        # Create new archive since SHA doesn't exist
        os.makedirs(older_versions_dir, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_folder_name = f"{timestamp}_{commit_sha[:8]}_{context}"
        archive_path = os.path.join(older_versions_dir, archive_folder_name)
        
        if os.path.exists(archive_path):
            shutil.rmtree(archive_path)
        os.makedirs(archive_path)
        
        for item in os.listdir(script_path):
            if item != "Older Versions":
                item_path = os.path.join(script_path, item)
                dest_path = os.path.join(archive_path, item)
                if os.path.isdir(item_path):
                    shutil.copytree(item_path, dest_path)
                else:
                    shutil.copy2(item_path, dest_path)
        
        logger.info(f"Archived current version to: {archive_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to archive current version: {e}")
        return False

def restore_version(script_path, version_folder_name, current_sha=None):
    """Restores a specific version from the archive.
    
    Args:
        script_path (str): Path to the script folder
        version_folder_name (str): Name of the version folder to restore
        current_sha (str): SHA of the currently active version (if known)
        
    Returns:
        bool: True if restoration was successful, False otherwise
    """
    try:
        older_versions_dir = os.path.join(script_path, "Older Versions")
        version_path = os.path.join(older_versions_dir, version_folder_name)
        
        if not os.path.exists(version_path):
            logger.error(f"Version folder does not exist: {version_path}")
            return False
        
        # Smart deduplication: Check if current SHA already has an archive
        if current_sha:
            existing_archive = find_existing_archive_by_sha(older_versions_dir, current_sha[:8])
            if existing_archive:
                logger.info(f"Current version SHA {current_sha[:8]} already archived in: {existing_archive}")
                # Don't create duplicate - the version is already safely stored
            else:
                # Create new archive since this SHA doesn't exist yet
                archive_current_version_smart(script_path, current_sha, "before-restore")
        else:
            # We don't have SHA info, create archive with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            archive_name = f"{timestamp}_active_before-restore"
            archive_path = os.path.join(older_versions_dir, archive_name)
            
            if os.path.exists(archive_path):
                shutil.rmtree(archive_path)
            os.makedirs(archive_path)
            
            for item in os.listdir(script_path):
                if item != "Older Versions":
                    item_path = os.path.join(script_path, item)
                    dest_path = os.path.join(archive_path, item)
                    if os.path.isdir(item_path):
                        shutil.copytree(item_path, dest_path)
                    else:
                        shutil.copy2(item_path, dest_path)
            
            logger.info(f"Archived current version before restore to: {archive_path}")
        
        # Remove current files (except Older Versions)
        for item in os.listdir(script_path):
            if item != "Older Versions":
                item_path = os.path.join(script_path, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        
        # Copy files from the selected version
        for item in os.listdir(version_path):
            src_path = os.path.join(version_path, item)
            dest_path = os.path.join(script_path, item)
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)
        
        logger.info(f"Restored version: {version_folder_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore version: {e}")
        return False

def get_available_versions(script_path):
    """Gets a list of available archived versions for a script.
    
    Args:
        script_path (str): Path to the script folder
        
    Returns:
        list: List of version folder names, sorted by date (newest first)
    """
    try:
        older_versions_dir = os.path.join(script_path, "Older Versions")
        if not os.path.exists(older_versions_dir):
            return []
        
        versions = []
        for item in os.listdir(older_versions_dir):
            item_path = os.path.join(older_versions_dir, item)
            if os.path.isdir(item_path):
                versions.append(item)
        
        # Sort by creation time (newest first)
        versions.sort(key=lambda x: os.path.getctime(os.path.join(older_versions_dir, x)), reverse=True)
        return versions
        
    except Exception as e:
        logger.error(f"Failed to get available versions: {e}")
        return []

def differential_update_from_github(repo_url, folder_path, local_save_path, branch=None):
    """Downloads and applies only changed files from a GitHub repository.
    
    Args:
        repo_url (str): The URL of the GitHub repository
        folder_path (str): The path to the folder within the repository
        local_save_path (str): The local directory where files should be updated
        branch (str): The branch to download from (defaults to main/master)
        
    Returns:
        tuple: (bool, str, str) indicating (success_status, message, final_script_path)
    """
    try:
        logger.info(f"Starting differential update for {repo_url}")
        
        # Preserve "Older Versions" folder if it exists
        older_versions_backup = None
        older_versions_path = os.path.join(local_save_path, "Older Versions")
        if os.path.exists(older_versions_path):
            older_versions_backup = tempfile.mkdtemp()
            shutil.copytree(older_versions_path, os.path.join(older_versions_backup, "Older Versions"))
            logger.debug(f"Backed up Older Versions to: {older_versions_backup}")
        
        # Download to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.debug(f"Downloading to temporary directory: {temp_dir}")
            
            # Use existing download logic to get the repository content
            success, message, temp_path = download_folder_from_github(repo_url, folder_path, temp_dir, branch)
            
            if not success:
                return False, f"Failed to download repository for comparison: {message}", local_save_path
            
            # Ensure local directory exists
            os.makedirs(local_save_path, exist_ok=True)
            
            # Restore "Older Versions" folder if it was backed up
            if older_versions_backup and os.path.exists(os.path.join(older_versions_backup, "Older Versions")):
                if os.path.exists(older_versions_path):
                    shutil.rmtree(older_versions_path)
                shutil.copytree(os.path.join(older_versions_backup, "Older Versions"), older_versions_path)
                logger.debug(f"Restored Older Versions folder")
            
            # Compare and update files
            files_updated = 0
            files_added = 0
            files_compared = 0
            
            # Walk through all files in the temporary download
            for root, dirs, files in os.walk(temp_dir):
                # Skip the "Older Versions" directory in comparisons
                if "Older Versions" in dirs:
                    dirs.remove("Older Versions")
                
                for file in files:
                    temp_file_path = os.path.join(root, file)
                    
                    # Calculate relative path from temp_dir
                    rel_path = os.path.relpath(temp_file_path, temp_dir)
                    local_file_path = os.path.join(local_save_path, rel_path)
                    
                    files_compared += 1
                    
                    # Calculate hash of the new file
                    new_file_hash = calculate_sha256(temp_file_path)
                    if new_file_hash is None:
                        logger.warning(f"Could not calculate hash for new file: {temp_file_path}")
                        continue
                    
                    # Check if local file exists and compare hashes
                    should_copy = True
                    if os.path.exists(local_file_path):
                        local_file_hash = calculate_sha256(local_file_path)
                        if local_file_hash is not None and local_file_hash == new_file_hash:
                            should_copy = False
                            logger.debug(f"File unchanged, skipping: {rel_path}")
                    
                    if should_copy:
                        # Ensure the directory exists
                        local_dir = os.path.dirname(local_file_path)
                        os.makedirs(local_dir, exist_ok=True)
                        
                        # Copy the file
                        shutil.copy2(temp_file_path, local_file_path)
                        
                        if os.path.exists(local_file_path):
                            files_updated += 1
                            logger.debug(f"Updated file: {rel_path}")
                        else:
                            files_added += 1
                            logger.debug(f"Added file: {rel_path}")
            
            # Clean up backup
            if older_versions_backup:
                shutil.rmtree(older_versions_backup)
            
            logger.info(f"Differential update completed. Files compared: {files_compared}, Updated: {files_updated}, Added: {files_added}")
            
            if files_updated > 0 or files_added > 0:
                return True, f"Differential update completed successfully. {files_updated} files updated, {files_added} files added.", local_save_path
            else:
                return True, "No file changes detected. All files are already up to date.", local_save_path
    
    except Exception as e:
        logger.error(f"An error occurred during differential update: {e}")
        logger.debug(traceback.format_exc())
        return False, f"An error occurred during differential update: {e}", local_save_path

def perform_update(repo_url, folder_path, local_save_path, category, branch=None):
    """Main update function that chooses between overwrite and differential update methods.
    
    Args:
        repo_url (str): The URL of the GitHub repository
        folder_path (str): The path to the folder within the repository
        local_save_path (str): The local directory where files should be updated
        category (str): The category of the script (Programs, Activities, etc.)
        branch (str): The branch to download from (defaults to main/master)
        
    Returns:
        tuple: (bool, str, str) indicating (success_status, message, final_script_path)
    """
    try:
        update_method = config_manager.get_update_method()
        logger.info(f"Using update method: {update_method}")
        
        if update_method == 'differential':
            return differential_update_from_github(repo_url, folder_path, local_save_path, branch)
        else:
            # Default to overwrite method (original behavior)
            return download_from_github(repo_url, folder_path, local_save_path, category, branch)
    
    except Exception as e:
        logger.error(f"Error in perform_update: {e}")
        # Fallback to original method in case of any configuration issues
        return download_from_github(repo_url, folder_path, local_save_path, category, branch)

if __name__ == '__main__':
    # Example Usage (for testing)
    # test_repo_url = "https://github.com/customtkinter/customtkinter"
    # test_folder_path = "customtkinter"  # Folder within the repo
    # test_local_save = "./downloaded_ctk_folder"
    
    # success, message = download_folder_from_github(test_repo_url, test_folder_path, test_local_save)
    # print(f"Success: {success}, Message: {message}")

    # test_repo_url_2 = "https://github.com/pallets/flask"
    # test_folder_path_2 = "examples/tutorial"
    # test_local_save_2 = "./downloaded_flask_tutorial"
    # success, message = download_folder_from_github(test_repo_url_2, test_folder_path_2, test_local_save_2)
    # print(f"Success: {success}, Message: {message}")

    # Test downloading root
    # test_repo_url_3 = "https://github.com/user/small-test-repo" # Replace with a small public repo
    # test_folder_path_3 = "" 
    # test_local_save_3 = "./downloaded_repo_root"
    # success, message = download_folder_from_github(test_repo_url_3, test_folder_path_3, test_local_save_3)
    # print(f"Success: {success}, Message: {message}")

    # Test commit SHA
    # sha = get_latest_commit_sha(test_repo_url)
    # print(f"Latest commit SHA for {test_repo_url}: {sha}")
    pass

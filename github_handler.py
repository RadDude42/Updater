import requests
import os
import shutil
import json
from zipfile import ZipFile
from io import BytesIO
import traceback

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
        response = requests.get(releases_url)
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
            print(f"Downloading release asset: {asset['name']}")
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
        repo_info = requests.get(api_url).json()
        default_branch = repo_info.get('default_branch', 'main')
        
        trees_url = f"{api_url}/git/trees/{default_branch}?recursive=1"
        print(f"[DEBUG] Getting repo tree from: {trees_url}")
        response = requests.get(trees_url)
        response.raise_for_status()
        tree_data = response.json()

        # Extensive logging to debug file finding
        print(f"[DEBUG] Repo tree response status: {response.status_code}")
        print(f"[DEBUG] Repo tree truncated: {tree_data.get('truncated')}")
        all_tree_items = tree_data.get('tree', [])
        print(f"[DEBUG] Total items in tree: {len(all_tree_items)}")
        
        print("[DEBUG] --- All Tree Items ---")
        for item in all_tree_items:
            print(f"[DEBUG] Item: path={item.get('path')}, type={item.get('type')}, mode={item.get('mode')}")
        print("[DEBUG] --- End of Tree Items ---")

        exe_files = [item for item in all_tree_items if item.get('path', '').lower().endswith('.exe') and item.get('type') == 'blob']
        print(f"[DEBUG] Found {len(exe_files)} .exe files after filtering.")

        if not exe_files:
            return False, "No .exe files found in the repository based on tree scan.", None

        if os.path.exists(local_save_path):
            shutil.rmtree(local_save_path)
        os.makedirs(local_save_path)

        # Using contents API to get download URLs is more reliable
        for exe_file in exe_files:
            file_path = exe_file['path']
            contents_url = f"{api_url}/contents/{file_path}?ref={default_branch}"
            print(f"[DEBUG] Getting contents for {file_path} from {contents_url}")
            
            contents_response = requests.get(contents_url)
            if contents_response.status_code != 200:
                print(f"[WARNING] Failed to get contents for {file_path}. Status: {contents_response.status_code}. Skipping.")
                continue
            
            download_url = contents_response.json().get('download_url')
            
            if not download_url:
                print(f"[WARNING] No download_url found for {file_path}. Skipping.")
                continue

            local_filename = os.path.join(local_save_path, os.path.basename(file_path))
            print(f"Downloading repo file: {file_path}")
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
        import traceback
        print(traceback.format_exc())
        return False, f"An error occurred while scanning repository for .exe files: {e}", None

def determine_effective_branch(repo_url, branch_hint=None):
    """Determines the effective branch from a repo URL and an optional hint."""
    parsed_branch_from_url = None
    if "/tree/" in repo_url:
        parts = repo_url.split('/tree/')
        if len(parts) > 1:
            branch_and_maybe_path = parts[1].split('/')
            parsed_branch_from_url = branch_and_maybe_path[0]
            print(f"[DEBUG] Parsed branch '{parsed_branch_from_url}' from URL: {repo_url}")
    
    effective_branch = parsed_branch_from_url if parsed_branch_from_url else (branch_hint if branch_hint else 'main')
    print(f"[DEBUG] Effective branch determined: {effective_branch}")
    return effective_branch

def download_from_github(repo_url, folder_path, local_save_path, category, branch=None):
    """Main function to download from GitHub, handling different categories."""
    if category == "Programs":
        print("Program download detected. Checking for releases first.")
        success, message, path = download_release_exe(repo_url, local_save_path)
        if success:
            return True, message, path
        
        print("No .exe in releases, scanning repository.")
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

        api_headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        zip_response = requests.get(archive_url, headers=api_headers, stream=True)
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

            if os.path.exists(local_save_path):
                shutil.rmtree(local_save_path)
            print(f"[DEBUG_CASCADE] github_handler.py: os.makedirs (main extraction) trying to create: {local_save_path}")
            os.makedirs(local_save_path, exist_ok=True)

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
                print(f"[DEBUG] Restructure: main.lua not found in root of {local_save_path}. Checking subdirectories.")
                items_in_root = os.listdir(local_save_path)
                subdirs = [item for item in items_in_root if os.path.isdir(os.path.join(local_save_path, item))]
                
                if len(subdirs) == 1:
                    single_subdir_name = subdirs[0]
                    single_subdir_path = os.path.join(local_save_path, single_subdir_name)
                    if os.path.exists(os.path.join(single_subdir_path, "main.lua")):
                        print(f"[DEBUG] Restructure: Found main.lua in single subdirectory '{single_subdir_name}'. Restructuring.")
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
                        print(f"[DEBUG] Restructure: Successfully moved contents from '{single_subdir_name}' to '{local_save_path}'.")
            # --- End of Lua Script Restructuring Logic ---
            return True, f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully. Extracted {extracted_count} files.", final_actual_path
        else:
            return False, f"Folder '{folder_path if folder_path else 'root'}' was processed, but no files were ultimately extracted.", final_actual_path

    except requests.exceptions.RequestException as e:
        return False, f"Error downloading repository: {e}", local_save_path # Fallback path
    except Exception as e:
        print(traceback.format_exc()) # Ensure traceback is printed for any other exception
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
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()['sha']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest commit SHA: {e}")
        return None
    except (KeyError, IndexError):
        print(f"Error parsing commit SHA from API response for {api_url}")
        return None

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

import requests
import os
import shutil
import json
from zipfile import ZipFile
from io import BytesIO

# Note: For private repositories, authentication (e.g., a token) would be needed.
# For public repositories, the GitHub API has rate limits for unauthenticated requests.

def get_repo_archive_link(repo_url, branch='Main'):
    """Generates the archive link for a GitHub repository."""
    # Example repo_url: https://github.com/user/repository
    parts = repo_url.strip('/').split('/')
    if len(parts) < 5 or parts[2] != 'github.com':
        raise ValueError("Invalid GitHub repository URL format.")
    user = parts[3]
    repo_name = parts[4]
    return f"https://api.github.com/repos/{user}/{repo_name}/zipball/{branch}"

def download_folder_from_github(repo_url, folder_path, local_save_path, branch='Main'):
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
        api_url = get_repo_archive_link(repo_url, branch)
        
        # Step 1: Get the redirect URL from the GitHub API
        api_headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            # If private repos, add: 'Authorization': f'token {YOUR_GITHUB_TOKEN}'
        }
        redirect_response = requests.get(api_url, headers=api_headers, allow_redirects=False)
        
        # Check if the request to the API itself failed before checking for 302
        if redirect_response.status_code >= 400:
            error_message = f"GitHub API request failed with status {redirect_response.status_code}."
            try:
                error_details = redirect_response.json() # Try to get more details
                error_message += f" Details: {error_details.get('message', 'No additional details.')}"
            except json.JSONDecodeError:
                pass # No JSON body
            return False, error_message, local_save_path

        if redirect_response.status_code == 302:
            download_url = redirect_response.headers.get('Location')
            if not download_url:
                return False, "Failed to get download URL: Location header missing after 302 redirect.", local_save_path
        elif redirect_response.status_code == 200: # Some API versions might directly return content or different structure
            # This case might need specific handling if the API behavior changes or if it's an unexpected success for this endpoint type
            # For zipball, a 302 is expected. If we get 200, it might be an error or unexpected response format.
            # For now, let's assume it's an issue if not 302 for zipball.
            return False, f"Failed to get download URL. API Status: {redirect_response.status_code}, Response: {redirect_response.text[:200]}", local_save_path
        else:
            return False, f"Failed to download archive. Status: {redirect_response.status_code}, URL: {api_url}", local_save_path

        # Step 2: Download the content from the obtained download_url
        download_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(download_url, headers=download_headers, stream=True)
        response.raise_for_status()  # Check for HTTP errors on the actual download

        with ZipFile(BytesIO(response.content)) as zf:
            print(f"[DEBUG] GitHub Handler: Zip opened. Namelist (first 10): {zf.namelist()[:10]}")
            if not zf.namelist():
                return False, "Downloaded zip file is empty.", local_save_path
            
            # The first directory in the zip file is usually <repo_name>-<branch_or_commit_sha>
            root_zip_dir = zf.namelist()[0].split('/')[0]
            print(f"[DEBUG] GitHub Handler: Calculated root_zip_dir: '{root_zip_dir}'")
            
            user_folder_path_stripped = folder_path.strip('/')
            print(f"[DEBUG] GitHub Handler: User's folder_path (stripped): '{user_folder_path_stripped}'")
            
            # Construct the full path prefix we expect for relevant files inside the zip
            # If user_folder_path_stripped is empty, we target the root_zip_dir itself.
            if user_folder_path_stripped:
                path_prefix_in_zip = os.path.join(root_zip_dir, user_folder_path_stripped)
            else:
                path_prefix_in_zip = root_zip_dir
            
            full_folder_path_in_zip = path_prefix_in_zip.replace('\\', '/') + '/'
            # Ensure it always ends with a slash to correctly identify contents *within* this path
            print(f"[DEBUG] GitHub Handler: Effective full_folder_path_in_zip for matching: '{full_folder_path_in_zip}'")

            if not os.path.exists(local_save_path):
                os.makedirs(local_save_path)
            else:
                # Clear existing contents if any, to ensure a fresh copy
                for item in os.listdir(local_save_path):
                    item_path = os.path.join(local_save_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

            extracted_count = 0
            print(f"[DEBUG] GitHub Handler: Starting extraction loop. Looping through {len(zf.infolist())} members.")
            for member_info in zf.infolist():
                member_path_original = member_info.filename
                member_path_normalized = member_path_original.replace('\\', '/')
                is_dir = member_info.is_dir() # Check if ZipInfo itself marks it as directory
                # Some zip files might not explicitly mark directories but imply them with trailing slashes
                if not is_dir and member_path_normalized.endswith('/'): 
                    is_dir = True

                print(f"[DEBUG] GitHub Handler: Checking member: '{member_path_normalized}', is_dir: {is_dir}")

                if member_path_normalized.startswith(full_folder_path_in_zip) and not is_dir:
                    # Ensure we are not trying to extract the directory prefix itself if it's listed as a file
                    if member_path_normalized == full_folder_path_in_zip.rstrip('/') and not user_folder_path_stripped:
                        print(f"[DEBUG] GitHub Handler: SKIPPING '{member_path_normalized}' - it's the root directory prefix itself, not a file within.")
                        continue
                
                    relative_path = member_path_normalized[len(full_folder_path_in_zip):]
                    # If relative_path is empty, it means member_path_normalized was exactly full_folder_path_in_zip
                    # This can happen if full_folder_path_in_zip points to a file, not a dir. But we added trailing slash.
                    # However, if user_folder_path_stripped was empty, full_folder_path_in_zip is 'root_zip_dir/'
                    # and member_path_normalized could be 'root_zip_dir/file.txt'. relative_path = 'file.txt'
                    if not relative_path and member_path_normalized != full_folder_path_in_zip.rstrip('/'): # Avoid issues if full_folder_path_in_zip is a file itself
                         print(f"[DEBUG] GitHub Handler: SKIPPING '{member_path_normalized}' - relative_path is empty but it's not the directory prefix.")
                         continue
                    if not relative_path and user_folder_path_stripped: # if a specific folder was requested and it is the item
                        print(f"[DEBUG] GitHub Handler: SKIPPING '{member_path_normalized}' - it is the requested folder itself, not a file within.")
                        continue

                    print(f"[DEBUG] GitHub Handler: EXTRACTING '{member_path_normalized}' as relative_path: '{relative_path}'")
                    target_file_path = os.path.join(local_save_path, relative_path)
                    
                    # Create subdirectories if they don't exist for the file
                    if os.path.dirname(relative_path): # only if relative_path contains subdirs
                        os.makedirs(os.path.join(local_save_path, os.path.dirname(relative_path)), exist_ok=True)
                    
                    with zf.open(member_info) as source, open(target_file_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    extracted_count += 1
                else:
                    if not member_path_normalized.startswith(full_folder_path_in_zip):
                        print(f"[DEBUG] GitHub Handler: SKIPPING '{member_path_normalized}' - does not start with '{full_folder_path_in_zip}'")
                    if is_dir:
                        print(f"[DEBUG] GitHub Handler: SKIPPING '{member_path_normalized}' - is a directory.")
            
            print(f"[DEBUG] GitHub Handler: Extraction loop finished. Final extracted_count: {extracted_count}")
            
            if extracted_count == 0 and folder_path: # Check if folder_path was specified and nothing was extracted
                 # Check if the folder_path itself was a valid prefix but empty or only contained dirs
                found_folder_prefix = any(name.startswith(full_folder_path_in_zip) for name in zf.namelist())
                if not found_folder_prefix:
                    return False, f"Folder '{folder_path}' not found in repository '{repo_url}' (branch '{branch}'). Searched for prefix '{full_folder_path_in_zip}' in zip.", local_save_path
                # If prefix found but no files, it might be an empty folder or only contains other folders
                # This is considered a successful download of an (effectively) empty folder for now.

        # After the loop, decide on success message based on extracted_count
            if extracted_count > 0:
                download_success = True
                message = f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully to '{local_save_path}'. Extracted {extracted_count} files."
            else:
                # Check if the target path in zip truly existed but was empty, or if it didn't exist at all
                path_exists_in_zip = any(name.replace('\\', '/').startswith(full_folder_path_in_zip) for name in zf.namelist())
                if not path_exists_in_zip and folder_path:
                     return False, f"Folder '{folder_path}' not found in repository '{repo_url}' (branch '{branch}'). Searched for prefix '{full_folder_path_in_zip}' in zip.", local_save_path
                elif not path_exists_in_zip and not folder_path: # Root download, but root_zip_dir itself seems not to be a prefix for anything.
                     download_success = False
                     message = f"Could not find any files/folders under the root path ('{root_zip_dir}/') in the downloaded zip for '{repo_url}'. The zip might be structured unexpectedly or the repository is empty."
                else: # Path prefix exists, but no files were extracted (folder is empty or contains only subdirs)
                    download_success = True
                    message = f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully to '{local_save_path}'. The target folder in the repository is empty or contains only subdirectories (0 files extracted)."
            # Determine initial success and message from extraction phase
            if extracted_count > 0:
                download_success = True
                message = f"Folder '{folder_path if folder_path else 'root'}' downloaded successfully to '{local_save_path}'. Extracted {extracted_count} files."
            # (The 'else' for extracted_count == 0 is handled by the logic above it for empty folders or not found paths)

        final_script_path = local_save_path # Default to original path

        if download_success:
            # --- Restructuring Logic --- #
            if not os.path.exists(os.path.join(local_save_path, "main.lua")):
                print(f"[DEBUG] Restructure: main.lua not found in root of {local_save_path}. Checking subdirectories.")
                items_in_root = os.listdir(local_save_path)
                subdirectories = [d for d in items_in_root if os.path.isdir(os.path.join(local_save_path, d))]
                
                promoted_dir_candidate = None
                if len(subdirectories) == 1:
                    candidate_name = subdirectories[0]
                    if os.path.exists(os.path.join(local_save_path, candidate_name, "main.lua")):
                        promoted_dir_candidate = candidate_name
                        print(f"[DEBUG] Restructure: Single subdirectory '{candidate_name}' contains main.lua. Will attempt to promote.")
                    else:
                        print(f"[DEBUG] Restructure: Single subdirectory '{candidate_name}' does not contain main.lua. No restructure.")
                elif len(subdirectories) > 1:
                    print(f"[DEBUG] Restructure: Multiple subdirectories found. Checking each for main.lua.")
                    # Optional: if multiple, pick first one with main.lua? For now, stick to single subdir rule for simplicity or user's explicit example.
                    # For now, only the single subdirectory case is handled for promotion.
                    pass 

                if promoted_dir_candidate:
                    source_dir_to_promote = os.path.join(local_save_path, promoted_dir_candidate)
                    parent_dir_of_current_target = os.path.dirname(local_save_path)
                    final_destination_basename = promoted_dir_candidate # e.g., "piteer"
                    final_destination_path = os.path.join(parent_dir_of_current_target, final_destination_basename)

                    print(f"[DEBUG] Restructure: Promoting '{source_dir_to_promote}' to replace '{local_save_path}' with '{final_destination_path}'")
                    
                    temp_promoted_path = final_destination_path + "_temp_restructure"
                    
                    try:
                        if os.path.exists(temp_promoted_path):
                            shutil.rmtree(temp_promoted_path)
                        
                        # Move the actual script content (e.g., piteertest/piteer) to a temporary sibling location (e.g., piteer_temp_restructure)
                        print(f"[DEBUG] Restructure: Moving '{source_dir_to_promote}' to '{temp_promoted_path}'")
                        shutil.move(source_dir_to_promote, temp_promoted_path)
                        
                        # Delete the original container directory (e.g., piteertest)
                        print(f"[DEBUG] Restructure: Deleting original container '{local_save_path}'")
                        shutil.rmtree(local_save_path)
                        
                        # Rename the temporary script folder to its final name (e.g., piteer_temp_restructure -> piteer)
                        print(f"[DEBUG] Restructure: Renaming '{temp_promoted_path}' to '{final_destination_path}'")
                        os.rename(temp_promoted_path, final_destination_path)
                        
                        final_script_path = final_destination_path # Update the path
                        message += f" Script folder restructured to '{final_script_path}'."
                        print(f"[INFO] GitHub Handler: Script folder restructured. New path: {final_script_path}")
                    except Exception as e_restructure:
                        message += f" Post-download restructuring failed: {e_restructure}. Script remains at '{local_save_path}'."
                        print(f"[ERROR] GitHub Handler: Restructuring failed: {e_restructure}. Script may be at '{local_save_path}' or '{temp_promoted_path}'.")
                        # If restructure fails, final_script_path remains local_save_path (original download location)
            else:
                print(f"[DEBUG] Restructure: main.lua found in root of {local_save_path}. No restructure needed.")
        
        return download_success, message, final_script_path

    except requests.exceptions.RequestException as e:
        return False, f"Error downloading repository: {e}", local_save_path
    except ValueError as e:
        return False, str(e), local_save_path
    except Exception as e:
        return False, f"An unexpected error occurred: {e}", local_save_path

def get_latest_commit_sha(repo_url, branch='Main'):
    """Fetches the SHA of the latest commit on a given branch of a GitHub repository."""
    parts = repo_url.strip('/').split('/')
    if len(parts) < 5 or parts[2] != 'github.com':
        raise ValueError("Invalid GitHub repository URL format.")
    user = parts[3]
    repo_name = parts[4]
    
    api_url = f"https://api.github.com/repos/{user}/{repo_name}/commits/{branch}"
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

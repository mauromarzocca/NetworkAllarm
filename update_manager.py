import os
import sys
import shutil
import ast
import time
import urllib.request
import urllib.error
import subprocess
import json

# Configuration defaults
DEFAULT_BRANCH = "main"
REPO_OWNER = "mauromarzocca"
REPO_NAME = "NetworkAllarm"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/branches"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"

# Files to track and update
TRACKED_FILES = [
    "main.py",
    "utils.py",
    "config.py",
    "notify_switch.py",
    "failover-monitor.py",
    "archive_log.py",
    "backup.py",
    "backup_no_transfer.py",
    "check_log.py",
    "check_service.py",
    "configure.py",
    "restore.py",
    "upgrade.py"
]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("==========================================")
    print("   NetworkAllarm Update Manager")
    print("==========================================")

def backup_file(filepath):
    """Creates a backup of the file with a timestamp."""
    if os.path.exists(filepath):
        timestamp = int(time.time())
        backup_path = f"{filepath}.{timestamp}.bak"
        shutil.copy2(filepath, backup_path)
        print(f"   [Backup] Created: {backup_path}")
        return backup_path
    return None

def merge_config(local_path, remote_content):
    """
    Parses local config and remote config.
    Appends only NEW variables and imports from remote to local.
    Does NOT overwrite existing values.
    """
    print(f"   [Config] Merging {local_path}...")

    try:
        with open(local_path, 'r') as f:
            local_content = f.read()
    except FileNotFoundError:
        print(f"   [Config] Local file not found. Creating new.")
        with open(local_path, 'w') as f:
            f.write(remote_content)
        return

    # Parse AST to find assigned variables and imports
    try:
        local_tree = ast.parse(local_content)
        remote_tree = ast.parse(remote_content)
    except SyntaxError as e:
        print(f"   [Error] Syntax error in config parsing: {e}")
        return

    local_elements = set()

    # Identify what's already in local file (vars and imports)
    for node in local_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_elements.add(f"var:{target.id}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_elements.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                local_elements.add(f"importfrom:{module}:{alias.name}")

    new_lines = []
    remote_lines = remote_content.splitlines()
    added_items = []

    for node in remote_tree.body:
        should_add = False
        item_id = ""

        if isinstance(node, ast.Assign):
            # Check if any target variable is new
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if f"var:{target.id}" not in local_elements:
                        should_add = True
                        item_id = target.id
                        local_elements.add(f"var:{target.id}") # Prevent duplicate adds

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if f"import:{alias.name}" not in local_elements:
                    should_add = True
                    item_id = f"import {alias.name}"
                    local_elements.add(f"import:{alias.name}")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if f"importfrom:{module}:{alias.name}" not in local_elements:
                    should_add = True
                    item_id = f"from {module} import {alias.name}"
                    local_elements.add(f"importfrom:{module}:{alias.name}")

        if should_add:
            # Extract source lines for this node
            start_line = node.lineno - 1
            end_line = node.end_lineno
            segment = "\n".join(remote_lines[start_line:end_line])

            new_lines.append(f"\n# Added by Update Manager")
            new_lines.append(segment)
            added_items.append(item_id)

    if new_lines:
        with open(local_path, 'a') as f:
            for line in new_lines:
                f.write(line + "\n")
        print(f"   [Config] Added new items: {', '.join(added_items)}")
    else:
        print("   [Config] No new items found to merge.")

def manual_update_editor():
    """
    Lists files in current directory.
    Allows user to select a file.
    Backs it up.
    Truncates it.
    Opens it in vim.
    """
    print("\nSelect file to edit manually:")

    # Filter only tracked files that exist locally
    available_files = [f for f in TRACKED_FILES if os.path.exists(f)]

    if not available_files:
        print("No tracked files found in current directory.")
        return

    for idx, filename in enumerate(available_files):
        print(f"{idx + 1}. {filename}")

    print("0. Cancel")

    try:
        choice = input("\nEnter choice: ").strip()
        if choice == '0':
            return

        idx = int(choice) - 1
        if 0 <= idx < len(available_files):
            filename = available_files[idx]

            print(f"\nProcessing {filename}...")
            backup_file(filename)

            # Truncate file
            with open(filename, 'w') as f:
                pass # Empty the file

            print(f"   [Update] File truncated. Opening vi...")

            # Open vi
            try:
                subprocess.call(['vi', filename])
                print(f"   [Update] Editing complete for {filename}")
            except FileNotFoundError:
                print("   [Error] 'vi' not found. Please edit the file manually.")
        else:
            print("Invalid choice.")
    except ValueError:
        print("Invalid input.")

def get_github_branches():
    """Fetches available branches from GitHub API."""
    print("Fetching available branches...")
    try:
        req = urllib.request.Request(GITHUB_API_URL)
        req.add_header('User-Agent', 'python-urllib')  # GitHub requires User-Agent
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return [branch['name'] for branch in data]
    except Exception as e:
        print(f"   [Error] Could not fetch branches: {e}")
        return []

def update_from_github():
    branches = get_github_branches()

    if not branches:
        print("No branches found or API error. Defaulting to 'main'.")
        branch = "main"
    else:
        print("\nAvailable Branches:")
        for idx, b in enumerate(branches):
            print(f"{idx + 1}. {b}")
        print("0. Cancel")

        try:
            choice = input("\nSelect branch: ").strip()
            if choice == '0':
                return
            idx = int(choice) - 1
            if 0 <= idx < len(branches):
                branch = branches[idx]
            else:
                print("Invalid choice. Defaulting to 'main'.")
                branch = "main"
        except ValueError:
            print("Invalid input. Defaulting to 'main'.")
            branch = "main"

    print(f"\nFetching from GitHub (Branch: {branch})...")
    raw_base = f"{RAW_BASE_URL}/{branch}"
    print(f"Target URL Base: {raw_base}")

    for filename in TRACKED_FILES:
        file_url = f"{raw_base}/{filename}"
        print(f"\nChecking {filename}...")

        try:
            with urllib.request.urlopen(file_url, timeout=10) as response:
                remote_content = response.read().decode('utf-8')
                backup_file(filename)

                if filename == "config.py":
                    merge_config(filename, remote_content)
                else:
                    with open(filename, 'w') as f:
                        f.write(remote_content)
                    print(f"   [Update] Downloaded and overwritten {filename}")
        except urllib.error.HTTPError as e:
            print(f"   [Skip] File not found or error (Status {e.code})")
        except Exception as e:
            print(f"   [Error] Failed to fetch {filename}: {e}")

def main():
    clear_screen()
    print_header()
    print("1. Manual Update (Edit File)")
    print("2. Update from GitHub")
    print("0. Exit")

    try:
        choice = input("\nSelect option: ").strip()
    except (EOFError, KeyboardInterrupt):
        sys.exit()

    if choice == '1':
        manual_update_editor()
    elif choice == '2':
        update_from_github()
    elif choice == '0':
        sys.exit()
    else:
        print("Invalid option.")

if __name__ == "__main__":
    main()
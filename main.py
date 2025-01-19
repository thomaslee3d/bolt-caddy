#!/usr/bin/env python3

"""
Comprehensive React Project Management & Analysis Tool
======================================================
This single Python script combines multiple functionalities:
  1) Monitoring a folder for ZIP files, unzipping them,
     initializing Git, generating error/warning reports.
  2) Organizing a React project's file structure.
  3) Cleaning up unused dependencies (by analyzing imports).
  4) Linting & formatting using ESLint + Prettier.
  5) Searching files for certain terms, skipping ignored dirs/files.
  6) Printing a tree of project files.
  7) (Optional) GUI interface built with PyQt5.
  8) (Optional) Multithreaded scanning for faster analysis.

You can invoke it as a typical CLI or integrate it with other AI tooling.
"""
import os
import sys
import re
import time
import json
import shutil
import logging
import zipfile
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Optional: PyQt5 for the GUI (if you want a graphical interface).
# If PyQt5 is not installed or you don't need a GUI, you can comment this out.
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QPushButton,
        QTextEdit, QFileDialog, QWidget
    )
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False

######################################################
# Logging Configuration
######################################################
logging.basicConfig(
    filename="project_tool.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

######################################################
# Global Settings
######################################################
MONITOR_DIR = "./monitored_folder"
UNZIP_DIR = "./unzipped_projects"
REPORT_DIR = "./reports"

# Git / Branching
BRANCH_PREFIX = "fix"
GITHUB_REMOTE = "origin"  # not strictly used in this example
LAST_WORKING_BRANCH = None

# Dev server command
DEV_SERVER_CMD = ["npm", "run", "dev"]

# Ignored directories/files for scanning
IGNORE_DIRS = {"node_modules", ".git", "build", "dist", "__pycache__"}
IGNORE_FILES = {".DS_Store", "package-lock.json", "yarn.lock"}

# Folder categorization for file organization
FOLDERS = {
    "components": [".jsx", ".tsx"],         # React components
    "hooks": ["use"],                       # Custom React hooks
    "pages": ["Page", "pages"],             # Next.js or React Router pages
    "styles": [".css", ".scss", ".less"],   # Stylesheets
    "utils": ["utils", "helper"],           # Utility functions
    "tests": [".test.js", ".spec.js"],      # Test files
    "assets": [".png", ".jpg", ".svg", ".gif"],  # Images/assets
    "configs": [".json", ".yaml", ".yml"],  # Config files
    "docs": [".md", ".markdown"],           # Documentation
}

######################################################
# 1. Folder Monitoring & ZIP Extraction
######################################################
def monitor_for_zip():
    """
    Continuously monitor MONITOR_DIR for any .zip file.
    Returns the full path to the .zip file once detected.
    """
    logging.info(f"Monitoring {MONITOR_DIR} for ZIP files...")
    os.makedirs(MONITOR_DIR, exist_ok=True)
    while True:
        for file in os.listdir(MONITOR_DIR):
            if file.endswith(".zip"):
                zip_path = os.path.join(MONITOR_DIR, file)
                logging.info(f"Found ZIP file: {zip_path}")
                return zip_path
        time.sleep(5)

def unzip_file(zip_path, output_dir):
    """
    Unzip the given file into `output_dir`.
    Returns the path to the unzipped project folder.
    """
    logging.info(f"Unzipping {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        project_name = os.path.splitext(os.path.basename(zip_path))[0]
        project_path = os.path.join(output_dir, project_name)
        zip_ref.extractall(project_path)
    logging.info(f"Unzipped to {project_path}")
    return project_path

######################################################
# 2. Git Initialization
######################################################
def initialize_git_repo(project_path):
    """
    Initialize a Git repository in the given path and create a base branch.
    """
    logging.info(f"Initializing Git repository in {project_path}...")
    subprocess.run(["git", "init"], cwd=project_path)
    subprocess.run(["git", "checkout", "-b", f"{BRANCH_PREFIX}_base"], cwd=project_path)

######################################################
# 3. File Organization
######################################################
def organize_files(base_path):
    """
    Organize the project's files into a standard React folder structure
    based on known patterns (FOLDERS dict).
    """
    print("Organizing files into categorized folders...")
    logging.info("Organizing files into categorized folders...")
    for root, _, files in os.walk(base_path):
        # We do not want to move files out of node_modules or other ignored dirs
        if any(ignored in root for ignored in IGNORE_DIRS):
            continue

        for file in files:
            file_path = os.path.join(root, file)
            # Skip ignoring the same file or infinite loops
            if not os.path.isfile(file_path):
                continue

            # Attempt matching against each folder's patterns
            for folder, keywords in FOLDERS.items():
                # If any pattern matches the filename
                if any(keyword in file or file.endswith(tuple(keywords)) for keyword in keywords):
                    target_folder = os.path.join(base_path, folder)
                    os.makedirs(target_folder, exist_ok=True)

                    # Move the file
                    try:
                        shutil.move(file_path, target_folder)
                        print(f"Moved {file} to {folder}/")
                        logging.info(f"Moved {file_path} to {target_folder}")
                    except shutil.Error as e:
                        logging.error(f"Error moving {file_path} to {target_folder}: {e}")
                    break
    print("File organization complete.\n")

######################################################
# 4. Dependency Analysis & Cleanup
######################################################
def parse_imports_in_file(file_path):
    """
    Extract imported modules from a given JavaScript/TypeScript file
    using a basic regex.
    """
    imports = set()
    import_pattern = re.compile(r"(?:import|require)\s+['\"]([\w\-]+)['\"]")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                match = import_pattern.search(line)
                if match:
                    imports.add(match.group(1))
    except (UnicodeDecodeError, FileNotFoundError):
        pass
    return imports

def analyze_file_usage(base_path):
    """
    Analyze JS/TS files to determine which dependencies are actually used.
    """
    print("Analyzing project files for imports...")
    logging.info("Analyzing project files for imports...")
    used_dependencies = set()
    for root, dirs, files in os.walk(base_path):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith((".js", ".jsx", ".ts", ".tsx")):
                file_path = os.path.join(root, file)
                used_dependencies.update(parse_imports_in_file(file_path))
    print(f"Used dependencies detected: {len(used_dependencies)}")
    return used_dependencies

def cleanup_dependencies(base_path):
    """
    Compare used dependencies to those in package.json, then uninstall
    any that are unused.
    """
    print("Checking for unused dependencies...")
    logging.info("Checking for unused dependencies...")
    package_json_path = os.path.join(base_path, "package.json")
    if not os.path.exists(package_json_path):
        print("No package.json found. Skipping dependency cleanup.\n")
        logging.info("No package.json found, skipping dependency cleanup.")
        return set(), set()

    # Load package.json dependencies
    with open(package_json_path, "r") as file:
        package_data = json.load(file)

    installed_deps = set(package_data.get("dependencies", {}).keys())
    used_deps = analyze_file_usage(base_path)

    unused_deps = installed_deps - used_deps
    if unused_deps:
        print(f"Unused dependencies found: {', '.join(unused_deps)}")
        logging.info(f"Unused dependencies found: {unused_deps}")
        # Optionally remove them (comment out if you just want a report)
        for dep in unused_deps:
            subprocess.run(["npm", "uninstall", dep], cwd=base_path)
            print(f"Uninstalled unused dependency: {dep}")
            logging.info(f"Uninstalled unused dependency: {dep}")
    else:
        print("No unused dependencies found.\n")
        logging.info("No unused dependencies found.")
    return used_deps, unused_deps

######################################################
# 5. Linting & Formatting
######################################################
def setup_and_run_linter(base_path):
    """
    Install ESLint + Prettier, then run them to lint & format code.
    """
    print("Setting up and running ESLint and Prettier...")
    logging.info("Setting up ESLint and Prettier...")

    # Install ESLint & Prettier
    subprocess.run(["npm", "install", "eslint", "prettier", "--save-dev"], cwd=base_path)

    # Initialize ESLint config
    subprocess.run(["npx", "eslint", "--init"], cwd=base_path)

    print("Running ESLint...")
    subprocess.run(["npx", "eslint", "--fix", "."], cwd=base_path)

    print("Running Prettier...")
    subprocess.run(["npx", "prettier", "--write", "."], cwd=base_path)

    print("Linting and formatting complete.\n")
    logging.info("Linting and formatting complete.")

######################################################
# 6. Folder Scanning & Searching
######################################################
def print_folder_tree(base_path, prefix=""):
    """
    Print the folder structure in a tree-like format, skipping IGNORED dirs/files.
    """
    try:
        entries = os.listdir(base_path)
    except (PermissionError, FileNotFoundError):
        return

    # Filter out ignored directories and hidden directories/files
    dirs = []
    local_files = []
    for e in entries:
        full_e = os.path.join(base_path, e)
        if os.path.isdir(full_e):
            if e in IGNORE_DIRS or e.startswith('.'):
                continue
            dirs.append(e)
        else:
            if e in IGNORE_FILES or e.startswith('.'):
                continue
            local_files.append(e)

    # Sort for consistent printing
    dirs.sort()
    local_files.sort()

    # Print the current folder name
    print(prefix + os.path.basename(base_path) + "/")

    child_prefix = prefix + "  "
    # Print subdirectories
    for d in dirs:
        print_folder_tree(os.path.join(base_path, d), prefix=child_prefix)

    # Print files
    for f in local_files:
        print(child_prefix + f)

def scan_directory(base_path):
    """
    Recursively walk the directory, skipping ignored dirs/files,
    and return a list of (index, filepath).
    """
    file_list = []
    idx = 1
    for root, dirs, files in os.walk(base_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for f in files:
            if f in IGNORE_FILES or f.startswith('.'):
                continue
            full_path = os.path.join(root, f)
            file_list.append((idx, full_path))
            idx += 1
    return file_list

def prompt_file_selection(file_list):
    """
    Show a numeric list of files and let the user pick which they want.
    (Used in an interactive/CLI scenario)
    """
    if not file_list:
        print("No files found.")
        return []

    print("\nList of discovered files:")
    for idx, path in file_list:
        print(f"{idx}. {path}")

    print("\nEnter the file indices separated by spaces (e.g., '1 3 5'),")
    print("or '.' to select all, or 'none' to select none.")
    print("Type 'q' or 'quit' to exit.")

    while True:
        selection = input("Your selection: ").strip()
        if selection.lower() in ['q', 'quit']:
            sys.exit("Quitting...")
        if selection == '.':
            return [p for _, p in file_list]
        if selection.lower() == 'none':
            return []

        try:
            indices = list(map(int, selection.split()))
            selected_files = []
            valid_indices = {idx for idx, _ in file_list}
            for i in indices:
                if i not in valid_indices:
                    print(f"Index {i} is not in the list of files.")
                    break
            else:
                for i in indices:
                    for idx, path in file_list:
                        if idx == i:
                            selected_files.append(path)
                            break
                return selected_files
        except ValueError:
            print("Invalid input. Please enter indices like '1 2 3' or '.' or 'none'.")

def search_in_files(files, search_terms):
    """
    Search each file for lines containing ALL the provided `search_terms`.
    Prints out matching lines with line numbers.
    """
    lower_terms = [t.lower() for t in search_terms]
    for f in files:
        try:
            with open(f, 'r', encoding="utf-8") as file_reader:
                lines = file_reader.readlines()
            matched_lines = []
            for line_num, line in enumerate(lines, 1):
                lower_line = line.lower()
                if all(term in lower_line for term in lower_terms):
                    matched_lines.append((line_num, line.strip()))
            if matched_lines:
                print(f"\nFile: {f}")
                for ln, text in matched_lines:
                    print(f"  Line {ln}: {text}")
        except (UnicodeDecodeError, PermissionError, FileNotFoundError):
            pass  # skip files that can't be read

######################################################
# 7. Multithreaded Analysis Example
######################################################
def analyze_file(file_path):
    """
    Example function to do some 'analysis' on a file.
    In real usage, you'd expand this to parse, lint, etc.
    """
    # This is a dummy example
    return f"Analyzed {file_path}"

def analyze_project_multithreaded(project_path):
    """
    Walks the project, analyzing JS/TS files in multiple threads.
    Returns a list of analysis results.
    """
    results = []
    with ThreadPoolExecutor() as executor:
        tasks = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if file.endswith((".js", ".jsx", ".ts", ".tsx")):
                    tasks.append(executor.submit(analyze_file, os.path.join(root, file)))
        for task in tasks:
            results.append(task.result())
    return results

######################################################
# 8. Error Handling / Automatic Fix Example
######################################################
def generate_report(project_path):
    """
    Example placeholder that might parse the project for common issues
    and produce a structure with 'errors' and 'warnings'.
    """
    logging.info("Generating a placeholder error report.")
    # This is a toy example
    return {
        "errors": [
            {"type": "unused_dependency", "message": "Remove unused dependency: left-pad"}
        ],
        "warnings": ["Large file: App.jsx"]
    }

def process_error_queue(project_path, error_queue):
    """
    Demonstrates how you'd iterate over each error in a queue,
    create a branch for it, fix it, commit, revert if something fails, etc.
    """
    global LAST_WORKING_BRANCH
    LAST_WORKING_BRANCH = f"{BRANCH_PREFIX}_base"

    for index, error in enumerate(error_queue, start=1):
        branch_name = f"{BRANCH_PREFIX}_{index}"
        logging.info(f"Processing error {index}: {error['message']}")

        # Create a new branch for the fix
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=project_path)

        # Example fix logic (very naive)
        if error["type"] == "unused_dependency":
            dep_name = error["message"].split(": ")[1]
            subprocess.run(["npm", "uninstall", dep_name], cwd=project_path)

        # Validate fix
        if not validate_project(project_path):
            # If fix fails, revert
            logging.warning(f"Fix failed: {error['message']}. Reverting branch {branch_name}")
            subprocess.run(["git", "checkout", LAST_WORKING_BRANCH], cwd=project_path)
            subprocess.run(["git", "branch", "-D", branch_name], cwd=project_path)
            continue

        # Commit fix
        subprocess.run(["git", "add", "."], cwd=project_path)
        subprocess.run(["git", "commit", "-m", f"Fix: {error['message']}"], cwd=project_path)
        LAST_WORKING_BRANCH = branch_name

    logging.info("All errors processed.")

def validate_project(project_path):
    """
    Attempt to run a development server to validate the fix.
    If it starts successfully, we assume success (very naive).
    """
    try:
        proc = subprocess.Popen(
            DEV_SERVER_CMD,
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(5)  # Let the dev server start
        proc.terminate()
        return True
    except Exception as e:
        logging.error(f"Validation failed: {str(e)}")
        return False

######################################################
# 9. Generating a Cleanup or Analysis Report
######################################################
def generate_cleanup_report(base_path, used_deps, unused_deps):
    """
    Create a JSON report summarizing unused/used deps, which
    folders were created, etc.
    """
    print("Generating cleanup/analysis report...")
    logging.info("Generating cleanup/analysis report...")
    report_data = {
        "unused_dependencies": list(unused_deps),
        "used_dependencies": list(used_deps),
        "organized_folders": list(FOLDERS.keys()),
    }
    report_path = os.path.join(base_path, "cleanup_report.json")
    with open(report_path, "w") as file:
        json.dump(report_data, file, indent=4)
    print(f"Cleanup report saved to {report_path}\n")
    logging.info(f"Cleanup report saved to {report_path}")

######################################################
# 10. Optional GUI (PyQt5)
######################################################
# Only define the GUI class if PyQt5 is installed
if HAS_PYQT:
    from PyQt5.QtCore import Qt

    class ReactProjectToolGUI(QMainWindow):
        """
        A simple PyQt5 GUI demonstrating how you might integrate
        the above functions into a GUI-based workflow.
        """
        def __init__(self):
            super().__init__()
            self.init_ui()

        def init_ui(self):
            self.setWindowTitle("React Project Tool")
            self.setGeometry(100, 100, 800, 600)
            central_widget = QWidget()
            layout = QVBoxLayout()

            # Upload/Run Buttons
            self.upload_button = QPushButton("Upload Project (ZIP)")
            self.upload_button.clicked.connect(self.upload_project)
            layout.addWidget(self.upload_button)

            self.run_tool_button = QPushButton("Run Tool (Monitor/Unzip)")
            self.run_tool_button.clicked.connect(self.run_tool)
            layout.addWidget(self.run_tool_button)

            # Log Display
            self.log_display = QTextEdit()
            self.log_display.setReadOnly(True)
            layout.addWidget(self.log_display)

            central_widget.setLayout(layout)
            self.setCentralWidget(central_widget)

        def upload_project(self):
            zip_path, _ = QFileDialog.getOpenFileName(self, "Select ZIP File", "", "ZIP Files (*.zip)")
            if zip_path:
                self.log_display.append(f"Uploaded ZIP: {zip_path}")

        def run_tool(self):
            self.log_display.append("Running tool in background...")
            # You could start a thread or do something more robust here
            # For simplicity, let's just call monitor_for_zip logic
            # Non-blocking approach recommended (threading, QThread, etc.)
            self.execute_tool()

        def execute_tool(self):
            try:
                # Demo: Just call the function that monitors for a zip
                # In practice, you might do more steps.
                found_zip = monitor_for_zip()
                self.log_display.append(f"Found ZIP: {found_zip}")
            except Exception as e:
                self.log_display.append(f"Error: {e}")


######################################################
# Main Entry Point
######################################################
def main():
    """
    Main entry point - demonstrates how you might chain
    these pieces together. Adjust logic to your needs.
    """
    print("=" * 50)
    print("   Comprehensive React Project Management Tool")
    print("=" * 50)

    # Quick menu demonstration (CLI-based). You can refine or remove.
    while True:
        print("\nSelect an action:")
        print("1) Monitor for ZIP & auto-unzip (Git init, etc.)")
        print("2) Organize files into React folders (FOLDERS dict)")
        print("3) Analyze & Cleanup unused dependencies")
        print("4) Lint and Format (ESLint + Prettier)")
        print("5) Print folder tree")
        print("6) Scan directory & optionally search files")
        print("7) Run multithreaded analysis example")
        print("8) Generate placeholder error report + process error queue")
        print("9) Launch optional GUI (PyQt) [if installed]")
        print("q) Quit")

        choice = input("Enter your choice: ").strip().lower()
        if choice == 'q':
            sys.exit(0)

        if choice == '1':
            # 1) Monitor for ZIP, unzip, init Git
            zip_path = monitor_for_zip()
            project_path = unzip_file(zip_path, UNZIP_DIR)
            initialize_git_repo(project_path)
            print(f"Project prepared at: {project_path}")

        elif choice == '2':
            # 2) Organize files
            project_path = input("Enter project path to organize (default '.'): ").strip() or "."
            if os.path.isdir(project_path):
                organize_files(project_path)
            else:
                print("Invalid folder.")

        elif choice == '3':
            # 3) Analyze & Cleanup
            project_path = input("Enter project path to cleanup (default '.'): ").strip() or "."
            used_deps, unused_deps = cleanup_dependencies(project_path)
            if used_deps or unused_deps:
                generate_cleanup_report(project_path, used_deps, unused_deps)

        elif choice == '4':
            # 4) Lint & Format
            project_path = input("Enter project path to lint (default '.'): ").strip() or "."
            setup_and_run_linter(project_path)

        elif choice == '5':
            # 5) Print folder tree
            project_path = input("Enter project path to scan (default '.'): ").strip() or "."
            print("\nFolder Tree:\n")
            print_folder_tree(project_path)

        elif choice == '6':
            # 6) Scan directory & search
            project_path = input("Enter folder path (default '.'): ").strip() or "."
            file_list = scan_directory(project_path)
            selected_files = prompt_file_selection(file_list)
            if selected_files:
                print(f"Selected {len(selected_files)} files.")
                do_search = input("Search for terms? (y/n): ").strip().lower()
                if do_search == 'y':
                    terms = input("Enter search terms (space-separated): ").split()
                    if terms:
                        search_in_files(selected_files, terms)
                    else:
                        print("No terms entered.")
            else:
                print("No files selected.")

        elif choice == '7':
            # 7) Multithreaded analysis
            project_path = input("Enter folder path (default '.'): ").strip() or "."
            results = analyze_project_multithreaded(project_path)
            print("Multithreaded Analysis Results:")
            for r in results:
                print(" -", r)

        elif choice == '8':
            # 8) Generate a placeholder error report & fix
            project_path = input("Enter project path (default '.'): ").strip() or "."
            # Usually you'd analyze the project to build a real report
            placeholder_report = generate_report(project_path)
            errors = placeholder_report.get("errors", [])
            if errors:
                process_error_queue(project_path, errors)
            else:
                print("No errors found to process.")
            print("Error queue processing complete.")

        elif choice == '9':
            # 9) Launch optional GUI (if PyQt5 is installed)
            if HAS_PYQT:
                from PyQt5.QtWidgets import QApplication
                app = QApplication(sys.argv)
                window = ReactProjectToolGUI()
                window.show()
                sys.exit(app.exec_())
            else:
                print("PyQt5 not available. Please install or remove GUI calls.")
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()


import os
import sys
import importlib
import traceback

def check_imports(root_dir):
    print(f"Checking imports in {root_dir}...")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"Adding to sys.path: {project_root}")
    sys.path.insert(0, project_root) # Add project root to sys.path
    
    success_count = 0
    failure_count = 0
    failures = []

    for root, dirs, files in os.walk(root_dir):
        if "venv" in root or "__pycache__" in root or ".git" in root:
            continue
            
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                
                # Convert file path to module name
                # standard approach: relative from parent of 'backend'
                # e.g., .../backend/app/main.py -> backend.app.main
                
                rel_path = os.path.relpath(file_path, os.path.dirname(root_dir))
                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                
                # Check for specific files to skip if they are scripts meant to be run directly
                if module_name.endswith("__init__"):
                     module_name = module_name[:-9]

                try:
                    print(f"Testing import: {module_name}")
                    importlib.import_module(module_name)
                    success_count += 1
                except Exception as e:
                    failure_count += 1
                    error_msg = f"Failed to import {module_name}: {e}"
                    failures.append(error_msg)
                    print(error_msg)
                    # traceback.print_exc() 

    print("\n" + "="*50)
    print(f"Import Check Complete.")
    print(f"Success: {success_count}")
    print(f"Failures: {failure_count}")
    
    if failures:
        print("\nList of Failures:")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("\nAll imports successful!")
    print("="*50)

if __name__ == "__main__":
    # Point to 'backend' directory
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    check_imports(backend_dir)

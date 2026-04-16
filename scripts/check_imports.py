import os
import sys
import importlib
import traceback

def check_directory(base_path):
    print(f"\n--- Scanning {base_path} ---")
    original_path = list(sys.path)
    sys.path.insert(0, base_path)
    
    modules_to_clear = [name for name in sys.modules if not name.startswith(('os', 'sys', 'importlib', 'traceback', 'builtins'))]
    for m in modules_to_clear:
        if any(m.startswith(prefix) for prefix in ['core', 'routers', 'services', 'models', 'schemas', 'db', 'agent', 'repositories']):
            del sys.modules[m]

    python_files = []
    for root, dirs, files in os.walk(base_path):
        if 'venv' in root or '__pycache__' in root or '.venv' in root:
            continue
        for file in files:
            if file.endswith(".py"):
                # Skip setup.py (which might execute code on import) 
                if file == "setup.py": continue
                # Skip alembic internal files that are not packages
                if 'alembic' in root: continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_path)
                
                parts = rel_path.split(os.path.sep)
                module_parts = [p.removesuffix(".py") for p in parts]
                module_name = ".".join(module_parts)
                if module_name.endswith(".__init__"):
                    module_name = module_name.removesuffix(".__init__")
                
                if not module_name:
                    continue
                    
                python_files.append((module_name, full_path))

    errors = 0
    for module_name, full_path in python_files:
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            print(f"FAILED: {module_name} ({full_path})")
            print(f"  Error: {e}")
            errors += 1
        except Exception:
            pass
            
    sys.path = original_path
    print(f"Modules checked: {len(python_files)}")
    print(f"Import errors: {errors}")
    return errors

if __name__ == "__main__":
    total_errors = 0
    services_dir = "services"
    for item in os.listdir(services_dir):
        item_path = os.path.join(services_dir, item)
        if os.path.isdir(item_path) and not item.startswith((".", "__")):
            total_errors += check_directory(os.path.abspath(item_path))
    
    sys.exit(1 if total_errors > 0 else 0)

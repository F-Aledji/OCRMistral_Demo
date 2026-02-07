
import sys
from pathlib import Path
import pytest

def test_debug_import():
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    print(f"\nSYS PATH: {sys.path}")
    
    try:
        import fastapi
        print(f"FastAPI found: {fastapi.__version__}")
    except ImportError as e:
        print(f"FastAPI import failed: {e}")

    try:
        from fastapi.testclient import TestClient
        print("TestClient imported successfully")
    except ImportError as e:
        print(f"TestClient import failed: {e}")
        
    try:
        from backend.app.main import app
        print("Backend App imported successfully")
    except ImportError as e:
        print(f"Backend App import failed: {e}")
    except Exception as e:
        print(f"Backend App import error (other): {e}")

if __name__ == "__main__":
    test_debug_import()

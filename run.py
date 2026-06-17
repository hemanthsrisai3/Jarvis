import os
import sys
import subprocess

def auto_activate_venv():
    # Detect the directory of the run.py file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to virtual environment python executable
    if os.name == "nt":
        venv_python = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(base_dir, ".venv", "bin", "python")
        
    if os.path.exists(venv_python):
        # Check if current executable is already the venv python
        try:
            is_venv = os.path.samefile(sys.executable, venv_python)
        except AttributeError:
            # Fallback for systems without os.samefile
            is_venv = os.path.abspath(sys.executable).lower() == os.path.abspath(venv_python).lower()
        except Exception:
            is_venv = False
            
        if not is_venv:
            print(f"Relaunching in local virtual environment: {venv_python}")
            # Run the current script using the virtual environment's python interpreter
            cmd = [venv_python] + sys.argv
            sys.exit(subprocess.call(cmd))

# Auto-activate before importing third-party libraries (e.g. uvicorn, pydantic)
auto_activate_venv()

import uvicorn
from config.settings import settings

if __name__ == "__main__":
    print(f"Starting J.A.R.V.I.S. on http://{settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run("core.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)

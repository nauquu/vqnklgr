---
name: build-executable
description: Automated packaging workflow for compiling klg.py into setup.exe using PyInstaller clean environment, checking syntax, moving output, and cleaning up temporary files.
---

# Build Executable Skill

This skill defines the standardized workflow for packaging `klg.py` into a lightweight, standalone Windows executable (`setup.exe`).

## Workflow Steps

1. **Syntax Verification**:
   Before compiling, always verify Python code syntax using the virtual environment Python interpreter:
   ```bash
   .\clean_env\Scripts\python.exe -m py_compile klg.py
   ```

2. **PyInstaller Compilation**:
   Run PyInstaller using the clean virtual environment interpreter to exclude unnecessary heavy dependencies (e.g., `numpy`, `cv2`) and keep executable size minimal (~47MB):
   ```bash
   .\clean_env\Scripts\python.exe -m PyInstaller --onefile --noconsole --clean --name setup --hidden-import playwright --hidden-import pynput.keyboard._win32 --exclude-module numpy --exclude-module cv2 klg.py
   ```

3. **Artifact Relocation & Cleanup**:
   Once PyInstaller completes, move `dist\setup.exe` to the root folder `.\setup.exe` and remove build artifacts:
   ```cmd
   if exist dist\setup.exe move /Y dist\setup.exe .\setup.exe >nul & if exist build rd /S /Q build & if exist dist rd /S /Q dist & if exist setup.spec del /F /Q setup.spec
   ```

4. **Verification**:
   Verify that `setup.exe` exists in the root `klg` directory and check its size (~50MB).
